"""Rii entry proves safe journal reset before activation/tracking in PostgreSQL."""
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import storage, zone_missions


class MissionWireOrderPostgresTests(PostgresCase):
    def test_rii_entry_uses_native_definitions_and_orders_reset_activate_track(self):
        account = self.store.register("journal-wire-order", "test-password")["id"]
        character = self.store.create_character(account, "Journal Wire")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])

        definitions = {
            5160: {
                "d": 5160,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [
                    {"d": objective, "ckc": "", "cke": "", "ckf": []}
                    for objective in (10612, 10613)
                ],
            },
            5146: {
                "d": 5146,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [
                    {"d": objective, "ckc": "", "cke": "", "ckf": []}
                    for objective in (10582, 10583, 10584)
                ],
            },
        }
        revision = "b" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,%s)",
                (revision, Jsonb({}), b"wire-order-test", len(definitions)),
            )
            for identity, native in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES (%s,%s,%s)",
                    (revision, identity, Jsonb({"native": native})),
                )
            db.execute(
                "UPDATE characters SET map_id=1385,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (character["id"],),
            )
            current = self.store.character(account, character["id"], db)
            before = storage.load_locked(db, character["id"])
            before["objectives"] = [990001]
            before["variables"] = {"990002": 7}
            storage.store(db, character["id"], before)

        with self.store.connection() as db:
            current = self.store.character(account, character["id"], db)
            packets = zone_missions.enter_rii(
                db,
                self.store,
                current,
                previous_map=527,
            )

        # Both active missions have explicit definitions in PostgreSQL. Their
        # safe native reset must precede activation and tracking for each quest.
        identities = (5146, 5160)
        expected = []
        for identity in identities:
            expected.extend(
                (
                    (13205, (character["id"], identity)),
                    (13312, (character["id"], identity)),
                    (13371, (character["id"], identity, 1)),
                )
            )
        decoded = []
        for opcode, body in packets:
            if opcode == 13371:
                import struct

                decoded.append((opcode, struct.unpack(">qiB", body)))
            else:
                import struct

                decoded.append((opcode, struct.unpack(">qi", body)))
        self.assertEqual(decoded, expected)

        with self.reopen().connection() as db:
            saved = storage.load_locked(db, character["id"])
            self.assertEqual(saved["running"], [5146, 5160])
            self.assertEqual(saved["tracking"], [5146, 5160])
            self.assertEqual(saved["objectives"], [990001])
            self.assertEqual(saved["variables"], {"990002": 7})
            receipt_ids = [
                row["payload"]["definition_id"]
                for row in db.execute(
                    "SELECT payload FROM character_achievement_events WHERE character_id=%s "
                    "AND event_key LIKE 'zone-entry-mission:%%' ORDER BY event_key",
                    (character["id"],),
                ).fetchall()
            ]
            self.assertEqual(receipt_ids, [5146, 5160])


if __name__ == "__main__":
    import unittest

    unittest.main()
