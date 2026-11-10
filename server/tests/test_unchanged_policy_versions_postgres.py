"""Identical saves retain revisions; changed payloads still publish atomically."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from postgres_case import PostgresCase


class UnchangedPolicyVersionsPostgresTests(PostgresCase):
    def test_combat_rates_reuse_versions_and_preserve_change_conflicts(self):
        from wakfu_server.admin_domain import AdminService
        from wakfu_server.admin_settings import SettingsConflict

        admin = AdminService(self.store)
        for name, table in (
            ("combat_xp_multiplier", "combat_reward_policy_versions"),
            ("combat_kamas_multiplier", "combat_reward_policy_versions"),
            ("combat_drop_multiplier", "combat_drop_policy_versions"),
        ):
            with self.subTest(name=name):
                current = admin.setting(name)
                with self.store.connection() as db:
                    count = db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()[
                        "n"
                    ]
                same = admin.update_setting(
                    name,
                    dict(
                        value=float(current["value"]),
                        expected_revision=current["revision"],
                    ),
                    "no-op-regression",
                )
                self.assertEqual(same["revision"], current["revision"])
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()[
                            "n"
                        ],
                        count,
                    )
                changed = admin.update_setting(
                    name,
                    dict(value=2.5, expected_revision=current["revision"]),
                    "no-op-regression",
                )
                self.assertNotEqual(changed["revision"], current["revision"])
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()[
                            "n"
                        ],
                        count + 1,
                    )
                with self.assertRaises(SettingsConflict):
                    admin.update_setting(
                        name,
                        dict(value=2.5, expected_revision=current["revision"]),
                        "stale-no-op-regression",
                    )

    def test_objective_reward_and_profile_equal_saves_keep_version_history(self):
        from tools import import_native_catalogs
        from wakfu_server import native_catalog

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name in ("item-stack-rules.json", "item-equipment-rules.json"):
                (source / name).write_text(json.dumps({"items": {}}))
            (source / "level-xp.json").write_text(
                json.dumps(
                    {"xp_by_level": {str(level): level - 1 for level in range(1, 246)}}
                )
            )
            import_native_catalogs.import_catalogs(self.store, source)
        with patch.object(native_catalog, "_database", return_value=self.store):
            native_catalog.release.cache_clear()
            try:
                from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
                from wakfu_server.objectives import (
                    repository,
                    reward_policies,
                    challenges_profiles,
                )
            finally:
                native_catalog.release.cache_clear()
        definition = dict(
            key="unchanged-objective",
            title="Unchanged objective",
            description="Regression",
            kind="achievement",
            enabled=True,
            scope="account",
            objectives=[
                dict(
                    key="count",
                    event="original_monster_killed",
                    filters={"references": [1]},
                    target=2,
                )
            ],
            schedule={"type": "daily", "timezone": "UTC"},
            rewards=[],
        )
        policy = {
            "bands": [
                {
                    "minimum": 1,
                    "maximum": MAX_CHARACTER_LEVEL,
                    "rewards": [{"kind": "kamas", "amount": 10}],
                }
            ]
        }
        with self.store.connection() as db:
            saved = repository.put_definition(db, definition, 0)
            same = repository.put_definition(
                db, deepcopy(definition), saved["revision"]
            )
            self.assertEqual(same, saved)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_definition_versions WHERE key=%s",
                    (definition["key"],),
                ).fetchone()["n"],
                1,
            )
            changed = dict(definition, title="Changed objective")
            self.assertEqual(
                repository.put_definition(db, changed, saved["revision"])["revision"], 2
            )

            saved_policy = reward_policies.put_policy(db, "unchanged-policy", policy, 0)
            same_policy = reward_policies.put_policy(
                db, "unchanged-policy", deepcopy(policy), 1
            )
            self.assertEqual(same_policy, saved_policy)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_reward_policy_versions WHERE key='unchanged-policy'",
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_reward_policy_audit WHERE policy_key='unchanged-policy'",
                ).fetchone()["n"],
                1,
            )
            changed_policy = deepcopy(policy)
            changed_policy["bands"][0]["rewards"][0]["amount"] = 20
            self.assertEqual(
                reward_policies.put_policy(db, "unchanged-policy", changed_policy, 1)[
                    "revision"
                ],
                2,
            )

            # Roster/geometry validation has separate tests; this assertion
            # exercises profile persistence without constructing game catalogs.
            with patch.object(
                challenges_profiles, "validate_profile", side_effect=lambda value: value
            ):
                profile = dict(key="unchanged-profile", title="Profile")
                saved_profile = challenges_profiles.put_profile(db, profile, 0)
                self.assertEqual(
                    challenges_profiles.put_profile(db, deepcopy(profile), 1),
                    saved_profile,
                )
                self.assertEqual(
                    challenges_profiles.put_profile(
                        db, dict(profile, title="Changed profile"), 1
                    )["revision"],
                    2,
                )

        for writer in (
            lambda db: repository.put_definition(db, changed, 1),
            lambda db: reward_policies.put_policy(
                db, "unchanged-policy", changed_policy, 1
            ),
        ):
            with self.subTest(writer=writer), self.assertRaises(
                repository.ConflictError
            ), self.store.connection() as db:
                writer(db)
