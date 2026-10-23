"""Static catalogue reuse never freezes current spell ownership or certificates."""
import unittest
from types import ModuleType
from unittest.mock import patch

from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.native.repertoire_metadata import SpellMetadataCache


class SpellMetadataCacheTests(unittest.TestCase):
    def test_static_templates_share_only_the_same_turn_catalogue_scope(self):
        from test_native_session import make_runtime, StubOracle, StubTransport
        from wakfu_ai.bridge.world_bridge import NativeSession, turn_catalogue_scope

        runtime, transport, exporter = make_runtime(), StubTransport(), object()
        builds = []

        def session(catalog=None):
            return NativeSession(
                StubOracle(runtime),
                transport,
                exporter,
                policy={},
                policy_version="test",
                fight_instance_id="test",
                catalog_manifest=catalog,
            )

        def record(spell, level):
            builds.append((spell, level))
            return dict(spellId=spell, level=level)

        with turn_catalogue_scope():
            first = session()
            first._spell_metadata_cache.rows({1: 1}, record)
            second = session()
            second._spell_metadata_cache.rows({1: 1}, record)
            self.assertIs(first._spell_metadata_cache, second._spell_metadata_cache)
            different_catalog = session("d" * 64)
            self.assertIsNot(
                first._spell_metadata_cache, different_catalog._spell_metadata_cache
            )
            different_catalog._spell_metadata_cache.rows({1: 1}, record)
        outside = session()
        self.assertIsNot(first._spell_metadata_cache, outside._spell_metadata_cache)
        outside._spell_metadata_cache.rows({1: 1}, record)
        self.assertEqual(builds, [(1, 1), (1, 1), (1, 1)])

    def test_real_session_reuses_static_rows_but_rebuilds_state_certificates(self):
        from test_native_session import make_runtime, StubOracle, StubTransport
        from wakfu_ai.bridge.world_bridge import NativeSession
        from wakfu_ai.context.native_context import NativeGraph

        runtime, transport = make_runtime(), StubTransport()
        oracle = StubOracle(runtime)
        oracle.owned_spells = lambda fight, actor_id: (
            {1: 1} if fight.current.position[0] == 0 else {1: 1, 2: 1}
        )
        certificates, envelopes, static_builds = [], [], []

        def prerequisites(fight, actor_id, source_state, **kwargs):
            certificates.append(source_state)
            return dict(
                schema="native-casting-root-prerequisites-v1",
                sourceState=source_state,
                actorId=actor_id,
                stateRevision=fight.sequence,
                complete=True,
                unavailable=[],
            )

        def bounds(fight, actor_id, **kwargs):
            envelopes.append(tuple(fight.current.position))
            return dict(origin=list(fight.current.position), futureField="retained")

        oracle.native_casting_root_prerequisites = prerequisites
        oracle.native_target_envelope = bounds
        casting, effects, inventory = (
            ModuleType(name) for name in ("casting", "effects", "inventory")
        )
        casting.catalog = lambda: {str(i): dict(futureCasting=i) for i in (1, 2)}
        effects.catalog = lambda: dict(
            spells={str(i): dict(futureDefinition=i) for i in (1, 2)}
        )
        inventory.SPELLS = {i: dict(futureInventory=i) for i in (1, 2)}

        def advisory(spell, level):
            static_builds.append((spell, level))
            return dict(spellId=spell, level=level, tags=["damage"])

        modules = {
            "wakfu_server.combat_native_spell_casting": casting,
            "wakfu_server.spell_audit": effects,
            "wakfu_server.spells": inventory,
        }
        with patch.dict("sys.modules", modules), patch(
            "wakfu_ai.bridge.world_bridge._advisory_spell_capabilities", advisory
        ):
            session = NativeSession(
                oracle,
                transport,
                object(),
                policy={},
                policy_version="test",
                fight_instance_id="test",
            )

            def book(key, query_id):
                reply = session.query(
                    dict(id=query_id, operation="repertoire", state=key, actorId=101)
                )
                graph = NativeGraph(transport.graphs[reply["result"]["nativeMetadata"]])
                return graph.plain(graph.data["root"])

            first = book(session.root, "first")
            again = book(session.root, "again")
            private, _, _ = oracle.preview(
                session.states[session.root], dict(type="move", path=[[1, 0, 0]])
            )
            moved_key = session.register(private)
            changed = book(moved_key, "changed")
        self.assertEqual(first, again)
        self.assertEqual(static_builds, [(1, 1), (2, 1)])
        self.assertEqual(certificates, [session.root, session.root, moved_key])
        self.assertEqual(envelopes, [(0, 0, 0), (0, 0, 0), (1, 0, 0)])
        self.assertEqual([row["spellId"] for row in changed["spells"]], [1, 2])
        self.assertEqual(
            changed["nativeCastingPrerequisites"]["sourceState"], moved_key
        )

    def test_static_records_are_built_once_but_ownership_and_level_stay_current(self):
        calls = []

        def build(spell, level):
            calls.append((spell, level))
            return dict(spellId=spell, level=level, casting=dict(costs=[level]))

        cache = SpellMetadataCache()
        cache.rows({1: 1, 2: 1}, build)
        self.assertEqual(
            cache.rows({1: 1}, build),
            [dict(spellId=1, level=1, casting=dict(costs=[1]))],
        )
        cache.rows({1: 2}, build)
        self.assertEqual(calls, [(1, 1), (2, 1), (1, 2)])
        self.assertEqual(cache.rows({}, build), [])

    def test_builder_input_and_returned_rows_cannot_poison_the_cache(self):
        source = dict(spellId=1, level=1, opaqueFuture=dict(values=[1]))
        cache = SpellMetadataCache()
        first = cache.rows({1: 1}, lambda *_: source)
        source["opaqueFuture"]["values"].append(2)
        first[0]["opaqueFuture"]["values"].append(3)
        self.assertEqual(
            cache.rows({1: 1}, lambda *_: self.fail("Unexpected rebuild")),
            [dict(spellId=1, level=1, opaqueFuture=dict(values=[1]))],
        )

    def test_session_catalogue_changes_never_share_records(self):
        one, two = SpellMetadataCache(), SpellMetadataCache()
        self.assertEqual(
            one.rows({1: 1}, lambda *_: dict(version=1)), [dict(version=1)]
        )
        self.assertEqual(
            two.rows({1: 1}, lambda *_: dict(version=2)), [dict(version=2)]
        )

    def test_entry_and_memory_caps_evict_or_skip_without_dropping_metadata(self):
        calls = []

        def build(spell, level):
            calls.append(spell)
            return dict(spellId=spell, payload="full" * 100)

        small = SpellMetadataCache(max_entries=1)
        for spell in (1, 2, 1):
            small.rows({spell: 1}, build)
        self.assertEqual(calls, [1, 2, 1])
        limited = SpellMetadataCache(max_bytes=32)
        first = limited.rows({3: 1}, build)
        second = limited.rows({3: 1}, build)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["payload"], "full" * 100)
        self.assertEqual(calls[-2:], [3, 3])

    def test_cache_hit_does_not_bypass_the_owner_deadline(self):
        cache = SpellMetadataCache()
        cache.rows({1: 1}, lambda *_: dict(spellId=1))
        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            now[0] = 2.0
            with self.assertRaises(TimeoutError):
                cache.rows({1: 1}, lambda *_: self.fail("Unexpected rebuild"))


if __name__ == "__main__":
    unittest.main()
