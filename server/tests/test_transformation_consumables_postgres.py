"""Isolated candidate qualification; this does not enable live visual support."""
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.consumable_buffs import active_states, retire_states
from wakfu_server.inventory_consumable_effects import use
from wakfu_server.wire import proto_field


class TransformationConsumablesPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("transformation-tests", "local-password")[
            "id"
        ]
        character = self.store.create_character(self.account, "Morph Survivor", breed=1)
        self.cid = character["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.cid)
        self.units = {}
        with self.store.connection() as db:
            # Only the isolated schema admits these exact native candidates.
            db.execute(
                "UPDATE native_consumable_actions SET available=true,unsupported_reason='' "
                "WHERE item_ref=ANY(%s)",
                ([10380, 21624, 21625],),
            )
            db.execute("UPDATE characters SET level=25 WHERE id=%s", (self.cid,))
            container = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.cid,),
            ).fetchone()["uid"]
            for slot, (ref, quantity) in enumerate(
                ((2021, 1), (10380, 2), (21624, 2), (21625, 1))
            ):
                self.units[ref] = db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                    (self.cid, ref, quantity, container, slot),
                ).fetchone()["uid"]
            equipment = proto_field(
                10, proto_field(8, self.units[2021]) + proto_field(16, 4)
            )
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s AND build_index=0",
                (equipment, self.cid),
            )
        health_store.initialize(self.store, self.account, self.generation, self.cid)

    def quantity(self, reference):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s",
                (self.units[reference],),
            ).fetchone()
        return row["quantity"] if row else 0

    def consume(self, reference):
        character = self.store.character(self.account, self.cid)
        return use(
            self.store,
            self.account,
            self.generation,
            self.cid,
            struct.pack(">qB", self.units[reference], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )

    def test_guard_reconnect_expiry_and_same_clock_renewal_preserve_identity_equipment_and_health(
        self,
    ):
        before = self.store.character(self.account, self.cid)
        first = self.consume(10380)
        self.assertTrue(first["applied"])
        self.assertEqual(self.quantity(10380), 1)
        (state,) = first["character"]["consumable_states"]
        self.assertEqual((state["state_id"], state["duration_ms"]), (949, 900000))
        self.assertEqual(state["metadata"]["native_visual_effect_ids"], [43974])
        with self.assertRaisesRegex(ValueError, "condiciones"):
            self.consume(10380)
        self.assertEqual(self.quantity(10380), 1)
        reconnect = self.reopen().character(self.account, self.cid)
        self.assertEqual(
            reconnect["consumable_states"][0]["metadata"][
                "native_visual_applied_at_ms"
            ],
            state["metadata"]["native_visual_applied_at_ms"],
        )
        with self.store.connection() as db:
            retire_states(self.store, db, self.cid, state_ids=[949])
        frozen = self.store.clock()
        self.store.clock = lambda: frozen
        pink = next(
            row
            for row in self.consume(21624)["character"]["consumable_states"]
            if row["state_id"] == 4662
        )
        layered = self.consume(10380)["character"]["consumable_states"]
        # State-ID order is model949 then color4662, but actual application
        # order was the opposite. Reconnect must follow the persisted stamp.
        ordered = sorted(
            layered, key=lambda row: row["metadata"]["native_visual_applied_at_ms"]
        )
        self.assertEqual([row["state_id"] for row in ordered], [4662, 949])
        middle = self.consume(21625)["character"]["consumable_states"]
        green = next(row for row in middle if row["state_id"] == 4742)
        final = self.consume(21624)["character"]
        renewed = next(
            row for row in final["consumable_states"] if row["state_id"] == 4662
        )
        # Original event2248 removes the previous color before applying a new
        # one; the independent model state949 remains active underneath it.
        self.assertNotEqual(pink["uid"], renewed["uid"])
        self.assertEqual(
            {row["state_id"] for row in final["consumable_states"]}, {949, 4662}
        )
        key = "native_visual_applied_at_ms"
        self.assertLess(pink["metadata"][key], green["metadata"][key])
        self.assertLess(green["metadata"][key], renewed["metadata"][key])
        for field in (
            "id",
            "name",
            "breed",
            "sex",
            "appearance",
            "level",
            "xp",
            "builds",
            "hp",
            "max_hp",
            "hp_damage",
            "health_dead",
        ):
            self.assertEqual(before[field], final[field], field)
        self.assertEqual(self.quantity(2021), 1)
        with self.store.connection() as db:
            active_states(
                self.store,
                db,
                self.cid,
                generation=self.generation,
                now_ms=int(self.store.clock() * 1000) + 900001,
            )
        self.assertEqual(
            self.store.character(self.account, self.cid)["consumable_states"], ()
        )

    def test_unqualified_visual_effect_rejects_before_state_or_source_mutation(self):
        with self.store.connection() as db:
            plan = db.execute(
                "SELECT plan FROM native_consumable_actions WHERE item_ref=10380"
            ).fetchone()["plan"]
            plan["states"][0]["metadata"]["native_effects"]["43974"]["generic"] = 122
            db.execute(
                "UPDATE native_consumable_actions SET plan=%s WHERE item_ref=10380",
                (Jsonb(plan),),
            )
        with self.assertRaisesRegex(ValueError, "transformation effect"):
            self.consume(10380)
        self.assertEqual(self.quantity(10380), 2)
        self.assertEqual(
            self.store.character(self.account, self.cid)["consumable_states"], ()
        )
