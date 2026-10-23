"""Native preparation measurements survive the zero-to-positive search boundary."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_SERVICE = Path(__file__).resolve().parents[1]
for _path in (str(_SERVICE), str(_SERVICE.parents[1] / "server")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.bridge.world_bridge import NativeSession, _json_bytes
from wakfu_ai.context.native_context import encode
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.planning.query_search import search


class _Transport:
    def __init__(self):
        self.graphs = {}

    def catalog(self, exporter):
        return "c" * 64

    def instance(self, graph):
        digest = hashlib.sha256(_json_bytes(graph)).hexdigest()
        self.graphs[digest] = deepcopy(graph)
        return digest

    def json(self, digest):
        return deepcopy(self.graphs[digest])


def _fixture():
    def actor(identity, team, position, controlled):
        return SimpleNamespace(
            id=identity,
            team=team,
            position=position,
            controlled=controlled,
            hp=20,
            max_hp=20,
            ap=6,
            mp=0,
            direction=0,
            effect_stats={4: 0, 97: 0},
            state_ledger=SimpleNamespace(entries=[]),
        )

    npc, player = actor(-23, 0, (0, 0, 0), False), actor(101, 1, (1, 0, 0), True)
    runtime = SimpleNamespace(
        fight=SimpleNamespace(
            id=88,
            phase="active",
            current=npc,
            actors={npc.id: npc, player.id: player},
            turn_id=1,
            sequence=1,
            walkable=frozenset({npc.position, player.position}),
            edges=frozenset(),
        ),
        action_id=1,
        awaiting_ack=None,
        pending=[],
    )
    oracle = NativeOracle(
        runtime,
        characters={101: {"id": 101}},
        monsters={-23: {"id": -23}},
        decks={101: {}},
        excluded_decks={101: frozenset()},
        viewer_id=101,
        flags={},
    )
    # Native progress still parses the actual casting criterion and first-entry
    # ledger. Only catalog I/O and unrelated geometry/factory setup are isolated.
    oracle.owned_spells = lambda fight, actor_id=None: {70001: 1, 70002: 1}
    oracle.observation_properties = lambda source: {}
    oracle.unobserved_areas = lambda source: frozenset()
    return runtime, oracle


_CASTING = {"70002": {"cast_criterion_raw": "GetStateLevel(1234)>=3"}}


class OwnedProgressZeroBaselineTests(unittest.TestCase):
    @patch("wakfu_server.combat_native_spell_casting.catalog", return_value=_CASTING)
    def test_native_measurement_retains_zero_and_caps_actual_first_entry(self, catalog):
        runtime, oracle = _fixture()
        before = encode(runtime)
        self.assertEqual(oracle.outcome_features(runtime), {"owned_state_progress": 0})
        self.assertEqual(encode(runtime), before)
        runtime.fight.current.state_ledger.entries.extend(
            [
                SimpleNamespace(reference=1234, level=1),
                SimpleNamespace(reference=1234, level=9),
            ]
        )
        self.assertEqual(oracle.outcome_features(runtime), {"owned_state_progress": 1})
        runtime.fight.current.state_ledger.entries[0].level = 9
        self.assertEqual(oracle.outcome_features(runtime), {"owned_state_progress": 3})

    @patch("wakfu_server.combat_native_spell_casting.catalog", return_value=_CASTING)
    def test_native_session_search_rewards_first_preparation_from_zero(self, catalog):
        runtime, oracle = _fixture()
        transport = _Transport()

        # Model just the producer's native result. Search, NativeSession and the
        # outcome measurement remain production implementations; this test does
        # not claim qualification of a particular spell's native effect chain.
        def preview(source, action):
            if (
                action.get("type") != "cast"
                or action.get("spellId") != 70001
                or action.get("targetId") != -23
                or source.fight.current.ap < 3
            ):
                raise ValueError("Fixture supports only the preparation cast")
            private = deepcopy(source)
            private.fight.current.ap -= 3
            private.fight.current.state_ledger.entries.append(
                SimpleNamespace(reference=1234, level=1)
            )
            private.fight.sequence += 1
            return private, (), None

        oracle.preview = preview
        with patch(
            "wakfu_ai.bridge.actor_repertoires.actor_repertoires", return_value={}
        ), patch(
            "wakfu_ai.native.native_facings.measure",
            return_value={
                "nativeFacingActorId": -23,
                "nativeFacings": {"101": "FRONT"},
            },
        ), patch(
            "wakfu_ai.planning.topology_distance.measure",
            return_value={
                "topologyDistances": {"-23": 1, "101": 1},
                "topologyCellCount": 2,
            },
        ):
            session = NativeSession(
                oracle,
                transport,
                None,
                policy={
                    "limits": {"depth": 1, "beam": 4, "nodes": 32, "budgetMs": 10000}
                },
                policy_version="preparation-zero-v1",
                fight_instance_id="preparation-zero",
            )
            original_query = session._query

            def repertoire(operation, key, request):
                if operation == "repertoire":
                    metadata = encode({"spells": [{"spellId": 70001, "level": 1}]})
                    return {"nativeMetadata": transport.instance(metadata)}
                return original_query(operation, key, request)

            session._query = repertoire
            envelope = session.envelope()
            envelope["operations"] = []
            before = encode(runtime)
            coroutine = search(envelope, transport)
            request = next(coroutine)
            while True:
                try:
                    request = coroutine.send(session.query(request))
                except StopIteration as completed:
                    decision = completed.value
                    break
            session.guard()
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(decision["action"]["spellId"], 70001)
        self.assertEqual(
            envelope["root"]["outcomeFeatures"], {"owned_state_progress": 0}
        )
        self.assertEqual(decision["components"]["feature:owned_state_progress"], 1)
        self.assertEqual(decision["unknownFeatureDependencies"], [])
        self.assertEqual(encode(runtime), before)


if __name__ == "__main__":
    unittest.main()
