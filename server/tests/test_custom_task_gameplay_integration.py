"""Actual combat and planting hooks atomically persist native and custom tasks."""
from types import SimpleNamespace
from unittest.mock import patch
import uuid
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import service as custom, adapters


class HookIntegrationTests(PostgresCase):
    def test_actual_native_combat_two_heroes_and_custom_failure_rollback(self):
        from wakfu_server.achievements import combat_adapter as adapter

        account = self.store.register("hook-combat", "local-password")["id"]
        chars = [
            self.store.create_character(account, name)
            for name in ("Hook Main", "Hook Hero")
        ]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
            ).fetchone()["id"]
            for character in chars:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                    (fight_id, character["id"], account),
                )
        actors = {
            c["id"]: SimpleNamespace(controlled=True, owner_id=account, team=0, hp=1)
            for c in chars
        }
        actors.update(
            {
                -1: SimpleNamespace(controlled=False, team=1, hp=0),
                -2: SimpleNamespace(controlled=False, team=1, hp=1),
                -3: SimpleNamespace(controlled=False, team=1, hp=0),
            }
        )
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={-3: object()},
        )
        members = [dict(character_id=c["id"], account_id=account) for c in chars]
        originals = [dict(id=-1, ref=1), dict(id=-2, ref=1), dict(id=-3, ref=1)]
        original = adapters.original_kills

        def fail_second(db, owner, identity, fight_id):
            if identity == chars[1]["id"]:
                raise RuntimeError("Second hero custom hook failed")
            return original(db, owner, identity, fight_id)

        with self.assertRaises(
            RuntimeError
        ), self.store.connection() as db, patch.object(
            adapters, "original_kills", side_effect=fail_second
        ):
            adapter.settle_participants(db, self.store, fight, members, originals)
        with self.store.connection() as db:
            for table in (
                "character_achievement_events",
                "character_achievement_progress",
                "character_custom_task_events",
                "character_custom_task_progress",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )
            result = adapter.settle_participants(
                db, self.store, fight, members, originals
            )
            self.assertEqual(
                [u["character_id"] for u in result["custom_task_updates"]],
                [c["id"] for c in chars],
            )
            self.assertNotIn(
                13369,
                [
                    op
                    for packets in result["packets_by_owner"].values()
                    for op, _ in packets
                ],
            )
            for c in chars:
                self.assertEqual(custom.snapshot(db, account, c["id"])[0]["count"], 1)
            self.assertEqual(
                adapter.settle_participants(db, self.store, fight, members, originals)[
                    "custom_task_updates"
                ],
                [],
            )

    def test_actual_planting_last_seed_and_custom_failure_roll_back_native_mutations(
        self,
    ):
        import test_planting as fixtures

        fixture = fixtures.PlantingTests("test_monster_native_family_and_outbox_retry")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from wakfu_server import planting

        item, body, prepared = fixture.seed(7361, quantity=1)
        from wakfu_server.planting_runtime import Plantings

        runtime = Plantings(fixture.store)
        runtime.begin(
            fixture.account, fixture.generation, fixture.char, body, lambda *args: 0
        )
        operation = runtime.pending[fixture.char["id"]]["token"]
        self.assertEqual(len(operation), 32)
        self.assertEqual(uuid.UUID(operation).hex, operation)
        arguments = dict(
            operation_id=operation, stage=1, creation_time=123, result_prefix=(0, 1)
        )
        with patch.object(
            adapters,
            "monster_planting",
            side_effect=RuntimeError("Custom planting failed"),
        ), self.assertRaises(RuntimeError):
            planting.complete(
                fixture.store,
                fixture.account,
                fixture.generation,
                prepared,
                **arguments
            )
        with fixture.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planting_receipts").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                0,
            )
        result = planting.complete(
            fixture.store, fixture.account, fixture.generation, prepared, **arguments
        )
        self.assertTrue(result["success"])
        with fixture.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()
            )
            self.assertEqual(
                custom.snapshot(db, fixture.account, fixture.char["id"])[1]["count"], 1
            )
        self.assertTrue(
            planting.complete(
                fixture.store,
                fixture.account,
                fixture.generation,
                prepared,
                **arguments
            )["duplicate"]
        )
