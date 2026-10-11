"""PostgreSQL contracts for safe, audited admin settings edits."""
from copy import deepcopy

from postgres_case import PostgresCase
from wakfu_server.admin_domain import AdminService
from wakfu_server.admin_settings import SettingsConflict


class AdminSettingsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.admin = AdminService(self.store)

    def _global_ecology_revision(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT revision FROM ecology_dirty_scopes WHERE map_id=-1 AND instance_id=-1"
            ).fetchone()
        return row["revision"]

    def _audit_count(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT count(*) AS n FROM admin_panel_audit WHERE action='setting.update'"
            ).fetchone()["n"]

    def test_ecology_policy_edit_is_validated_audited_and_marks_global_scope(self):
        current = self.admin.setting("personal_ecology_policy")
        changed = deepcopy(current["value"])
        changed["plant"]["maximum"] += 1
        revision = self._global_ecology_revision()
        audits = self._audit_count()

        result = self.admin.update_setting(
            "personal_ecology_policy",
            {"value": changed, "expected_revision": current["revision"]},
            "settings-test",
        )

        self.assertEqual(result["changed_name"], "personal_ecology_policy")
        self.assertEqual(result["apply_mode"], "new_actions")
        self.assertEqual(
            self.admin.setting("personal_ecology_policy")["value"], changed
        )
        self.assertEqual(self._audit_count(), audits + 1)
        self.assertGreater(self._global_ecology_revision(), revision)

    def test_stale_revision_and_invalid_policy_roll_back_without_audit_or_trigger(self):
        current = self.admin.setting("personal_ecology_policy")
        audits = self._audit_count()
        dirty_revision = self._global_ecology_revision()

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value, '{plant,maximum}', to_jsonb((value->'plant'->>'maximum')::integer + 1)) WHERE name='personal_ecology_policy'"
            )
        external_revision = self.admin.setting("personal_ecology_policy")["revision"]
        dirty_after_external = self._global_ecology_revision()
        self.assertNotEqual(external_revision, current["revision"])

        with self.assertRaises(ValueError):
            self.admin.update_setting(
                "personal_ecology_policy",
                {"value": current["value"], "expected_revision": current["revision"]},
                "settings-test",
            )
        after_stale = self.admin.setting("personal_ecology_policy")
        self.assertEqual(after_stale["revision"], external_revision)
        self.assertEqual(self._audit_count(), audits)
        self.assertEqual(self._global_ecology_revision(), dirty_after_external)

        invalid = deepcopy(after_stale["value"])
        invalid["balance_delta"] = 0
        with self.assertRaises(ValueError):
            self.admin.update_setting(
                "personal_ecology_policy",
                {"value": invalid, "expected_revision": external_revision},
                "settings-test",
            )
        self.assertEqual(
            self.admin.setting("personal_ecology_policy")["revision"], external_revision
        )
        self.assertEqual(self._audit_count(), audits)
        self.assertEqual(self._global_ecology_revision(), dirty_after_external)
        self.assertGreater(dirty_after_external, dirty_revision)

    def test_malformed_revision_and_oversized_value_are_rejected_before_mutation(self):
        current = self.admin.setting("monster_reproduction")
        audits = self._audit_count()
        dirty_revision = self._global_ecology_revision()

        for data in (
            {"value": current["value"], "expected_revision": "not-a-revision"},
            {
                "value": {"blob": "x" * (5 * 1024 * 1024)},
                "expected_revision": current["revision"],
            },
        ):
            with self.subTest(data_keys=tuple(data)):
                with self.assertRaises(ValueError):
                    self.admin.update_setting(
                        "monster_reproduction", data, "settings-test"
                    )

        self.assertEqual(
            self.admin.setting("monster_reproduction")["revision"], current["revision"]
        )
        self.assertEqual(self._audit_count(), audits)
        self.assertEqual(self._global_ecology_revision(), dirty_revision)

    def test_consumer_policy_ranges_reject_invalid_reproduction_values(self):
        current = self.admin.setting("monster_reproduction")
        audits = self._audit_count()
        dirty_revision = self._global_ecology_revision()

        invalid_policies = []
        too_long = deepcopy(current["value"])
        too_long["interval_ms"] = 86400001
        invalid_policies.append(too_long)
        too_many = deepcopy(current["value"])
        too_many["max_members"] = 9
        invalid_policies.append(too_many)
        non_finite = deepcopy(current["value"])
        non_finite["birth_probability"] = float("nan")
        invalid_policies.append(non_finite)

        for invalid in invalid_policies:
            with self.subTest(policy=invalid):
                with self.assertRaises(ValueError):
                    self.admin.update_setting(
                        "monster_reproduction",
                        {"value": invalid, "expected_revision": current["revision"]},
                        "settings-test",
                    )

        self.assertEqual(
            self.admin.setting("monster_reproduction")["revision"], current["revision"]
        )
        self.assertEqual(self._audit_count(), audits)
        self.assertEqual(self._global_ecology_revision(), dirty_revision)

    def _install_dungeon(self):
        from test_dungeon_runtime_config import RuntimeConfigTests
        from wakfu_server.dungeon_runtime_config import install_configuration

        fixture = RuntimeConfigTests()
        fixture.setUp()
        config = fixture.configuration()
        with self.store.connection() as db:
            install_configuration(db, config)
        return config

    def test_dungeon_virtual_editor_reads_dedicated_history_without_settings_rows(self):
        config = self._install_dungeon()
        current = self.admin.setting("dungeon_runtime_config:test:v1")
        self.assertEqual(current["value"], config)
        self.assertEqual(current["edit_mode"], "new_version")
        active = self.admin.setting("dungeon_runtime_active:test")
        self.assertEqual(
            active["value"], {"version": 1, "key": "dungeon_runtime_config:test:v1"}
        )
        self.assertEqual([row["version"] for row in active["versions"]], [1])
        listed = self.admin.settings(q="dungeon_runtime_")["items"]
        self.assertFalse(
            any(
                row["name"].startswith(
                    ("dungeon_runtime_config:", "dungeon_runtime_active:")
                )
                for row in listed
            )
        )
        # Filtering happens before pagination and count, including explicit searches.
        self.assertEqual(
            self.admin.settings(q="dungeon_runtime_config:test")["total"], 0
        )
        self.assertEqual(
            self.admin.settings(q="dungeon_runtime_active:test")["total"], 0
        )
        self.assertTrue(self.admin.settings(q="personal_ecology_policy")["items"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM settings WHERE name LIKE 'dungeon_runtime_config:%%' OR name LIKE 'dungeon_runtime_active:%%'"
                ).fetchone()["n"],
                0,
            )

    def test_dungeon_publish_and_select_preserve_immutable_history_and_audit(self):
        from unittest.mock import patch

        self._install_dungeon()
        current = self.admin.setting("dungeon_runtime_config:test:v1")
        changed = deepcopy(current["value"])
        changed["compiled_plan"]["rooms"][0]["monsters"][0]["count"] = 4
        before_audits = self._audit_count()
        with patch(
            "wakfu_server.monsters.reference",
            return_value={"min_level": 8, "max_level": 12},
        ):
            published = self.admin.update_setting(
                current["name"],
                {
                    "value": changed,
                    "expected_revision": current["revision"],
                    "new_version": 2,
                },
                "dungeon-editor-test",
            )
        self.assertEqual(published["changed_name"], "dungeon_runtime_config:test:v2")
        self.assertEqual(self.admin.setting(current["name"])["value"], current["value"])
        active = self.admin.setting("dungeon_runtime_active:test")
        self.assertEqual(active["value"]["version"], 2)
        self.assertEqual([r["version"] for r in active["versions"]], [1, 2])
        self.admin.update_setting(
            active["name"],
            {
                "value": {"version": 1, "key": current["name"]},
                "expected_revision": active["revision"],
            },
            "dungeon-editor-test",
        )
        self.assertEqual(self.admin.setting(active["name"])["value"]["version"], 1)
        self.assertEqual(self._audit_count(), before_audits + 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM dungeon_runtime_configurations WHERE route_key=%s",
                    ("test",),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM settings WHERE name LIKE 'dungeon_runtime_config:%%' OR name LIKE 'dungeon_runtime_active:%%'"
                ).fetchone()["n"],
                0,
            )

    def test_dungeon_stale_selection_rolls_back_pointer_and_audit(self):
        from wakfu_server.dungeon_runtime_config import (
            install_configuration,
            prepare_configuration,
        )

        config = self._install_dungeon()
        current = self.admin.setting("dungeon_runtime_active:test")
        version2 = prepare_configuration(
            config["compiled_plan"],
            config["topology"],
            config["route"],
            version=2,
            provenance="second reviewed version",
        )
        with self.store.connection() as db:
            install_configuration(db, version2)
        audits = self._audit_count()
        with self.assertRaises(ValueError):
            self.admin.update_setting(
                current["name"],
                {"value": current["value"], "expected_revision": current["revision"]},
                "stale-editor",
            )
        self.assertEqual(self.admin.setting(current["name"])["value"]["version"], 2)
        self.assertEqual(self._audit_count(), audits)

    def _combat_multiplier_state(self):
        with self.store.connection() as db:
            reward = db.execute(
                "SELECT a.version,v.xp_rate_bp,v.kamas_rate_bp,v.conquest_rate_bp "
                "FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version) "
                "WHERE a.singleton=true"
            ).fetchone()
            drop = db.execute(
                "SELECT a.version,v.drop_rate_bp FROM combat_drop_policy_active a "
                "JOIN combat_drop_policy_versions v USING(version) WHERE a.singleton=true"
            ).fetchone()
        return dict(reward), dict(drop)

    def test_combat_multiplier_virtual_settings_publish_atomic_versions_and_preserve_siblings(
        self,
    ):
        names = (
            "combat_xp_multiplier",
            "combat_kamas_multiplier",
            "combat_drop_multiplier",
        )
        listed = {
            row["name"]: row
            for row in self.admin.settings(q="combat_", limit=100)["items"]
        }
        for name in names:
            with self.subTest(name=name):
                detail = self.admin.setting(name)
                self.assertIn(name, listed)
                self.assertEqual(detail["category"], "Combat")
                self.assertEqual(detail["apply_mode"], "new_actions")
                self.assertAlmostEqual(float(detail["value"]), 1.0)
                self.assertEqual(detail["revision"], listed[name]["revision"])

        audits_before = self._audit_count()
        original_reward, original_drop = self._combat_multiplier_state()
        xp = self.admin.setting("combat_xp_multiplier")
        result = self.admin.update_setting(
            xp["name"],
            {"value": 1.2345, "expected_revision": xp["revision"]},
            "combat-multiplier-test",
        )
        self.assertAlmostEqual(float(result["value"]), 1.2345)
        kamas = self.admin.setting("combat_kamas_multiplier")
        self.admin.update_setting(
            kamas["name"],
            {"value": 2.5, "expected_revision": kamas["revision"]},
            "combat-multiplier-test",
        )
        drop = self.admin.setting("combat_drop_multiplier")
        self.admin.update_setting(
            drop["name"],
            {"value": 0.75, "expected_revision": drop["revision"]},
            "combat-multiplier-test",
        )

        reward, drop_state = self._combat_multiplier_state()
        self.assertEqual(reward["version"], original_reward["version"] + 2)
        self.assertEqual(reward["xp_rate_bp"], 12345)
        self.assertEqual(reward["kamas_rate_bp"], 25000)
        self.assertEqual(
            reward["conquest_rate_bp"], original_reward["conquest_rate_bp"]
        )
        self.assertEqual(drop_state["version"], original_drop["version"] + 1)
        self.assertEqual(drop_state["drop_rate_bp"], 7500)
        self.assertEqual(self._audit_count(), audits_before + 3)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM settings WHERE name = ANY(%s)",
                    (list(names),),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_reward_policy_versions"
                ).fetchone()["n"],
                original_reward["version"] + 2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_drop_policy_versions"
                ).fetchone()["n"],
                original_drop["version"] + 1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM admin_panel_audit WHERE action='setting.update' "
                    "AND target = ANY(%s)",
                    (list(names),),
                ).fetchone()["n"],
                3,
            )

    def test_combat_multiplier_zero_is_valid_and_invalid_values_have_no_side_effects(
        self,
    ):
        name = "combat_drop_multiplier"
        current = self.admin.setting(name)
        before_audits = self._audit_count()
        reward_before, drop_before = self._combat_multiplier_state()
        saved = self.admin.update_setting(
            name,
            {"value": 0, "expected_revision": current["revision"]},
            "combat-multiplier-test",
        )
        self.assertEqual(float(saved["value"]), 0.0)
        self.assertEqual(self._combat_multiplier_state()[1]["drop_rate_bp"], 0)
        self.assertEqual(self._audit_count(), before_audits + 1)

        revision = saved["revision"]
        audits = self._audit_count()
        reward_after, drop_after = self._combat_multiplier_state()
        self.assertEqual(reward_after, reward_before)
        invalid_values = (-0.0001, 10_000_000, 1.00001, True, float("nan"))
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.admin.update_setting(
                        name,
                        {"value": invalid, "expected_revision": revision},
                        "combat-multiplier-test",
                    )
        self.assertEqual(self.admin.setting(name)["revision"], revision)
        self.assertEqual(self._combat_multiplier_state()[1], drop_after)
        self.assertEqual(self._audit_count(), audits)

    def test_combat_multiplier_round_trips_minimum_quantum_and_maximum(self):
        cases = (
            ("combat_xp_multiplier", "xp_rate_bp"),
            ("combat_kamas_multiplier", "kamas_rate_bp"),
            ("combat_drop_multiplier", "drop_rate_bp"),
        )
        audits_before = self._audit_count()
        for name, column in cases:
            for multiplier, expected_rate in (
                (9_999_999.9999, 99_999_999_999),
                (0.0001, 1),
            ):
                with self.subTest(name=name, multiplier=multiplier):
                    opened = self.admin.setting(name)
                    saved = self.admin.update_setting(
                        name,
                        {"value": multiplier, "expected_revision": opened["revision"]},
                        "combat-multiplier-range-test",
                    )
                    self.assertAlmostEqual(float(saved["value"]), multiplier, places=4)
                    reward, drop = self._combat_multiplier_state()
                    active = drop if name == "combat_drop_multiplier" else reward
                    self.assertEqual(active[column], expected_rate)
        self.assertEqual(self._audit_count(), audits_before + 6)
        self.assertEqual(self._audit_count(), audits_before + 6)

    def test_combat_multiplier_stale_revision_does_not_publish_or_audit(self):
        name = "combat_xp_multiplier"
        opened = self.admin.setting(name)
        saved = self.admin.update_setting(
            name,
            {"value": 1.5, "expected_revision": opened["revision"]},
            "combat-multiplier-test",
        )
        state_after_save = self._combat_multiplier_state()
        audits_after_save = self._audit_count()
        with self.assertRaises(SettingsConflict):
            self.admin.update_setting(
                name,
                {"value": 2, "expected_revision": opened["revision"]},
                "stale-combat-editor",
            )
        self.assertEqual(self.admin.setting(name)["revision"], saved["revision"])
        self.assertEqual(self._combat_multiplier_state(), state_after_save)
        self.assertEqual(self._audit_count(), audits_after_save)

    def test_combat_multiplier_virtual_settings_work_before_dungeon_tables_exist(self):
        names = {
            "combat_xp_multiplier",
            "combat_kamas_multiplier",
            "combat_drop_multiplier",
        }
        with self.store.connection() as db:
            db.execute("DROP TABLE IF EXISTS dungeon_runtime_active_configurations")
            db.execute("DROP TABLE IF EXISTS dungeon_runtime_configurations CASCADE")
            db.execute(
                "INSERT INTO settings(name,value) VALUES('legacy_compat_probe','{\"enabled\":true}'::jsonb)"
            )

        listing = self.admin.settings(q="combat_", limit=100)
        self.assertTrue(names <= {row["name"] for row in listing["items"]})
        for name in names:
            with self.subTest(name=name):
                self.assertAlmostEqual(float(self.admin.setting(name)["value"]), 1.0)
        legacy = self.admin.setting("legacy_compat_probe")
        self.assertEqual(legacy["value"], {"enabled": True})
        self.assertIn(
            "legacy_compat_probe",
            {
                row["name"]
                for row in self.admin.settings(q="legacy_compat_probe")["items"]
            },
        )

    def test_server_name_is_editable_persisted_and_audited(self):
        name = "server_name"
        listed = self.admin.settings(q=name)
        self.assertIn(name, {row["name"] for row in listed["items"]})
        current = self.admin.setting(name)
        self.assertEqual(current["value"], "Rubilax")
        self.assertTrue(current["editable"])
        self.assertEqual(current["apply_mode"], "next_load")
        audits = self._audit_count()

        updated = self.admin.update_setting(
            name,
            {"value": "Rubilax — Étoile 東京", "expected_revision": current["revision"]},
            "server-name-test",
        )

        persisted = self.admin.setting(name)
        self.assertEqual(persisted["value"], "Rubilax — Étoile 東京")
        self.assertNotEqual(persisted["revision"], current["revision"])
        self.assertEqual(updated["revision"], persisted["revision"])
        self.assertEqual(self._audit_count(), audits + 1)

    def test_server_name_invalid_and_stale_edits_roll_back_without_audit(self):
        name = "server_name"
        current = self.admin.setting(name)
        audits = self._audit_count()
        invalid_values = (
            "",
            "   ",
            " leading",
            "trailing ",
            "x" * 81,
            "😀" * 64,
            "bad\x00name",
            "bad\u200bname",
        )
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    self.admin.update_setting(
                        name,
                        {"value": value, "expected_revision": current["revision"]},
                        "server-name-test",
                    )
        after_invalid = self.admin.setting(name)
        self.assertEqual(after_invalid["revision"], current["revision"])
        self.assertEqual(after_invalid["value"], current["value"])
        self.assertEqual(self._audit_count(), audits)

        saved = self.admin.update_setting(
            name,
            {"value": "New name", "expected_revision": current["revision"]},
            "server-name-test",
        )
        audits_after_save = self._audit_count()
        with self.assertRaises(SettingsConflict):
            self.admin.update_setting(
                name,
                {"value": "Stale name", "expected_revision": current["revision"]},
                "server-name-test",
            )
        self.assertEqual(self.admin.setting(name)["revision"], saved["revision"])
        self.assertEqual(self.admin.setting(name)["value"], "New name")
        self.assertEqual(self._audit_count(), audits_after_save)
