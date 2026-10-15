import struct
import unittest
from datetime import timedelta
from unittest.mock import patch
from wakfu_server.inventory_elements import create, masks, bonuses as selected_bonuses
from wakfu_server.inventory_items import grant, item_proto, item_form
from wakfu_server.equipment_stats import bonuses, CATALOG, _flat
from postgres_case import PostgresCase
from wakfu_server.wire import proto_field, proto_fields
from wakfu_server.element_selection import (
    decode_request,
    encode_result,
    select as select_elements,
)


class InventoryElementsTests(PostgresCase):
    def test_low_level_element_identification_splits_one_and_preserves_failed_remainder(
        self,
    ):
        store = self.store
        account = store.register("low-element", "local-test-password")["id"]
        char = store.create_character(account, "Low Element")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2869,
            quantity=1,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2869},
        )
        with store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=3 WHERE uid=%s", (item["uid"],)
            )
        result = select_elements(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qBB", item["uid"], 26, 0),
        )
        self.assertEqual((result["status"], result["applied"]), (0, True))
        self.assertEqual(struct.unpack_from(">i", result["packet"][1])[0], 0)
        owned = store.character(account, char["id"])["inventory_items"]
        self.assertEqual(sum(row["quantity"] for row in owned), 3)
        original = next(row for row in owned if row["uid"] == item["uid"])
        remainder = next(row for row in owned if row["uid"] != item["uid"])
        self.assertEqual(original["quantity"], 1)
        self.assertEqual(masks(original), (26, 0))
        self.assertEqual(remainder["quantity"], 2)
        with store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','7') WHERE name='socket_identification_policy'"
            )
        with self.assertRaisesRegex(ValueError, "Insufficient local-policy kamas"):
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", remainder["uid"], 26, 0),
            )
        reopened = next(
            row
            for row in self.reopen().character(account, char["id"])["inventory_items"]
            if row["uid"] == remainder["uid"]
        )
        self.assertEqual(masks(reopened), (0, 0))
        self.assertEqual(reopened["quantity"], 2)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_item_shards"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_element_selection_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"],
                0,
            )

    def test_native_element_selection_codec_is_uid_scoped_and_strict(self):
        body = struct.pack(">qBB", 12345, 22, 8)
        self.assertEqual(
            decode_request(body),
            dict(uid=12345, damage_elements=22, resistance_elements=8),
        )
        self.assertEqual(
            encode_result(12345, 22, 8),
            (
                13766,
                struct.pack(">iqBI", 0, 12345, 0, 2)
                + bytes((22, 8))
                + struct.pack(">I", 0),
            ),
        )
        for bad in (
            body[:-1],
            struct.pack(">qBB", 12345, 1, 0),
            struct.pack(">qBB", 12345, 32, 0),
            struct.pack(">qBB", 0, 22, 8),
        ):
            with self.assertRaises(ValueError):
                decode_request(bad)

    def test_selection_commits_once_for_owned_uid_and_retry_returns_same_result(self):
        store = self.store
        account = store.register("element-choice", "local-test-password")["id"]
        char = store.create_character(account, "Element Choice")
        with store.connection() as db:
            db.execute("UPDATE characters SET level=100 WHERE id=%s", (char["id"],))
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2869,
            quantity=1,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2869},
        )
        # New items remain pending until an explicit native choice.
        with store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=20 WHERE account_id=%s", (account,)
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','7') WHERE name='socket_identification_policy'"
            )
        body = struct.pack(">qBB", item["uid"], 26, 0)
        applied = select_elements(store, account, generation, char["id"], body)
        self.assertTrue(applied["applied"])
        self.assertEqual(
            (applied["damage_elements"], applied["resistance_elements"]), (26, 0)
        )
        self.assertEqual(applied["packet"][0], 13766)
        self.assertIsNotNone(applied["shard_state"])
        self.assertGreater(len(applied["packet"][1]), 23)
        self.assertEqual((applied["cost_kamas"], applied["wallet_kamas"]), (7, 13))
        reopened = self.reopen().character(account, char["id"])["inventory_items"][0]
        self.assertEqual(
            (reopened["damage_elements"], reopened["resistance_elements"]), (26, 0)
        )
        from wakfu_server.inventory_items import equipment_inventory

        # Reconnect reconstructs a separate native hR equipment-item registry.
        # It must carry the same chosen masks as the physical inventory item.
        refreshed = self.reopen().character(account, char["id"])
        equipment_packet = equipment_inventory(refreshed)
        self.assertEqual(equipment_packet[0], 13078)
        native_items = [
            dict(proto_fields(value))
            for tag, value in proto_fields(equipment_packet[1][13:])
            if tag == 10
        ]
        native_item = next(row for row in native_items if row[8] == item["uid"])
        self.assertEqual(dict(proto_fields(native_item[450])), {8: 26, 16: 0})
        retry = select_elements(store, account, generation, char["id"], body)
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["packet"], applied["packet"])
        self.assertEqual(retry["shard_state"], applied["shard_state"])
        self.assertEqual((retry["cost_kamas"], retry["wallet_kamas"]), (0, 13))
        changed = select_elements(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qBB", item["uid"], 22, 0),
        )
        self.assertTrue(changed["applied"])
        self.assertEqual(changed["damage_elements"], 22)
        self.assertEqual(changed["shard_state"], applied["shard_state"])
        self.assertEqual((changed["cost_kamas"], changed["wallet_kamas"]), (0, 13))
        self.assertFalse(
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", item["uid"], 22, 0),
            )["applied"]
        )
        stacked = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2869,
            quantity=2,
            container=char["inventory_containers"][0]["uid"],
            slot=1,
            allowed_references={2869},
        )
        selected_stack = select_elements(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qBB", stacked["uid"], 22, 0),
        )
        self.assertTrue(selected_stack["applied"])
        with store.connection() as db:
            rows = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s "
                "AND reference=2869",
                (char["id"],),
            ).fetchall()
            self.assertEqual(sum(row["quantity"] for row in rows), 3)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["quantity"] == 1 for row in rows))
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", item["uid"] + 999, 22, 0),
            )

        # Inactive build references retain the same UID after editing elements.
        from wakfu_server.wire import proto_field

        equipment = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, 15))
        with store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,1,%s,%s,%s,%s)",
                (char["id"], proto_field(24, (1 << 64) - 1), equipment, b"", b""),
            )
        result = select_elements(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qBB", item["uid"], 28, 0),
        )
        self.assertTrue(result["applied"])
        saved = store.character(account, char["id"])
        self.assertEqual(saved["builds"][1]["equipment"], equipment.hex())

    def test_native_creation_selection_and_legacy_absence_are_distinct(self):
        selected = create(2869)
        self.assertEqual(selected, dict(damage_elements=0, resistance_elements=0))
        effect = next(x for x in CATALOG[2869]["effects"] if x["generic"] == 1068)
        self.assertEqual(selected_bonuses({}, effect), {})
        actual = selected_bonuses(selected, effect)
        expected = {
            20 + element: 21
            for element in (1, 2, 3, 4)
            if selected["damage_elements"] & (1 << element)
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            selected_bonuses(
                dict(damage_elements=2, resistance_elements=8),
                dict(effect, generic=1069),
            ),
            {30: 21},
        )
        for bad in (
            dict(damage_elements=1, resistance_elements=0),
            dict(damage_elements=32, resistance_elements=0),
            dict(damage_elements=2),
        ):
            with self.assertRaises(ValueError):
                masks(bad)

    def test_sql_grant_reopen_item_codecs_and_repeated_equipment_preserve_masks(self):
        store = self.store
        account = store.register("element-unit", "local-test-password")["id"]
        char = store.create_character(account, "Element Unit")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2869,
            quantity=1,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2869},
        )
        selected = masks(item)
        reopened = self.reopen().character(account, char["id"])["inventory_items"][0]
        self.assertEqual(masks(reopened), selected)
        nested = dict(proto_fields(item_proto(item)))[450]
        self.assertEqual(dict(proto_fields(nested)), {8: selected[0], 16: selected[1]})
        self.assertEqual(item_form(item)[14:], bytes(5) + bytes((1, *selected, 0, 0)))
        sheet = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, 15)).hex()
        loaded = dict(
            store.character(account, char["id"]),
            level=200,
            effective_level=200,
            builds={
                0: dict(equipment=sheet, sheet=proto_field(24, (1 << 64) - 1).hex())
            },
        )
        first = bonuses(loaded)
        self.assertFalse(first["unsupported"])
        self.assertEqual(first, bonuses(loaded))
        for element in (1, 2, 3, 4):
            self.assertEqual(
                first["stats"].get(20 + element, 0),
                21 if selected[0] & (1 << element) else 0,
            )

    def test_native_copy_minus_one_with_absent_equipment_trigger_is_zero(self):
        effect = dict(
            runner="eWQ",
            values=[-1],
            stat_id=27,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            parameter_count=1,
        )
        self.assertEqual(_flat(effect), (27, 0))
        self.assertEqual(_flat(dict(effect, values=[-3])), (27, -3))
        self.assertEqual(_flat(dict(effect, values=[-2])), (27, -2))
