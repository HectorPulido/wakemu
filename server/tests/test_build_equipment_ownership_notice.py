"""Rejected cross-owner saves explain authorized custody without moving items."""
import struct
from copy import deepcopy

from postgres_case import PostgresCase
from wakfu_server import builds, heroes, wire
from wakfu_server.equipment_stacks import EquipmentOwnershipError
from wakfu_server.inventory_uids import allocate


class BuildEquipmentOwnershipNoticeTests(PostgresCase):
    def test_real_save_rejection_notice_guards_and_inventory_conservation(self):
        from test_build_save_dispatch import BuildSaveDispatchTest

        account = self.store.register("ownership-notice", "local-password")["id"]
        main = self.store.create_character(account, "Notice Main")
        active = self.store.create_character(account, "Notice Hero")
        inactive = self.store.create_character(account, "Private Inactive")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], active["id"])
        foreign_account = self.store.register("foreign-notice", "local-password")["id"]
        foreign = self.store.create_character(foreign_account, "Private Foreign")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, foreign_generation, foreign["id"])
        # Physical custody rows are the input; actual Store hydration and
        # transaction rollback remain part of this integration case.
        units = {}
        with self.store.connection() as db:
            for owner in (main, active, inactive, foreign):
                uid = allocate(db)
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,2021,2,%s,0)",
                    (uid, owner["id"], owner["inventory_containers"][0]["uid"]),
                )
                units[owner["id"]] = {"uid": uid}

        def durable_state():
            with self.store.connection() as db:
                return deepcopy(
                    (
                        list(db.execute("SELECT * FROM inventory_items ORDER BY uid")),
                        list(
                            db.execute(
                                "SELECT * FROM character_builds ORDER BY character_id,build_index"
                            )
                        ),
                        db.execute(
                            "SELECT character_id FROM sessions WHERE account_id=%s",
                            (account,),
                        ).fetchone(),
                    )
                )

        before = durable_state()
        cases = (
            ("active owned hero", units[active["id"]]["uid"], active["name"]),
            ("inactive owned hero", units[inactive["id"]]["uid"], None),
            ("foreign account", units[foreign["id"]]["uid"], None),
            ("missing item", 1 << 60, None),
        )
        for label, uid, expected_owner in cases:
            with self.subTest(case=label):
                equipment = b"".join(
                    wire.proto_field(
                        10, wire.proto_field(8, item_uid) + wire.proto_field(16, slot)
                    )
                    for item_uid, slot in ((units[main["id"]]["uid"], 0), (uid, 4))
                )
                # Exercise actual Store hydration alongside the lease, roster,
                # inventory checks and rollback of any singleton split.
                with self.assertRaises(EquipmentOwnershipError) as raised:
                    self.store.save_build(
                        account,
                        generation,
                        main["id"],
                        0,
                        {
                            "sheet": b"",
                            "equipment": equipment,
                            "deck": b"",
                            "aptitudes": b"",
                        },
                    )
                error = raised.exception
                self.assertEqual(error.uid, uid)
                self.assertEqual(error.owner_name, expected_owner)
                self.assertEqual(
                    str(error), "Equipment sheet item is unavailable or foreign"
                )
                self.assertEqual(builds.rejection_status(error), 7)
                context = BuildSaveDispatchTest().dispatch(save_error=error)
                packets = [call.args[2:] for call in context["send"].call_args_list]
                notices = [body for opcode, body in packets if opcode == 349]
                self.assertEqual(len(notices), 1)
                subtype, size = struct.unpack(">hh", notices[0][:4])
                self.assertEqual(subtype, 4)
                self.assertEqual(size, len(notices[0][4:]))
                text = notices[0][4:].decode("utf-8")
                self.assertEqual(text, error.player_message)
                if expected_owner:
                    self.assertIn(expected_owner, text)
                    self.assertIn("transfiérelo", text.casefold())
                    self.assertIn("inventario normal de bolsas", text)
                    self.assertIn("fuera del editor de builds", text)
                else:
                    for name in (active["name"], inactive["name"], foreign["name"]):
                        self.assertNotIn(name, text)
                self.assertEqual([opcode for opcode, _ in packets], [349, 22318, 12284])
                self.assertEqual(context["character"]["id"], 37)
                self.assertEqual(durable_state(), before)
