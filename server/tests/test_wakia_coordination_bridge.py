"""World-owned WakIA team facts remain advisory and publication scoped."""
from copy import deepcopy
from types import SimpleNamespace
from types import ModuleType
import importlib.util
import sys
import time
import unittest
from unittest.mock import patch

_oracle_module = ModuleType("wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle")
_oracle_module.NativeOracle = object
# These focused tests supply their own oracle. Avoid opening the native catalog
# while loading a private turn adapter; integration tests exercise the real oracle.
from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_snapshot

_entry_path = jondo_snapshot.__file__.replace("jondo_snapshot.py", "jondo_entry.py")
_entry_spec = importlib.util.spec_from_file_location(
    "wakfu_server.wakia_bridge.wakfu_ai.bridge._test_jondo_entry", _entry_path
)
jondo_entry = importlib.util.module_from_spec(_entry_spec)
with patch.dict(sys.modules, {_oracle_module.__name__: _oracle_module}):
    _entry_spec.loader.exec_module(jondo_entry)
from wakfu_server.wakia_bridge.wakfu_ai.planning import team_blackboard


class CoordinationSnapshotTests(unittest.TestCase):
    def test_visible_confirmed_context_uses_cell_ids_and_filters_hidden_facts(self):
        actor = SimpleNamespace(id=-1, team=1, native_obstacle_id=4)
        fight = SimpleNamespace(native_los_ignored_affiliations=frozenset({2}))
        runtime = SimpleNamespace(fight=fight, tactical_encounter_id="fight")
        cells = {(0, 0, 0): 0, (1, 0, 0): 1}
        context = dict(
            focusId=7,
            corridors=[
                dict(ownerId=-2, targetId=7, cells=[[1, 0, 0]]),
                dict(ownerId=-2, targetId=8, cells=[[0, 0, 0]]),
                dict(ownerId=-2, targetId=7, cells=[[4, 0, 0]]),
            ],
        )
        with patch.object(
            jondo_snapshot, "effective_affiliation", return_value=1
        ), patch.object(team_blackboard, "team_context", return_value=context):
            result = jondo_snapshot._coordination_projection(
                runtime, actor, {-1, -2, 7}, cells
            )
        self.assertEqual(
            result,
            dict(
                actorId=-1,
                team=1,
                focusId=7,
                actorBlocksNativeLos=True,
                corridors=[dict(ownerId=-2, targetId=7, cells=[1])],
            ),
        )
        context["focusId"] = 8
        fight.native_los_ignored_affiliations = frozenset({4})
        with patch.object(
            jondo_snapshot, "effective_affiliation", return_value=1
        ), patch.object(team_blackboard, "team_context", return_value=context):
            result = jondo_snapshot._coordination_projection(
                runtime, actor, {-1, -2, 7}, cells
            )
        self.assertIsNone(result["focusId"])
        self.assertFalse(result["actorBlocksNativeLos"])

    def test_unavailable_or_malformed_advice_stays_empty(self):
        actor = SimpleNamespace(id=1, team=1)
        runtime = SimpleNamespace(
            fight=SimpleNamespace(native_los_ignored_affiliations=[1]),
            tactical_encounter_id="fight",
        )
        with patch.object(
            jondo_snapshot, "effective_affiliation", return_value=1
        ), patch.object(team_blackboard, "team_context", side_effect=ValueError("bad")):
            result = jondo_snapshot._coordination_projection(runtime, actor, {1}, {})
        self.assertEqual(
            result,
            dict(
                actorId=1, team=1, focusId=None, actorBlocksNativeLos=None, corridors=[]
            ),
        )


class CoordinationDeliveryTests(unittest.TestCase):
    def test_focus_is_created_only_after_publication_confirmation(self):
        actor = SimpleNamespace(id=-1, team=1, hp=20, effect_stats={97: 0})
        enemy = SimpleNamespace(id=7, team=0, hp=30, effect_stats={97: 0})
        fight = SimpleNamespace(
            current=actor,
            actors={-1: actor, 7: enemy},
            turn_id=1,
            sequence=1,
            native_table_turn=1,
        )
        runtime = SimpleNamespace(fight=fight, tactical_encounter_id="fight")
        with patch.object(
            team_blackboard, "effective_affiliation", side_effect=lambda f, a: a.team
        ):
            before = team_blackboard.observe(fight)
            enemy.hp = 20
            self.assertIsNone(
                team_blackboard.team_context(fight, "fight", -1)["focusId"]
            )
            team_blackboard.confirm(runtime, before, [dict(action=dict(type="cast"))])
            self.assertEqual(
                team_blackboard.team_context(fight, "fight", -1)["focusId"], 7
            )

    def test_optional_slow_corridor_does_not_delay_cast_or_retry(self):
        runtime = SimpleNamespace(
            fight=SimpleNamespace(
                phase="active", current=SimpleNamespace(id=-1), turn_id=1
            ),
            awaiting_ack=None,
            pending=[],
        )
        runtime.end_server_turn = lambda actor, turn: [(9000, b"end")]

        class Oracle:
            identity = "before"

            def state_identity(self, _runtime):
                return self.identity

            def coordination_for_action(self, action):
                raise AssertionError("Optional corridor must not delay native commit")

            def commit(self, action, **_kwargs):
                if action["spellId"] == 1:
                    raise ValueError("rejected")
                self.identity = "after"
                return [(12588, b"cast")]

        oracle = Oracle()
        bad = dict(type="cast", spellId=1, level=1, target=[1, 0, 0])
        good = dict(type="cast", spellId=2, level=1, target=[1, 0, 0])

        def snapshot(oracle, *, excluded_actions, budget_ms):
            return dict(
                protocol=1, requestId="test", source={"nativeIdentity": oracle.identity}
            )

        class Transport:
            def request(self, endpoint, request, *, deadline):
                return 200, dict(
                    protocol=1,
                    requestId=request["requestId"],
                    source=deepcopy(request["source"]),
                    action=bad,
                    alternatives=[good],
                )

        with patch.object(jondo_entry, "build_snapshot", snapshot):
            events = list(
                jondo_entry.run_prepared_turn(
                    runtime,
                    oracle,
                    object(),
                    Transport(),
                    deadline=time.monotonic() + 5,
                    max_actions=1,
                )
            )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0][1]["action"]["spellId"], 2)
        self.assertIsNone(events[0][1]["coordinationDraft"])
        self.assertEqual(
            events[0][1]["coordinationUnknown"], "corridor_evidence_unavailable"
        )
        self.assertEqual(len(events[0][1]["rejectedActions"]), 1)


if __name__ == "__main__":
    unittest.main()
