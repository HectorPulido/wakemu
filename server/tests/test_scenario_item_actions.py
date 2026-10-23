"""Bounded native scenario reading preserves its reusable source."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import scenario_item_actions as actions
from wakfu_server.inventory_items import grant


class ReadingScenarioWireTests(unittest.TestCase):
    def test_only_the_qualified_scenario_uses_exact_twelve_byte_request(self):
        self.assertEqual(actions.action_class(struct.pack(">iq", 14933, 1)), "bIn")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 2372, 1)))
        for request in (
            b"",
            struct.pack(">iq", 14933, 0),
            struct.pack(">iqB", 14933, 1, 0),
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                actions.action_class(request)


class ReadingScenarioPostgresTests(PostgresCase):
    def fixture(self, suffix=""):
        account = self.store.register("diary-reader" + suffix, "local-password")["id"]
        character_name = "Diary Reader" if not suffix else "Other Diary Reader"
        character = self.store.create_character(account, character_name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(self, account, generation, character, ref, slot=0):
        container = next(
            row for row in character["inventory_containers"] if row["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=ref,
            quantity=2,
            container=container["uid"],
            slot=slot,
            allowed_references={ref},
        )

    def test_repeated_native_read_is_reusable_and_returns_exact_owned_ui_event(self):
        account, generation, character = self.fixture()
        item = self.give(account, generation, character, 30723)
        body = struct.pack(">iq", 14933, item["uid"])
        for _ in range(2):
            result = actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
            self.assertEqual(
                (result["native_class"], result["consumed"], result["background_id"]),
                ("bIn", 0, 415),
            )
            self.assertEqual(
                result["packets"], [(13411, struct.pack(">BiiB", 0, 24072, 2704, 0))]
            )
        restored = self.reopen().character(account, character["id"])
        physical = next(
            row for row in restored["inventory_items"] if row["uid"] == item["uid"]
        )
        self.assertEqual((physical["reference"], physical["quantity"]), (30723, 2))

    def test_foreign_source_stale_session_wrong_item_and_combat_never_publish(self):
        account, generation, character = self.fixture()
        item = self.give(account, generation, character, 30723)
        wrong = self.give(account, generation, character, 9724, 1)
        other, other_generation, other_character = self.fixture("_Other")
        requests = (
            (other, other_generation, other_character["id"], item["uid"], False),
            (account, "expired", character["id"], item["uid"], False),
            (account, generation, character["id"], wrong["uid"], False),
            (account, generation, character["id"], item["uid"], True),
        )
        for owner, lease, actor, uid, fight in requests:
            with self.subTest(owner=owner, uid=uid), self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    owner,
                    lease,
                    actor,
                    struct.pack(">iq", 14933, uid),
                    in_fight=fight,
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                2,
            )
