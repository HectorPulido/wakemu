"""Source-bound NativeSession query contract using harmless oracle stubs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from native_context import encode, NativeGraph
from world_bridge import NativeSession, _json_bytes


def make_actor(identity, team, position, *, controlled=False, hp=40):
    return SimpleNamespace(
        id=identity,
        team=team,
        controlled=controlled,
        position=tuple(position),
        hp=hp,
        max_hp=40,
        ap=6,
        mp=3,
        effect_stats={4: 7, 97: 11},
        direction=2,
        future_actor_extension={"all": [b"bytes", "retained"]},
    )


def make_runtime():
    pc = make_actor(101, 1, (0, 0, 0), controlled=True)
    npc = make_actor(-23, 0, (2, 0, 0), hp=25)
    fight = SimpleNamespace(
        id=801,
        actors={101: pc, -23: npc},
        phase="active",
        current=pc,
        turn_id=9,
        sequence=97,
        future_fight_extension={"version": 4},
        walkable=frozenset((x, 0, 0) for x in range(3)),
        edges=frozenset([((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))]),
    )
    return SimpleNamespace(
        fight=fight,
        action_id=15,
        round=3,
        pending=[],
        awaiting_ack=None,
        future_runtime_extension="preserve",
    )


class StubTransport:
    def __init__(self):
        self.catalog_calls = []
        self.graphs = {}

    def catalog(self, exporter):
        self.catalog_calls.append(exporter)
        return "c" * 64

    def instance(self, graph):
        payload = _json_bytes(graph)
        digest = hashlib.sha256(payload).hexdigest()
        self.graphs[digest] = deepcopy(graph)
        return digest


class StubOracle:
    def __init__(self, runtime):
        self.runtime = runtime
        self.flags = {"native-preview": True, "future-flag": "preserved"}
        self.mutate_source = False
        self.preview_calls = []

    def authorities(self, runtime=None):
        return {
            "characters": {101: {"id": 101, "futureAuthorityField": b"authority"}},
            "monsters": {-23: {"id": -23, "type": "future-npc"}},
            "runtimeAlias": self.runtime if runtime is None else runtime,
        }

    def complete_state(self, runtime):
        return encode(
            {
                "runtime": runtime,
                "authorities": self.authorities(runtime),
                "flags": self.flags,
            }
        )

    def preview(self, runtime, action):
        self.preview_calls.append((runtime, action))
        if not isinstance(action, dict) or action.get("type") != "move":
            raise ValueError("Unsupported or illegal native candidate")
        if self.mutate_source:
            runtime.fight.current.hp -= 1
        path = action.get("path")
        if not isinstance(path, list) or len(path) != 1 or path[0] != [1, 0, 0]:
            raise ValueError("Illegal native movement route")
        private = deepcopy(runtime)
        private.fight.current.position = tuple(path[0])
        private.fight.current.mp -= 1
        private.fight.sequence += 1
        private.action_id += 1
        return private, (b"private-preview-packet",), None


class NativeSessionTests(unittest.TestCase):
    def test_distinct_preview_receipts_share_runtime_identity_when_native_state_is_identical(
        self,
    ):
        original = self.oracle.preview
        calls = []

        def preview(runtime, action):
            private, _, transaction = original(runtime, action)
            calls.append(True)
            return private, ((42, bytes([len(calls)])),), transaction

        self.oracle.preview = preview
        query = dict(
            id="same-state",
            operation="preview",
            state=self.session.root,
            action={"type": "move", "path": [[1, 0, 0]]},
        )
        first = self.session.query(query)["result"]
        second = self.session.query(dict(query, id="same-state-again"))["result"]
        self.assertNotEqual(first["key"], second["key"])
        self.assertEqual(first["runtimeIdentity"], second["runtimeIdentity"])
        self.assertIn(first["transitionContext"], self.transport.graphs)
        self.assertIn(second["transitionContext"], self.transport.graphs)

    def test_preview_retains_complete_transaction_packets_future_fields_and_fight_alias(
        self,
    ):
        original = self.oracle.preview

        def preview(runtime, action):
            private, _, _ = original(runtime, action)
            transaction = SimpleNamespace(
                fight=private.fight,
                future_native_field={
                    "binary": b"\x00\xff",
                    "callback_metadata": "retained",
                },
            )
            return private, ((987654, b"\x00\x80native-outbox"),), transaction

        self.oracle.preview = preview
        before = encode(self.runtime)
        action = {"type": "move", "path": [[1, 0, 0]]}
        response = self.session.query(
            dict(
                id="receipt",
                operation="preview",
                state=self.session.root,
                action=action,
            )
        )
        self.assertTrue(response["supported"])
        result = response["result"]
        self.assertEqual(result["transitionContext"], result["nativeContext"])
        graph = NativeGraph(self.transport.graphs[result["transitionContext"]])
        receipt = graph.field(graph.data["root"], "transition")
        self.assertEqual(
            graph.plain(graph.field(receipt, "sourceState")), self.session.root
        )
        self.assertEqual(graph.plain(graph.field(receipt, "action")), action)
        self.assertEqual(
            graph.plain(graph.field(receipt, "publication")),
            "uncommitted_native_preview",
        )
        self.assertEqual(
            graph.plain(graph.field(receipt, "packets")),
            ((987654, b"\x00\x80native-outbox"),),
        )
        transaction = graph.field(receipt, "transaction")
        self.assertEqual(
            graph.plain(graph.field(transaction, "future_native_field")),
            {"binary": b"\x00\xff", "callback_metadata": "retained"},
        )
        runtime = graph.field(graph.data["root"], "runtime")
        self.assertEqual(
            graph.field(transaction, "fight"), graph.field(runtime, "fight")
        )
        self.assertEqual(encode(self.runtime), before)
        # Legacy oracle fallback retains its entire graph too, including any
        # future root fields the generic SDK cannot predict.
        self.assertEqual(
            graph.plain(graph.field(graph.data["root"], "completeState")),
            self.oracle.complete_state(self.session.states[result["key"]]),
        )

    def test_production_transition_graph_and_byte_path_preserve_identical_complete_data(
        self,
    ):
        from native_oracle import NativeOracle

        oracle = NativeOracle.__new__(NativeOracle)
        oracle.flags = {"future": b"flags"}
        oracle.authorities = lambda runtime: {"future": b"authority"}
        transition = dict(
            transaction=SimpleNamespace(fight=self.runtime.fight, future=b"data"),
            packets=((42, b"full"),),
            publication="uncommitted_native_preview",
        )
        graph = oracle.complete_transition_state(self.runtime, transition)
        self.assertEqual(
            oracle.complete_transition_bytes(self.runtime, transition),
            _json_bytes(graph),
        )
        decoded = NativeGraph(graph)
        runtime = decoded.field(decoded.data["root"], "runtime")
        receipt = decoded.field(decoded.data["root"], "transition")
        tx = decoded.field(receipt, "transaction")
        self.assertEqual(decoded.field(tx, "fight"), decoded.field(runtime, "fight"))
        identity = oracle.state_identity(self.runtime)
        self.assertEqual(identity, oracle.state_identity(deepcopy(self.runtime)))
        altered = deepcopy(self.runtime)
        altered.future_runtime_extension = b"new future authority"
        self.assertNotEqual(identity, oracle.state_identity(altered))

    def test_confirmed_team_context_is_transmitted_and_source_guard_covers_memory(self):
        from team_blackboard import observe, confirm

        self.runtime.tactical_encounter_id = "encounter-uuid-801"
        before = observe(self.runtime.fight)
        self.runtime.fight.actors[-23].hp -= 5
        self.runtime.fight.sequence += 1
        confirm(self.runtime, before, [dict(action={"type": "cast"})])
        session = NativeSession(
            self.oracle,
            self.transport,
            self.exporter,
            policy={},
            policy_version="v1",
            fight_instance_id="encounter-uuid-801",
        )
        context = session.envelope()["teamContext"]
        self.assertEqual(context["focusId"], -23)
        self.assertEqual(context["stateRevision"], 98)
        self.runtime.fight.native_ai_team_context["1"]["focusId"] = None
        with self.assertRaisesRegex(ValueError, "source changed"):
            session.guard()

    def setUp(self):
        self.runtime = make_runtime()
        self.oracle = StubOracle(self.runtime)
        self.transport = StubTransport()
        self.exporter = object()
        self.session = NativeSession(
            self.oracle,
            self.transport,
            self.exporter,
            policy={"version": 4, "weights": {"future": 2}},
            policy_version="policy-v4",
            fight_instance_id="encounter-uuid-801",
        )

    def test_session_registers_complete_root_and_exposes_wp_armor_metrics(self):
        self.assertEqual(self.transport.catalog_calls, [self.exporter])
        self.assertIn(self.session.root, self.session.states)
        self.assertIn(self.session.root, self.transport.graphs)
        root_graph = self.transport.graphs[self.session.root]
        self.assertEqual(root_graph["encoding"], "wakfu-native-graph-1")
        self.assertGreaterEqual(len(root_graph["nodes"]), 10)

        response = self.session.query(
            {"id": "state-1", "operation": "state", "state": self.session.root}
        )

        self.assertTrue(response["supported"])
        self.assertEqual(response["id"], "state-1")
        result = response["result"]
        self.assertEqual(result["key"], self.session.root)
        actor_rows = {actor["id"]: actor for actor in result["actors"]}
        self.assertEqual(actor_rows[101]["wp"], 7)
        self.assertEqual(actor_rows[101]["armor"], 11)
        self.assertEqual(actor_rows[-23]["wp"], 7)
        self.assertEqual(actor_rows[-23]["armor"], 11)
        self.assertEqual(
            (result["turnId"], result["stateRevision"], result["currentId"]),
            (9, 97, 101),
        )

    def test_budget_hint_is_optional_and_tracks_bounded_envelope_and_query_work(self):
        from unittest.mock import patch

        with patch("world_bridge.remaining", return_value=None):
            self.assertNotIn("nativeBudgetMs", self.session.envelope())

        with patch("world_bridge.remaining", return_value=0.125):
            envelope = self.session.envelope()
        self.assertEqual(envelope["nativeBudgetMs"], 125)

        request = {
            "id": "bounded-state",
            "operation": "state",
            "state": self.session.root,
        }
        with patch("world_bridge.remaining", return_value=0.04):
            supported = self.session.query(request)
        self.assertTrue(supported["supported"])
        self.assertEqual(supported["nativeBudgetMs"], 40)

        request = {
            "id": "bounded-unsupported",
            "operation": "preview",
            "state": self.session.root,
            "action": {"type": "move", "path": [[2, 0, 0]]},
        }
        with patch("world_bridge.remaining", return_value=0.015):
            unsupported = self.session.query(request)
        self.assertFalse(unsupported["supported"])
        self.assertEqual(unsupported["nativeBudgetMs"], 15)

    def test_valid_preview_registers_private_state_without_mutating_source(self):
        before = encode(self.runtime)

        response = self.session.query(
            {
                "id": "move-1",
                "operation": "preview",
                "state": self.session.root,
                "action": {"type": "move", "path": [[1, 0, 0]]},
            }
        )

        self.assertTrue(response["supported"])
        self.assertEqual(response["id"], "move-1")
        self.assertNotEqual(response["result"]["key"], self.session.root)
        self.assertIn(response["result"]["key"], self.session.states)
        moved = self.session.states[response["result"]["key"]]
        self.assertEqual(moved.fight.current.position, (1, 0, 0))
        self.assertEqual(moved.fight.current.mp, 2)
        self.assertEqual(moved.fight.sequence, 98)
        self.assertEqual(encode(self.runtime), before)
        self.assertEqual(self.runtime.fight.current.position, (0, 0, 0))
        self.assertEqual(self.runtime.fight.current.mp, 3)
        self.assertEqual(self.runtime.fight.current.hp, 40)

    def test_illegal_native_preview_is_an_unsupported_query_result(self):
        response = self.session.query(
            {
                "id": "bad-move",
                "operation": "preview",
                "state": self.session.root,
                "action": {"type": "move", "path": [[2, 0, 0]]},
            }
        )
        self.assertEqual(response["id"], "bad-move")
        self.assertFalse(response["supported"])
        self.assertEqual(
            response["unknownDependencies"], ["Illegal native movement route"]
        )
        self.assertEqual(set(self.session.states), {self.session.root})

    def test_foreign_state_and_unknown_operation_are_fatal(self):
        with self.assertRaisesRegex(ValueError, "foreign state"):
            self.session.query(
                {"id": "foreign", "operation": "state", "state": "f" * 64}
            )
        with self.assertRaisesRegex(ValueError, "Unknown native oracle operation"):
            self.session.query(
                {
                    "id": "unknown",
                    "operation": "execute-code",
                    "state": self.session.root,
                }
            )

    def test_source_mutation_during_preview_is_fatal(self):
        self.oracle.mutate_source = True
        with self.assertRaisesRegex(
            ValueError, "Native oracle source changed during decision"
        ):
            self.session.query(
                {
                    "id": "mutating",
                    "operation": "preview",
                    "state": self.session.root,
                    "action": {"type": "move", "path": [[1, 0, 0]]},
                }
            )
        self.assertEqual(self.runtime.fight.current.hp, 39)

    def test_future_runtime_fields_and_alias_changes_invalidate_source(self):
        shared = ["complete"]
        self.runtime.future_aliases = {"left": shared, "right": shared}
        session = NativeSession(
            self.oracle,
            self.transport,
            self.exporter,
            policy={},
            policy_version="future",
            fight_instance_id="future-fields",
        )
        self.runtime.future_aliases["right"] = list(shared)
        with self.assertRaisesRegex(ValueError, "Native oracle source changed"):
            session.guard()

    def test_reused_catalogue_still_uploads_fresh_complete_root_and_source(self):
        old_root, old_source = self.session.root, self.session.source
        self.runtime.fight.current.ap -= 1
        self.runtime.future_runtime_extension = "new-complete-value"
        session = NativeSession(
            self.oracle,
            self.transport,
            self.exporter,
            policy=self.session.policy,
            policy_version=self.session.policy_version,
            fight_instance_id=self.session.fight_instance_id,
            catalog_manifest=self.session.catalog,
        )
        self.assertEqual(self.transport.catalog_calls, [self.exporter])
        self.assertNotEqual(session.root, old_root)
        self.assertNotEqual(session.source, old_source)
        self.assertEqual(session.describe(session.root)["actors"][1]["ap"], 5)
        session.guard()

    def test_reused_catalogue_reference_must_be_a_complete_hash(self):
        with self.assertRaisesRegex(ValueError, "catalogue manifest"):
            NativeSession(
                self.oracle,
                self.transport,
                self.exporter,
                policy={},
                policy_version="test",
                fight_instance_id="test",
                catalog_manifest="partial",
            )

    def test_register_accepts_complete_descendant_and_rejects_unknown_describe_key(
        self,
    ):
        child = deepcopy(self.runtime)
        child.fight.current.position = (1, 0, 0)
        child.fight.sequence += 1
        key = self.session.register(child)
        self.assertIn(key, self.session.states)
        self.assertEqual(self.session.describe(key)["actors"][1]["position"], [1, 0, 0])
        with self.assertRaisesRegex(ValueError, "Unknown native oracle state"):
            self.session.describe("unknown-state")


if __name__ == "__main__":
    unittest.main()
