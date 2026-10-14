"""Cold-start allowance follows each actor's actual first turn."""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge import world_entry
from wakfu_ai.native.native_deadline import remaining


class FirstTurnBudgetTests(unittest.TestCase):
    def run_entry(self, turn_count, *, policy_ms=10000, round_number=1):
        actor = SimpleNamespace(id=-71, turn_count=turn_count)
        runtime = SimpleNamespace(
            fight=SimpleNamespace(
                id=41, current=actor, native_timeline_round=round_number
            )
        )
        authorities = dict(
            characters={}, monsters={}, decks={}, excluded_decks={}, registrations={}
        )
        observed = {}

        def run_turn(candidate, **kwargs):
            observed.update(kwargs)
            observed["available_seconds"] = remaining()
            return iter(())

        with ExitStack() as stack:
            for name, value in (
                ("load_authorities", authorities),
                (
                    "encounter_profiles",
                    {
                        None: {
                            "policy": {"limits": {"turnMs": policy_ms}},
                            "identity": "test",
                        }
                    },
                ),
                ("NativeStats", object()),
                ("native_exporter", object()),
            ):
                stack.enter_context(patch.object(world_entry, name, return_value=value))
            transport = stack.enter_context(
                patch.object(world_entry, "ContextTransport")
            )
            stack.enter_context(
                patch.object(world_entry, "run_turn", side_effect=run_turn)
            )
            list(
                world_entry._run_npc_turn(
                    runtime,
                    store=None,
                    viewer_character={"id": 1, "map_id": 527},
                    monsters={},
                    stats_serializer=None,
                )
            )
            observed["transport_kwargs"] = transport.call_args.kwargs
        return observed

    def test_first_turn_has_twenty_seconds_through_transport_and_planning(self):
        result = self.run_entry(1)
        self.assertEqual(result["budget_seconds"], 20)
        self.assertGreater(result["available_seconds"], 19)
        self.assertEqual(result["transport_kwargs"], {"timeout": 20})

    def test_first_turn_overrides_shorter_ai_policy(self):
        result = self.run_entry(1, policy_ms=4300)
        self.assertEqual(result["budget_seconds"], 20)
        self.assertGreater(result["available_seconds"], 19)

    def test_later_turn_retains_normal_budget(self):
        result = self.run_entry(2)
        self.assertEqual(result["budget_seconds"], 10)
        self.assertLessEqual(result["available_seconds"], 10)
        self.assertEqual(result["transport_kwargs"], {})

    def test_later_turn_retains_shorter_policy(self):
        result = self.run_entry(7, policy_ms=4300)
        self.assertEqual(result["budget_seconds"], 4.3)
        self.assertLessEqual(result["available_seconds"], 4.3)

    def test_new_rift_actor_gets_allowance_in_late_round(self):
        result = self.run_entry(1, round_number=47)
        self.assertEqual(result["budget_seconds"], 20)
        self.assertGreater(result["available_seconds"], 19)

    def test_retry_of_same_actor_turn_does_not_consume_first_turn(self):
        self.assertEqual(self.run_entry(1)["budget_seconds"], 20)
        self.assertEqual(self.run_entry(1)["budget_seconds"], 20)


if __name__ == "__main__":
    unittest.main()
