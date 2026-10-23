"""Pure native compass authorization never mutates inventory or guild state."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import world_marker_item_actions as actions
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant


class WorldMarkerWireTests(unittest.TestCase):
    def test_three_compass_actions_have_exact_native_grammar_and_both_criteria(self):
        rows = actions.descriptors()["items"]
        self.assertEqual({row["item_ref"] for row in rows}, {16942, 25100, 25101})
        for row in rows:
            self.assertEqual(row["marker"], dict(x=71, y=-13, z=0, map_id=527))
            body = struct.pack(">iq", row["action_id"], 123)
            self.assertEqual(actions.action_class(body), "bHA")
            for malformed in (body + b"\0", struct.pack(">iq", row["action_id"], 0)):
                with self.assertRaises(ValueError):
                    actions.action_class(malformed)
        self.assertEqual(rows[0]["use_criterion"], "GetInstanceId() == 527")
        self.assertIsNone(rows[0]["use_in_fight_criterion"])
        self.assertEqual(
            [row["use_in_fight_criterion"] for row in rows[1:]], ["False", "False"]
        )
        self.assertIsNone(actions.action_class(struct.pack(">iq", 8071, 123)))


class WorldMarkerPostgresTests(PostgresCase):
    def fixture(self, other=False):
        account = self.store.register(
            "marker-other" if other else "marker-owner", "local-password"
        )["id"]
        actor = self.store.create_character(
            account, "Other Marker" if other else "Marker Owner"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        return account, generation, actor

    def give(self, account, generation, actor, reference, slot=0):
        bag = next(row for row in actor["inventory_containers"] if row["kind"] == 0)
        return grant(
            self.store,
            account,
            generation,
            actor["id"],
            reference=reference,
            quantity=2,
            container=bag["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def body(self, item):
        row = next(
            row
            for row in actions.descriptors()["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", row["action_id"], item["uid"])

    def test_all_three_repeated_markers_use_live_map_and_preserve_inventory_wallet_and_disabled_guild_policy(
        self,
    ):
        account, generation, actor = self.fixture()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET map_id=9 WHERE id=%s", (actor["id"],))
        actor["map_id"] = 9
        for slot, reference in enumerate((16942, 25100, 25101)):
            item = self.give(account, generation, actor, reference, slot)
            with self.store.connection() as db:
                before = dict(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE uid=%s", (item["uid"],)
                    ).fetchone()
                )
                wallet = dict(
                    db.execute(
                        "SELECT * FROM account_wallets WHERE account_id=%s", (account,)
                    ).fetchone()
                )
                policy = db.execute(
                    "SELECT value FROM settings WHERE name='guild_policy'"
                ).fetchone()["value"]
            self.assertNotEqual(actor["map_id"], 527)
            for unused in range(2):
                result = actions.use(
                    self.store,
                    account,
                    generation,
                    actor["id"],
                    self.body(item),
                    in_fight=False,
                    native_map_id=527,
                )
                self.assertEqual(
                    (result["consumed"], result["packets"], result["actor_id"]),
                    (0, [], actor["id"]),
                )
                self.assertNotIn("character", result)
            with self.store.connection() as db:
                self.assertEqual(
                    dict(
                        db.execute(
                            "SELECT * FROM inventory_items WHERE uid=%s", (item["uid"],)
                        ).fetchone()
                    ),
                    before,
                )
                self.assertEqual(
                    dict(
                        db.execute(
                            "SELECT * FROM account_wallets WHERE account_id=%s",
                            (account,),
                        ).fetchone()
                    ),
                    wallet,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT value FROM settings WHERE name='guild_policy'"
                    ).fetchone()["value"],
                    policy,
                )
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM guilds").fetchone()["n"], 0
                )
        restored = self.reopen().character(account, actor["id"])
        self.assertEqual(
            {row["reference"]: row["quantity"] for row in restored["inventory_items"]},
            {16942: 2, 25100: 2, 25101: 2},
        )

    def test_foreign_stale_wrong_source_map_private_and_explicit_combat_conditions_preserve_sources(
        self,
    ):
        account, generation, actor = self.fixture()
        other, lease, foreign = self.fixture(other=True)
        items = [
            self.give(account, generation, actor, reference, slot)
            for slot, reference in enumerate((16942, 25100, 25101))
        ]
        for item in items:
            for owner, gen, selected, context in (
                (other, lease, foreign["id"], {}),
                (account, "stale", actor["id"], {}),
                (account, generation, actor["id"], {"native_map_id": 9}),
                (account, generation, actor["id"], {"private_context": True}),
            ):
                kwargs = dict(in_fight=False, native_map_id=527)
                kwargs.update(context)
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store, owner, gen, selected, self.body(item), **kwargs
                    )
            if item["reference"] != 16942:
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        actor["id"],
                        self.body(item),
                        in_fight=True,
                        native_map_id=527,
                    )
        # Native16942 has no USE_IN_FIGHT=False; a compass ACK does not invent one.
        actions.use(
            self.store,
            account,
            generation,
            actor["id"],
            self.body(items[0]),
            in_fight=True,
            native_map_id=527,
        )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                actor["id"],
                struct.pack(">iq", 10384, items[1]["uid"]),
                in_fight=False,
                native_map_id=527,
            )
        after = self.store.character(account, actor["id"])
        self.assertEqual(
            {row["uid"]: row["quantity"] for row in after["inventory_items"]},
            {item["uid"]: 2 for item in items},
        )

    def test_active_hero_custody_is_authorized_but_inactive_hero_is_rejected(self):
        account, generation, main = self.fixture()
        hero = self.store.create_character(account, "Marker Hero")
        self.store.select_character(account, generation, hero["id"])
        item = self.give(account, generation, hero, 16942)
        self.store.select_character(account, generation, main["id"])
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(item),
                in_fight=False,
                native_map_id=527,
            )
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        outcome = actions.use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(item),
            in_fight=False,
            native_map_id=527,
        )
        self.assertEqual(outcome["actor_id"], hero["id"])
        self.assertEqual(outcome["consumed"], 0)
