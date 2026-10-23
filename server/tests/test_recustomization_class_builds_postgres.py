"""A class change migrates every saved spell loadout without replacing identity."""
import struct

from postgres_case import PostgresCase
from wakfu_server import aptitudes, builds, spells
from wakfu_server.character_recustomization import complete, request
from wakfu_server.progression import level_xp
from wakfu_server.wire import proto_field


class RecustomizationClassBuildsPostgresTests(PostgresCase):
    def test_class_change_rebuilds_all_decks_and_refunds_allocations_preserving_aggregate(
        self,
    ):
        account = self.store.register("class-migration", "local-password")["id"]
        character = self.store.create_character(account, "Class Survivor", breed=15)
        cid = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, cid)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=80 WHERE id=%s", (cid,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(80), cid),
            )
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (cid,),
            ).fetchone()["uid"]
            ticket = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,19164,2,%s,0) RETURNING uid",
                (cid, bag),
            ).fetchone()["uid"]
            keepsake = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,2021,1,%s,1) RETURNING uid",
                (cid, bag),
            ).fetchone()["uid"]
            bonus = next(iter(aptitudes.BONUS_CATEGORY))
            for index, level in ((0, 80), (1, 50)):
                sheet = b"".join(
                    proto_field(t, v)
                    for t, v in (
                        (8, index),
                        (18, f"Saved {index}".encode()),
                        (24, level),
                        (56, 1),
                        (64, 0),
                    )
                )
                allocation = proto_field(24, level) + proto_field(
                    34, proto_field(8, bonus) + proto_field(16, 1)
                )
                aptitudes.validate(dict(level=level), allocation)
                db.execute(
                    "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                    "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) DO UPDATE SET "
                    "sheet=EXCLUDED.sheet,equipment=EXCLUDED.equipment,deck=EXCLUDED.deck,aptitudes=EXCLUDED.aptitudes",
                    (
                        cid,
                        index,
                        sheet,
                        builds.EMPTY_EQUIPMENT,
                        spells.default_deck(dict(breed=15, level=level)),
                        allocation,
                    ),
                )
            db.execute(
                "UPDATE character_build_selection SET active_index=1 WHERE character_id=%s",
                (cid,),
            )
        before = self.store.character(account, cid)
        request(self.store, account, generation, cid, struct.pack(">iq", 7192, ticket))
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s", (account,)
            )
        result = complete(
            self.store,
            account,
            generation,
            dict(
                character_id=cid,
                breed_id=16,
                character_name=before["name"],
                creation_flag=False,
                appearance={"sex": 1, "faceIndex": 1},
            ),
        )
        after = self.store.character(account, cid)
        self.assertTrue(result["recustomized"])
        self.assertEqual(
            (cid, before["name"], 80, level_xp(80), 1),
            (
                after["id"],
                after["name"],
                after["level"],
                after["xp"],
                after["active_build_index"],
            ),
        )
        self.assertEqual(16, after["breed"])
        self.assertEqual(set(before["builds"]), set(after["builds"]))
        for index, build in after["builds"].items():
            self.assertEqual(before["builds"][index]["sheet"], build["sheet"])
            self.assertEqual(before["builds"][index]["equipment"], build["equipment"])
            self.assertEqual(builds.EMPTY_APTITUDES, bytes.fromhex(build["aptitudes"]))
            level = builds.effective_sheet_level(after, index)
            parsed = spells.validate_deck(bytes.fromhex(build["deck"]), 16, level)
            self.assertTrue(parsed["active"])
            self.assertNotEqual(before["builds"][index]["deck"], build["deck"])
            self.assertEqual(
                {},
                aptitudes.validate(
                    dict(level=level), bytes.fromhex(build["aptitudes"])
                )["allocations"],
            )
        self.assertEqual(
            {ticket: 1, keepsake: 1},
            {
                row["uid"]: row["quantity"]
                for row in after["inventory_items"]
                if row["uid"] in (ticket, keepsake)
            },
        )
        self.assertIsNone(after["recustomization"])
        selected = self.store.select_character(account, generation, cid)
        self.assertEqual(
            (cid, 16, 1),
            (selected["id"], selected["breed"], selected["active_build_index"]),
        )
