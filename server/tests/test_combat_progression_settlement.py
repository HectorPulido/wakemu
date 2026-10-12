"""Post-group progression executes in the real reward settlement transaction."""
import unittest
from types import SimpleNamespace
from postgres_case import PostgresCase
import test_combat_rewards as fixture
from wakfu_server.combat_lifecycle import prepare_finish, prepare_finish_shared
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_rewards import Policy
from wakfu_server.combat_state import Actor


class CombatProgressionSettlementTests(PostgresCase):
    def setUp(self):
        super().setUp()
        (
            self.store,
            self.account,
            self.character,
            self.generation,
            self.fight,
        ) = fixture.setup_reward_state(self.store)
        self.runtime = RuntimeMessages(self.fight)
        self.metadata = {
            self.character["id"]: dict(
                kind="player",
                account_id=self.account,
                name=self.character["name"],
                breed=self.character["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (self.fight.id,)
            )
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s WHERE fight_id=%s",
                (self.generation, self.fight.id),
            )

    def finish(self, callback, **kwargs):
        return prepare_finish(
            self.store,
            self.account,
            self.generation,
            self.character,
            self.runtime,
            self.metadata,
            duration_ms=100,
            fight_instance_id=self.fight.id,
            policy=Policy(10, 3),
            progression_resolver=callback,
            **kwargs
        )

    def assert_rollback(self, before):
        after = self.store.character(self.account, self.character["id"])
        self.assertEqual((after["xp"], after["kamas"]), (before["xp"], before["kamas"]))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight.id,),
                ).fetchone()["n"],
                0,
            )

    def test_solo_callback_runs_after_group_and_appends_private_packets(self):
        order = []

        def group(db, lease, defeated):
            order.append("group")
            return dict(applied=True, packets=[])

        def progression(db, members, fight):
            self.assertEqual(order, ["group"])
            self.assertEqual(
                members,
                [
                    dict(
                        account_id=self.account,
                        character_id=self.character["id"],
                        session_generation=self.generation,
                    )
                ],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                1,
            )
            order.append("progression")
            return {self.account: [(13295, b"private")]}

        result = self.finish(
            progression, groups=object(), group_lease=object(), group_settlement=group
        )
        self.assertEqual(order, ["group", "progression"])
        self.assertIn((13295, b"private"), result["packets"])

    def test_resolver_exception_rolls_back_rewards_and_runtime(self):
        before = self.store.character(self.account, self.character["id"])

        def fail(db, members, fight):
            raise ValueError("progression failure")

        with self.assertRaisesRegex(ValueError, "progression failure"):
            self.finish(fail)
        self.assert_rollback(before)

    def test_foreign_owner_and_malformed_packets_roll_back(self):
        before = self.store.character(self.account, self.character["id"])
        for packets in (
            {self.account + 999: [(13295, b"foreign")]},
            {self.account: [(13295, "not-bytes")]},
        ):
            with self.subTest(packets=packets), self.assertRaises(ValueError):
                self.finish(lambda *args: packets)
            self.assert_rollback(before)

    def test_shared_owned_hero_routes_after_group_once_per_account(self):
        hero = self.store.create_character(self.account, "Progress Hero")
        self.fight.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"],
            6,
            3,
            80,
            hero["level"],
            self.account,
            True,
            max_hp=hero["max_hp"],
        )
        self.metadata[hero["id"]] = dict(
            kind="player",
            account_id=self.account,
            name=hero["name"],
            breed=hero["breed"],
            is_male=True,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (self.fight.id, hero["id"], self.account, self.generation),
            )
        order = []

        def group(*args):
            order.append("group")
            return dict(applied=True, packets=[])

        def progression(db, members, fight):
            self.assertEqual(order, ["group"])
            self.assertEqual(
                {row["character_id"] for row in members},
                {self.character["id"], hero["id"]},
            )
            self.assertEqual({row["account_id"] for row in members}, {self.account})
            return {self.account: [(13295, b"hero-a"), (13295, b"hero-b")]}

        packets = prepare_finish_shared(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.runtime,
            self.metadata,
            duration_ms=100,
            fight_instance_id=self.fight.id,
            policy_resolver=lambda *args: Policy(10, 3),
            group_settlement=group,
            progression_resolver=progression,
            expected_accounts={self.account},
        )
        self.assertEqual(
            [body for op, body in packets[self.account] if op == 13295],
            [b"hero-a", b"hero-b"],
        )


if __name__ == "__main__":
    unittest.main()
