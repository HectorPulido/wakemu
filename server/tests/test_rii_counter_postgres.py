"""Rii ecosystem counter packets and receipts persist in isolated PostgreSQL."""
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import counter_missions, storage


class RiiCounterPostgresTests(PostgresCase):
    def test_crozoli_plant_seed_and_harvest_refresh_same_tracked_mission(self):
        account = self.store.register("rii-counter-test", "test-password")["id"]
        character = self.store.create_character(account, "Rii Counter")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        definition = {
            "d": 5155,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [
                {
                    "d": objective,
                    "ckc": "",
                    "cke": "",
                    "ckf": [
                        {
                            "ckm": f'GetAchievementVariable("{name}") >= 3',
                            "ckn": [variable],
                        },
                    ],
                }
                for objective, name, variable in (
                    (10598, "INCARNAM_nbCrozoliSeedCollected", 759),
                    (10599, "INCARNAM_nbCrozoliResourceCollected", 758),
                    (10600, "INCARNAM_nbCrozoliPlanted", 760),
                )
            ],
            "cjK": [],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("c" * 64, Jsonb({}), b"rii-counter-test"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                "VALUES (%s,5155,%s)",
                ("c" * 64, Jsonb({"native": definition})),
            )
            db.execute(
                "UPDATE characters SET map_id=1385,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [5155]
            state["tracking"] = [5155]
            storage.store(db, character["id"], state)
            current = self.store.character(account, character["id"], db)

        events = (
            ("planting", 31007, 760),
            ("resource_harvest", 31006, 758),
            ("resource_harvest", 31007, 759),
        )
        for index, (kind, item_reference, variable) in enumerate(events):
            with self.store.connection() as db:
                packets = counter_missions.settle_rii_event(
                    db,
                    self.store,
                    current,
                    token=f"counter-event-{index}",
                    kind=kind,
                    item_reference=item_reference,
                )
            encoded = [
                (opcode, struct.unpack(">qiq", body)[1:])
                for opcode, body in packets
                if opcode == 13295
            ]
            self.assertEqual(encoded, [(13295, (variable, 1))])
            self.assertEqual(
                [
                    (opcode, struct.unpack(">qiB", body)[1:])
                    for opcode, body in packets
                    if opcode == 13371
                ],
                [(13371, (5155, 0)), (13371, (5155, 1))],
            )
            self.assertEqual([opcode for opcode, _ in packets], [13295, 13371, 13371])
            with self.reopen().connection() as db:
                saved = storage.load_locked(db, character["id"])
                self.assertEqual(saved["running"], [5155])
                self.assertEqual(saved["tracking"], [5155])
                self.assertEqual(
                    saved["variables"], {str(v): 1 for _, _, v in events[: index + 1]}
                )

        with self.store.connection() as db:
            before_duplicate = storage.load_locked(db, character["id"])
            with self.assertRaisesRegex(
                ValueError, "Duplicate ecosystem mission receipt"
            ):
                counter_missions.settle_rii_event(
                    db,
                    self.store,
                    current,
                    token="counter-event-2",
                    kind="resource_harvest",
                    item_reference=31007,
                )
        with self.reopen().connection() as db:
            self.assertEqual(storage.load_locked(db, character["id"]), before_duplicate)


if __name__ == "__main__":
    import unittest

    unittest.main()
