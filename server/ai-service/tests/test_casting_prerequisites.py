"""Pure validation for native casting-root no-action certificates."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
for _path in (str(_ROOT / "server"), str(_ROOT / "server" / "ai-service")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.bridge.world_bridge import NativeSession
from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.planning.casting_prerequisites import (
    all_owned_spells_unavailable,
    certified_unavailable_spell_keys,
)


class CastingPrerequisiteTests(unittest.TestCase):
    def test_npc_certificate_uses_baseline_level_roots_and_fails_open(self):
        oracle = object.__new__(NativeOracle)
        actor_id = -77
        oracle.characters = {}
        oracle.monsters = {actor_id: {"id": actor_id}}
        oracle.owned_spells = lambda fight, identity: {
            100: 1,
            200: 0,
            300: 1,
            400: 1,
        }
        fight = SimpleNamespace(
            actors={actor_id: SimpleNamespace(id=actor_id, hp=20)},
            native_summon_registrations={},
            sequence=13,
        )
        casting = {
            "100": {
                "levels": [[1, 0, [81, 82]]],
                "conditional": [{"levels": [[2, 0, [999]]]}],
            },
            "300": {"levels": [[1, 0, [83]]]},
        }
        roots = {
            "roots": {
                "81": {"native_casting_collision_area": None},
                "83": {"native_casting_collision_area": None},
            }
        }
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value=casting,
        ), patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value=roots,
        ):
            result = oracle.native_casting_root_prerequisites(
                fight, actor_id, "state-13"
            )

        self.assertEqual(
            result,
            dict(
                schema="native-casting-root-prerequisites-v1",
                sourceState="state-13",
                actorId=actor_id,
                stateRevision=13,
                complete=True,
                unavailable=[
                    dict(
                        spellId=100,
                        level=1,
                        reason="missing_root_metadata",
                        missingRootIds=[82],
                    ),
                    dict(
                        spellId=400,
                        level=1,
                        reason="missing_casting_table",
                        missingRootIds=[],
                    ),
                ],
            ),
        )
        oracle.characters = {actor_id: {"id": actor_id}}
        self.assertIsNone(
            oracle.native_casting_root_prerequisites(fight, actor_id, "state-13")
        )

    def test_unknown_casting_rows_are_omitted_from_certificate(self):
        oracle = object.__new__(NativeOracle)
        actor_id = -78
        oracle.characters = {}
        oracle.monsters = {actor_id: {"id": actor_id}}
        oracle.owned_spells = lambda fight, identity: {400: 1}
        fight = SimpleNamespace(
            actors={actor_id: SimpleNamespace(id=actor_id, hp=20)},
            native_summon_registrations={},
            sequence=14,
        )
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"400": {"levels": "future-schema"}},
        ), patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": {"1": {}}},
        ):
            result = oracle.native_casting_root_prerequisites(
                fight, actor_id, "state-14"
            )

        self.assertEqual(result["unavailable"], [])
        self.assertIs(result["complete"], True)

    def test_repertoire_attaches_certificate_and_skips_only_useless_range_scan(self):
        actor_id, source_state = -80, "state-root"
        runtime = SimpleNamespace(
            fight=SimpleNamespace(current=SimpleNamespace(id=actor_id), sequence=20),
            action_id=3,
        )
        certificate = dict(
            schema="native-casting-root-prerequisites-v1",
            sourceState=source_state,
            actorId=actor_id,
            stateRevision=20,
            complete=True,
            unavailable=[
                dict(
                    spellId=500,
                    level=1,
                    reason="missing_root_metadata",
                    missingRootIds=[901],
                )
            ],
        )

        class Oracle:
            def __init__(self):
                self.runtime = runtime
                self.range_calls = 0

            def owned_spells(self, fight, identity):
                return {500: 1}

            def native_casting_root_prerequisites(
                self, fight, identity, *, source_state, owned_spells
            ):
                self.asserted_owned = owned_spells
                return certificate

            def native_target_envelope(self, fight, identity, *, action_id):
                self.range_calls += 1
                return {"unexpected": True}

        class Transport:
            def instance(self, encoded):
                self.encoded = encoded
                return "catalog-blob"

        oracle, transport = Oracle(), Transport()
        session = object.__new__(NativeSession)
        session.oracle = oracle
        session.transport = transport
        session.states = {source_state: runtime}
        session.native_query_metrics = {}
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"500": {"levels": [[1, 0, [901]]]}},
        ), patch(
            "wakfu_server.spell_audit.catalog",
            return_value={"spells": {500: {"reference": 500}}},
        ), patch(
            "wakfu_server.spells.SPELLS", {500: {"id": 500}}
        ):
            result = session._query_unmeasured(
                "repertoire",
                source_state,
                {"id": "1", "state": source_state, "actorId": actor_id},
            )

        metadata = NativeGraph(transport.encoded).plain(transport.encoded["root"])
        self.assertEqual(result, {"nativeMetadata": "catalog-blob"})
        self.assertEqual(oracle.asserted_owned, {500: 1})
        self.assertEqual(oracle.range_calls, 0)
        self.assertEqual(len(metadata["spells"]), 1)
        self.assertEqual(metadata["nativeCastingPrerequisites"], certificate)
        self.assertNotIn("nativeTargetEnvelope", metadata)

    def test_shared_validator_is_state_bound_and_fail_open(self):
        state = {"key": "state-a", "stateRevision": 8}
        spell = {"spellId": 600, "level": 2, "casting": {"levels": []}}
        certificate = dict(
            schema="native-casting-root-prerequisites-v1",
            sourceState="state-a",
            actorId=-90,
            stateRevision=8,
            complete=True,
            unavailable=[
                dict(
                    spellId=600,
                    level=2,
                    reason="missing_root_metadata",
                    missingRootIds=[999],
                )
            ],
        )
        repertoire = dict(spells=[spell], nativeCastingPrerequisites=certificate)
        self.assertEqual(
            certified_unavailable_spell_keys(repertoire, state, -90), {(600, 2)}
        )
        self.assertTrue(all_owned_spells_unavailable(repertoire, state, -90))
        null_table = dict(spells=[dict(spellId=601, level=1, casting=None)])
        self.assertEqual(
            certified_unavailable_spell_keys(null_table, state, -90), set()
        )
        self.assertFalse(all_owned_spells_unavailable(null_table, state, -90))
        for stale_state in (
            dict(state, key="state-b"),
            dict(state, stateRevision=9),
        ):
            self.assertEqual(
                certified_unavailable_spell_keys(repertoire, stale_state, -90),
                set(),
            )
            self.assertFalse(all_owned_spells_unavailable(repertoire, stale_state, -90))
        future = dict(
            repertoire,
            nativeCastingPrerequisites=dict(certificate, schema="future-v2"),
        )
        self.assertEqual(certified_unavailable_spell_keys(future, state, -90), set())
        malformed = dict(
            repertoire,
            spells=[dict(spellId=[600], level=2)],
        )
        self.assertEqual(certified_unavailable_spell_keys(malformed, state, -90), set())

    def test_repertoire_without_npc_certificate_keeps_optional_range_scan(self):
        actor_id, source_state = 7, "pc-state"
        runtime = SimpleNamespace(
            fight=SimpleNamespace(current=SimpleNamespace(id=actor_id), sequence=4),
            action_id=1,
        )

        class Oracle:
            def __init__(self):
                self.runtime = runtime
                self.range_calls = 0

            def owned_spells(self, fight, identity):
                return {500: 1}

            def native_casting_root_prerequisites(self, *args, **kwargs):
                return None

            def native_target_envelope(self, fight, identity, *, action_id):
                self.range_calls += 1
                return {"maximum": 3}

        class Transport:
            def instance(self, encoded):
                self.encoded = encoded
                return "pc-catalog-blob"

        oracle, transport = Oracle(), Transport()
        session = object.__new__(NativeSession)
        session.oracle = oracle
        session.transport = transport
        session.states = {source_state: runtime}
        session.native_query_metrics = {}
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"500": {"levels": [[1, 0, [901]]]}},
        ), patch(
            "wakfu_server.spell_audit.catalog",
            return_value={"spells": {"500": {"reference": 500}}},
        ), patch(
            "wakfu_server.spells.SPELLS", {500: {"id": 500}}
        ):
            session._query_unmeasured(
                "repertoire",
                source_state,
                {"id": "2", "state": source_state, "actorId": actor_id},
            )

        metadata = NativeGraph(transport.encoded).plain(transport.encoded["root"])
        self.assertEqual(oracle.range_calls, 1)
        self.assertNotIn("nativeCastingPrerequisites", metadata)
        self.assertEqual(metadata["nativeTargetEnvelope"], {"maximum": 3})


if __name__ == "__main__":
    unittest.main()
