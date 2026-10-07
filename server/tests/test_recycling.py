from concurrent.futures import ThreadPoolExecutor
import json
import threading
import uuid
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb

from wakfu_server import inventory_items, player_exchanges, recycling, recycling_wire
from wakfu_server.wire import proto_field


class RecyclingAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 2_000_000_000.0
        self.store.clock = lambda: self.now

    def player(self, label="recycler"):
        account = self.store.register(
            "r" + uuid.uuid4().hex[:12], "recycling-test-password"
        )["id"]
        suffix = (
            uuid.uuid4()
            .hex[:8]
            .translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
        )
        character = self.store.create_character(account, "Recycle" + suffix)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        return {"account": account, "generation": generation, "character": character}

    def add_item(self, owner, reference, quantity=1, slot=0, kind=0):
        container = self.fetchone(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=%s",
            (owner["character"]["id"], kind),
        )["uid"]
        return inventory_items.grant(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            reference=reference,
            quantity=quantity,
            container=container,
            slot=slot,
            allowed_references={reference},
        )

    def fetchone(self, sql, params=()):
        with self.store.connection() as db:
            return db.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self.store.connection() as db:
            return db.execute(sql, params).fetchall()

    def request(self, owner, *uids, rng=None, fight=None):
        _, body = recycling_wire.request(list(uids))
        return recycling.recycle(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            body,
            rng=rng,
            fight=fight,
        )

    def owned_rows(self, owner):
        return self.fetchall(
            "SELECT uid,reference,quantity,container,slot FROM inventory_items "
            "WHERE character_id=%s ORDER BY uid",
            (owner["character"]["id"],),
        )

    def test_fixed_native_products_are_granted_with_result_and_replay_is_idempotent(
        self,
    ):
        owner = self.player()
        powder_source = self.add_item(owner, 27083, quantity=3, slot=0)
        shard_source = self.add_item(owner, 16163, quantity=2, slot=1)
        body = recycling_wire.request([powder_source["uid"], shard_source["uid"]])[1]
        forbidden_rng_calls = []

        first = recycling.recycle(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            body,
            rng=lambda: forbidden_rng_calls.append(True),
        )

        self.assertTrue(first["applied"])
        self.assertEqual([], forbidden_rng_calls)
        result_packet = first["packets"][-1]
        # Native preview/result reports consumed stack units (3+2), not UIDs.
        self.assertEqual((12890, bytes.fromhex("00000007 00000005")), result_packet)
        self.assertEqual({"27083": 4, "27093": 3}, first["receipt"]["products"])
        self.assertEqual({}, first["receipt"]["rounding_draws"])
        rows = self.owned_rows(owner)
        products = {(row["reference"], row["quantity"]) for row in rows}
        self.assertEqual({(27083, 4), (27093, 3)}, products)
        self.assertNotIn(powder_source["uid"], {row["uid"] for row in rows})
        self.assertNotIn(shard_source["uid"], {row["uid"] for row in rows})

        reopened = self.reopen()
        reopened.clock = self.store.clock
        replay_body = recycling_wire.request(
            [shard_source["uid"], powder_source["uid"]]
        )[1]
        replay = recycling.recycle(
            reopened,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            replay_body,
            rng=lambda: self.fail("A retry must not draw again"),
        )
        self.assertFalse(replay["applied"])
        self.assertEqual([result_packet], replay["packets"])
        self.assertEqual(rows, self.owned_rows(owner))
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM item_recycling_receipts WHERE character_id=%s",
                (owner["character"]["id"],),
            )["n"],
        )

    def test_stochastic_rounding_uses_native_fraction_and_persists_the_draw(self):
        owner = self.player()
        item = self.add_item(owner, 1718)
        first = self.request(owner, item["uid"], rng=lambda: 0.003)
        self.assertEqual({"27093": 1}, first["receipt"]["products"])
        self.assertEqual(0.003, first["receipt"]["rounding_draws"]["27093"])
        product = next(
            row for row in self.owned_rows(owner) if row["reference"] == 27093
        )
        self.assertEqual(1, product["quantity"])

        second_owner = self.player()
        second_item = self.add_item(second_owner, 1718)
        second = self.request(second_owner, second_item["uid"], rng=lambda: 0.005)
        self.assertEqual({"27093": 0}, second["receipt"]["products"])
        self.assertEqual(0.005, second["receipt"]["rounding_draws"]["27093"])
        self.assertEqual(
            [],
            [row for row in self.owned_rows(second_owner) if row["reference"] == 27093],
        )

    def test_reference_2021_preview_fraction_can_legitimately_recover_zero(self):
        # The native catalog marks ref 2021 as SHARD -> 27083, with low factor
        # 0.022613581, variable yield, and template gjv=true. Under this server's
        # explicit local stochastic-round policy, the native float32 factor is
        # about 0.0271: a one-item recycle can consume the source and yield zero.
        definition = recycling.CATALOG["2021"]
        self.assertEqual("SHARD", definition["recycling_kind"])
        self.assertEqual(27083, definition["recycling_product_reference"])
        self.assertAlmostEqual(
            0.0271363, recycling._factor(definition, 1, None), places=7
        )

        success_owner = self.player("2021-low-draw")
        success_item = self.add_item(success_owner, 2021)
        success = self.request(success_owner, success_item["uid"], rng=lambda: 0.02)
        self.assertEqual({"27083": 1}, success["receipt"]["products"])

        zero_owner = self.player("2021-high-draw")
        zero_item = self.add_item(zero_owner, 2021)
        zero = self.request(zero_owner, zero_item["uid"], rng=lambda: 0.03)
        self.assertEqual({"27083": 0}, zero["receipt"]["products"])
        self.assertEqual(
            (0, 1),
            (
                zero["receipt"]["recovered_resources"],
                zero["receipt"]["destroyed_items"],
            ),
        )
        self.assertNotIn(
            zero_item["uid"], {row["uid"] for row in self.owned_rows(zero_owner)}
        )

    def test_same_product_yields_are_aggregated_before_one_local_rounding_draw(self):
        owner = self.player()
        first_item = self.add_item(owner, 1718, slot=0)
        second_item = self.add_item(owner, 1718, slot=1)
        draws = []
        result = self.request(
            owner,
            first_item["uid"],
            second_item["uid"],
            rng=lambda: draws.append(0.005) or 0.005,
        )
        self.assertEqual([0.005], draws)
        self.assertEqual({"27093": 1}, result["receipt"]["products"])
        self.assertEqual({"27093": 0.005}, result["receipt"]["rounding_draws"])
        self.assertEqual(2, result["receipt"]["destroyed_items"])
        self.assertEqual(1, result["receipt"]["recovered_resources"])

    def test_stochastic_round_pure_policy_boundaries_and_strict_inputs(self):
        self.assertEqual(2, recycling.stochastic_round(2.0, 0.999))
        self.assertEqual(3, recycling.stochastic_round(2.25, 0.249))
        self.assertEqual(2, recycling.stochastic_round(2.25, 0.25))
        for value, draw in (
            (True, 0.5),
            (-0.1, 0.5),
            (float("nan"), 0.5),
            (1.5, True),
            (1.5, float("inf")),
            (1.5, 1.0),
        ):
            with self.subTest(value=value, draw=draw), self.assertRaises(ValueError):
                recycling.stochastic_round(value, draw)

    def test_variable_yield_uses_native_template_and_empty_socket_map_defaults(self):
        owner = self.player()
        unknown = self.add_item(owner, 12)
        draws = []
        result = self.request(
            owner, unknown["uid"], rng=lambda: draws.append(0.08) or 0.08
        )
        self.assertEqual([0.08], draws)
        self.assertEqual({"27083": 1}, result["receipt"]["products"])
        self.assertEqual({"27083": 0.08}, result["receipt"]["rounding_draws"])

        socketed_owner = self.player()
        socketed = self.add_item(socketed_owner, 12)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,FALSE,TRUE)",
                (socketed["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "Socketed item"):
            self.request(socketed_owner, socketed["uid"], rng=lambda: 0.1)

    def test_recyclable_equipment_templates_without_emitted_option_map_are_allowed(
        self,
    ):
        # All three references have native equipment slots; current item_proto
        # emits no fpI installed-option map, so the client's socket test is false.
        for reference in (12, 17605, 20385):
            with self.subTest(reference=reference):
                row = recycling.CATALOG[str(reference)]
                self.assertTrue(row["equipment_slots"])
                owner = self.player()
                item = self.add_item(owner, reference)
                result = self.request(owner, item["uid"], rng=lambda: 0.0)
                self.assertTrue(result["applied"])

    def test_persisted_socket_occupancy_still_blocks_before_consumption(self):
        owner = self.player()
        item = self.add_item(owner, 17605)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,NULL,TRUE)",
                (item["uid"],),
            )
        draws = []
        with self.assertRaisesRegex(ValueError, "Socketed item"):
            self.request(owner, item["uid"], rng=lambda: draws.append(0.1))
        self.assertEqual([], draws)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["quantity"],
        )

    def test_template_without_bonus_option_uses_native_gjv_false_default(self):
        owner = self.player()
        item = self.add_item(owner, 3920)
        row = recycling.CATALOG["3920"]
        self.assertTrue(row["variable_yield"])
        self.assertFalse(row["template_gjv"])
        result = self.request(owner, item["uid"], rng=lambda: 0.033)
        self.assertEqual({"27083": 0}, result["receipt"]["products"])
        self.assertEqual({"27083": 0.033}, result["receipt"]["rounding_draws"])

    def test_socketed_item_does_not_consume_valid_items_in_same_selection(self):
        owner = self.player()
        fixed = self.add_item(owner, 27083, quantity=2, slot=0)
        variable = self.add_item(owner, 12, slot=1)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,NULL,TRUE)",
                (variable["uid"],),
            )
        draws = []
        with self.assertRaisesRegex(ValueError, "Socketed item"):
            self.request(
                owner, fixed["uid"], variable["uid"], rng=lambda: draws.append(0.1)
            )
        self.assertEqual([], draws)
        self.assertEqual(
            {fixed["uid"], variable["uid"]},
            {row["uid"] for row in self.owned_rows(owner)},
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM item_recycling_receipts WHERE character_id=%s",
                (owner["character"]["id"],),
            )["n"],
        )

    def test_native_false_delete_achievement_and_instance_criteria_fail_closed(self):
        owner = self.player()
        literal_false = self.add_item(owner, 13598)
        with self.assertRaisesRegex(ValueError, "not recyclable|DELETE"):
            self.request(owner, literal_false["uid"], rng=lambda: 0.1)
        achievement = self.add_item(owner, 17496, slot=1)
        with self.assertRaisesRegex(ValueError, "Unsupported native recycling DELETE"):
            self.request(owner, achievement["uid"], rng=lambda: 0.1)

        def set_instance(target, instance_id):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET instance_id=%s WHERE id=%s",
                    (instance_id, target["character"]["id"]),
                )

        # Native DELETE means an item may be deleted when the predicate is
        # true: != 702 permits every other instance and forbids instance 702.
        allowed = self.player()
        set_instance(allowed, 701)
        permitted = self.add_item(allowed, 17605, slot=0)
        self.assertTrue(
            self.request(allowed, permitted["uid"], rng=lambda: 0.0)["applied"]
        )

        forbidden = self.player()
        set_instance(forbidden, 702)
        blocked = self.add_item(forbidden, 17605, slot=0)
        with self.assertRaisesRegex(ValueError, "DELETE criterion"):
            self.request(forbidden, blocked["uid"], rng=lambda: 0.0)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE uid=%s",
                (blocked["uid"],),
            )["n"],
        )

        # The second native predicate allows every instance except 1076/1073.
        allowed_other = self.player()
        stack = self.add_item(allowed_other, 20385, slot=0)
        self.assertTrue(
            self.request(allowed_other, stack["uid"], rng=lambda: 0.0)["applied"]
        )

        for instance_id in (1076, 1073):
            with self.subTest(instance_id=instance_id):
                restricted_owner = self.player()
                set_instance(restricted_owner, instance_id)
                restricted = self.add_item(restricted_owner, 20385, slot=0)
                with self.assertRaisesRegex(ValueError, "DELETE criterion"):
                    self.request(restricted_owner, restricted["uid"], rng=lambda: 0.0)
                self.assertEqual(
                    1,
                    self.fetchone(
                        "SELECT count(*) AS n FROM inventory_items WHERE uid=%s",
                        (restricted["uid"],),
                    )["n"],
                )

    def test_unrepresented_identification_override_fails_before_rng_or_consumption(
        self,
    ):
        owner = self.player()
        item = self.add_item(owner, 12)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,FALSE,FALSE)",
                (item["uid"],),
            )
        draws = []
        with self.assertRaisesRegex(ValueError, "conflicts with emitted ProtoItem"):
            self.request(owner, item["uid"], rng=lambda: draws.append(0.1))
        self.assertEqual([], draws)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["quantity"],
        )

    def test_policy_disabled_references_and_binding_guards(self):
        owner = self.player()
        disabled = self.add_item(owner, 16163)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='recycling_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "rounding_mode": "stochastic_round",
                            "aggregation_mode": "sum_per_product_then_round",
                            "disabled_item_refs": [16163],
                        }
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "not recyclable"):
            self.request(owner, disabled["uid"], rng=lambda: 0.1)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (disabled["uid"],)
            )["quantity"],
        )

        bound_template = self.add_item(owner, 2603, slot=1)
        with self.assertRaisesRegex(ValueError, "bound item"):
            self.request(owner, bound_template["uid"], rng=lambda: 0.1)

        unbound = self.add_item(owner, 16163, slot=2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='recycling_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "rounding_mode": "stochastic_round",
                            "aggregation_mode": "sum_per_product_then_round",
                            "disabled_item_refs": [],
                        }
                    ),
                ),
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,TRUE,%s)",
                (unbound["uid"], 16163),
            )
        with self.assertRaisesRegex(ValueError, "Bound item"):
            self.request(owner, unbound["uid"], rng=lambda: 0.1)

    def test_equipment_in_any_build_and_in_fight_are_read_only_guards(self):
        owner = self.player()
        item = self.add_item(owner, 16163)
        equipment = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, 1))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,1,%s,%s,%s,%s)",
                (owner["character"]["id"], b"", equipment, b"", b""),
            )
        with self.assertRaisesRegex(ValueError, "every build"):
            self.request(owner, item["uid"], rng=lambda: 0.1)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["quantity"],
        )

        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_builds WHERE character_id=%s",
                (owner["character"]["id"],),
            )
        with self.assertRaisesRegex(ValueError, "combat"):
            self.request(owner, item["uid"], fight=object(), rng=lambda: 0.1)
        from wakfu_server.combat import fight_store

        fight_store.create(
            self.store, owner["account"], owner["generation"], owner["character"]["id"]
        )
        with self.assertRaisesRegex(ValueError, "combat"):
            self.request(owner, item["uid"], rng=lambda: 0.1)
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["quantity"],
        )

    def test_exchange_offered_item_and_foreign_selection_are_atomic_rejections(self):
        owner = self.player()
        peer = self.player("peer")
        item = self.add_item(owner, 16163)
        other = self.add_item(peer, 16163)
        exchange = player_exchanges.invite(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            peer["character"]["id"],
        )
        exchange = player_exchanges.answer(
            self.store,
            peer["account"],
            peer["generation"],
            peer["character"]["id"],
            exchange["id"],
            True,
        )
        player_exchanges.offer_item(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        with self.assertRaisesRegex(ValueError, "Exchange-offered"):
            self.request(owner, item["uid"], rng=lambda: 0.1)
        with self.assertRaisesRegex(ValueError, "foreign or missing"):
            self.request(owner, other["uid"], rng=lambda: 0.1)
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                ([item["uid"], other["uid"]],),
            )["n"],
        )

    def test_product_grants_never_merge_into_equipped_or_exchange_offered_uids(self):
        equipped_owner = self.player()
        equipped_product = self.add_item(equipped_owner, 27093, slot=0)
        source = self.add_item(equipped_owner, 27083, slot=0, kind=1)
        equipment = proto_field(
            10, proto_field(8, equipped_product["uid"]) + proto_field(16, 1)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,1,%s,%s,%s,%s)",
                (equipped_owner["character"]["id"], b"", equipment, b"", b""),
            )
        result = self.request(
            equipped_owner,
            source["uid"],
            rng=lambda: self.fail("Fixed yield draws none"),
        )
        self.assertTrue(result["applied"])
        equipped_row = self.fetchone(
            "SELECT quantity FROM inventory_items WHERE uid=%s",
            (equipped_product["uid"],),
        )
        self.assertEqual(1, equipped_row["quantity"])
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=27093",
                (equipped_owner["character"]["id"],),
            )["n"],
        )

        offered_owner = self.player()
        peer = self.player()
        offered_product = self.add_item(offered_owner, 27093, slot=0)
        source = self.add_item(offered_owner, 27083, slot=0, kind=1)
        exchange = player_exchanges.invite(
            self.store,
            offered_owner["account"],
            offered_owner["generation"],
            offered_owner["character"]["id"],
            peer["character"]["id"],
        )
        exchange = player_exchanges.answer(
            self.store,
            peer["account"],
            peer["generation"],
            peer["character"]["id"],
            exchange["id"],
            True,
        )
        player_exchanges.offer_item(
            self.store,
            offered_owner["account"],
            offered_owner["generation"],
            offered_owner["character"]["id"],
            exchange["id"],
            offered_product["uid"],
            1,
        )
        result = self.request(
            offered_owner,
            source["uid"],
            rng=lambda: self.fail("Fixed yield draws none"),
        )
        self.assertTrue(result["applied"])
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s",
                (offered_product["uid"],),
            )["quantity"],
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=27093",
                (offered_owner["character"]["id"],),
            )["n"],
        )

    def test_product_full_bag_failure_rolls_back_source_and_receipt(self):
        owner = self.player()
        source = self.add_item(owner, 27083, slot=0, kind=1)
        for slot in range(30):
            self.add_item(owner, 30000, slot=slot, kind=0)
        with self.assertRaisesRegex(ValueError, "cannot hold recycling products"):
            self.request(
                owner, source["uid"], rng=lambda: self.fail("Fixed yield draws none")
            )
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (source["uid"],)
            )["quantity"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM item_recycling_receipts WHERE character_id=%s",
                (owner["character"]["id"],),
            )["n"],
        )

    def test_receipt_failure_rolls_back_item_deletion_product_and_retry_is_possible(
        self,
    ):
        owner = self.player()
        item = self.add_item(owner, 27083, quantity=2)
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_recycling_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected recycling receipt failure'; END $$"""
            )
            db.execute(
                """CREATE TRIGGER injected_recycling_receipt BEFORE INSERT
                ON item_recycling_receipts FOR EACH ROW EXECUTE FUNCTION reject_recycling_receipt()"""
            )
        with self.assertRaisesRegex(Exception, "injected recycling receipt failure"):
            self.request(
                owner, item["uid"], rng=lambda: self.fail("Fixed yield draws none")
            )
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=27093",
                (owner["character"]["id"],),
            )["n"],
        )
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER injected_recycling_receipt ON item_recycling_receipts"
            )
            db.execute("DROP FUNCTION reject_recycling_receipt()")
        retry = self.request(
            owner, item["uid"], rng=lambda: self.fail("Fixed yield draws none")
        )
        self.assertTrue(retry["applied"])
        self.assertEqual({"27093": 2}, retry["receipt"]["products"])

    def test_concurrent_same_request_applies_once_and_draws_once(self):
        owner = self.player()
        item = self.add_item(owner, 1718)
        body = recycling_wire.request([item["uid"]])[1]
        count = 0
        guard = threading.Lock()

        def draw():
            nonlocal count
            with guard:
                count += 1
            return 0.003

        def apply():
            return recycling.recycle(
                self.store,
                owner["account"],
                owner["generation"],
                owner["character"]["id"],
                body,
                rng=draw,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(1, count)
        self.assertEqual([False, True], sorted(result["applied"] for result in results))
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM item_recycling_receipts WHERE character_id=%s",
                (owner["character"]["id"],),
            )["n"],
        )
        self.assertEqual(
            1,
            sum(
                row["quantity"]
                for row in self.owned_rows(owner)
                if row["reference"] == 27093
            ),
        )

    def test_policy_and_stale_lease_reject_without_item_mutation(self):
        owner = self.player()
        item = self.add_item(owner, 27083)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='recycling_policy'",
                (
                    Jsonb(
                        {
                            "version": True,
                            "rounding_mode": "stochastic_round",
                            "aggregation_mode": "sum_per_product_then_round",
                            "disabled_item_refs": [],
                        }
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            self.request(
                owner, item["uid"], rng=lambda: self.fail("Invalid policy draws none")
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='recycling_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "rounding_mode": "stochastic_round",
                            "aggregation_mode": "sum_per_product_then_round",
                            "disabled_item_refs": [],
                        }
                    ),
                ),
            )
        self.store.begin_session(owner["account"], ttl=10_000)
        with self.assertRaisesRegex(ValueError, "Sesión|session|lease"):
            self.request(
                owner, item["uid"], rng=lambda: self.fail("Stale lease draws none")
            )
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["quantity"],
        )


if __name__ == "__main__":
    unittest.main()
