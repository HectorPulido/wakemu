"""One actual Ultimate NPC KO and scoped original4199 cleanup.

The curse is seeded with original179235 through the real handler. Actual phase
5650 acquisition and the40-turn encounter have a separate integration receipt.
Only immutable source readers are bound to the closed original dataset; no
eligibility, targeting, death publication or native state handler is replaced.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class NativeRiftKoCleanupTests(unittest.TestCase):
    def test_actual_npc_ko_clears_two_original_carriers_only_inside_owned_boundary(
        self,
    ):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server import (
            combat_casting_context,
            combat_death_events,
            combat_health_ordering_authority,
            combat_npc_attack,
            combat_server_spell,
            rift_ko_cleanup,
            spell_audit,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_effect_runtime import _merge_effects
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import default_deck
        from wakfu_server.wire import proto_field
        from rift_native_flow_fixture import build_flow_fixture
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from test_rift_artifact_generation_component import (
            RiftArtifactGenerationComponentTests,
        )

        manifest = os.environ.get("WAKFU_RIFT_KO_MANIFEST")
        if not manifest:
            raise RuntimeError(
                "Explicit closed3866 plus original health-authority manifest required"
            )
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
        casting_roots = dataset.read(dataset.manifest["rift_casting_root_catalog"])
        health = dataset.read(dataset.manifest["native_health_ordering_authority"])

        class OriginalHealthAuthority:
            @contextmanager
            def connection(self):
                yield self

            def execute(self, query, parameters):
                if query == (
                    "SELECT * FROM native_health_ordering_authority_versions WHERE catalog_revision=%s"
                ) and parameters == (health["version"]["catalog_revision"],):
                    return SimpleNamespace(fetchone=lambda: deepcopy(health["version"]))
                if query == (
                    "SELECT * FROM native_health_ordering_authority_rows WHERE authority_key=%s "
                    "ORDER BY effect_reference"
                ) and parameters == (health["version"]["authority_key"],):
                    return SimpleNamespace(fetchall=lambda: deepcopy(health["rows"]))
                raise ValueError("Unlisted immutable native health authority query")

        combat_health_ordering_authority._for_revision.cache_clear()
        reader = patch.object(
            combat_health_ordering_authority,
            "_database",
            return_value=OriginalHealthAuthority(),
        )
        reader.start()
        self.addCleanup(reader.stop)
        for module, name, value in (
            (spell_audit, "states_catalog", compiled.source_states),
            (spell_audit, "catalog", class_catalog),
            (combat_server_spell, "catalog", class_catalog),
            (combat_server_spell, "states_catalog", compiled.source_states),
            (combat_server_spell, "compiled_runtime_catalog", compiled),
            (combat_npc_attack, "npc_runtime_catalog", compiled),
            (combat_casting_context, "casting_root_catalog", casting_roots),
        ):
            reader = patch.object(module, name, return_value=value)
            reader.start()
            self.addCleanup(reader.stop)

        policy = NativeRiftCarrierComponentTests.policy()
        native = RiftArtifactGenerationComponentTests.native_policy()
        native["compensation"] = policy["native_gameplay"]["compensation"]
        policy["native_gameplay"] = native
        migration = next(
            (Path(__file__).resolve().parents[1] / "migrations").glob("090_*.sql")
        )
        catalogs = next(
            value
            for text in re.findall(r"'({.*})'::jsonb", migration.read_text())
            for value in [json.loads(text)]
            if "8" in value and "37" in value
        )
        run = dict(
            catalog=catalogs["8"],
            policy=policy,
            seed="owned-ko-component",
            instance_id=8,
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
                level=245,
                real_level=245,
                map_id=run["catalog"]["map_id"],
                instance_id=8,
                x=0,
                y=0,
                z=0,
                hp=maximum(1, 245),
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
            4199,
            (-200, -201),
            (3866, 3866),
            compiled=compiled,
            registry=registry,
            minimum_separation=5,
            additional_player_ids=(8,),
        )
        fight = component.fight
        for index, (identity, member) in enumerate(component.characters.items()):
            fight, _ = combat_server_spell.prepare_server_initialization(
                member,
                fight.rift_monsters,
                fight,
                member["account_id"],
                component.decks[identity],
                action_id=1,
                rng=component.rng,
                fight_start=index == len(component.characters) - 1,
                player_characters=component.characters,
                deck_blobs=component.decks,
            )
        component.fight = fight
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from rift_native_phase_fixture import execute_health_floor_transition

        def serialize(actor, current):
            if actor.controlled:
                return actual_actor_stats(
                    component.characters[actor.id],
                    actor,
                    current.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    direction=actor.direction,
                    fight=current,
                )
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, current, run["catalog"]["map_id"])
            return actual_monster_actor_stats(
                current.rift_monsters[actor.id],
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                direction=actor.direction,
                fight=current,
            )

        def turn_provider(current, *, actor_id, action_id, start):
            callback = (
                combat_server_spell.prepare_server_turn_start
                if start
                else combat_server_spell.prepare_server_turn_end
            )
            return callback(
                component.character,
                current.rift_monsters,
                current,
                component.decks[7],
                actor_id=actor_id,
                action_id=action_id,
                rng=component.rng,
                player_characters=component.characters,
                deck_blobs=component.decks,
            )

        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=serialize,
            expiration_runtime_factory=lambda *, action_id: component.runtime_factory(
                runtime.fight, action_id=action_id
            ),
            turn_start_provider=lambda current, **kw: turn_provider(
                current, **kw, start=True
            ),
            turn_end_provider=lambda current, **kw: turn_provider(
                current, **kw, start=False
            ),
        )
        runtime.turn_started()
        for _ in range(8):
            if runtime.fight.current.id == 7:
                break
            current = runtime.fight
            actor = current.current
            if actor.controlled:
                runtime.end_turn(actor.owner_id, actor.id, current_wire_turn(current))
            else:
                runtime.end_server_turn(actor.id, current.turn_id)
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        self.assertEqual(runtime.fight.current.id, 7)
        context_hex = constructed_execution_context().payload().hex()
        # Reuse the same paid-cast phase helper as the qualified integrated
        # witness. Native instant death respects the original877 HP floors;
        # two actual Feca casts advance65->35->0 through damage callbacks.
        phase_minima = [runtime.fight.actors[-200].effect_minima[1]]
        for _ in range(2):
            dispatcher, _ = component.factory(runtime.fight)
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        402298,
                        1,
                        7,
                        -200,
                        runtime.fight.actors[-200].position,
                        native_context_hex=context_hex,
                        native_explicit_target=True,
                        native_retained_container={"present": False},
                    )
                )
            )
            self.assertGreater(runtime.fight.actors[-200].hp, 0)
            self.assertTrue(
                execute_health_floor_transition(
                    runtime, component, -200, stats_serializer=serialize
                )
            )
            phase_minima.append(runtime.fight.actors[-200].effect_minima[1])
        self.assertGreater(phase_minima[0], phase_minima[1])
        self.assertGreater(phase_minima[1], phase_minima[2])
        self.assertEqual(phase_minima[2], 0)
        fight = component.fight = runtime.fight
        dispatcher, _ = component.factory(fight)

        def cursed(current, identity):
            return any(
                row.reference == 4199
                for row in current.actors[identity].state_ledger.entries
            )

        for identity in (7, 8):
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        179235,
                        1,
                        -200,
                        identity,
                        fight.actors[identity].position,
                        native_context_hex=context_hex,
                        native_explicit_target=True,
                        native_retained_container={"present": False},
                    )
                )
            )
            self.assertTrue(cursed(fight, identity))
        before_players = {
            identity: (fight.actors[identity].hp, fight.actors[identity].max_hp)
            for identity in (7, 8)
        }
        captured, selected = {}, []
        actual_death = combat_death_events.deliver_owned_death
        actual_population = rift_ko_cleanup.cleanup_population

        def observe_death(current, actor_id, **kwargs):
            if actor_id == -200:
                # This is observed after real registered KO/OFF_PLAY, before
                # the actual producer journals and delivers its local1010.
                captured.update(source=kwargs["source"], fight=deepcopy(current))
            return actual_death(current, actor_id, **kwargs)

        def observe_population(effect, invocation, actors, **kwargs):
            result = actual_population(effect, invocation, actors, **kwargs)
            if result is not None:
                selected.append(
                    (invocation.reference, tuple(actor.id for actor in result))
                )
                # Inside the genuine scope, a preselected native PV is still
                # authoritative and must never be converted into fanout.
                self.assertIsNone(
                    actual_population(
                        effect,
                        replace(invocation, native_preselected_target=True),
                        actors,
                        **kwargs
                    )
                )
            return result

        with patch.object(
            combat_death_events, "deliver_owned_death", observe_death
        ), patch.object(rift_ko_cleanup, "cleanup_population", observe_population):
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        402298,
                        1,
                        7,
                        -200,
                        fight.actors[-200].position,
                        native_context_hex=context_hex,
                        native_explicit_target=True,
                        native_retained_container={"present": False},
                    )
                )
            )
        self.assertEqual(fight.actors[-200].hp, 0)
        self.assertGreater(fight.actors[-201].hp, 0)
        self.assertTrue(
            any(
                reference == 315378 and set(actors) == {7, 8}
                for reference, actors in selected
            )
        )
        self.assertFalse(cursed(fight, 7))
        self.assertFalse(cursed(fight, 8))
        self.assertEqual(
            before_players,
            {
                identity: (fight.actors[identity].hp, fight.actors[identity].max_hp)
                for identity in (7, 8)
            },
        )
        self.assertIn("source", captured)
        self.assertTrue(fight.native_death_event_deliveries)

        # Reuse the observed causal KO snapshot, never a fabricated death/HP0.
        observed = captured["fight"]
        replay_dispatcher, _ = component.factory(observed)
        source = replace(captured["source"], event_ids=(1010,))
        retention = replay_dispatcher.native_retention
        retention.synchronize()
        entry = next(
            row
            for row in retention.view().entries
            if row.generic_effect == 315373 and row.manager_id == -200
        )
        row = observed.native_owned_group_effects[entry.uid]
        original = EffectInvocation(
            **dict(row["invocation"], cell=tuple(row["invocation"]["cell"]))
        )
        effect = replay_dispatcher.effects["315373"]
        definition = retention.metadata["effects"]["315373"]
        child = replace(
            original,
            reference=315378,
            caster_id=-200,
            target_id=-200,
            native_explicit_target=True,
            native_trigger_context=asdict(source),
        )
        child_effect = replay_dispatcher.effects["315378"]
        actors = tuple(observed.actors.values())
        direct_policy = (321, False, False)
        # Ordinary explicit-PV321 remains literal: a dead NPC target is not an
        # instruction to remove the two living players' states.
        self.assertFalse(
            replay_dispatcher.execute(
                replace(child, native_trigger_context=None, base_uid=None)
            )
        )
        self.assertTrue(all(cursed(observed, identity) for identity in (7, 8)))

        with rift_ko_cleanup.cleanup_scope(
            retention,
            replay_dispatcher,
            source,
            entry=entry,
            original=original,
            effect=effect,
            definition=definition,
        ):
            self.assertIsNone(
                actual_population(
                    child_effect, child, actors, direct_policy=direct_policy
                )
            )
        observed.native_death_event_deliveries = deepcopy(
            fight.native_death_event_deliveries
        )
        variants = (
            ("global1010", replace(source, channel=61)),
            ("non-KO", replace(source, event_ids=(1002,))),
            ("player-manager", replace(source, manager_actor_id=7, target_id=7)),
            ("forged-UID", replace(source, uid=source.uid + 99999)),
        )
        with rift_ko_cleanup.owned_ko_boundary(observed, source):
            for name, candidate in variants:
                with self.subTest(boundary=name):
                    with rift_ko_cleanup.cleanup_scope(
                        retention,
                        replay_dispatcher,
                        candidate,
                        entry=entry,
                        original=original,
                        effect=effect,
                        definition=definition,
                    ):
                        self.assertIsNone(
                            actual_population(
                                child_effect, child, actors, direct_policy=direct_policy
                            )
                        )
        # Even authentic death history and a matching once-only receipt cannot
        # enable the scope without the actual synchronous producer boundary.
        observed.native_death_event_deliveries = deepcopy(
            fight.native_death_event_deliveries
        )
        original_kind = observed.rift_wave_state["catalog"]["type"]
        for kind in (None, "INFINITE_WAVE"):
            with self.subTest(scope=kind):
                saved = observed.rift_wave_state
                if kind is None:
                    del observed.rift_wave_state
                else:
                    observed.rift_wave_state["catalog"]["type"] = kind
                with rift_ko_cleanup.owned_ko_boundary(observed, source):
                    with rift_ko_cleanup.cleanup_scope(
                        retention,
                        replay_dispatcher,
                        source,
                        entry=entry,
                        original=original,
                        effect=effect,
                        definition=definition,
                    ):
                        self.assertIsNone(
                            actual_population(
                                child_effect, child, actors, direct_policy=direct_policy
                            )
                        )
                observed.rift_wave_state = saved
                observed.rift_wave_state["catalog"]["type"] = original_kind
        self.assertTrue(all(cursed(observed, identity) for identity in (7, 8)))
