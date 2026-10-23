"""Orchestration tests for the SDK-owned native encounter entry point."""
from pathlib import Path
import os
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.bridge import world_entry


def npc(identity, **attributes):
    return SimpleNamespace(
        id=identity,
        controlled=False,
        hp=20,
        owner_id=None,
        native_controlled_by_ai=True,
        **attributes
    )


class NativeWorldEntryTests(unittest.TestCase):
    def test_default_complete_turn_budget_is_ten_seconds(self):
        import inspect
        from wakfu_ai.native.native_turn import run_turn

        self.assertEqual(
            inspect.signature(run_turn).parameters["budget_seconds"].default, 10
        )
        runtime = SimpleNamespace(
            fight=SimpleNamespace(id=41, current=SimpleNamespace(id=7))
        )
        authorities = dict(
            characters={}, monsters={}, decks={}, excluded_decks={}, registrations={}
        )
        with patch.object(
            world_entry, "load_authorities", return_value=authorities
        ), patch.object(
            world_entry,
            "encounter_profiles",
            return_value={None: {"policy": {}, "identity": "default"}},
        ), patch.object(
            world_entry, "native_exporter"
        ), patch.object(
            world_entry, "context_transport"
        ), patch.object(
            world_entry, "NativeStats"
        ), patch.object(
            world_entry, "run_turn", return_value=iter(())
        ) as turn:
            list(
                world_entry._run_npc_turn(
                    runtime,
                    store=None,
                    viewer_character={"id": 1, "map_id": 1134},
                    monsters={},
                    stats_serializer=None,
                )
            )
        self.assertEqual(turn.call_args.kwargs["budget_seconds"], 10)

    def test_preparation_timeout_closes_native_turn_without_transport_or_planning(self):
        import time
        from unittest.mock import Mock
        from wakfu_ai.native.native_deadline import bounded, remaining

        actor = npc(-7)
        runtime = SimpleNamespace(
            awaiting_ack=None,
            pending=[],
            fight=SimpleNamespace(
                id=41,
                phase="active",
                turn_id=3,
                current=actor,
                actors={actor.id: actor},
            ),
            end_server_turn=Mock(return_value=["native-barrier"]),
        )
        authorities = dict(
            characters={}, monsters={}, decks={}, excluded_decks={}, registrations={}
        )

        def slow_authorities(*args, **kwargs):
            time.sleep(0.015)
            return authorities

        with patch.object(
            world_entry, "load_authorities", side_effect=slow_authorities
        ), patch.object(world_entry, "context_transport") as transport, patch.object(
            world_entry, "run_turn"
        ) as turn:
            with bounded(time.monotonic() + 0.005):
                deliveries = list(
                    world_entry.run_npc_turn(
                        runtime,
                        store=None,
                        viewer_character={"id": 1, "map_id": 1134},
                        monsters={},
                        stats_serializer=None,
                    )
                )
        self.assertIsNone(remaining())
        self.assertEqual(deliveries[0][1]["error"], "TimeoutError")
        self.assertEqual(deliveries[-1][0], ["native-barrier"])
        runtime.end_server_turn.assert_called_once_with(-7, 3)
        transport.assert_not_called()
        turn.assert_not_called()

    def setUp(self):
        world_entry._EXPORTERS.clear()

    def test_entry_forwards_all_authorities_policy_flags_and_transport_to_sdk(self):
        actor = npc(7)
        runtime = SimpleNamespace(
            awaiting_ack=None,
            pending=[],
            fight=SimpleNamespace(
                id=41, current=actor, phase="active", actors={actor.id: actor}
            ),
        )
        characters = {1: {"id": 1, "future": b"pc"}, 2: {"id": 2, "future": b"party"}}
        monsters = {
            7: {"id": 7, "ref": 777, "future": b"npc"},
            8: {"id": 8, "ref": 888},
        }
        decks = {1: b"deck-one", 2: b"deck-two"}
        excluded = {1: frozenset(), 2: frozenset()}
        authorities = dict(
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=1,
            registrations={99: {"ownerId": 7}},
        )
        default = {"policy": {"weights": {"damage": 1}}, "identity": "default:1:hash"}
        bound = {
            "policy": {"weights": {"control": 3}, "limits": {"turnMs": 4300}},
            "identity": "boss:4:hash",
        }
        exporter = object()
        transport = object()
        calls = {}

        def fake_run_turn(runtime_arg, **kwargs):
            calls["runtime"] = runtime_arg
            calls.update(kwargs)
            return iter(["delivery-a", "delivery-b"])

        psycopg = ModuleType("psycopg")
        psycopg.Error = type("DatabaseError", (Exception,), {})
        with patch.dict(
            os.environ,
            {
                "WAKFU_NATIVE_AREA_CALLBACKS": "1",
                "WAKFU_COMBAT_START_EVENTS": "0",
                "WAKFU_NATIVE_FUTURE_SWITCH": "future-value",
                "WAKFU_AI_URL": "tcp://native-ai:9100",
                "UNRELATED_SECRET": "must-not-forward",
            },
            clear=True,
        ), patch.dict(sys.modules, {"psycopg": psycopg}), patch.object(
            world_entry, "load_authorities", return_value=authorities
        ) as load, patch.object(
            world_entry, "encounter_profiles", return_value={None: default, 777: bound}
        ) as profiles, patch.object(
            world_entry, "context_transport", return_value=transport
        ) as transport_ctor, patch.object(
            world_entry, "native_exporter", return_value=exporter
        ) as get_exporter, patch.object(
            world_entry, "run_turn", side_effect=fake_run_turn
        ) as turn:
            deliveries = list(
                world_entry.run_npc_turn(
                    runtime,
                    store=object(),
                    viewer_character={"id": 1, "map_id": 1134},
                    monsters=monsters,
                    stats_serializer="serializer",
                )
            )

        self.assertEqual(deliveries, ["delivery-a", "delivery-b"])
        load.assert_called_once()
        self.assertEqual(load.call_args.kwargs["viewer_id"], 1)
        profiles.assert_called_once_with(runtime, load.call_args.args[1], monsters)
        transport_ctor.assert_called_once_with("tcp://native-ai:9100", first_turn=False)
        get_exporter.assert_called_once_with()
        turn.assert_called_once()
        self.assertIs(calls["runtime"], runtime)
        self.assertIs(calls["characters"], characters)
        self.assertIs(calls["monsters"], monsters)
        self.assertIs(calls["decks"], decks)
        self.assertIs(calls["excluded_decks"], excluded)
        self.assertEqual(calls["viewer_id"], 1)
        self.assertIs(calls["transport"], transport)
        self.assertIs(calls["exporter"], exporter)
        self.assertIs(calls["policy"], bound["policy"])
        self.assertEqual(calls["policy_version"], "boss:4:hash")
        self.assertEqual(calls["budget_seconds"], 4.3)
        self.assertIsInstance(calls["stats_serializer"], world_entry.NativeStats)
        self.assertEqual(calls["stats_serializer"].characters, characters)
        self.assertEqual(calls["stats_serializer"].monsters, monsters)
        self.assertEqual(
            calls["stats_serializer"].registrations, authorities["registrations"]
        )
        self.assertEqual(calls["stats_serializer"].fight_id, 41)
        self.assertTrue(calls["flags"]["native_area_callbacks"])
        self.assertFalse(calls["flags"]["native_start_events"])
        self.assertEqual(
            calls["flags"]["native_environment"],
            {
                "WAKFU_NATIVE_AREA_CALLBACKS": "1",
                "WAKFU_NATIVE_FUTURE_SWITCH": "future-value",
            },
        )

    def test_pending_ack_or_presentation_stops_before_loading_or_transport(self):
        for runtime in (
            SimpleNamespace(
                awaiting_ack=12, pending=[], fight=SimpleNamespace(current=None)
            ),
            SimpleNamespace(
                awaiting_ack=None,
                pending=[b"pending"],
                fight=SimpleNamespace(current=None),
            ),
        ):
            with self.subTest(runtime=runtime), patch.object(
                world_entry, "load_authorities"
            ) as load, patch.object(
                world_entry, "context_transport"
            ) as transport, patch.object(
                world_entry, "run_turn"
            ) as turn:
                deliveries = list(
                    world_entry.run_npc_turn(
                        runtime,
                        store=object(),
                        viewer_character={"id": 1, "map_id": 1134},
                        monsters={},
                        stats_serializer=None,
                    )
                )
            self.assertEqual(deliveries, [])
            load.assert_not_called()
            transport.assert_not_called()
            turn.assert_not_called()

    def test_preparation_failure_ends_native_turn_without_spending_or_querying(self):
        actor = npc(-7, ap=6, mp=3)
        runtime = SimpleNamespace(
            awaiting_ack=None,
            pending=[],
            fight=SimpleNamespace(
                phase="active", current=actor, turn_id=4, actors={actor.id: actor}
            ),
        )
        calls = []

        def end_turn(actor_id, turn_id):
            calls.append((actor_id, turn_id))
            runtime.awaiting_ack = 42
            return [(42, b"native-barrier")]

        runtime.end_server_turn = end_turn
        psycopg = ModuleType("psycopg")
        psycopg.Error = type("DatabaseError", (Exception,), {})
        with patch.dict(sys.modules, {"psycopg": psycopg}), patch.object(
            world_entry, "load_authorities", side_effect=ValueError("missing authority")
        ), patch.object(world_entry, "context_transport") as transport:
            deliveries = list(
                world_entry.run_npc_turn(
                    runtime,
                    store=object(),
                    viewer_character={"id": 1, "map_id": 1134},
                    monsters={},
                    stats_serializer=None,
                )
            )
        self.assertEqual(deliveries[0][0], [])
        self.assertEqual(deliveries[0][1]["reason"], "complete_native_bridge_rejected")
        self.assertEqual(deliveries[1][0], [(42, b"native-barrier")])
        self.assertEqual(calls, [(-7, 4)])
        self.assertEqual((actor.ap, actor.mp), (6, 3))
        self.assertEqual(runtime.awaiting_ack, 42)
        transport.assert_not_called()

    def test_exporter_roots_cover_catalog_engine_and_entire_server_without_whitelist(
        self,
    ):
        created = []

        class Exporter:
            def __init__(self, roots, **kwargs):
                self.roots = roots
                self.kwargs = kwargs
                created.append(self)

        with patch.object(world_entry, "CompleteContextExporter", Exporter):
            exporter = world_entry.native_exporter()
            again = world_entry.native_exporter()

        self.assertIs(exporter, again)
        self.assertEqual(len(created), 1)
        self.assertEqual(set(exporter.roots), {"catalog", "engine", "server"})
        self.assertEqual(exporter.roots["catalog"].name, "protocol")
        self.assertEqual(exporter.roots["engine"].name, "wakfu_server")
        self.assertEqual(exporter.roots["server"], exporter.roots["engine"].parent)
        self.assertEqual(set(exporter.kwargs), {"cache_root"})
        self.assertEqual(
            exporter.kwargs["cache_root"].name, "wakfu-ai-native-catalog-cache"
        )
        self.assertTrue(
            exporter.roots["engine"].is_relative_to(exporter.roots["server"])
        )
        self.assertTrue(
            exporter.roots["catalog"].is_relative_to(exporter.roots["server"])
        )


if __name__ == "__main__":
    unittest.main()
