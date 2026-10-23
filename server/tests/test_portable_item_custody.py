"""Physical furniture and equipped bags retain mutable per-UID state."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class PortableItemCustodyTests(PostgresCase):
    def _owner(self):
        account = self.store.register("portable-custody-owner", "local-password")["id"]
        character = self.store.create_character(account, "Portable Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def _metadata(self, uid, reference):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,%s)",
                (uid, reference),
            )
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,true,false)",
                (uid,),
            )

    def _assert_metadata(self, uid, reference):
        from wakfu_server.item_custody_metadata import snapshot

        with self.store.connection() as db:
            metadata = snapshot(db, uid)
        self.assertEqual(
            metadata["inventory_item_bindings"],
            {
                "uid": uid,
                "bound": True,
                "template_reference": reference,
            },
        )
        self.assertEqual(
            metadata["inventory_item_recycling_state"],
            {
                "uid": uid,
                "unidentified": True,
                "socketed": False,
            },
        )

    def test_physical_furniture_reconnect_pack_preserves_binding_and_options(self):
        from wakfu_server.inventory_items import grant
        from wakfu_server.haven_bag_furniture_transfer import deploy, edit

        account, generation, character = self._owner()
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=6293,
            quantity=2,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={6293},
        )
        self._metadata(source["uid"], 6293)
        location = {"map_id": 9, "instance_id": character["id"]}
        placed = deploy(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iqiihi", 6293, source["uid"], 1, 1, 0, 0),
            location=location,
        )
        unit_uid = placed["character"]["haven_bag"]["furniture"][0]["item_uid"]
        self.assertNotEqual(unit_uid, source["uid"])
        self._assert_metadata(source["uid"], 6293)
        with patch(
            "wakfu_server.haven_bag_furniture_transfer._persist",
            side_effect=ValueError("failed save"),
        ):
            with self.assertRaisesRegex(ValueError, "failed save"):
                edit(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    12870,
                    struct.pack(">qH", 2770, 23) + b"\x00\x00",
                    location=location,
                )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s", (unit_uid,)
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM portable_item_custody WHERE uid=%s", (unit_uid,)
                ).fetchone()
            )
        packed = edit(
            self.reopen(),
            account,
            generation,
            character["id"],
            12870,
            struct.pack(">qH", 2770, 23) + b"\x00\x00",
            location=location,
        )
        self.assertEqual(
            {item["uid"] for item in packed["character"]["inventory_items"]},
            {source["uid"], unit_uid},
        )
        self._assert_metadata(unit_uid, 6293)

    def test_bag_equip_reconnect_remove_preserves_binding_and_options(self):
        from wakfu_server.inventory_bags import equip, remove

        account, generation, character = self._owner()
        base, extra = character["inventory_containers"]
        remove(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(
                ">qqqqb", base["uid"], extra["uid"], extra["uid"], base["uid"], 0
            ),
        )
        self._metadata(extra["uid"], extra["reference"])
        equip(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qqqb", extra["uid"], base["uid"], character["id"], 1),
        )
        remove(
            self.reopen(),
            account,
            generation,
            character["id"],
            struct.pack(
                ">qqqqb", base["uid"], extra["uid"], extra["uid"], base["uid"], 0
            ),
        )
        self._assert_metadata(extra["uid"], extra["reference"])

    def test_native_character_binding_remains_authoritative_without_legacy_sidecar(
        self,
    ):
        from wakfu_server.inventory_items import grant
        from wakfu_server.portable_item_custody import hold, restore

        account, generation, character = self._owner()
        other = self.store.create_character(account, "Other Portable")
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=9940,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={9940},
        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_item_bindings WHERE uid=%s", (source["uid"],)
            )
            hold(db, source, uid=source["uid"], account_id=account, kind="furniture")
        with self.assertRaisesRegex(ValueError, "bound to another character"):
            with self.store.connection() as db:
                db.execute("DELETE FROM inventory_items WHERE uid=%s", (source["uid"],))
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,9940,1,%s,0)",
                    (
                        source["uid"],
                        other["id"],
                        other["inventory_containers"][0]["uid"],
                    ),
                )
                restore(
                    db,
                    uid=source["uid"],
                    account_id=account,
                    character_id=other["id"],
                    reference=9940,
                    kind="furniture",
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT character_id FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["character_id"],
                character["id"],
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM portable_item_custody WHERE uid=%s", (source["uid"],)
                ).fetchone()
            )
