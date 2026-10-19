"""Public seasonal entry pays only with a committed authoritative transition."""
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.maps import seasonal_transport


class SeasonalTransportPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("seasonal-owner", "test-password")["id"]
        self.actor = self.store.create_character(self.account, "Seasonal Main")
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.actor["id"])
        with self.store.connection() as db:
            from wakfu_server.items.account_quest_inventory import grant

            grant(db, self.account, 33075, 2)
        self.actor = self.store.character(self.account, self.actor["id"])
        self.route = dict(
            criterion="",
            item_payment=dict(reference=33075, quantity=1),
            destination=dict(map_id=146, instance_id=0, x=0, y=0, z=9),
        )

    def quantity(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=33075",
                (self.account,),
            ).fetchone()
            return row["quantity"] if row else 0

    def enter(self):
        return seasonal_transport.transition(
            self.store, self.account, self.generation, self.actor, self.route
        )

    def test_success_and_stale_origin_replay_never_double_charge(self):
        self.assertEqual(self.enter()["map_id"], 146)
        self.assertEqual(self.quantity(), 1)
        with self.assertRaisesRegex(ValueError, "origin is desynchronized"):
            self.enter()
        self.assertEqual(self.quantity(), 1)

    def test_failed_map_transition_rolls_back_payment(self):
        with patch.object(
            self.store,
            "transition_map_in_transaction",
            side_effect=ValueError("failed map"),
        ):
            with self.assertRaisesRegex(ValueError, "failed map"):
                self.enter()
        self.assertEqual(self.quantity(), 2)
        self.assertEqual(
            self.store.character(self.account, self.actor["id"])["map_id"],
            self.actor["map_id"],
        )

    def test_changed_level_criterion_rejects_before_payment(self):
        self.route["criterion"] = "GetRealLevel() >= 200"
        with self.assertRaisesRegex(ValueError, "criterion is not met"):
            self.enter()
        self.assertEqual(self.quantity(), 2)

    def test_missing_native_item_does_not_move(self):
        self.route["item_payment"]["reference"] = 15133
        with self.assertRaisesRegex(ValueError, "entrance item"):
            self.enter()
        self.assertEqual(self.quantity(), 2)
        self.assertEqual(
            self.store.character(self.account, self.actor["id"])["map_id"],
            self.actor["map_id"],
        )

    def test_normal_grant_routes_account_items_without_physical_bag_units(self):
        from wakfu_server.inventory_items import grant, insertion

        item = grant(
            self.store,
            self.account,
            self.generation,
            self.actor["id"],
            reference=33075,
            quantity=1,
            container=0,
            slot=0,
            allowed_references={33075},
        )
        self.assertEqual(self.quantity(), 3)
        self.assertEqual(insertion(item)[0], 13873)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=33075",
                    (self.actor["id"],),
                ).fetchone()["n"],
                0,
            )

    def test_console_can_grant_account_and_personal_quest_items(self):
        from wakfu_server.test_console import execute
        from wakfu_server.command_permissions import set_admin
        from wakfu_server.combat_groups import Groups

        set_admin(self.store, self.account, True, operator="test", reason="fixture")
        result = execute(
            self.store,
            Groups(),
            self.account,
            self.generation,
            self.actor,
            "!item 33075 1",
        )
        self.assertEqual(self.quantity(), 3)
        self.assertTrue(result["item"]["account_quest_item"])
        self.assertIn(13873, [opcode for opcode, _ in result["packets"]])
        result = execute(
            self.store,
            Groups(),
            self.account,
            self.generation,
            self.actor,
            "!item 20389 1",
        )
        self.assertEqual(result["character"]["quest_items"][0]["reference"], 20389)
        self.assertIn(13879, [opcode for opcode, _ in result["packets"]])
