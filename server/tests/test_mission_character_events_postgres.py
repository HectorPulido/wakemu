"""Real selected readiness and XP/admin progression activate finite reviewed intros."""

from types import SimpleNamespace
from uuid import uuid4
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_mission_toolkit_settlement_postgres import quest, objective
from test_mission_character_events import intro
from wakfu_server.achievements import (
    mission_toolkit,
    mission_character_events,
    service,
    storage,
)
from wakfu_server import item_progression, character_levels


class MissionCharacterEventsPostgresTests(PostgresCase):
    def test_selected_ready_item_quest_admin_combat_levels_and_once_rewards(self):
        account = self.store.register("reviewed-ready", "isolated-password")["id"]
        character = self.store.create_character(account, "Reviewed Ready")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        ids = list(range(910101, 910107))
        native = [
            quest(identity, [objective(920101 + n)]) for n, identity in enumerate(ids)
        ]
        native[1]["cjI"] = "GetRealLevel() >= 3"
        declarations = dict(
            version=1,
            id="reviewed-ready-fixture",
            evidence=["Synthetic isolated positive guide/native admission fixture."],
            bindings=[],
            links=[],
            activations=[
                intro(identity, minimum)
                for identity, minimum in zip(ids[:5], (2, 2, 4, 5, 6))
            ],
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    "b" * 64,
                    Jsonb({"fixture": "reviewed-ready"}),
                    b"isolated native fixtures",
                    len(native),
                ),
            )
            for definition in native:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    ("b" * 64, definition["d"], Jsonb(dict(native=definition))),
                )
            mission_toolkit.install(db, declarations, activate=True)
        self.assertEqual(
            mission_character_events.ready(self.store, account, generation, character),
            [],
        )
        with self.assertRaises(ValueError):
            mission_character_events.ready(self.store, account, str(uuid4()), character)
        xp = character_levels.XP_BY_LEVEL
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            self.store.lock_character(db, account, generation, character["id"])
            result = item_progression.award_item_xp(
                self.store, db, account, generation, character["id"], xp[2]
            )
            self.assertIn(13205, [opcode for opcode, _ in result["packets"]])
            current = storage.load_locked(db, character["id"])
            self.assertIn(ids[0], current["running"])
            self.assertNotIn(ids[1], current["running"])
        # This synthetic earned native outbox entry exercises the real delivery
        # boundary: mark delivered before intro settlement can drain again.
        with self.store.connection() as db:
            # Isolate event timing from the migration's configured XP multiplier.
            version = db.execute(
                "SELECT max(version)+1 AS n FROM combat_reward_policy_versions"
            ).fetchone()["n"]
            db.execute(
                "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(%s,10000,10000,10000)",
                (version,),
            )
            db.execute(
                "UPDATE combat_reward_policy_active SET version=%s WHERE singleton",
                (version,),
            )
            current = self.store.character(account, character["id"], db)
            reward = dict(d=930101, aeV=6, ckl=[xp[4] - current["xp"]])
            storage.enqueue_reward(
                db, character["id"], ids[0], "fixture-earned", "930101", reward
            )
            packets = service.drain_rewards(db, self.store, current)
            self.assertIn(13205, [opcode for opcode, _ in packets])
            after = self.store.character(account, character["id"], db)
            self.assertEqual(after["level"], 4)
            self.assertEqual(after["xp"], xp[4])
            self.assertTrue(
                set(ids[:3]) <= set(storage.load_locked(db, character["id"])["running"])
            )
            self.assertEqual(service.drain_rewards(db, self.store, after), [])
            self.assertEqual(
                self.store.character(account, character["id"], db)["xp"], xp[4]
            )
        from wakfu_server.command_permissions import set_admin
        from wakfu_server.test_console import execute
        from wakfu_server.combat_groups import Groups

        set_admin(
            self.store,
            account,
            True,
            operator="test",
            reason="isolated lifecycle fixture",
        )
        execute(self.store, Groups(), account, generation, after, "!level 5")
        with self.store.connection() as db:
            self.assertIn(ids[3], storage.load_locked(db, character["id"])["running"])
        from wakfu_server import fight_store, combat_rewards

        fight_id = fight_store.create(self.store, account, generation, character["id"])
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors={
                character["id"]: SimpleNamespace(
                    controlled=True, owner_id=account, team=0
                )
            },
        )
        with self.store.connection() as db:
            fight_store.finish(
                self.store, db, account, generation, character["id"], fight_id
            )
            current = self.store.character(account, character["id"], db)
            receipt = combat_rewards.award(
                self.store,
                account,
                generation,
                character["id"],
                fight,
                combat_rewards.Policy(xp=xp[6] - current["xp"]),
                db=db,
            )
            self.assertEqual(receipt["character"]["level"], 6)
            self.assertTrue(
                mission_character_events.after_combat(db, self.store, current, fight_id)
            )
            self.assertEqual(
                mission_character_events.after_combat(
                    db, self.store, current, fight_id
                ),
                [],
            )
            final = storage.load_locked(db, character["id"])
            self.assertTrue(set(ids[:5]) <= set(final["running"]))
            self.assertNotIn(ids[5], final["running"])
            self.assertEqual(final["completed"], [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND delivered_at IS NOT NULL",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )
        self.assertEqual(
            mission_character_events.ready(self.store, account, generation, character),
            [],
        )
