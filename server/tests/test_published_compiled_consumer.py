"""Bounded original records through published views and real owned execution.

The finite publication reader models storage only; all admission, native
callbacks, snapshots, pinning and dispatch remain production implementations.
This is not qualification of the complete published NPC/weapon catalogues.
"""
from copy import copy, deepcopy
import hashlib
import json
import os
import unittest
from unittest.mock import patch


def _bytes(value, *, canonical=False):
    return json.dumps(value, sort_keys=canonical, separators=(",", ":")).encode()


class _OriginalPublication:
    def __init__(self, compiled):
        from wakfu_server.combat_owned_equipment_pin import _plain
        from wakfu_server.combat_original_producer_events import original_output_index

        self.collections, self.readers = {}, []
        self.manifest = dict(
            policy="wakemu.compiled-combat-catalog.v1", collections={}, variants={}
        )
        self.output_index = [
            [key, family, sorted(events)]
            for key, (family, events) in original_output_index(compiled.effects).items()
        ]

        def collection(name, rows, representation):
            raw = {key: _bytes(_plain(value)) for key, value in rows.items()}
            self.collections[name] = raw
            self.manifest["collections"][name] = dict(
                kind="dict",
                representation=representation,
                count=len(raw),
                ordered_keys_sha256=hashlib.sha256(_bytes(list(raw))).hexdigest(),
            )
            return name

        sources = collection(
            "player.source_effects", compiled.source_effects, "native_json"
        )
        effects = collection("player.effects", compiled.effects, "frozen_effect")
        self.manifest["states"] = collection(
            "shared.states", compiled.source_states["states"], "native_json"
        )
        self.manifest["state_effects"] = collection(
            "shared.state_effects", compiled.source_states["effects"], "native_json"
        )
        # Four constructor handles share this bounded original reference. This
        # checks aliases, not the complete four production variant universes.
        self.manifest["original_output_index"] = {}
        for variant in ("player", "npc_imported", "npc_baseline", "weapon"):
            for field, origin in (("source_effects", sources), ("effects", effects)):
                name = variant + "." + field
                self.collections[name] = self.collections[origin]
                self.manifest["collections"][name] = dict(
                    self.manifest["collections"][origin]
                )
            self.manifest["variants"][variant] = dict(
                source_effects=variant + ".source_effects", effects=variant + ".effects"
            )
            self.manifest["original_output_index"][variant] = self.output_index
        self.generation = hashlib.sha256(
            _bytes(self.manifest, canonical=True)
        ).hexdigest()
        self.header = dict(
            self.manifest, generation=self.generation, manifest_sha256=self.generation
        )
        self.digests = {
            name: {key: hashlib.sha256(raw).hexdigest() for key, raw in rows.items()}
            for name, rows in self.collections.items()
        }

    def reader(self, descriptor):
        from wakfu_server.native_compiled_catalog import (
            descriptor_for,
            CompiledBatchLimit,
        )
        from wakfu_server.combat_published_catalogs import (
            validate_static_catalog_descriptor,
        )

        descriptor = validate_static_catalog_descriptor(descriptor)
        name = descriptor["collection"]
        if descriptor != descriptor_for(self.header, name):
            raise ValueError("Original bounded publication descriptor differs")
        publication = self

        class Reader:
            representation = publication.manifest["collections"][name]["representation"]

            def __init__(self):
                self.descriptor = descriptor
                self.iterations = self.record_reads = self.batches = 0
                self.batch_limit = 128

            def __iter__(self):
                self.iterations += 1
                return iter(publication.collections[name])

            def __contains__(self, key):
                return key in publication.collections[name]

            def record_bytes(self, key):
                self.record_reads += 1
                raw = publication.collections[name][key]
                if hashlib.sha256(raw).hexdigest() != publication.digests[name][key]:
                    raise ValueError("Original bounded record SHA256 differs")
                return raw

            def get_many_bytes(self, keys):
                self.batches += 1
                if len(keys) > self.batch_limit:
                    raise CompiledBatchLimit("Bounded source byte batch")
                return {key: self.record_bytes(key) for key in keys}

            def original_output_index(self):
                variant = next(
                    variant
                    for variant, rows in publication.manifest["variants"].items()
                    if rows["effects"] == name
                )
                return deepcopy(publication.manifest["original_output_index"][variant])

        reader = Reader()
        self.readers.append(reader)
        return reader


class PublishedCompiledConsumerTests(unittest.TestCase):
    def test_original_published_views_preserve_owned_replay_and_private_rollback(self):
        from contextlib import ExitStack
        from tools.sublimation_semantic_fixture import build_fixture

        manifest = os.environ.get("WAKFU_PUBLISHED_CONSUMER_MANIFEST")
        if not manifest:
            raise RuntimeError("Original bounded semantic manifest is required")
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(os.environ, WAKFU_COMPILED_CATALOG_BUILD="1")
            )
            saved = {}

            def transform(eager):
                from wakfu_server import spell_audit
                from wakfu_server.combat_static_catalogs import CompiledEffects
                from wakfu_server.combat_published_catalogs import (
                    resolve_static_catalog_descriptor,
                )
                from wakfu_server.native_compiled_catalog import descriptor_for
                from wakfu_server.combat_original_producer_events import (
                    original_output_index,
                )

                publication = _OriginalPublication(eager)
                saved.update(publication=publication, eager=eager)
                stack.enter_context(
                    patch(
                        "wakfu_server.native_compiled_catalog.published_collection",
                        side_effect=publication.reader,
                    )
                )
                stack.enter_context(
                    patch(
                        "wakfu_server.native_compiled_catalog.resolve_publication",
                        return_value=publication.header,
                    )
                )
                state_document = dict(eager.source_states)
                for field, name in (("states", "states"), ("effects", "state_effects")):
                    state_document[field] = resolve_static_catalog_descriptor(
                        descriptor_for(publication.header, publication.manifest[name])
                    )
                stack.enter_context(
                    patch.object(
                        spell_audit, "states_catalog", return_value=state_document
                    )
                )
                for variant in publication.manifest["variants"]:
                    current = CompiledEffects.from_published(variant)
                    self.assertIs(current.source_states, state_document)
                current = CompiledEffects.from_published()
                self.assertEqual(tuple(current.effects), tuple(eager.effects))
                self.assertEqual(dict(current.effects), dict(eager.effects))
                self.assertEqual(
                    original_output_index(current.effects),
                    original_output_index(eager.effects),
                )
                source_key = next(iter(current.source_effects))
                raw = current.source_effects[source_key]
                self.assertIsInstance(raw["parameters"], list)
                raw["parameters"].append(123456)
                self.assertNotEqual(raw, current.source_effects[source_key])
                frozen_key = next(iter(current.effects))
                held = current.effects[frozen_key]
                import wakfu_server.combat_published_catalogs as published

                with patch.object(published, "_HOT_MAX_ENTRIES", 1):
                    for other_key in current.effects:
                        identity = (publication.generation, "player.effects", other_key)
                        if (
                            other_key != frozen_key
                            and identity not in published._HOT_ROWS
                        ):
                            current.effects[other_key]
                            break
                    self.assertNotIn(
                        (publication.generation, "player.effects", frozen_key),
                        published._HOT_ROWS,
                    )
                    self.assertIs(current.effects[frozen_key], held)
                self.assertIs(deepcopy(current.effects), current.effects)
                # Key-only iteration must not read a single definition.
                reads = sum(reader.record_reads for reader in publication.readers)
                tuple(current.source_effects)
                self.assertEqual(
                    reads, sum(reader.record_reads for reader in publication.readers)
                )
                # The reader's typed capacity exception splits only batches;
                # malformed source/authority errors must still propagate.
                current.source_effects._reader.batch_limit = 3
                self.assertEqual(
                    dict(current.source_effects.items()), dict(eager.source_effects)
                )
                bad = deepcopy(current.source_effects[source_key])
                bad["criteria"] = "False"
                with self.assertRaisesRegex(ValueError, "Conflicting native"):
                    current.with_effect_sources({source_key: bad})
                return current

            fixture = build_fixture(27159, manifest, compiled_transform=transform)
            from wakfu_server import combat_server_spell
            from wakfu_server.combat_static_catalogs import DefinitionOverlay
            from wakfu_server.combat_effect_dispatch import EffectInvocation
            from wakfu_server.combat_execution_context import (
                constructed_execution_context,
            )
            from wakfu_server.combat_random_transaction import rollback_external_rng
            from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids
            from wakfu_server.fight_checkpoint_store import snapshot

            publication = saved["publication"]
            # Keep fresh state composition/pin authority, not a metadata-only
            # fake factory. This is the same caller used by production previews.
            stack.enter_context(
                patch.object(
                    combat_server_spell,
                    "compiled_runtime_catalog",
                    return_value=fixture.compiled,
                )
            )
            source = fixture.fight
            before = snapshot(source)
            rng = fixture.factory.transaction_rng
            rng_before = rng.getstate()
            context = constructed_execution_context().payload().hex()

            @rollback_external_rng
            def execute(*, reject, rng):
                preview = deepcopy(source)
                dispatcher, packets = fixture.dispatcher_for(preview)
                target = next(
                    actor for actor in preview.actors.values() if not actor.controlled
                )
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            fixture.damage_reference,
                            1,
                            7,
                            target.id,
                            target.position,
                            native_context_hex=context,
                            native_explicit_target=True,
                            native_retained_container={"present": False},
                        )
                    )
                )
                if reject:
                    raise ValueError("Discard published original preview")
                return preview, dispatcher, packets

            with self.assertRaisesRegex(ValueError, "Discard published"):
                execute(reject=True, rng=rng)
            self.assertEqual(snapshot(source), before)
            self.assertEqual(rng.getstate(), rng_before)
            fight, dispatcher, packets = execute(reject=False, rng=rng)
            self.assertTrue(packets)
            carrier = next(
                state
                for state in fight.actors[7].state_ledger.entries
                if state.reference == 6035
            )
            self.assertEqual(carrier.caster_id, -200)
            self.assertNotIn(carrier.uid, qualified_npc_uids(dispatcher))
            # Empty private deltas preserve the real owned factory and never
            # enumerate a remote definition population.
            private = copy(fixture.factory)
            private.effects = DefinitionOverlay(private.effects, {})
            iterations = sum(reader.iterations for reader in publication.readers)
            private(fight, fixture.plan)
            self.assertEqual(
                iterations, sum(reader.iterations for reader in publication.readers)
            )
            # Native point tampering anywhere in a private delta rejects before
            # changing the fight, including refs unrelated to equipped roots.
            point = next(
                key
                for key, row in saved["eager"].effects.items()
                if row.get("area_class") in ("anE", "anJ")
            )
            changed = dict(
                fixture.compiled.effects[point], native_area_points=[[987654, 987654]]
            )
            private = copy(fixture.factory)
            private.effects = DefinitionOverlay(private.effects, {point: changed})
            checkpoint = snapshot(fight)
            with self.assertRaisesRegex(
                ValueError, "Conflicting native point area offsets"
            ):
                private(fight, fixture.plan)
            self.assertEqual(snapshot(fight), checkpoint)
            self.assertEqual(snapshot(source), before)
