"""Recovered ultimate starts pay once in the run transaction, never per hero."""
import struct
import unittest
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from wakfu_server import rift_key_admission as keys, rift_runtime, rift_entry_adapter
from wakfu_server.characters import heroes


class RiftKeyContractTests(unittest.TestCase):
    def test_all_native_contracts_and_unrecognized_source_fail_closed(self):
        for map_id, object_id, reference in (
            (1318, 33018, 28789),
            (1324, 33024, 28790),
            (1347, 33271, 29594),
        ):
            catalog = dict(
                type="ULTIMATE_INFINITE_WAVE",
                map_id=map_id,
                native_start_contract=dict(
                    object_id=object_id,
                    descriptor_id=1457,
                    reference=reference,
                    quantity=1,
                    action=1,
                    consume=True,
                    criterion="not IsHero()",
                    script_reference=3296,
                    source="native_table_31",
                ),
                objects=[
                    dict(
                        id=object_id,
                        map_id=map_id,
                        type="GenericActivableInteractiveElement",
                    )
                ],
            )
            price = keys.contract(catalog)
            self.assertEqual(
                (price["reference"], price["quantity"], price["action"]),
                (reference, 1, 1),
            )
            with self.assertRaises(ValueError):
                keys.contract(dict(catalog, objects=[]))
        with self.assertRaises(ValueError):
            keys.contract(dict(type="ULTIMATE_INFINITE_WAVE", map_id=999))
        db = Mock()
        self.assertEqual(
            keys.consume(db, dict(catalog=dict(type="INFINITE_WAVE")), 1, 2), ()
        )
        db.execute.assert_not_called()

    def test_classic_lore_action_and_ultimate_missing_key_action_do_not_start(self):
        for kind, action, map_id, object_id in (
            ("INFINITE_WAVE", 1, 1314, 33012),
            ("ULTIMATE_INFINITE_WAVE", 0, 1318, 33018),
        ):
            db, store = Mock(), Mock()
            store.character.return_value = dict(instance_id=99)
            db.execute.return_value.fetchone.return_value = dict(
                catalog=dict(
                    type=kind,
                    map_id=map_id,
                    native_start_contract=dict(
                        object_id=object_id,
                        descriptor_id=1457,
                        reference=28789,
                        quantity=1,
                        action=1,
                        consume=True,
                        criterion="not IsHero()",
                        script_reference=3296,
                        source="native_table_31",
                    ),
                    objects=[
                        dict(
                            id=object_id,
                            map_id=map_id,
                            type="GenericActivableInteractiveElement",
                        )
                    ],
                )
            )
            self.assertIsNone(
                rift_entry_adapter.authorize_start(
                    db,
                    store,
                    1,
                    "lease",
                    2,
                    struct.pack(">qHH", object_id, action, 0),
                    source_allowed=lambda *_: True,
                )
            )


class RiftKeyAdmissionPostgresTests(PostgresCase):
    def test_paid_owner_with_hero_rollback_replay_and_native_action_contracts(self):
        account = self.store.register("rift-paid-main", "local-password")["id"]
        main = self.store.create_character(account, "Riftpaidmain")["id"]
        hero = self.store.create_character(account, "Riftpaidhero")["id"]
        generation = self.store.begin_session(account, ttl=10000)
        self.store.select_character(account, generation, main)
        heroes.add(self.store, account, generation, main, hero)
        from wakfu_server import quest_inventory
        from wakfu_server.maps.dungeon_entry_payment import available

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{ultimate_enabled}','true') "
                "WHERE name='rift_policy'"
            )
        for wave_id in (5, 8, 37):
            with self.subTest(wave_id=wave_id):
                with self.store.connection() as db:
                    run = rift_runtime.enter(
                        db,
                        wave_id,
                        main,
                        [main, hero],
                        seed="paid",
                        authorize=lambda *_: True,
                    )
                    price = keys.contract(run["catalog"])
                    reference = price["reference"]
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=ANY(%s)",
                        (run["catalog"]["map_id"], run["instance_id"], [main, hero]),
                    )
                    fight = db.execute(
                        "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
                    ).fetchone()["id"]
                    for cid in (main, hero):
                        db.execute(
                            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                            "VALUES(%s,%s,%s,0,%s)",
                            (fight, cid, account, generation),
                        )
                    if (
                        reference
                        in quest_inventory._SOURCE["account_quest_property_references"]
                    ):
                        db.execute(
                            "INSERT INTO account_quest_items(account_id,reference,quantity) VALUES(%s,%s,1)",
                            (account, reference),
                        )
                    elif reference in quest_inventory.REFERENCES:
                        db.execute(
                            "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,%s,1)",
                            (main, reference),
                        )
                    else:
                        bag = db.execute(
                            "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                            "VALUES(%s,1,0,30,0) ON CONFLICT(character_id,kind) DO UPDATE SET capacity=30 RETURNING uid",
                            (main,),
                        ).fetchone()["uid"]
                        db.execute(
                            "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,%s,1,%s,0)",
                            (main, reference, bag),
                        )
                with self.store.connection() as db:
                    authorized = rift_entry_adapter.authorize_start(
                        db,
                        self.store,
                        account,
                        generation,
                        main,
                        struct.pack(">qHH", price["object_id"], 1, 0),
                        source_allowed=lambda *_: True,
                    )
                    self.assertEqual(authorized["members"], [main, hero])
                    with self.assertRaises(ValueError):
                        rift_runtime.start(db, run["instance_id"], hero, fight)
                with self.assertRaisesRegex(RuntimeError, "bind rollback"):
                    with self.store.connection() as db:
                        rift_runtime.start(db, run["instance_id"], main, fight)
                        self.assertFalse(available(db, main, reference, 1))
                        raise RuntimeError("bind rollback")
                with self.store.connection() as db:
                    self.assertTrue(available(db, main, reference, 1))
                    first = rift_runtime.start(db, run["instance_id"], main, fight)
                    replay = rift_runtime.start(db, run["instance_id"], main, fight)
                    self.assertEqual(first, replay)
                    self.assertFalse(available(db, main, reference, 1))
                    packets = keys.publication(db, self.store, account, main)
                    self.assertEqual([packet[0] for packet in packets], [13713, 13078])
                    self.assertEqual(
                        packets, keys.publication(db, self.store, account, main)
                    )
                    self.assertEqual(struct.unpack(">q", packets[0][1][:8])[0], main)
                    self.assertEqual(packets[0][1][8], 35)
                    db.execute(
                        "UPDATE rift_instances SET status='closed',ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                        (run["instance_id"],),
                    )
                    db.execute(
                        "UPDATE combat_fights SET status='finished' WHERE id=%s",
                        (fight,),
                    )
