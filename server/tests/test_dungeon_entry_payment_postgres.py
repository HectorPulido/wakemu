"""Native entrance keys commit with the run, never with failed or repeated entry."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
import test_dungeon_progression as fixture
from wakfu_server import dungeon_transport
from wakfu_server.maps.dungeon_entry_payment import available, consume


class DungeonEntryPaymentPostgresTests(PostgresCase):
    player = fixture.DungeonProgressionPostgresTests.player
    party = fixture.DungeonProgressionPostgresTests.party
    install_context_policy = (
        fixture.DungeonProgressionPostgresTests.install_context_policy
    )

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.ids = tuple(member["character"]["id"] for member in self.members)
        self.body = struct.pack(">qiBi", 26842, 2504, 0, 2)
        self.resolved = dungeon_transport.resolve_request(527, self.body)
        self.resolved["native_destination"] = dict(
            self.resolved["native_destination"], item_reference=15133, cyW=1
        )

    def grant(self, member, quantity=2, *, kind=0, slot=0):
        with self.store.connection() as db:
            bag = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,1,%s,30,0) ON CONFLICT(character_id,kind) "
                "DO UPDATE SET capacity=30 RETURNING uid",
                (member, kind),
            ).fetchone()["uid"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,15133,%s,%s,%s) RETURNING uid",
                (member, quantity, bag, slot),
            ).fetchone()["uid"]

    def quantities(self):
        with self.store.connection() as db:
            return tuple(
                (row["character_id"], row["quantity"])
                for row in db.execute(
                    "SELECT character_id,quantity FROM inventory_items ORDER BY character_id,uid"
                )
            )

    def enter(self, initializer=None):
        leader = self.members[0]
        with patch.object(
            dungeon_transport, "resolve_request", return_value=self.resolved
        ):
            return dungeon_transport.enter(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                527,
                self.body,
                source_allowed=lambda *_: True,
                criterion_allowed=lambda *_: True,
                initialize_instance=initializer,
            )

    def test_roster_paid_once_replay_without_remaining_key_succeeds(self):
        for member in self.ids:
            self.grant(member, 1)
        observed = []
        result = self.enter(lambda db, session: observed.append(session["reused"]))
        self.assertEqual(self.quantities(), ())
        self.assertEqual(
            {row["character_id"] for row in result["entry_item_payment"]}, set(self.ids)
        )
        replay = self.enter(lambda db, session: observed.append(session["reused"]))
        self.assertEqual(result["instance_id"], replay["instance_id"])
        self.assertTrue(replay["reused"])
        self.assertEqual(observed, [False, True])
        self.assertEqual(self.quantities(), ())
        # Returning one frozen member outside must not charge again either.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 WHERE id=%s",
                (self.ids[0],),
            )
        rejoined = self.enter()
        self.assertEqual(result["instance_id"], rejoined["instance_id"])
        self.assertTrue(rejoined["reused"])
        self.assertEqual(self.quantities(), ())

    def test_companion_missing_key_rolls_back_run_and_all_locations(self):
        self.grant(self.ids[0])
        self.grant(self.ids[1], kind=4)  # Stored items cannot pay entrance fees.
        before = self.quantities()
        with self.assertRaisesRegex(ValueError, "Every party member"):
            self.enter()
        self.assertEqual(self.quantities(), before)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
                ).fetchone()["n"],
                0,
            )
            locations = list(db.execute("SELECT map_id,instance_id FROM characters"))
        self.assertTrue(
            all((row["map_id"], row["instance_id"]) == (527, 0) for row in locations)
        )

    def test_initializer_failure_refunds_partial_stacks_and_cancels_run(self):
        for member in self.ids:
            self.grant(member, 3)
        before = self.quantities()

        def fail(db, session):
            raise ValueError("Initializer failed")

        with self.assertRaisesRegex(ValueError, "Initializer failed"):
            self.enter(fail)
        self.assertEqual(self.quantities(), before)
        result = self.enter()
        self.assertFalse(result["reused"])
        self.assertEqual(
            self.quantities(), tuple((member, 2) for member in sorted(self.ids))
        )

    def test_consume_splits_owned_stacks_and_rejects_equipped_units(self):
        from wakfu_server.wire import proto_field

        first = self.grant(self.ids[0], 1)
        second = self.grant(self.ids[0], 1, slot=1)
        third = self.grant(self.ids[0], 1, slot=2)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,0,'',%s,'','') ON CONFLICT(character_id,build_index) "
                "DO UPDATE SET equipment=EXCLUDED.equipment",
                (self.ids[0], proto_field(10, proto_field(8, first))),
            )
            self.assertTrue(available(db, self.ids[0], 15133, 2))
            self.assertFalse(available(db, self.ids[0], 15133, 3))
            result = consume(db, (self.ids[0],), 15133, 2)
        self.assertEqual(tuple(row["uid"] for row in result), (second, third))
        self.assertEqual(self.quantities(), ((self.ids[0], 1),))
        with self.assertRaisesRegex(ValueError, "Every party member"):
            with self.store.connection() as db:
                consume(db, (self.ids[0],), 15133, 1)

    def test_personal_quest_item_cost_uses_quest_storage_and_rolls_back(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,20389,3)",
                (self.ids[0],),
            )
        with self.assertRaisesRegex(ValueError, "Transition rejected"):
            with self.store.connection() as db:
                self.assertTrue(available(db, self.ids[0], 20389, 1))
                self.assertFalse(available(db, self.ids[1], 20389, 1))
                consume(db, (self.ids[0],), 20389, 1)
                raise ValueError("Transition rejected")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=20389",
                    (self.ids[0],),
                ).fetchone()["quantity"],
                3,
            )
            consumed = consume(db, (self.ids[0],), 20389, 2)
            self.assertTrue(consumed[0]["quest_item"])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=20389",
                    (self.ids[0],),
                ).fetchone()["quantity"],
                1,
            )
            consume(db, (self.ids[0],), 20389, 1)
            self.assertFalse(available(db, self.ids[0], 20389, 1))

    def test_account_quest_payment_is_owned_atomic_and_visible_in_snapshot(self):
        from wakfu_server.items import account_quest_inventory
        from wakfu_server.characters import exploration_secrets
        from wakfu_server.wire import proto_fields

        owner = self.members[0]["account"]
        with self.store.connection() as db:
            account_quest_inventory.grant(db, owner, 33075, 3)
            self.assertTrue(available(db, self.ids[0], 33075, 1))
            self.assertFalse(available(db, self.ids[1], 33075, 1))
            # Globally projected exploration artifacts are not consumable fees.
            self.assertFalse(available(db, self.ids[0], 18722, 1))
        with self.assertRaisesRegex(ValueError, "Every party member"):
            with self.store.connection() as db:
                consume(db, self.ids, 33075, 1)
        with self.store.connection() as db:
            self.assertEqual(account_quest_inventory.load(db, owner)[0]["quantity"], 3)
            self.assertEqual(
                account_quest_inventory.load(db, self.members[1]["account"]), []
            )
            consume(db, (self.ids[0],), 33075, 1)
            packet_id, body = exploration_secrets.account_packet(db, owner)
            self.assertEqual(packet_id, 13873)
            snapshots = [
                dict(proto_fields(value))
                for tag, value in proto_fields(body[12:])
                if tag == 10
            ]
            self.assertIn({8: 33075, 16: 2}, snapshots)
        actor = self.store.character(owner, self.ids[0])
        self.assertEqual(exploration_secrets.account_quantity(actor, (33075,)), 2)
        actor["account_id"] = self.members[1]["account"]
        with self.assertRaisesRegex(ValueError, "Foreign"):
            exploration_secrets.account_quantity(actor, (33075,))

    def test_same_account_members_pay_per_member_and_failed_transition_refunds(self):
        from wakfu_server.items import account_quest_inventory

        owner = self.members[0]["account"]
        hero = self.store.create_character(owner, "Seasonal Hero")
        roster = (self.ids[0], hero["id"])
        with self.store.connection() as db:
            account_quest_inventory.grant(db, owner, 33075, 3)
        with self.assertRaisesRegex(ValueError, "Transition failed"):
            with self.store.connection() as db:
                consume(db, roster, 33075, 1)
                raise ValueError("Transition failed")
        with self.store.connection() as db:
            self.assertEqual(account_quest_inventory.load(db, owner)[0]["quantity"], 3)
            result = consume(db, roster, 33075, 1)
            self.assertEqual(result[0]["consumed"], 2)
            self.assertEqual(account_quest_inventory.load(db, owner)[0]["quantity"], 1)
            consume(db, (self.ids[0],), 33075, 1)
            self.assertEqual(account_quest_inventory.load(db, owner), [])
