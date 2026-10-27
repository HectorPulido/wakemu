"""NPC source custody at reconstructed round/wave boundaries, including gear.

The first component uses genuine5295 initialization and native terrain. The
second preserves an actual owned item pin and declares original304313 as an
NPC source-program input; it does not claim5525 originally owns that spell.
Only immutable metadata readers receive the verified bounded compiled closure.
"""
from contextlib import ExitStack
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch


class RiftNpcRoundWaveProducerTests(unittest.TestCase):
    def test_original_npc_managed_round_wave_and_mixed_equipment_retry_rollback(self):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server import combat_server_spell, combat_npc_attack, spell_audit
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.combat_effect_runtime import _merge_effects
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_equipment_external_events import (
            deliver_completed_round,
        )
        from wakfu_server.combat_equipment_wave_events import deliver_registered_wave
        from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import default_deck
        from wakfu_server.wire import proto_field
        from wakfu_server.rift_npc_creation import (
            install_native_wave,
        )
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from rift_native_flow_fixture import build_flow_fixture
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from tools.sublimation_semantic_fixture import build_fixture
        from wakfu_server.combat_owned_equipment_factory import _compiled_sources

        manifest = os.environ.get("WAKFU_RIFT_NPC_PRODUCER_MANIFEST")
        if not manifest:
            raise RuntimeError(
                "Explicit NPC round/wave closed source manifest required"
            )
        mode = os.environ.get("WAKFU_RIFT_NPC_PRODUCER_MODE", "full")
        if mode not in ("full", "rebind_only"):
            raise ValueError("Unknown strict NPC producer qualification selector")
        if mode == "rebind_only":
            return self._real_equipment_rebind_witness(manifest)
        dataset = BoundedDataset(manifest)
        dataset.install_catalog_backend()
        effects = _merge_effects(
            dataset.closure["effects"],
            dataset.read(dataset.manifest["semantic"]["extra_effects"]),
        )
        states = {
            **dataset.states["states"],
            **dataset.read(dataset.manifest["semantic"]["extra_states"])["states"],
        }
        compiled = CompiledEffects(effects, dict(states=states, effects=effects))
        registry = {"effects": dataset.closure["registry"]}
        class_catalog = dataset.read(dataset.manifest["rift_player_class_catalog"])
        roots = dataset.read(dataset.manifest["rift_casting_root_catalog"])
        from wakfu_server import combat_casting_context

        context = constructed_execution_context().payload().hex()

        def has_state(fight, identity, reference):
            return any(
                row.reference == reference
                for row in fight.actors[identity].state_ledger.entries
            )

        def round_component(fight, dispatcher_for, rng, *, mixed):
            dispatcher, _ = dispatcher_for(fight)
            self.assertEqual(
                any(
                    row.get("sources")
                    for row in getattr(
                        fight, "native_owned_equipment_initializations", {}
                    ).values()
                ),
                mixed,
            )
            self.assertEqual(deliver_completed_round(dispatcher), ())
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        304313,
                        1,
                        next(
                            uid
                            for uid, actor in fight.actors.items()
                            if not actor.controlled
                        ),
                        7,
                        fight.actors[7].position,
                        native_context_hex=context,
                        native_explicit_target=True,
                        native_retained_container={"present": False},
                    )
                )
            )
            self.assertTrue(has_state(fight, 7, 6849))
            dispatcher.native_retention.synchronize()
            entries = dispatcher.native_retention.view().entries
            with patch.object(dispatcher, "native_clone_authority", object()):
                self.assertEqual(qualified_npc_uids(dispatcher), frozenset())
            eligible = qualified_npc_uids(dispatcher)
            self.assertTrue(
                any(row.uid in eligible and row.manager_id == 7 for row in entries)
            )
            before, rng_before = snapshot(fight), rng.getstate()

            @rollback_external_rng
            def complete(*, reject, rng):
                preview = deepcopy(fight)
                # This is an actual SU lifecycle component, not a paid END claim.
                start_round = preview.native_timeline_round
                while preview.native_timeline_round == start_round:
                    preview._advance()
                live, packets = dispatcher_for(preview)
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=256
                ):
                    deliver_completed_round(live)
                self.assertFalse(has_state(preview, 7, 6849))
                self.assertTrue(
                    any(
                        row.get("effect_reference") == 316100
                        and row.get("status") == "completed"
                        for row in trace
                    )
                )
                accepted, outbox = snapshot(preview), tuple(packets)
                self.assertEqual(deliver_completed_round(live), ())
                self.assertEqual(snapshot(preview), accepted)
                self.assertEqual(tuple(packets), outbox)
                if reject:
                    raise ValueError("rejected unpublished completed round")
                return preview

            with self.assertRaisesRegex(ValueError, "unpublished"):
                complete(reject=True, rng=rng)
            self.assertEqual(snapshot(fight), before)
            self.assertEqual(rng.getstate(), rng_before)
            gc.collect()
            accepted = complete(reject=False, rng=rng)
            self.assertTrue(
                accepted.native_equipment_completed_rounds[
                    str(accepted.native_timeline_round - 1)
                ]["delivered"]
            )
            self.assertEqual(snapshot(fight), before)
            return accepted

        with ExitStack() as readers:
            for module, name, value in (
                (spell_audit, "states_catalog", compiled.source_states),
                (spell_audit, "catalog", class_catalog),
                (combat_server_spell, "catalog", class_catalog),
                (combat_server_spell, "states_catalog", compiled.source_states),
                (combat_server_spell, "compiled_runtime_catalog", compiled),
                (combat_npc_attack, "npc_runtime_catalog", compiled),
                (combat_casting_context, "casting_root_catalog", roots),
            ):
                readers.enter_context(patch.object(module, name, return_value=value))
            migration = next(
                (Path(__file__).resolve().parents[1] / "migrations").glob("090_*.sql")
            )
            catalogs = next(
                value
                for text in re.findall(r"'({.*})'::jsonb", migration.read_text())
                for value in [json.loads(text)]
                if "37" in value
            )
            component_catalog = deepcopy(catalogs["37"])
            component_catalog["species_refs"] = [5295]
            # A declared one-species source component, not the full native pool.
            run = dict(
                catalog=component_catalog,
                policy=NativeRiftCarrierComponentTests.policy(),
                seed="npc-round-wave",
                instance_id=37,
                wave=1,
            )
            aptitudes = proto_field(24, (1 << 64) - 1) + proto_field(
                34, proto_field(8, 20) + proto_field(16, 2)
            )
            character = effective_character(
                dict(
                    id=7,
                    account_id=3,
                    breed=1,
                    sex=False,
                    level=100,
                    real_level=100,
                    map_id=run["catalog"]["map_id"],
                    instance_id=37,
                    x=0,
                    y=0,
                    z=0,
                    hp=maximum(1, 100),
                    inventory_items=[],
                    active_build_index=0,
                    builds={
                        0: dict(
                            equipment="",
                            sheet=proto_field(24, 0xFFFFFFFF).hex(),
                            aptitudes=aptitudes.hex(),
                        )
                    },
                )
            )
            character["hp"] = character["max_hp"]
            character["builds"][0]["deck"] = default_deck(character).hex()
            component = build_flow_fixture(
                character,
                run,
                10041048,
                (-200, -201),
                (5295, 5295),
                compiled=compiled,
                registry=registry,
            )
            fight, _ = combat_server_spell.prepare_server_initialization(
                component.character,
                component.fight.rift_monsters,
                component.fight,
                3,
                component.decks[7],
                action_id=1,
                rng=component.rng,
                fight_start=True,
                player_characters=component.characters,
                deck_blobs=component.decks,
            )
            component.fight = fight
            accepted = round_component(
                fight, component.factory, component.rng, mixed=False
            )
            self.assertFalse(
                any(
                    row.get("sources")
                    for row in getattr(
                        accepted, "native_owned_equipment_initializations", {}
                    ).values()
                )
            )
            wave_before, rng_before = snapshot(accepted), component.rng.getstate()

            @rollback_external_rng
            def next_wave(*, reject, rng):
                preview = deepcopy(accepted)
                for uid in tuple(preview.rift_wave_state["wave_actor_ids"]):
                    preview.apply_effect_damage(7, uid, preview.actors[uid].hp)
                self.assertIsNotNone(preview.rift_wave_state["pending_wave"])
                occupied = {
                    actor.position
                    for actor in preview.actors.values()
                    if preview._in_play(actor)
                }
                cells = sorted(set(preview.walkable) - occupied)
                from wakfu_server.rift_policy import select_wave
                from wakfu_server.monsters import owned_instance, reference

                references = select_wave(run["catalog"], run["policy"], run["seed"], 2)
                born = [
                    owned_instance(
                        ref,
                        reference(ref)["min_level"],
                        -300 - index,
                        map_id=run["catalog"]["map_id"],
                        instance_id=37,
                        x=cells[index][0],
                        y=cells[index][1],
                        z=cells[index][2],
                        team=1,
                    )
                    for index, ref in enumerate(references)
                ]
                preview.rift_monsters.update({row["id"]: row for row in born})
                observed = []

                def initialize(current, actors, monsters):
                    live, packets = component.factory(current)
                    with combat_diagnostic_scope(
                        lambda **row: observed.append(row), limit=512
                    ):
                        deliver_registered_wave(
                            live, actors=actors, monsters=monsters, player_ids=(7,)
                        )
                    checkpoint, outbox = snapshot(current), tuple(packets)
                    self.assertEqual(
                        deliver_registered_wave(
                            live, actors=actors, monsters=monsters, player_ids=(7,)
                        ),
                        (),
                    )
                    self.assertEqual(snapshot(current), checkpoint)
                    self.assertEqual(tuple(packets), outbox)
                    if reject:
                        raise ValueError("rejected unpublished NPC wave")
                    return tuple(packets)

                install_native_wave(
                    preview,
                    born,
                    initialize_actor=lambda *_: (),
                    initialize_wave=initialize,
                )
                self.assertTrue(
                    any(
                        row.get("effect_reference") == 318546
                        and row.get("status") == "completed"
                        for row in observed
                    )
                )
                return preview

            with self.assertRaisesRegex(ValueError, "unpublished NPC wave"):
                next_wave(reject=True, rng=component.rng)
            self.assertEqual(snapshot(accepted), wave_before)
            self.assertEqual(component.rng.getstate(), rng_before)
            gc.collect()
            preview = next_wave(reject=False, rng=component.rng)
            self.assertEqual(preview.rift_wave_state["wave"], 2)
            del preview, accepted, fight, component
        del compiled, effects, states
        _compiled_sources.cache_clear()
        gc.collect()

        # A genuine item custody proof must coexist with NPC-hosted sources;
        # no invented equipment marker or eligible-UID override is accepted.
        gear = build_fixture(27126, manifest)
        with patch.object(
            combat_server_spell, "compiled_runtime_catalog", return_value=gear.compiled
        ):
            accepted = round_component(
                gear.fight,
                gear.dispatcher_for,
                gear.factory.transaction_rng,
                mixed=True,
            )
            self.assertEqual(
                accepted.native_owned_equipment_initializations,
                gear.fight.native_owned_equipment_initializations,
            )

    def _real_equipment_rebind_witness(self, manifest):
        """Physical item ancestry survives rebinding, retirement and checkpoints."""
        from dataclasses import asdict
        from tools.sublimation_semantic_fixture import build_fixture
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids
        from wakfu_server.combat_retained_source_provenance import (
            state_source_provenance,
        )
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server import combat_server_spell

        fixture = build_fixture(27159, manifest)
        source = fixture.fight
        source_before = snapshot(source)
        rng = fixture.factory.transaction_rng
        rng_before = rng.getstate()
        context = constructed_execution_context().payload().hex()
        with patch.object(
            combat_server_spell,
            "compiled_runtime_catalog",
            return_value=fixture.compiled,
        ):

            @rollback_external_rng
            def rebound(*, reject, rng):
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
                    raise ValueError("discard original gear rebound preview")
                return preview, dispatcher, packets

            with self.assertRaisesRegex(ValueError, "discard original"):
                rebound(reject=True, rng=rng)
            self.assertEqual(snapshot(source), source_before)
            self.assertEqual(rng.getstate(), rng_before)
            gc.collect()
            fight, dispatcher, packets = rebound(reject=False, rng=rng)
            target = next(
                actor for actor in fight.actors.values() if not actor.controlled
            )
            parent = next(
                row
                for row in fight.actors[7].state_ledger.entries
                if row.reference == 6034
            )
            carrier = next(
                row
                for row in fight.actors[7].state_ledger.entries
                if row.reference == 6035
            )
            self.assertEqual(carrier.caster_id, target.id)
            dispatcher.native_retention.synchronize()
            entries = dispatcher.native_retention.view().entries
            wire = bytes.fromhex(fight.state_wire_payloads[carrier.uid])
            fields = _identity_fields(wire, integer_fields=(1, 2, 3, 4, 6, 7, 9, 10))
            eligible = qualified_npc_uids(dispatcher)
            evidence = dict(
                scroll=27159,
                source_kind="actual_owned_FocalizationII_rebind",
                component_full_class_ready_qualified=fixture.full_class_ready_qualified,
                parent6034=asdict(parent),
                carrier6035=asdict(carrier),
                wire_payload=wire.hex(),
                wire_fields={str(key): value for key, value in fields.items()},
                actual_retained_record=fight.native_retained_records[carrier.uid],
                carrier_entries=[
                    asdict(row)
                    for row in entries
                    if row.uid == carrier.uid or row.owner_uid == carrier.uid
                ],
                npc_scope_uids=sorted(eligible),
                carrier_in_npc_scope=carrier.uid in eligible,
                owned_sources=fight.native_owned_equipment_initializations,
            )
            output = os.environ.get("WAKFU_RIFT_NPC_REBIND_RECEIPT")

            def persist():
                if output:
                    path = Path(output)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(evidence, default=str, indent=2) + "\n")

            persist()
            print(
                "real_equipment_rebound_provenance "
                + json.dumps(
                    dict(
                        parent_uid=parent.uid,
                        carrier_uid=carrier.uid,
                        caster_id=carrier.caster_id,
                        wire2=fields.get(2),
                        wire6=fields.get(6),
                        carrier_in_npc_scope=carrier.uid in eligible,
                    )
                ),
                flush=True,
            )
            self.assertNotIn(
                carrier.uid, eligible, "Actual item-rooted rebound is not NPC origin"
            )
            source_facts = state_source_provenance(fight)
            self.assertEqual(source_facts[carrier.uid]["parent_state_uid"], parent.uid)
            self.assertTrue(source_facts[carrier.uid]["parent_known"])
            self.assertIsNone(
                next(row for row in entries if row.uid == carrier.uid).owner_uid
            )
            self.assertEqual(
                fields[2], carrier.uid
            )  # Native removal base remains SELF.
            with self.assertRaises(TypeError):
                source_facts[carrier.uid]["parent_state_uid"] = None
            # A direct original NPC input remains eligible; exclusion must not
            # collapse into rejecting all NPC casters or all PC-hosted states.
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        304313,
                        1,
                        target.id,
                        7,
                        fight.actors[7].position,
                        native_context_hex=context,
                        native_explicit_target=True,
                        native_retained_container={"present": False},
                    )
                )
            )
            ordinary = next(
                row
                for row in fight.actors[7].state_ledger.entries
                if row.reference == 6849
            )
            self.assertIn(ordinary.uid, qualified_npc_uids(dispatcher))
            evidence["ordinary_npc_positive_uid"] = ordinary.uid
            dispatcher.native_retention.synchronize()
            view = dispatcher.native_retention.view()
            dispatcher.native_retention.removal(view).remove((parent.uid,))
            dispatcher.native_retention.synchronize()
            self.assertFalse(
                any(
                    row.uid == parent.uid
                    for row in fight.actors[7].state_ledger.entries
                )
            )
            self.assertTrue(
                any(
                    row.uid == carrier.uid
                    for row in fight.actors[7].state_ledger.entries
                )
            )
            self.assertEqual(fight.state_wire_payloads[carrier.uid], wire.hex())
            self.assertNotIn(carrier.uid, qualified_npc_uids(dispatcher))
            self.assertIn(ordinary.uid, qualified_npc_uids(dispatcher))
            evidence[
                "retired_parent_preserved_in_source_facts"
            ] = parent.uid in state_source_provenance(fight)
            # Recovery does not resume fights. This proves actual checkpoint
            # serialization and rehydration of the plain provenance ledger on
            # an independently copied native graph, not a server-resume claim.
            checkpoint = json.loads(json.dumps(snapshot(fight)))
            restored = deepcopy(fight)
            restored.native_state_source_provenance = checkpoint[
                "native_state_source_provenance"
            ]
            restored_dispatcher, _ = fixture.dispatcher_for(restored)
            self.assertEqual(
                dict(state_source_provenance(restored)[carrier.uid]),
                dict(state_source_provenance(fight)[carrier.uid]),
            )
            self.assertNotIn(carrier.uid, qualified_npc_uids(restored_dispatcher))
            self.assertIn(ordinary.uid, qualified_npc_uids(restored_dispatcher))
            restored.native_state_source_provenance["entries"][str(carrier.uid)][
                "caster_id"
            ] = 7
            with self.assertRaisesRegex(ValueError, "carrier identity"):
                state_source_provenance(restored)
            del restored
            gc.collect()
            legacy = deepcopy(fight)
            del legacy.native_state_source_provenance
            legacy_dispatcher, _ = fixture.dispatcher_for(legacy)
            self.assertNotIn(carrier.uid, qualified_npc_uids(legacy_dispatcher))
            self.assertIn(ordinary.uid, qualified_npc_uids(legacy_dispatcher))
            self.assertEqual(snapshot(source), source_before)
            evidence.update(
                checkpoint_json_roundtrip=True,
                native_parent_retirement_preserved_rebound=True,
                unknown_legacy_item_ancestry_excluded=True,
                source_snapshot_and_failed_preview_rng_unchanged=True,
                verified_source_facts={
                    str(key): dict(value)
                    for key, value in state_source_provenance(fight).items()
                },
            )
            persist()
