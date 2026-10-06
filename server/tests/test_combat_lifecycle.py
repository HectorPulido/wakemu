import struct
import tempfile
from postgres_case import PostgresCase
from tests import test_combat_rewards
from wakfu_server.combat_lifecycle import (
    policy_from_env,
    prepare_finish,
    return_to_world,
)
from wakfu_server.combat_rewards import Policy
from wakfu_server.progression import level_xp
from wakfu_server import health_store, health


class LifecycleTests(PostgresCase):
    def test_finish_encoder_failure_rolls_back_reward_and_runtime_cleanup(self):
        from unittest.mock import patch
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = test_combat_rewards.setup_reward_state(self.store)
            before = store.character(account, char["id"])
            runtime = RuntimeMessages(fight)
            runtime.awaiting_ack = 17
            pending = [(123, b"queued")]
            runtime.pending = pending
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }

            def fail(*args, **kwargs):
                runtime.awaiting_ack = None
                runtime.pending = []
                raise ValueError("Injected finish encoder failure")

            with patch("wakfu_server.combat_results.finish_messages", side_effect=fail):
                with self.assertRaises(ValueError):
                    prepare_finish(
                        store,
                        account,
                        generation,
                        char,
                        runtime,
                        metadata,
                        duration_ms=1000,
                        fight_instance_id=8,
                        policy=Policy(level_xp(3), 17),
                    )
            after = store.character(account, char["id"])
            for key in ("level", "xp", "hp", "max_hp", "kamas", "builds"):
                self.assertEqual(after[key], before[key])
            self.assertEqual(runtime.awaiting_ack, 17)
            self.assertIs(runtime.pending, pending)
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )

    def test_policy_is_explicit_zero_default_and_rejects_bad_native_amounts(self):
        self.assertEqual(policy_from_env({}), Policy())
        self.assertEqual(
            policy_from_env(
                {"WAKFU_LOCAL_FIGHT_XP": "103", "WAKFU_LOCAL_FIGHT_KAMAS": "7"}
            ),
            Policy(103, 7),
        )
        for value in ("-1", "1.5", "true", "１２", ""):
            with self.assertRaises(ValueError):
                policy_from_env({"WAKFU_LOCAL_FIGHT_XP": value})
        with self.assertRaises(ValueError):
            policy_from_env({"WAKFU_LOCAL_FIGHT_KAMAS": str(2**31)})

    def test_committed_rewards_report_then_matching_return_refreshes_level_hp_wallet(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = test_combat_rewards.setup_reward_state(self.store)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            actor = fight.actors[char["id"]]
            actor.hp = char["hp"] - 7
            actor.max_hp = char["max_hp"]
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            runtime = RuntimeMessages(fight)
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            done = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(level_xp(2) + 1, 13),
            )
            self.assertEqual([op for op, b in done["packets"]], [13613, 12238, 12755])
            self.assertEqual(done["character"]["level"], 2)
            with self.assertRaises(ValueError):
                return_to_world(
                    store,
                    account,
                    generation,
                    char,
                    runtime,
                    struct.pack(">iB", 999, 0),
                    wp=6,
                )
            result = return_to_world(
                store,
                account,
                generation,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            own = result["character"]
            self.assertEqual(own["max_hp"], health.maximum(own["breed"], 2))
            self.assertEqual(
                own["hp"], own["max_hp"] - (actor.max_hp - actor.hp)
            )  # Level-up preserves the actor's wound count as the maximum grows.
            envelope = result["packets"][2][1]
            self.assertEqual(
                struct.unpack_from(">h", envelope, 8)[0], len(envelope) - 10
            )
            progression = envelope[:8] + envelope[10:]
            self.assertEqual(
                struct.unpack_from(">q", progression, 9)[0], level_xp(2) + 1
            )
            self.assertEqual(struct.unpack_from(">i", progression, 8 + 29)[0], -1)
            self.assertEqual(result["packets"][-2], (13021, struct.pack(">q", 13)))
            self.assertEqual(
                store.character(account, char["id"])["haven_bag"], char["haven_bag"]
            )
