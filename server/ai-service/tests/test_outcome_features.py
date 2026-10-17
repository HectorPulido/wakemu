"""Explicit native outcome feature transport and v3 ranking contract."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
_ROOT = _HERE.parents[1]
for _path in (str(_HERE), str(_ROOT / "server")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.planning.feature_values import validate_features
from wakfu_ai.context.native_context import encode
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.planning.query_search import _metrics, search
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS
from wakfu_ai.bridge.world_bridge import NativeSession, _json_bytes


class _Transport:
    def __init__(self):
        self.graphs = {}

    def catalog(self, exporter):
        return "c" * 64

    def instance(self, graph):
        digest = hashlib.sha256(_json_bytes(graph)).hexdigest()
        self.graphs[digest] = deepcopy(graph)
        return digest


def _runtime():
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor_snapshot import (
        build_player_snapshot,
        build_npc_snapshot,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )

    # Use the same ordinary breed15/5525 construction contract as the native
    # NPC attack fixture; feature providers do not substitute actor authority.
    pc = Actor(101, 1, (0, 0, 0), 60, 6, 3, 20, 1, 7, True, direction=2)
    npc = Actor(-23, 0, (2, 0, 0), 20, 6, 3, 10, 1, direction=4)
    character = dict(
        id=101,
        account_id=7,
        breed=15,
        level=1,
        map_id=1134,
        hp=60,
        max_hp=60,
        builds={},
        inventory_items=[],
    )
    monster = dict(id=-23, ref=5525, level=1, map_id=1134, wp=0)
    build_player_snapshot(
        character,
        pc,
        wp_current=2,
        wp_maximum=6,
        running_effects=(),
    ).install(pc)
    build_npc_snapshot(
        monster,
        npc,
        wp_current=0,
        wp_maximum=0,
        running_effects=(),
    ).install(npc)
    cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
    fight = Fight(
        88,
        [pc, npc],
        cells,
        {1: {pc.position}, 0: {npc.position}},
        {((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))},
    )
    fight.native_qi_snapshot = dict(x=0, y=0, width=7, height=1, cell_masks=[0] * 7)
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                actor.id: actor.physical_radius for actor in fight.actors.values()
            },
        ),
    )
    fight.ready(7)
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    runtime = RuntimeMessages(fight)
    runtime.action_id = 7
    runtime.feature_value = 12
    runtime.fixture_character = character
    runtime.fixture_monster = monster
    return runtime


def _oracle(runtime, provider=None):
    from wakfu_server.spells import default_deck

    return NativeOracle(
        runtime,
        characters={101: runtime.fixture_character},
        monsters={-23: runtime.fixture_monster},
        decks={101: default_deck(runtime.fixture_character)},
        excluded_decks={101: frozenset()},
        viewer_id=101,
        flags={},
        outcome_features=provider,
    )


class OutcomeFeatureTests(unittest.TestCase):
    def test_shared_feature_validator_accepts_signed_values_and_rejects_bad_maps(self):
        self.assertEqual(
            validate_features({"glyph_control": -12.5}, "feature", 1e9),
            {"glyph_control": -12.5},
        )
        for invalid in (
            {"Glyph": 1},
            {"glyph": float("nan")},
            {"glyph": float("inf")},
            {"glyph": "10"},
            {"feature" + str(index): 1 for index in range(65)},
        ):
            with self.assertRaises(ValueError):
                validate_features(invalid, "feature", 1e9)
        with self.assertRaises(ValueError):
            _metrics({"actors": [], "outcomeFeatures": {"bad-name": 1}}, 101)

    def test_signed_score_is_preview_minus_root_measurement(self):
        actors = [
            dict(
                id=101,
                team=1,
                controlled=True,
                position=[0, 0, 0],
                hp=30,
                max_hp=30,
                armor=0,
                ap=6,
                mp=3,
                wp=2,
            ),
            dict(
                id=-23,
                team=0,
                controlled=False,
                position=[2, 0, 0],
                hp=20,
                max_hp=20,
                armor=0,
                ap=6,
                mp=3,
                wp=1,
            ),
        ]
        root = _metrics(dict(actors=actors, outcomeFeatures={"glyph_control": 12}), 101)
        selected = _metrics(
            dict(actors=actors, outcomeFeatures={"glyph_control": 9}), 101
        )
        score, components, _, _ = evaluate(
            root, selected, 101, DEFAULT_WEIGHTS, {}, {"glyph_control": 2}
        )
        self.assertEqual(components["feature:glyph_control"], -6)
        self.assertEqual(score, -6)

    def test_native_oracle_provider_is_optional_authoritative_and_part_of_identity(
        self,
    ):
        runtime = _runtime()
        provider = lambda source: {"glyph_control": source.feature_value}
        oracle = _oracle(runtime, provider)
        without_provider = _oracle(runtime)
        self.assertEqual(oracle.outcome_features(runtime), {"glyph_control": 12})
        self.assertIs(
            oracle.authorities()["outcomeFeaturesProvider"]["callable"], provider
        )
        self.assertNotEqual(
            oracle.state_identity(runtime), without_provider.state_identity(runtime)
        )
        self.assertIsNone(without_provider.outcome_features(runtime))

        def configured(offset):
            return lambda source: {"glyph_control": source.feature_value + offset}

        first_config = _oracle(runtime, configured(1))
        second_config = _oracle(runtime, configured(2))
        self.assertNotEqual(
            first_config.state_identity(runtime), second_config.state_identity(runtime)
        )

    def test_provider_runtime_mutation_is_rejected(self):
        runtime = _runtime()
        before = encode(runtime)
        identity = _oracle(runtime).state_identity(runtime)

        def mutating_provider(source):
            source.fight.current.hp -= 1
            return {"glyph_control": 1}

        oracle = _oracle(runtime, mutating_provider)
        with self.assertRaisesRegex(
            ValueError, "provider mutated its runtime snapshot"
        ):
            oracle.outcome_features(runtime)
        self.assertEqual(encode(runtime), before)
        self.assertEqual(_oracle(runtime).state_identity(runtime), identity)

    def test_provider_external_capture_mutation_is_detected_on_live_runtime(self):
        runtime = _runtime()

        def mutating_capture(snapshot):
            runtime.fight.current.hp -= 1
            return {"glyph_control": snapshot.feature_value}

        oracle = _oracle(runtime, mutating_capture)
        with self.assertRaisesRegex(
            ValueError, "Native source changed while measuring"
        ):
            oracle.outcome_features(runtime)

    def test_native_session_describe_propagates_only_explicit_provider_measurements(
        self,
    ):
        runtime = _runtime()
        provider = lambda source: {"glyph_control": source.feature_value}
        oracle = _oracle(runtime, provider)
        transport = _Transport()
        session = NativeSession(
            oracle,
            transport,
            None,
            policy={"featureWeights": {"glyph_control": 2}},
            policy_version="features-v1",
            fight_instance_id="fight-features",
        )
        with patch(
            "wakfu_ai.native.native_facings.measure",
            return_value={
                "nativeFacingActorId": 101,
                "nativeFacings": {"-23": "FRONT"},
            },
        ), patch(
            "wakfu_ai.planning.topology_distance.measure",
            return_value={"topologyDistances": {"101": 2}, "topologyCellCount": 3},
        ):
            envelope = session.envelope()
            reply = session.query(
                dict(id="state-1", operation="state", state=session.root)
            )
        self.assertEqual(envelope["root"]["outcomeFeatures"], {"glyph_control": 12})
        self.assertEqual(reply["result"]["outcomeFeatures"], {"glyph_control": 12})
        session.guard()

    def test_native_session_provider_snapshot_mutation_is_rejected_without_source_change(
        self,
    ):
        runtime = _runtime()
        before = encode(runtime)

        def mutating_provider(source):
            source.feature_value += 1
            return {"glyph_control": source.feature_value}

        oracle = _oracle(runtime, mutating_provider)
        session = NativeSession(
            oracle,
            _Transport(),
            None,
            policy={},
            policy_version="features-v1",
            fight_instance_id="fight-features",
        )
        with patch(
            "wakfu_ai.native.native_facings.measure",
            return_value={
                "nativeFacingActorId": 101,
                "nativeFacings": {"-23": "FRONT"},
            },
        ), patch(
            "wakfu_ai.planning.topology_distance.measure",
            return_value={"topologyDistances": {"101": 2}, "topologyCellCount": 3},
        ):
            reply = session.query(
                dict(id="mutating-state", operation="state", state=session.root)
            )
        self.assertFalse(reply["supported"])
        self.assertIn(
            "provider mutated its runtime snapshot", reply["unknownDependencies"][0]
        )
        self.assertEqual(encode(runtime), before)
        session.guard()

    def test_actual_native_session_measurements_reach_v3_search_without_graph_inference(
        self,
    ):
        runtime = _runtime()
        oracle = _oracle(
            runtime, lambda source: {"glyph_control": source.feature_value}
        )
        transport = _Transport()
        session = NativeSession(
            oracle,
            transport,
            None,
            policy={
                "featureWeights": {"glyph_control": 2, "owned_state_progress": 0},
                "limits": {
                    "depth": 1,
                    "beam": 4,
                    "nodes": 32,
                    "budgetMs": 10000,
                    "probeQuantum": 2,
                },
            },
            policy_version="features-v1",
            fight_instance_id="fight-features",
        )
        envelope = session.envelope()
        envelope["operations"] = []  # Isolate native transition feature ranking.

        original_query = session._query

        def one_native_spell(operation, key, request):
            if operation == "repertoire":
                native_metadata = encode({"spells": [{"spellId": 70001, "level": 1}]})
                return {"nativeMetadata": transport.instance(native_metadata)}
            return original_query(operation, key, request)

        session._query = one_native_spell

        def preview(source, action):
            private = deepcopy(source)
            if action["type"] == "cast":
                private.feature_value += 4
            elif action["type"] == "move":
                private.fight.current.position = tuple(action["path"][-1])
                private.fight.current.mp -= 1
            else:
                raise ValueError("unsupported fixture action")
            private.fight.sequence += 1
            return private, (), None

        oracle.preview = preview
        envelope = session.envelope()
        envelope["operations"] = []

        class Store:
            def json(self, digest):
                return deepcopy(transport.graphs[digest])

        coroutine = search(envelope, Store())
        request = next(coroutine)
        with patch(
            "wakfu_ai.native.native_facings.measure",
            return_value={
                "nativeFacingActorId": 101,
                "nativeFacings": {"-23": "FRONT"},
            },
        ), patch(
            "wakfu_ai.planning.topology_distance.measure",
            return_value={"topologyDistances": {"101": 2}, "topologyCellCount": 3},
        ):
            while True:
                try:
                    request = coroutine.send(session.query(request))
                except StopIteration as completed:
                    result = completed.value
                    break
        self.assertEqual(result["action"]["type"], "cast")
        self.assertEqual(result["components"]["feature:glyph_control"], 8)
        self.assertEqual(result["unknownFeatureDependencies"], [])
        session.guard()
