"""Original neutrality scroll consumption and canonical nation transition."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import neutrality_item_actions as actions
from wakfu_server.characters import nation_state
from wakfu_server.inventory_items import grant


class NeutralityItemWireTests(unittest.TestCase):
    def test_five_variants_have_exact_native_grammar_and_unknown_scenarios_stay_unqualified(
        self,
    ):
        plans = actions.descriptors()["items"]
        self.assertEqual(
            {row["item_ref"] for row in plans}, {16979, 16980, 16981, 16982, 24836}
        )
        for row in plans:
            body = struct.pack(">iq", row["action_id"], 123)
            self.assertEqual(actions.action_class(body), "bIn")
            with self.assertRaises(ValueError):
                actions.action_class(body + b"\0")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 3773, 123)))


class NeutralityItemPostgresTests(PostgresCase):
    def fixture(self, other=False):
        self.store.clock = lambda: 1000
        account = self.store.register(
            "neutral-other" if other else "neutral-owner", "local-password"
        )["id"]
        character = self.store.create_character(
            account, "Other Neutral" if other else "Neutral Owner"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(self, account, generation, character, ref, slot=0):
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=ref,
            quantity=2,
            container=bag["uid"],
            slot=slot,
            allowed_references={ref},
        )

    def body(self, item):
        plan = next(
            row
            for row in actions.descriptors()["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", plan["action_id"], item["uid"])

    def test_all_five_variants_reset_atomically_and_reenrollment_and_reconnect_work(
        self,
    ):
        account, generation, character = self.fixture()
        for slot, plan in enumerate(actions.descriptors()["items"]):
            nation = 30 + slot % 4
            before = nation_state.enroll(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">i", nation) + b"\0\0",
            )
            item = self.give(account, generation, character, plan["item_ref"], slot)
            outcome = actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(item),
                in_fight=False,
            )
            after = outcome["character"]
            self.assertEqual(
                (
                    outcome["consumed"],
                    outcome["previous_nation_id"],
                    after["nation_id"],
                ),
                (1, nation, 0),
            )
            self.assertEqual(
                outcome["packets"],
                [
                    (12470, struct.pack(">qh", item["uid"], -1)),
                    (13411, struct.pack(">BiiB", 0, 19332, 2318, 0)),
                ],
            )
            for key in (
                "id",
                "account_id",
                "level",
                "breed",
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "active_build_index",
            ):
                self.assertEqual(after[key], before[key], key)
            with self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    self.body(item),
                    in_fight=False,
                )
            restored = self.reopen().character(account, character["id"])
            self.assertEqual(restored["nation_id"], 0)
            self.assertEqual(
                next(
                    row["quantity"]
                    for row in restored["inventory_items"]
                    if row["uid"] == item["uid"]
                ),
                1,
            )
        self.assertEqual(nation_state.selection_packet({30: 1})[0], 14006)

    def test_foreign_stale_wrong_source_and_combat_preserve_nation_and_scroll(self):
        account, generation, character = self.fixture()
        nation_state.enroll(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">i", 30) + b"\0\0",
        )
        source = self.give(account, generation, character, 16979)
        other, other_generation, other_character = self.fixture(other=True)
        body = self.body(source)
        for owner, lease, actor, fight in (
            (other, other_generation, other_character["id"], False),
            (account, "stale", character["id"], False),
            (account, generation, character["id"], True),
        ):
            with self.assertRaises(ValueError):
                actions.use(self.store, owner, lease, actor, body, in_fight=fight)
        wrong = self.give(account, generation, character, 16980, 1)
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">iq", 4280, wrong["uid"]),
                in_fight=False,
            )
        after = self.store.character(account, character["id"])
        self.assertEqual(after["nation_id"], 30)
        self.assertEqual(
            next(
                row["quantity"]
                for row in after["inventory_items"]
                if row["uid"] == source["uid"]
            ),
            2,
        )

    def test_modern_scroll_preserves_physical_currency_icons_with_real_zero_pvp_state(
        self,
    ):
        account, generation, character = self.fixture()
        nation_state.enroll(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">i", 30) + b"\0\0",
        )
        scroll = self.give(account, generation, character, 24836)
        icons = [
            self.give(account, generation, character, ref, slot)
            for slot, ref in enumerate((24268, 24844), 1)
        ]
        before = self.store.character(account, character["id"])
        self.assertEqual(nation_state.synchro(before), bytes(27))
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(scroll),
            in_fight=False,
        )
        self.assertEqual((result["character"]["nation_id"], result["consumed"]), (0, 1))
        self.assertEqual(nation_state.synchro(result["character"]), bytes(27))
        with self.store.connection() as db:
            for item in icons:
                saved = db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()
                self.assertEqual(
                    (saved["reference"], saved["quantity"], saved["character_id"]),
                    (item["reference"], 2, character["id"]),
                )
