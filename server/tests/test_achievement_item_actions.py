"""Real item activation retains missions without fabricating their completion."""
import struct
import unittest
from unittest.mock import patch
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import achievement_item_actions as actions
from wakfu_server.achievements import storage
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.progression import level_xp


class AchievementItemGrammarTests(unittest.TestCase):
    def test_original_fixed_and_optional_position_grammars(self):
        self.assertEqual(actions.action_class(struct.pack(">iq", 2594, 1)), "bHw")
        self.assertEqual(actions.action_class(struct.pack(">iqB", 3773, 1, 0)), "bHw")
        self.assertEqual(
            actions.action_class(struct.pack(">iqBiih", 3773, 1, 1, 3, 4, 5)), "bHw"
        )
        self.assertIsNone(actions.action_class(struct.pack(">iq", 8071, 1)))
        for body in (
            b"",
            struct.pack(">iq", 2594, 0),
            struct.pack(">iqB", 2594, 1, 0),
            struct.pack(">iq", 3773, 1),
            struct.pack(">iqB", 3773, 1, 1),
            struct.pack(">iqB", 3773, 1, 2),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                actions.action_class(body)


class AchievementItemPostgresTests(PostgresCase):
    def fixture(self, suffix="", level=105):
        account = self.store.register(
            "mission-item" + suffix.replace(" ", "_"), "local-password"
        )["id"]
        character = self.store.create_character(account, "Mission Item" + suffix)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        self.set_level(character["id"], level)
        return account, generation, character

    def set_level(self, identity, level):
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=%s WHERE id=%s", (level, identity))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(level), identity),
            )

    def give(self, account, generation, character, reference, slot=0):
        current = self.store.character(account, character["id"])
        bag = next(row for row in current["inventory_containers"] if row["kind"] == 0)
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=1,
            container=bag["uid"],
            slot=slot,
            allowed_references={reference},
        )

    @staticmethod
    def request(plan, uid):
        return struct.pack(">iq", plan["action_id"], uid) + (
            b"\x00" if plan["positional_suffix"] else b""
        )

    def test_both_native_starters_activate_once_persist_without_consume_or_rewards(
        self,
    ):
        account, generation, character = self.fixture()
        before = self.store.character(account, character["id"])
        for slot, plan in enumerate(actions.descriptors().values()):
            item = self.give(account, generation, character, plan["item_ref"], slot)
            body = self.request(plan, item["uid"])
            result = actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
            self.assertTrue(result["applied"])
            self.assertEqual(
                result["packets"],
                [(13312, struct.pack(">qi", character["id"], plan["definition_id"]))],
            )
            self.assertEqual(
                (
                    result["consumed"],
                    result["completed"],
                    result["new_objectives"],
                    result["xp_changed"],
                ),
                (0, [], [], False),
            )
            repeat = actions.use(
                self.reopen(),
                account,
                generation,
                character["id"],
                body,
                in_fight=False,
            )
            self.assertFalse(repeat["applied"])
            self.assertEqual(repeat["packets"], [])
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(restored["xp"], before["xp"])
        for key in ("level", "map_id", "instance_id", "x", "y", "z", "builds"):
            self.assertEqual(restored[key], before[key], key)
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            self.assertTrue({652, 1197} <= set(state["running"]))
            self.assertFalse({2907, 2909} & set(state["running"]))
            self.assertEqual(state["completed"], [])
            self.assertEqual(state["objectives"], [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference IN(14539,16471)",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )

    def test_low_level_foreign_stale_wrong_source_and_combat_leave_state_unchanged(
        self,
    ):
        account, generation, character = self.fixture(level=94)
        item = self.give(account, generation, character, 14539)
        wrong = self.give(account, generation, character, 2026, 1)
        other, other_generation, other_character = self.fixture(" Other")
        body = struct.pack(">iq", 2594, item["uid"])
        cases = (
            (account, generation, character["id"], body, False),
            (account, "stale", character["id"], body, False),
            (other, other_generation, other_character["id"], body, False),
            (
                account,
                generation,
                character["id"],
                struct.pack(">iq", 2594, wrong["uid"]),
                False,
            ),
            (account, generation, character["id"], body, True),
        )
        for owner, lease, actor, request, fight in cases:
            with self.subTest(owner=owner, lease=lease, fight=fight), self.assertRaises(
                ValueError
            ):
                actions.use(self.store, owner, lease, actor, request, in_fight=fight)
        self.set_level(character["id"], 95)
        with patch.object(actions, "_equipped", return_value=True), self.assertRaises(
            ValueError
        ):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            self.assertNotIn(652, state["running"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )

    def test_activation_failure_rolls_back_receipt_then_retry_preserves_completed(self):
        account, generation, character = self.fixture(level=95)
        item = self.give(account, generation, character, 14539)
        body = struct.pack(">iq", 2594, item["uid"])
        with patch(
            "wakfu_server.achievements.item_activation.storage.store",
            side_effect=RuntimeError("injected activation failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
        self.assertTrue(
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )["applied"]
        )
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["running"].remove(652)
            state["completed"].append(652)
            storage.store(db, character["id"], state)
        result = actions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertEqual((result["applied"], result["packets"]), (False, []))
        with self.store.connection() as db:
            retained = storage.load_locked(db, character["id"])
            self.assertIn(652, retained["completed"])
            self.assertNotIn(652, retained["running"])
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(
            result["character"]["achievement_section"], restored["achievement_section"]
        )

    def test_same_action_id_with_changed_native_criteria_or_descriptor_rejects(self):
        account, generation, character = self.fixture(level=95)
        item = self.give(account, generation, character, 14539)
        body = struct.pack(">iq", 2594, item["uid"])
        changed = {
            14539: dict(
                use_action_class="bHw", use_action_id=2594, use_has_criteria=True
            )
        }
        with patch(
            "wakfu_server.haven_bag_furniture_knowledge._rules", return_value=changed
        ):
            with self.assertRaisesRegex(ValueError, "active native catalog"):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
        plan = actions.descriptors()[2594]
        for key, value in (
            ("native_action_criterion", "True"),
            ("native_definition_criterion", "GetRealLevel()>=1"),
            ("scope", "complete_mission"),
            ("consumes_source", True),
        ):
            with self.subTest(field=key):
                modified = dict(plan, **{key: value})
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE native_achievement_item_actions SET descriptor=%s WHERE item_ref=14539",
                        (Jsonb(modified),),
                    )
                with self.assertRaisesRegex(ValueError, "authority has changed"):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        body,
                        in_fight=False,
                    )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertNotIn(652, storage.load_locked(db, character["id"])["running"])

    def test_active_hero_uses_its_own_level_and_mission_not_the_main(self):
        account, generation, main = self.fixture(level=1)
        hero = self.store.create_character(account, "Mission Hero")
        self.set_level(hero["id"], 105)
        self.store.select_character(account, generation, hero["id"])
        item = self.give(account, generation, hero, 16471)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        body = struct.pack(">iqB", 3773, item["uid"], 0)
        result = actions.use(
            self.store, account, generation, main["id"], body, in_fight=False
        )
        self.assertEqual(result["actor_id"], hero["id"])
        self.assertEqual(
            result["packets"], [(13312, struct.pack(">qi", hero["id"], 1197))]
        )
        with self.store.connection() as db:
            self.assertNotIn(1197, storage.load_locked(db, main["id"])["running"])
            self.assertIn(1197, storage.load_locked(db, hero["id"])["running"])
        heroes.remove(self.store, account, generation, main["id"], hero["id"])
        with self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, main["id"], body, in_fight=False
            )
