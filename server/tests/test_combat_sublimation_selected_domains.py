"""Native selected/rebound group levels use real current PV operands."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_level_group import runtime_group_level as actor_level
from wakfu_server.combat_characteristic_level_group import (
    runtime_group_level as pa_level,
)
from wakfu_server.combat_group_pv import resolve_group_level_pv, group_pa
from wakfu_server.combat_equipment_dynamic_levels import (
    OwnerLevelFacts,
    group_child_levels,
    UnknownDynamicLevel,
)
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_trap_area import trap_pa_pair, trap_characteristics
from wakfu_server.combat_area_damage_snapshot import copy_area_damage_snapshot


class SublimationSelectedDomainTests(unittest.TestCase):
    def test_original_selected_actor_rebind_pa_and_trap_keep_actual_values_and_guards(
        self,
    ):
        source = json.loads(
            (
                Path(__file__).parent
                / "fixtures/native_sublimation_selected_domains.json"
            ).read_text()
        )
        effects = source["effects"]
        owner = Actor(7, 0, (0, 0, 0), 100, 6, 3, 20, 100, owner_id=3, controlled=True)
        target = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 10, 23)
        fight = Fight(
            8,
            [owner, target],
            {owner.position, target.position},
            {0: {owner.position}, 1: {target.position}},
        )
        fight.phase = "active"
        owner.effect_stats = {18: 11, 87: 4}
        owner.effect_maxima = {18: 99, 87: 88}
        target.effect_stats = {18: 37, 87: 9}
        target.effect_maxima = {18: 120, 87: 90}
        facts = OwnerLevelFacts.capture(fight, 7, 3)
        invocation = EffectInvocation(238217, 7, 7, -7, (1, 0, 0))

        def level(effect, selected=invocation):
            return actor_level(
                effect,
                effect_profile(effect, selected.level),
                selected,
                fight.actors,
                active=True,
                resolve_pv=lambda identity: resolve_group_level_pv(fight, identity),
            )

        def value(effect, selected=invocation):
            return pa_level(
                effect,
                effect_profile(effect, selected.level),
                selected,
                fight.actors,
                resolve_pa=lambda identity, stat: group_pa(fight, identity, stat),
            )

        native = effects["238217"]
        domain = group_child_levels(native, 7, facts)
        self.assertEqual(domain.child_level_domain, (-32768, 32767))
        self.assertEqual(level(native), 23)
        target.effective_level = 41
        self.assertEqual(level(native), 41)
        # Declared generic rebind variants retain original native parameter
        # layout; source records remain untouched and owned level is not guessed.
        swapped = deepcopy(native)
        swapped["parameters"][10] = 2
        self.assertEqual(level(swapped), 100)
        selected_caster = deepcopy(native)
        selected_caster["parameters"][10] = 1
        selected_caster["parameters"][12] = 1
        self.assertEqual(level(selected_caster), 41)
        self.assertEqual(level(effects["332061"]), 82)
        self.assertEqual(level(native, replace(invocation, target_id=None)), 7)
        with self.assertRaises(ValueError):
            level(native, replace(invocation, target_id=9999))
        with self.assertRaises(UnknownDynamicLevel):
            group_child_levels(native, 7, dict(effective_level=100))

        characteristic = effects["299605"]
        self.assertEqual(value(characteristic), 37)
        target.effect_stats[18] = 44
        self.assertEqual(value(characteristic), 44)
        max_mode = deepcopy(characteristic)
        max_mode["parameters"][20] = 1
        self.assertEqual(value(max_mode), 120)
        pa_rebind = deepcopy(characteristic)
        pa_rebind["parameters"][10] = 2
        self.assertEqual(value(pa_rebind), 11)
        self.assertEqual(value(effects["353139"]), 9)
        self.assertEqual(value(characteristic, replace(invocation, target_id=None)), 7)
        del target.effect_maxima[18]
        with self.assertRaisesRegex(ValueError, "complete native PA"):
            value(characteristic)
        target.effect_maxima[18] = 120

        # Create an actual original fbc through the production area constructor,
        # then read its PA through registered-group resolution after real eYWcopy.
        (
            area_fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        trap_reference = next(
            int(key)
            for key, row in native_effect_areas().items()
            if row["type"] == "TRAP" and 3 in row["native_area_properties"]
        )
        definition = native_effect_areas()[str(trap_reference)]
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [trap_reference]},
                EffectInvocation(323843, 1, 7, None, (2, 3, 0)),
            )
        )
        area = area_fight.native_effect_areas[allocated[0]]
        before_max = trap_pa_pair(area, definition, 18)[1]
        self.assertTrue(
            copy_area_damage_snapshot(
                area, definition, source_stats={18: 7, 22: 30}, container_type=0
            )
        )
        self.assertEqual(group_pa(area_fight, area["uid"], 18), (37, before_max))
        self.assertEqual(
            before_max, trap_characteristics()["characteristics"]["18"]["maximum"]
        )
        self.assertIsNone(group_pa(area_fight, area["uid"], 1))
        # Qq is not eGj: native999 keeps the incoming container level.
        area_invocation = replace(invocation, target_id=area["uid"])
        self.assertEqual(
            actor_level(
                native,
                effect_profile(native, 7),
                area_invocation,
                area_fight.actors,
                active=True,
                resolve_pv=lambda identity: resolve_group_level_pv(
                    area_fight, identity
                ),
            ),
            7,
        )
        self.assertEqual(
            pa_level(
                characteristic,
                effect_profile(characteristic, 7),
                area_invocation,
                area_fight.actors,
                resolve_pa=lambda identity, stat: group_pa(area_fight, identity, stat),
            ),
            37,
        )
        original_constructor = deepcopy(area["native_trap_constructor"])
        area["native_trap_constructor"]["parameters"] = ()
        with self.assertRaisesRegex(ValueError, "constructor"):
            group_pa(area_fight, area["uid"], 18)
        area["native_trap_constructor"] = original_constructor
        self.assertEqual(effects["238217"], native)

    def test_original_signed_state_and_844_domains_keep_subscriptions_and_negative_guards(
        self,
    ):
        import os
        from tools.sublimation_bounded_census import BoundedDataset, construct_factory
        from wakfu_server.combat_equipment_hp_group_parser import child_domain_witnesses
        from wakfu_server.combat_equipment_state_level_domain import (
            state_level_witnesses,
        )
        from wakfu_server.combat_equipment_trigger_level_domain import (
            leaf_domain_witnesses,
        )
        from wakfu_server.combat_equipment_world_final_state_capability import (
            state_level_domain,
        )
        from wakfu_server.combat_state_level_group import level_from_state
        from wakfu_server.combat_equipment_operation_capability import validate_effect
        from wakfu_server.combat_state_handler import NativeStateHandler
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_definitions import state_profile
        from wakfu_server.combat_state_parameters import pack_state_identity

        manifest = Path(
            os.environ.get(
                "WAKFU_SUBLIMATION_SEMANTIC_MANIFEST",
                ".runtime/sublimation-phase1-dataset/manifest-semantic.json",
            )
        )
        dataset = BoundedDataset(manifest)
        factory, compiled, registry, facts, _, _ = construct_factory(dataset)
        effects, states = dataset.closure["effects"], dataset.states
        root = effects["315469"]
        witnesses = child_domain_witnesses(root, effects, states, registry=registry)
        self.assertTrue({(315471, 16384), (315471, 32767)} <= set(witnesses))
        state_effect = effects["315471"]
        self.assertTrue(
            {16384, 32767}
            <= set(
                state_level_witnesses(
                    state_effect, range(32768), states["states"], effects
                )
            )
        )
        signed = json.loads(
            (
                Path(__file__).parent / "fixtures/native_signed_state_carrier.json"
            ).read_text()
        )
        catalog = dict(states=signed["states"], effects=signed["effects"])
        for parent_level, grade in ((16384, -32768), (32767, -2)):
            owner = Actor(
                7, 0, (0, 0, 0), 100, 6, 3, 10, 10, owner_id=3, controlled=True
            )
            enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 1, 10)
            fight = Fight(
                77,
                [owner, enemy],
                {owner.position, enemy.position},
                {0: {owner.position}, 1: {enemy.position}},
            )
            fight.ready(3)
            fight.native_effect_uid_next = 500
            packets = []
            timing = NativeEffectTimingProvider(catalog)
            plan = {"native_retained_container": {"present": False}}
            retention = NativeRetainedRuntime(
                fight,
                packets,
                plan=plan,
                state_catalog=catalog,
                action_id=1,
                timing=timing,
                metadata=signed["retained_metadata"],
            )
            handler = NativeStateHandler(
                fight,
                packets,
                catalog,
                action_id=1,
                allocate_uid=fight.allocate_effect_uid,
                execute_child=lambda _: self.fail(
                    "Negative state must not execute min0 descendants"
                ),
                context=lambda effect, invocation: timing.state(
                    fight, plan, effect, invocation
                ),
                rng=lambda: 0.99,
                applied_state_scope=retention.applied_state_scope,
            )
            self.assertTrue(
                retention.wrap(handler, state=True)(
                    state_effect,
                    effect_profile(state_effect, parent_level),
                    EffectInvocation(315471, parent_level, 7, 7, (0, 0, 0)),
                )
            )
            (carrier,) = owner.state_ledger.entries
            self.assertEqual((carrier.reference, carrier.level), (6844, grade))
            self.assertEqual(state_profile(catalog, 6844, grade)["effects"], [])
            self.assertEqual(
                pack_state_identity(6844, grade), (6844 << 16) + (grade & 65535)
            )
            self.assertEqual([opcode for opcode, _ in packets], [12613])

        malformed = dict(effects)
        state_child = states["states"]["6844"]["effect_ids"][0]
        malformed[str(state_child)] = dict(effects[str(state_child)], minimum_level=-1)
        with self.assertRaises(UnknownDynamicLevel):
            state_level_witnesses(
                state_effect, range(32768), states["states"], malformed
            )
        overflowing = deepcopy(state_effect)
        overflowing["parameters"][3] = 1e38
        with self.assertRaises(UnknownDynamicLevel):
            state_level_witnesses(overflowing, range(32768), states["states"], effects)
        routes, provider = factory.equipment_operation_capability()
        from wakfu_server.combat_copied_equipment_plan import (
            copied_equipment_plan,
            SOURCE,
        )

        definitions = dict(dataset.closure["source_definitions"])
        definitions[str(dataset.parent["reference"])] = dataset.parent
        parent = copied_equipment_plan(
            dataset.parent["reference"],
            dict(
                producer=SOURCE,
                complete=True,
                definition_count=len(definitions),
                definitions=definitions,
            ),
        )["native_retained_container"]
        subscribed = effects["315671"]
        self.assertIn(1004, subscribed["target_masks"][2])
        low, high = leaf_domain_witnesses(subscribed, registry=registry)
        self.assertEqual(
            (low, high), (subscribed["minimum_level"], subscribed["maximum_level"])
        )
        for level in (low, high):
            verdict = validate_effect(
                subscribed,
                level,
                registry,
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container=parent,
                owner_level_facts=facts,
                state_catalog=states,
                effect_reference=315671,
            )
            self.assertEqual(verdict.status, "supported", verdict.reasons)
        bad_mask = deepcopy(subscribed)
        bad_mask["target_masks"][2] = [True]
        with self.assertRaises(UnknownDynamicLevel):
            leaf_domain_witnesses(bad_mask, registry=registry)

        readers = {
            reference: effect
            for reference, effect in effects.items()
            if effect["effect_class"] == 844
        }
        self.assertEqual(len(readers), 6)
        for reference, effect in readers.items():
            profile = effect_profile(effect, 7)
            domain = state_level_domain(effect, profile, 7, states)
            self.assertIn(7, domain.child_levels)
            for grade in (-32768, -2):
                child_level = level_from_state(effect, profile["parameters"], 7, grade)
                if child_level < 0:
                    self.assertTrue(
                        all(
                            not (
                                effects[str(child)]["minimum_level"]
                                <= child_level
                                <= effects[str(child)]["maximum_level"]
                            )
                            for child in effect["children"]
                        )
                    )
            if reference == "256088":
                self.assertTrue(set(range(15)) <= set(domain.child_levels))
                self.assertEqual(
                    level_from_state(effect, profile["parameters"], 7, -2), 13
                )
                self.assertEqual(
                    level_from_state(effect, profile["parameters"], 7, -16), 7
                )
            else:
                self.assertEqual(
                    level_from_state(effect, profile["parameters"], 7, -1), 7
                )
            invalid_effects = dict(effects)
            child = str(effect["children"][0])
            invalid_effects[child] = dict(effects[child], minimum_level=-1)
            invalid_states = dict(states, effects=invalid_effects)
            with self.assertRaises(UnknownDynamicLevel):
                state_level_domain(effect, profile, 7, invalid_states)
        invalid_factor = deepcopy(readers["256088"])
        invalid_factor["parameters"][16] = 2
        with self.assertRaises(UnknownDynamicLevel):
            state_level_domain(
                invalid_factor, effect_profile(invalid_factor, 7), 7, states
            )

    def test_original_longevity_rebinding_and_final_modifier_domains_keep_owned_sources(
        self,
    ):
        """Real group dispatch and FAQ arithmetic; observed children are not damage proof."""
        import os
        from copy import copy
        from tools.sublimation_bounded_census import BoundedDataset, construct_factory
        from wakfu_server.combat_copied_equipment_plan import (
            copied_equipment_plan,
            SOURCE,
        )
        from wakfu_server.combat_equipment_hp_group_parser import child_domain_witnesses
        from wakfu_server.combat_equipment_trigger_level_domain import (
            leaf_domain_witnesses,
        )
        from wakfu_server.combat_equipment_selected_level_domain import (
            group_rebinding_preflight,
        )
        from wakfu_server.combat_equipment_operation_capability import validate_effect
        from wakfu_server.combat_effect_groups import decode_group_mode
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_effect_resolver import (
            NativeEffectResolver,
            EffectResolutionContext,
        )
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_final_modifier import (
            NativeFinalModifier,
            NativeFinalModifierHandler,
            final_modifier_source,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from test_combat_final_modifier import source

        dataset = BoundedDataset(
            Path(
                os.environ.get(
                    "WAKFU_SUBLIMATION_SEMANTIC_MANIFEST",
                    ".runtime/sublimation-phase1-dataset/manifest-semantic.json",
                )
            )
        )
        factory, _, registry, facts, fight, _ = construct_factory(dataset)
        effects = dataset.closure["effects"]
        definitions = dict(dataset.closure["source_definitions"])
        definitions[str(dataset.parent["reference"])] = dataset.parent
        parent = copied_equipment_plan(
            dataset.parent["reference"],
            dict(
                producer=SOURCE,
                complete=True,
                definition_count=len(definitions),
                definitions=definitions,
            ),
        )["native_retained_container"]
        routes, provider = factory.equipment_operation_capability()
        root = effects["309451"]
        mode = decode_group_mode(
            effect_profile(root, 1)["parameters"],
            raw_target_parameter=root["parameters"][4],
        )
        route = routes.routes[330]
        self.assertEqual(mode.actor_rebind, 1)
        self.assertTrue(group_rebinding_preflight(factory, parent, mode, route=route))
        self.assertFalse(
            group_rebinding_preflight(copy(factory), parent, mode, route=route)
        )
        self.assertFalse(
            group_rebinding_preflight(
                factory, parent, mode, route=replace(route, family=400)
            )
        )
        self.assertFalse(
            group_rebinding_preflight(
                factory, parent, replace(mode, actor_rebind=3), route=route
            )
        )
        verdict = validate_effect(
            root,
            1,
            registry,
            runtime_bindings=routes,
            criteria_capability=provider,
            retained_container=parent,
            owner_level_facts=facts,
            state_catalog=dataset.states,
            effect_reference=309451,
        )
        self.assertEqual(verdict.status, "supported", verdict.reasons)

        for actor in fight.actors.values():
            actor.physical_radius = 0
        contexts = {
            identity: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for identity in fight.actors
        }
        resolver = NativeEffectResolver(
            actors=lambda *_: tuple(fight.actors.values()),
            caster=lambda _effect, invocation: fight.actors[invocation.caster_id],
            native_context=lambda *_: contexts,
            context=lambda *_: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
        )

        def conditions(invocation):
            return ConditionContext(
                {
                    name: ConditionActor(
                        actor_id=identity,
                        effective_level=fight.actors[identity].effective_level,
                    )
                    for name, identity in (
                        ("caster", invocation.caster_id),
                        ("target", invocation.target_id),
                    )
                }
            )

        seen = []
        children = {str(ref): effects[str(ref)] for ref in root["children"]}

        def observe_child_boundary(effect, selected):
            resolved = tuple(resolver(effect, selected))
            if selected.reference in root["children"]:
                seen.extend(resolved)
                return ()  # Stop at actual child delivery; no child arithmetic claim.
            return resolved

        dispatcher = EffectDispatcher(
            dict(children, **{"309451": root}),
            {
                effect["effect_class"]: lambda effect, values, invocation: seen.append(
                    invocation
                )
                or True
                for effect in children.values()
            },
            resolve=observe_child_boundary,
            condition_context=conditions,
            probability_accepts=lambda *_: True,
            group_cells=lambda *_: (),
            actor_position=lambda identity: fight.actors[identity].position,
        )
        invocation = EffectInvocation(
            309451, 1, 7, -200, (1, 0, 0), native_preselected_target=True
        )
        self.assertFalse(dispatcher.execute(invocation))
        self.assertEqual([row.reference for row in seen], root["children"])
        self.assertTrue(
            all((row.caster_id, row.target_id) == (-200, -200) for row in seen)
        )
        self.assertEqual((invocation.caster_id, invocation.target_id), (7, -200))

        packets = []
        fight.native_effect_uid_next = 902
        handler = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *_: StatExecutionContext(
                executable=True,
                source_guards_verified=True,
                trigger_value=None,
                retained=False,
                timing_payload=b"",
                timer=None,
            ),
        )
        stats_before = {
            identity: deepcopy(actor.effect_stats)
            for identity, actor in fight.actors.items()
        }
        for reference in (383969, 383972):
            witnesses = child_domain_witnesses(
                effects[str(reference)], effects, dataset.states, registry=registry
            )
            first, second = effects[str(reference)]["children"]
            expected = {(first, 1), (first, 5), (second, 6)}
            for child in effects[str(reference)]["children"]:
                leaf = effects[str(child)]
                for level in (1, 5, 6, 32767):
                    if not leaf["minimum_level"] <= level <= leaf["maximum_level"]:
                        continue
                    modifier = NativeFinalModifier(901, 1)
                    selected = EffectInvocation(
                        child,
                        level,
                        7,
                        7,
                        (0, 0, 0),
                        native_trigger_context={"uid": 901},
                    )
                    with final_modifier_source(source(modifier)):
                        self.assertTrue(
                            handler(leaf, effect_profile(leaf, level), selected)
                        )
                    self.assertEqual(modifier.value, level * 5 if level <= 5 else 30)
                    with self.assertRaisesRegex(ValueError, "live native triggering"):
                        handler(leaf, effect_profile(leaf, level), selected)
                bad = deepcopy(leaf)
                bad["parameters"].extend([0, 1])
                bad["parameter_count"] += 1
                with self.assertRaises(UnknownDynamicLevel):
                    leaf_domain_witnesses(bad, registry=registry)
                bad = deepcopy(leaf)
                bad["target_masks"][2] = [True]
                with self.assertRaises(UnknownDynamicLevel):
                    leaf_domain_witnesses(bad, registry=registry)
            self.assertTrue(expected <= set(witnesses))
        self.assertEqual(
            stats_before,
            {identity: actor.effect_stats for identity, actor in fight.actors.items()},
        )
