"""Original positional simple-item requests and real template USE conditions."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import simple_item_actions as actions
from wakfu_server.inventory_items import grant
from wakfu_server.progression import level_xp


class SimpleNativeContextWireTests(unittest.TestCase):
    def test_all_633_original_contexts_select_their_actual_native_request_grammar(self):
        contexts = actions.native_use_contexts()
        self.assertEqual(len(contexts), 633)
        for context in contexts.values():
            header = struct.pack(">iq", context["action_id"], 123)
            body = header + b"\0" if context["flag_cqc"] else header
            self.assertEqual(actions.action_class(body), context["native_class"])

    def test_global_maximum_uses_native_configuration_instead_of_an_accounts_highest_character(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.combat_system_conditions import CONFIG_SOURCE

        state = dict(source=CONFIG_SOURCE, overrides={"player.level.cap": 106})
        with patch(
            "wakfu_server.combat_system_conditions.fresh_system_configuration",
            return_value=state,
        ):
            self.assertTrue(
                actions._criterion(
                    None,
                    None,
                    99,
                    dict(level=105),
                    "GetRealLevel() < GetPlayerMaxLevel()",
                    None,
                )
            )
            self.assertFalse(
                actions._criterion(
                    None,
                    None,
                    99,
                    dict(level=106),
                    "GetRealLevel() < GetPlayerMaxLevel()",
                    None,
                )
            )

    def test_two_original_positional_fragment_actions_accept_only_exact_optional_cell_grammar(
        self,
    ):
        for action in (3581, 3614):
            header = struct.pack(">iq", action, 123)
            self.assertEqual(actions.action_class(header + b"\0"), "bHS")
            self.assertEqual(
                actions.action_class(header + b"\1" + struct.pack(">iih", -10, 20, -3)),
                "bHS",
            )
            for body in (
                header,
                header + b"\2",
                header + b"\0" + bytes(10),
                header + b"\1",
                header + b"\1" + bytes(11),
            ):
                with self.assertRaises(ValueError):
                    actions.action_class(body)

    def test_zero_count_policy_uses_explicit_flag_and_keeps_all_positive_merges_unchanged(
        self,
    ):
        import json
        from pathlib import Path

        rows = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-simple-item-actions.json"
            ).read_text()
        )["actions"]
        merges = [row for row in rows if row["native_class"] == "bHS"]
        self.assertEqual(len(merges), 106)
        positive = [row for row in merges if row["required_quantity"] > 0]
        self.assertEqual(len(positive), 105)
        for row in positive:
            self.assertIs(
                actions.normalize_source_consumption(
                    row,
                    actions.native_use_contexts()[row["action_id"]],
                    output_present=True,
                ),
                row,
            )
        zero = next(row for row in merges if row["required_quantity"] == 0)
        context = actions.native_use_contexts()[zero["action_id"]]
        normalized = actions.normalize_source_consumption(
            zero, context, output_present=True
        )
        self.assertEqual(
            (normalized["required_quantity"], normalized["available"]), (1, True)
        )
        self.assertEqual((zero["required_quantity"], zero["available"]), (0, False))
        for changed, present in (
            (None, True),
            (dict(context, consume_flag_cqa=False), True),
            (dict(context, consume_flag_cqa=1), True),
            (context, False),
        ):
            self.assertIs(
                actions.normalize_source_consumption(
                    zero, changed, output_present=present
                ),
                zero,
            )


class SimpleNativeContextPostgresTests(PostgresCase):
    def fixture(self):
        account = self.store.register("native-fragment-owner", "local-password")["id"]
        actor = self.store.create_character(account, "Native Fragment Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        return account, generation, actor

    def level(self, actor, value):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s", (value, actor["id"])
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(value), actor["id"]),
            )

    def give(self, account, generation, actor, reference, quantity=1, slot=0):
        return grant(
            self.store,
            account,
            generation,
            actor["id"],
            reference=reference,
            quantity=quantity,
            container=actor["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def test_real_fragment_level_gate_and_both_native_requests_preserve_position_and_quest_output(
        self,
    ):
        account, generation, actor = self.fixture()
        source = self.give(account, generation, actor, 15985, 2)
        body = struct.pack(">iqB", 3614, source["uid"], 0)
        self.level(actor, 104)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM character_quest_items WHERE character_id=%s AND reference=15986",
                    (actor["id"],),
                ).fetchone()
            )
        self.level(actor, 105)
        for count, request in enumerate(
            (
                body,
                struct.pack(">iqBiih", 3614, source["uid"], 1, -1000000, 1000000, -300),
            ),
            1,
        ):
            result = actions.use(
                self.store, account, generation, actor["id"], request, in_fight=False
            )
            self.assertEqual(result["consumed"], 1)
            self.assertEqual(
                next(
                    row["quantity"]
                    for row in result["character"]["quest_items"]
                    if row["reference"] == 15986
                ),
                count,
            )
            self.assertEqual(
                tuple(
                    result["character"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                tuple(actor[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            )
        restored = self.reopen().character(account, actor["id"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in restored["quest_items"]
                if row["reference"] == 15986
            ),
            2,
        )
        self.assertFalse(
            any(row["uid"] == source["uid"] for row in restored["inventory_items"])
        )

    def test_zero_count_consuming_fragment_obeys_real_level_and_once_only_owned_delivery(
        self,
    ):
        account, generation, actor = self.fixture()
        source = self.give(account, generation, actor, 15931)
        body = struct.pack(">iqB", 3581, source["uid"], 0)
        self.level(actor, 99)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM character_quest_items WHERE character_id=%s AND reference=15934",
                    (actor["id"],),
                ).fetchone()
            )
        self.level(actor, 100)
        result = actions.use(
            self.store, account, generation, actor["id"], body, in_fight=False
        )
        self.assertEqual((result["native_class"], result["consumed"]), ("bHS", 1))
        self.assertEqual(
            next(
                row["quantity"]
                for row in result["character"]["quest_items"]
                if row["reference"] == 15934
            ),
            1,
        )
        self.assertFalse(
            any(
                row["uid"] == source["uid"]
                for row in result["character"]["inventory_items"]
            )
        )
        with self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
        reopened = self.reopen().character(account, actor["id"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in reopened["quest_items"]
                if row["reference"] == 15934
            ),
            1,
        )
        self.assertEqual(
            tuple(reopened[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            tuple(actor[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )

    def test_zero_count_fragment_full_native_quest_capacity_rolls_back_consumption(
        self,
    ):
        from wakfu_server.quest_inventory import MAXIMUMS

        account, generation, actor = self.fixture()
        self.level(actor, 100)
        source = self.give(account, generation, actor, 15931)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,15934,%s)",
                (actor["id"], MAXIMUMS[15934]),
            )
        # The original optional position changes no world position or capacity.
        body = struct.pack(">iqBiih", 3581, source["uid"], 1, -1000000, 1000000, -300)
        with self.assertRaisesRegex(ValueError, "capacity"):
            actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=15934",
                    (actor["id"],),
                ).fetchone()["quantity"],
                MAXIMUMS[15934],
            )

    def test_seven_real_level_xp_scrolls_reject_before_their_native_threshold_and_apply_at_it(
        self,
    ):
        account, generation, actor = self.fixture()
        plans = [
            row
            for row in actions.native_use_contexts().values()
            if row["native_class"] == "bHK"
            and "GetRealLevel() >=" in row["use_criterion"]
        ]
        self.assertEqual(len(plans), 7)
        for slot, plan in enumerate(plans):
            threshold = int(plan["use_criterion"].rsplit(">=", 1)[1].strip())
            source = self.give(account, generation, actor, plan["item_ref"], 2, slot)
            body = struct.pack(">iq", plan["action_id"], source["uid"])
            self.level(actor, threshold - 1)
            with self.assertRaisesRegex(ValueError, "condiciones"):
                actions.use(
                    self.store, account, generation, actor["id"], body, in_fight=False
                )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT quantity FROM inventory_items WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()["quantity"],
                    2,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT xp FROM character_progression WHERE character_id=%s",
                        (actor["id"],),
                    ).fetchone()["xp"],
                    level_xp(threshold - 1),
                )
            self.level(actor, threshold)
            outcome = actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
            self.assertEqual(outcome["consumed"], 1)
            self.assertGreater(outcome["character"]["xp"], level_xp(threshold))

    def test_maximum_level_xp_scroll_uses_server_cap_and_never_consumes_at_cap(self):
        from types import SimpleNamespace
        from wakfu_server.combat_max_level_conditions import player_max_level
        from wakfu_server.combat_system_conditions import fresh_system_configuration

        maximum = player_max_level(
            SimpleNamespace(native_system_configuration=fresh_system_configuration())
        )
        account, generation, actor = self.fixture()
        source = self.give(account, generation, actor, 22457, 2)
        plan = next(
            row
            for row in actions.native_use_contexts().values()
            if row["item_ref"] == 22457
        )
        body = struct.pack(">iq", plan["action_id"], source["uid"])
        self.level(actor, maximum - 1)
        outcome = actions.use(
            self.store, account, generation, actor["id"], body, in_fight=False
        )
        self.assertEqual(outcome["consumed"], 1)
        self.assertGreater(outcome["character"]["xp"], level_xp(maximum - 1))
        self.level(actor, maximum)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (actor["id"],),
                ).fetchone()["xp"],
                level_xp(maximum),
            )

    def test_reusable_admin_hammer_keeps_exact_source_uid_across_repeated_use_and_reconnect(
        self,
    ):
        account, generation, actor = self.fixture()
        source = self.give(account, generation, actor, 30804)
        body = struct.pack(">iq", 13380, source["uid"])
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
        for count in range(1, 4):
            if count == 3:
                self.store = self.reopen()
                generation = self.store.begin_session(account)
                self.store.select_character(account, generation, actor["id"])
            result = actions.use(
                self.store, account, generation, actor["id"], body, in_fight=False
            )
            self.assertEqual(result["consumed"], 0)
            self.assertFalse(
                any(
                    opcode == 12470
                    and struct.unpack_from(">q", payload)[0] == source["uid"]
                    for opcode, payload in result["packets"]
                )
            )
            inventory = result["character"]["inventory_items"]
            self.assertEqual(
                next(
                    row["quantity"] for row in inventory if row["uid"] == source["uid"]
                ),
                1,
            )
            self.assertEqual(
                sum(row["quantity"] for row in inventory if row["reference"] == 27083),
                count * 9999,
            )

    def test_reusable_hammer_capacity_failure_is_atomic_and_does_not_free_its_source_slot(
        self,
    ):
        from wakfu_server.combat_drop_delivery import _container_can_hold

        account, generation, actor = self.fixture()
        source = self.give(account, generation, actor, 30804)
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
            containers = db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s",
                (actor["id"],),
            ).fetchall()
            for bag in containers:
                if not _container_can_hold(bag, actor["id"]):
                    continue
                for slot in range(bag["capacity"]):
                    if bag["uid"] == source["container"] and slot == source["slot"]:
                        continue
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,1,1,%s,%s)",
                        (actor["id"], bag["uid"], slot),
                    )
        before = self.store.character(account, actor["id"])["inventory_items"]
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                actor["id"],
                struct.pack(">iq", 13380, source["uid"]),
                in_fight=False,
            )
        self.assertEqual(
            self.reopen().character(account, actor["id"])["inventory_items"], before
        )
