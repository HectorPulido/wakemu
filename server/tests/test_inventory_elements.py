import struct
import unittest
from datetime import timedelta
from random import Random
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
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        with patch(
            "wakfu_server.inventory_elements.SystemRandom", return_value=Random(0)
        ):
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
        # The server's grant has a generated selection; the manual native
        # request is allowed to set a different template-valid choice.
        body = struct.pack(">qBB", item["uid"], 26, 0)
        applied = select_elements(store, account, generation, char["id"], body)
        self.assertTrue(applied["applied"])
        self.assertEqual(
            (applied["damage_elements"], applied["resistance_elements"]), (26, 0)
        )
        self.assertEqual(applied["packet"][0], 13766)
        reopened = self.reopen().character(account, char["id"])["inventory_items"][0]
        self.assertEqual(
            (reopened["damage_elements"], reopened["resistance_elements"]), (26, 0)
        )
        retry = select_elements(store, account, generation, char["id"], body)
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["packet"], applied["packet"])
        changed = select_elements(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qBB", item["uid"], 22, 0),
        )
        self.assertTrue(changed["applied"])
        self.assertEqual(changed["damage_elements"], 22)
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
        with self.assertRaisesRegex(ValueError, "one unstacked item UID"):
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", stacked["uid"], 22, 0),
            )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", item["uid"] + 999, 22, 0),
            )

        # An item referenced in any persisted build is protected even if a
        # forged request bypasses the client-side identification dialog.
        from wakfu_server.wire import proto_field

        equipped_build = proto_field(
            10, proto_field(8, item["uid"]) + proto_field(16, 15)
        ).hex()
        with patch.object(
            store,
            "character",
            return_value={"builds": {0: {"equipment": equipped_build}}},
        ):
            with self.assertRaisesRegex(ValueError, "Unequip item"):
                select_elements(
                    store,
                    account,
                    generation,
                    char["id"],
                    struct.pack(">qBB", item["uid"], 28, 0),
                )

        # Exchange membership is guarded under the same owned session, even
        # when this UID has not yet been placed in the offer list.
        other_account = store.register("element-other", "local-other-password")["id"]
        other_char = store.create_character(other_account, "Element Other")
        now = store.now()
        with store.connection() as db:
            exchange = db.execute(
                "INSERT INTO player_exchanges "
                "(inviter_id,invitee_id,inviter_account,invitee_account,"
                "inviter_generation,invitee_generation,created_at,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (
                    char["id"],
                    other_char["id"],
                    account,
                    other_account,
                    generation,
                    "other-generation",
                    now,
                    now + timedelta(minutes=1),
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO player_exchange_members(character_id,exchange_id) "
                "VALUES(%s,%s)",
                (char["id"], exchange["id"]),
            )
        with self.assertRaisesRegex(ValueError, "active exchange"):
            select_elements(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", item["uid"], 28, 0),
            )

    def test_native_creation_selection_and_legacy_absence_are_distinct(self):
        selected = create(2869, rng=Random(0))
        self.assertEqual(selected["damage_elements"].bit_count(), 3)
        self.assertNotEqual(selected["damage_elements"], (1 << 1) | (1 << 2) | (1 << 3))
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
        with patch(
            "wakfu_server.inventory_elements.SystemRandom", return_value=Random(0)
        ):
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
