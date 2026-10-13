import struct
import unittest
from dataclasses import replace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.craft_catalog import load_catalog
from wakfu_server.crafting import (
    begin,
    cancel,
    complete,
    completion_target,
    craft_duration_ms,
    current,
)
from wakfu_server.profession_store import ensure_learned
from wakfu_server import inventory_items
from wakfu_server.inventory_move import STACKS
from wakfu_server.player_exchanges import answer, invite, offer_item


class CraftingAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("crafting-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Crafting Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.table = 31517
        self.definition_id = 72
        self.profession_id = 40
        self.recipe_id = 3600
        self.catalog = load_catalog()
        self.station = dict(
            table_uid=self.table,
            map_id=1134,
            instance_id=0,
            definition_id=self.definition_id,
            profession_id=self.profession_id,
            in_range=True,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,x=-22,y=38,z=-8 WHERE id=%s",
                (self.character["id"],),
            )
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [40]
        )
        self.items = {}
        for reference, quantity in ((2504, 20), (11451, 20)):
            row = self.store.character(self.account, self.character["id"])
            item = inventory_items.grant(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                reference=reference,
                quantity=quantity,
                container=row["inventory_containers"][0]["uid"],
                slot=reference % 20,
                allowed_references=set(STACKS),
            )
            self.items[reference] = item

    def request12231(self, batch=1):
        return struct.pack(">qii", self.table, self.recipe_id, batch)

    def request13382(self, batch=1, mode=0):
        return (
            struct.pack(">qib", self.table, self.recipe_id, mode)
            + struct.pack(">ih", 2504, 5 * batch)
            + struct.pack(">ih", 11451, 5 * batch)
        )

    def test_native_craft_speed_formula_and_local_batch_timer_policy(self):
        # eTx.av uses Math.round(raw / (1 + CRAFT_SPEED / 100)); batches
        # serialize those per-recipe timers in the current emulator policy.
        self.assertEqual(1000, craft_duration_ms(1000, 1, 0))
        self.assertEqual(500, craft_duration_ms(1000, 1, 100))
        self.assertEqual(2000, craft_duration_ms(1000, 1, -50))
        self.assertEqual(1002, craft_duration_ms(1001, 2, 100))
        for raw, batch, modifier in (
            (True, 1, 0),
            (1000, True, 0),
            (1000, 1, True),
            (1000, 1, -100),
            (1000, 1, 1.5),
            (2**31 - 1, 32767, 0),
        ):
            with self.subTest(raw=raw, batch=batch, modifier=modifier):
                with self.assertRaises(ValueError):
                    craft_duration_ms(raw, batch, modifier)

    def test_begin_persists_actor_craft_speed_modifier_in_timer_snapshot(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
            craft_speed_modifier=100,
        )
        self.assertEqual(500, started["duration_ms"])
        self.assertEqual(
            (13989, struct.pack(">qibqq", self.table, self.recipe_id, 0, 500, 0)),
            started["packets"][0],
        )
        with self.store.connection() as db:
            snapshot = db.execute(
                "SELECT inventory_snapshot,duration_ms FROM craft_occupations WHERE token=%s",
                (started["token"],),
            ).fetchone()
        self.assertEqual(500, snapshot["duration_ms"])
        self.assertEqual(100, snapshot["inventory_snapshot"]["craft_speed_modifier"])
        self.assertEqual(
            "native_craft_speed_sequential_batch_v1",
            snapshot["inventory_snapshot"]["duration_policy"],
        )

    def test_success_consumes_and_grants_product_and_xp_once(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.assertEqual(1, started["version"])
        self.assertEqual([13989], [opcode for opcode, _ in started["packets"]])
        self.assertEqual(
            started["token"],
            current(self.store, self.account, self.generation, self.character["id"])[
                "token"
            ],
        )
        retry = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.assertTrue(retry["duplicate"])
        self.assertEqual(started["token"], retry["token"])
        with self.assertRaisesRegex(ValueError, "before its duration"):
            complete(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                started["token"],
                started["version"],
                bytes.fromhex("020008"),
                station=self.station,
            )

        self.clock[0] += 1.1
        outcome = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )
        self.assertFalse(outcome["replay"])
        self.assertEqual(200, outcome["applied_xp"])
        self.assertEqual(
            {self.items[2504]["uid"], self.items[11451]["uid"]},
            {row["uid"] for row in outcome["consumed"]},
        )
        self.assertIn((13479, bytes.fromhex("00000000000001")), outcome["packets"])
        replay = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )
        self.assertTrue(replay["replay"])
        self.assertEqual([], replay["packets"])
        self.assertIsNone(
            current(self.store, self.account, self.generation, self.character["id"])
        )
        state = self.store.character(self.account, self.character["id"])
        by_reference = {
            item["reference"]: item["quantity"] for item in state["inventory_items"]
        }
        self.assertEqual(15, by_reference[2504])
        self.assertEqual(15, by_reference[11451])
        self.assertEqual(1, by_reference[18783])
        with self.store.connection() as db:
            self.assertEqual(
                200,
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=40",
                    (self.account,),
                ).fetchone()["xp"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts WHERE account_id=%s AND operation=%s",
                    (self.account, f"craft:{started['token']}"),
                ).fetchone()["n"],
            )

    def test_occupation_request_derives_batch_from_exact_component_set(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            13382,
            self.request13382(2),
            station=self.station,
        )
        self.assertEqual(1, started["version"])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT batch_count,request_opcode,mode FROM craft_occupations WHERE token=%s",
                (started["token"],),
            ).fetchone()
        self.assertEqual(
            (2, 13382, 0), (row["batch_count"], row["request_opcode"], row["mode"])
        )
        self.assertEqual(2000, started["duration_ms"])

    def test_recipe_xp_counts_distinct_ingredient_slots_for_each_batch(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            13382,
            self.request13382(2),
            station=self.station,
        )
        self.clock[0] += 2.1
        outcome = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )

        # This fixture has two distinct ingredient slots. Each of its two
        # recipes earns 2 * 100 configured slot XP, regardless of the
        # quantities consumed from those slots.
        self.assertEqual(400, outcome["applied_xp"])
        self.assertIn(
            (12916, struct.pack(">iq", self.profession_id, 400)), outcome["packets"]
        )
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT applied_xp FROM profession_xp_receipts "
                "WHERE account_id=%s AND operation=%s AND profession_id=%s",
                (self.account, f"craft:{started['token']}", self.profession_id),
            ).fetchone()
        self.assertEqual(400, receipt["applied_xp"])

    def test_completed_request_replay_after_reconnect_only_resolves_latest_snapshot(
        self,
    ):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.clock[0] += 1.1
        completed = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )
        self.assertFalse(completed["replay"])
        before = self.store.character(self.account, self.character["id"])
        before_items = sorted(
            (item["uid"], item["reference"], item["quantity"])
            for item in before["inventory_items"]
        )

        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character["id"])
        target = completion_target(
            self.store, self.account, generation, self.character["id"]
        )
        self.assertEqual(started["token"], target["token"])
        self.assertEqual("completed", target["state"])
        replay = complete(
            self.store,
            self.catalog,
            self.account,
            generation,
            self.character["id"],
            target["token"],
            target["version"],
            bytes.fromhex("020008"),
            station=None,
        )
        self.assertTrue(replay["replay"])
        self.assertEqual([], replay["packets"])
        after = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            before_items,
            sorted(
                (item["uid"], item["reference"], item["quantity"])
                for item in after["inventory_items"]
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts "
                    "WHERE account_id=%s AND operation=%s",
                    (self.account, f"craft:{started['token']}"),
                ).fetchone()["n"],
            )

    def test_existing_product_stack_receives_one_net_delta(self):
        current = self.store.character(self.account, self.character["id"])
        product = inventory_items.grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=18783,
            quantity=2,
            container=current["inventory_containers"][0]["uid"],
            slot=22,
            allowed_references=set(STACKS),
        )
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.clock[0] += 1.1
        outcome = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )
        delta = (12470, struct.pack(">qh", product["uid"], 1))
        self.assertEqual(1, outcome["packets"].count(delta))
        current = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            3,
            next(
                item["quantity"]
                for item in current["inventory_items"]
                if item["uid"] == product["uid"]
            ),
        )

    def test_cancel_is_versioned_and_does_not_consume_or_award(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        canceled = cancel(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("030008"),
        )
        self.assertEqual(2, canceled["version"])
        replay = cancel(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("030008"),
        )
        self.assertTrue(replay["replay"])
        self.assertEqual([], replay["packets"])
        with self.assertRaisesRegex(ValueError, "Stale crafting completion"):
            complete(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                started["token"],
                started["version"],
                bytes.fromhex("020008"),
                station=self.station,
            )
        current = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            20,
            sum(
                item["quantity"]
                for item in current["inventory_items"]
                if item["reference"] == 2504
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
            )

    def test_special_mode_and_unknown_criteria_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "occupation mode"):
            begin(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                13382,
                self.request13382(mode=-1),
                station=self.station,
            )
        recipes = dict(self.catalog.recipes)
        secret = dict(recipes[self.recipe_id], raw_clT="IsAchievementActive(1)")
        recipes[self.recipe_id] = secret
        restricted = replace(self.catalog, recipes=recipes)
        with self.assertRaisesRegex(ValueError, "recipe criterion"):
            begin(
                self.store,
                restricted,
                self.account,
                self.generation,
                self.character["id"],
                12231,
                self.request12231(),
                station=self.station,
            )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) AS n FROM craft_occupations").fetchone()[
                    "n"
                ],
            )

    def test_malformed_13382_never_reserves_or_consumes_materials(self):
        valid = self.request13382()
        malformed = (
            valid[:-1],
            valid + b"\x00",
            struct.pack(">qibihih", self.table, self.recipe_id, 0, 2504, 5, 2504, 5),
            struct.pack(">qibihih", self.table, self.recipe_id, 0, 2504, 0, 11451, 5),
            struct.pack(">qibihih", 0, self.recipe_id, 0, 2504, 5, 11451, 5),
        )
        before = self.store.character(self.account, self.character["id"])
        before_items = sorted(
            (item["uid"], item["reference"], item["quantity"])
            for item in before["inventory_items"]
        )
        for body in malformed:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                begin(
                    self.store,
                    self.catalog,
                    self.account,
                    self.generation,
                    self.character["id"],
                    13382,
                    body,
                    station=self.station,
                )
            self.assertIsNone(
                current(self.store, self.account, self.generation, self.character["id"])
            )
        after = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            before_items,
            sorted(
                (item["uid"], item["reference"], item["quantity"])
                for item in after["inventory_items"]
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM craft_occupations WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_station_context_is_checked_again_when_occupation_completes(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.clock[0] += 1.1
        elsewhere = dict(self.station, in_range=False)
        with self.assertRaisesRegex(ValueError, "unreachable crafting station"):
            complete(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                started["token"],
                started["version"],
                bytes.fromhex("020008"),
                station=elsewhere,
            )

    def test_unreachable_or_foreign_station_is_rejected_before_reservation(self):
        for invalid in (
            dict(self.station, in_range=False),
            dict(self.station, map_id=1135),
            dict(self.station, instance_id=9),
            dict(self.station, profession_id=41),
        ):
            with self.subTest(station=invalid):
                with self.assertRaises(ValueError):
                    begin(
                        self.store,
                        self.catalog,
                        self.account,
                        self.generation,
                        self.character["id"],
                        12231,
                        self.request12231(),
                        station=invalid,
                    )
                self.assertIsNone(
                    current(
                        self.store,
                        self.account,
                        self.generation,
                        self.character["id"],
                    )
                )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM craft_occupations WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_active_combat_cannot_reserve_crafting_ingredients(self):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "unavailable during combat"):
            begin(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                12231,
                self.request12231(),
                station=self.station,
            )
        state = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            20,
            sum(
                row["quantity"]
                for row in state["inventory_items"]
                if row["reference"] == 2504
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM craft_occupations WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_xp_failure_rolls_back_consumption_product_and_occupation_for_retry(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.clock[0] += 1.1
        with patch(
            "wakfu_server.profession_store.award",
            side_effect=RuntimeError("receipt failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt failed"):
                complete(
                    self.store,
                    self.catalog,
                    self.account,
                    self.generation,
                    self.character["id"],
                    started["token"],
                    started["version"],
                    bytes.fromhex("020008"),
                    station=self.station,
                )
        state = self.store.character(self.account, self.character["id"])
        quantities = {}
        for item in state["inventory_items"]:
            quantities[item["reference"]] = (
                quantities.get(item["reference"], 0) + item["quantity"]
            )
        self.assertEqual(20, quantities[2504])
        self.assertEqual(20, quantities[11451])
        self.assertNotIn(18783, quantities)
        with self.store.connection() as db:
            occupation = db.execute(
                "SELECT state,version FROM craft_occupations WHERE token=%s",
                (started["token"],),
            ).fetchone()
            self.assertEqual(
                ("active", 1), (occupation["state"], occupation["version"])
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts "
                    "WHERE account_id=%s AND operation=%s",
                    (self.account, f"craft:{started['token']}"),
                ).fetchone()["n"],
            )

        result = complete(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=self.station,
        )
        self.assertFalse(result["replay"])
        self.assertEqual(200, result["applied_xp"])

    def test_replacement_lease_cancels_old_occupation_without_consuming_materials(self):
        started = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        old_generation = self.generation
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.assertIsNone(
            current(self.store, self.account, self.generation, self.character["id"])
        )

        replacement = begin(
            self.store,
            self.catalog,
            self.account,
            self.generation,
            self.character["id"],
            12231,
            self.request12231(),
            station=self.station,
        )
        self.assertNotEqual(started["token"], replacement["token"])
        with self.store.connection() as db:
            states = db.execute(
                "SELECT token,state,terminal_reason FROM craft_occupations "
                "WHERE character_id=%s ORDER BY started_at,token",
                (self.character["id"],),
            ).fetchall()
        old = next(row for row in states if row["token"] == started["token"])
        self.assertEqual(
            ("canceled", "lease_replaced"), (old["state"], old["terminal_reason"])
        )
        with self.assertRaises(ValueError):
            complete(
                self.store,
                self.catalog,
                self.account,
                old_generation,
                self.character["id"],
                started["token"],
                started["version"],
                bytes.fromhex("020008"),
                station=self.station,
            )
        state = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            20,
            sum(
                row["quantity"]
                for row in state["inventory_items"]
                if row["reference"] == 2504
            ),
        )

    def test_offered_ingredient_cannot_be_consumed(self):
        other_account = self.store.register("crafting-other", "local-password")["id"]
        other = self.store.create_character(other_account, "Crafting Other")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        exchange = invite(
            self.store, self.account, self.generation, self.character["id"], other["id"]
        )
        answer(
            self.store,
            other_account,
            other_generation,
            other["id"],
            exchange["id"],
            True,
        )
        offer_item(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            exchange["id"],
            self.items[2504]["uid"],
            5,
        )
        with self.assertRaisesRegex(ValueError, "unprotected crafting ingredients"):
            begin(
                self.store,
                self.catalog,
                self.account,
                self.generation,
                self.character["id"],
                12231,
                self.request12231(),
                station=self.station,
            )


if __name__ == "__main__":
    unittest.main()
