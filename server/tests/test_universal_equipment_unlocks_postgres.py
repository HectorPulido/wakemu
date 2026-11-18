"""Universal equipment facts share real journal and native company publication."""
from copy import deepcopy
from pathlib import Path
import os
import tempfile
from unittest.mock import patch
import struct
import uuid

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import universal_equipment_unlocks as subject
from wakfu_server.achievements import storage
from wakfu_server.company_authority import CompanySnapshot
from wakfu_server.equipment_conditions import evaluate


class UniversalEquipmentUnlocksPostgresTests(PostgresCase):
    def setUp(self):
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        # Production still runs the canonical base374 schema. Qualify only the
        # authorized additive SQL, without unrelated pending mission batches.
        with tempfile.TemporaryDirectory(prefix="universal-base374-") as directory:
            for source in migrations.glob("*.sql"):
                if int(source.name.split("_", 1)[0]) <= 374:
                    (Path(directory) / source.name).symlink_to(source.resolve())
            with patch.dict(os.environ, WAKFU_MIGRATIONS_TEST_DIR=directory):
                super().setUp()
        # Qualify the same additive feature SQL used with production base374.
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        with self.store.connection() as db:
            for name in (
                "382_reconstructed_mount_item_aliases.sql",
                "383_universal_equipment_unlocks.sql",
            ):
                db.execute((migrations / name).read_text())

    def policy(self, enabled):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (
                    Jsonb(dict(subject.DEFAULT, enabled=enabled)),
                    subject.SETTING,
                ),
            )

    def actor(self, name):
        account = self.store.register(
            "universal-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        return account, self.store.create_character(account, name, breed=8)

    def progress(self, identity):
        with self.store.connection() as db:
            return deepcopy(storage.load_locked(db, identity))

    def assert_publication(self, actor, *, enabled):
        context = actor["equipment_criterion_context"]
        company = CompanySnapshot.from_record(context["company_snapshot"])
        self.assertEqual(company.rank, 12 if enabled else 1)
        self.assertEqual(company.score, 4001 if enabled else 3)
        opcode, packet = company.packet()
        self.assertEqual(opcode, 13873)
        self.assertEqual(struct.unpack(">IIqqiqIiB", packet)[7], company.score)
        from wakfu_server import social

        self.assertEqual(social.company(actor["account_id"], actor), packet[8:])
        for criterion in ("GetCompanyRank() >= 10", "IsAchievementComplete(1509)"):
            self.assertEqual(
                evaluate(
                    criterion, item={}, selected=[], owned={}, criterion_context=context
                ),
                enabled,
            )

    def test_new_characters_have_scoped_facts_without_levels_items_or_rewards(self):
        account, actor = self.actor("Universal New")
        self.assert_publication(actor, enabled=True)
        state = self.progress(actor["id"])
        self.assertIn(1509, state["completed"])
        self.assertIn(2825, state["objectives"])
        self.assertNotIn(1508, state["completed"])
        self.assertNotIn(2192, state["completed"])
        self.assertNotIn(2824, state["objectives"])
        self.assertNotIn(1509, state["running"])
        self.assertEqual(actor["level"], 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (actor["id"],),
                ).fetchone()["xp"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=1509",
                    (actor["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=29724",
                    (actor["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (actor["id"], "universal-equipment-unlocks:v1:1509"),
                ).fetchone()["n"],
                1,
            )

    def test_existing_selection_is_idempotent_and_preserves_other_progress(self):
        self.policy(False)
        account, actor = self.actor("Universal Existing")
        self.assert_publication(actor, enabled=False)
        with self.store.connection() as db:
            state = storage.load_locked(db, actor["id"])
            state["running"] = sorted(set(state["running"]) | {5568})
            state["objectives"] = sorted(set(state["objectives"]) | {11510})
            state["tracking"] = [5568]
            storage.store(db, actor["id"], state)
        before = self.progress(actor["id"])
        self.policy(True)
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, actor["id"])
        self.assert_publication(selected, enabled=True)
        after = self.progress(actor["id"])
        self.assertEqual(set(after["completed"]) - set(before["completed"]), {1509})
        self.assertEqual(set(after["objectives"]) - set(before["objectives"]), {2825})
        for key in ("variables", "tracking", "running"):
            self.assertEqual(after[key], before[key])
        selected_again = self.store.select_character(account, generation, actor["id"])
        self.assert_publication(selected_again, enabled=True)
        self.assertEqual(self.progress(actor["id"]), after)
        with self.store.connection() as db:
            self.assertFalse(
                subject.grant(db, actor["id"], int(self.store.now().timestamp() * 1000))
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=1509",
                    (actor["id"],),
                ).fetchone()["n"],
                0,
            )

    def test_disabled_policy_preserves_real_score_and_does_not_grant_achievement(self):
        self.policy(False)
        account, actor = self.actor("Universal Disabled")
        before = self.progress(actor["id"])
        with self.store.connection() as db:
            self.assertFalse(subject.grant(db, actor["id"], 123456))
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, actor["id"])
        self.assert_publication(selected, enabled=False)
        self.assertEqual(self.progress(actor["id"]), before)
