import unittest
import copy
from unittest.mock import patch
from wakfu_server.combat import combat_border_policy as border_policy
from types import SimpleNamespace

from wakfu_server.combat_battleground_border import (
    POLICY,
    ensure_battleground_border,
    install_battleground_border,
)
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_area_targets import area_targets
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_state_managers import registered_area_pv


class NativeBorderPoolExecutionTests(unittest.TestCase):
    def test_original_border_48_executes_resource_loss_and_once_marker(self):
        from dataclasses import replace
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        # Reuse the isolated runtime's actual actor/stat ledger, without loading
        # or compiling the full class catalog. Only original border definitions
        # are supplied; the factory and handlers remain production code.
        fixture = NativeRuntimeFactoryTests()
        fixture.spells = area_effect_catalog()
        fixture.effects = dict(fixture.spells["effects"])
        fixture.states = states_catalog()
        fixture.registry = characteristic_registry()
        fixture.setUp()
        fight = fixture.fight
        fight.actors = {7: fight.actors[7]}
        fight.order = [7]
        actor = fight.actors[7]
        fight.turn_index = 0
        actor.effect_stats[86] = 0
        actor.effect_minima[86] = 0
        actor.effect_maxima[86] = 1000
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=2, height=2, cell_masks=[128, 0, 0, 256]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        arena = dict(
            native_border_policy=POLICY, native_border_cells={(0, 0, 0)}, min_z=0
        )
        install_battleground_border(fight, arena, reference=48, identity=-100)
        timing = NativeEffectTimingProvider(fixture.states)

        def condition(preview, plan, effect, invocation):
            rows = native_retained_condition_effects(preview, invocation.target_id)
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=-100, is_native_fighter=False),
                    "target": ConditionActor(
                        actor_id=invocation.target_id,
                        characteristics={
                            "WILLPOWER": preview.actors[
                                invocation.target_id
                            ].effect_stats[86]
                        },
                        retained_effect_ids=frozenset(row[0] for row in rows),
                    ),
                }
            )

        actor_authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1)},
            monsters={},
            decks={7: []},
            excluded_decks={7: []},
        )
        adapter = SimpleNamespace(actor_authority=actor_authority)

        def healing_events(preview, plan, replay, retention):
            return OrdinaryHealingEvents(
                adapter=adapter,
                preview=preview,
                plan=plan,
                replay=replay,
                retention=retention,
            )

        contexts = replace(
            fixture.contexts,
            condition=condition,
            stat=timing.stat,
            healing_events=healing_events,
        )
        property_actor_ids = []

        def properties(preview, target):
            property_actor_ids.append(target.id)
            return frozenset()

        class TestSummonAuthority(RegisteredSummonAuthority):
            def __init__(self):
                super().__init__(object())

            def properties(self, preview, target):
                return properties(preview, target)

        factory = NativeEffectRuntimeFactory(
            effects=fixture.effects,
            state_catalog=fixture.states,
            characteristic_registry=fixture.registry,
            action_id=1,
            contexts=contexts,
            summon_authority=TestSummonAuthority(),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        self.assertEqual(actor.ap, 6)
        with fight.effect_resolution():
            dispatcher.native_area_events.event(10000, actor.id)
        self.assertEqual(actor.ap, 4)  # no actor caster means native willpower is zero.
        rows = native_retained_condition_effects(fight, actor.id)
        self.assertIn(177620, {row[0] for row in rows})
        self.assertIn(5227, {entry.reference for entry in actor.state_ledger.entries})
        self.assertEqual(set(property_actor_ids), {actor.id})
        with fight.effect_resolution():
            dispatcher.native_area_events.event(10000, actor.id)
        self.assertEqual(actor.ap, 4)

    def test_original_border_194_executes_resource_loss_and_once_marker(self):
        from dataclasses import replace
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        # Reuse the isolated runtime's actual actor/stat ledger, without loading
        # or compiling the full class catalog. Only original border definitions
        # are supplied; the factory and handlers remain production code.
        fixture = NativeRuntimeFactoryTests()
        fixture.spells = area_effect_catalog()
        fixture.effects = dict(fixture.spells["effects"])
        fixture.states = states_catalog()
        fixture.registry = characteristic_registry()
        fixture.setUp()
        fight = fixture.fight
        fight.actors = {7: fight.actors[7]}
        fight.order = [7]
        actor = fight.actors[7]
        fight.turn_index = 0
        actor.effect_stats[86] = 0
        actor.effect_minima[86] = 0
        actor.effect_maxima[86] = 1000
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=2, height=2, cell_masks=[128, 0, 0, 256]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        arena = dict(
            native_border_policy=POLICY, native_border_cells={(0, 0, 0)}, min_z=0
        )
        install_battleground_border(fight, arena, reference=194, identity=-100)
        timing = NativeEffectTimingProvider(fixture.states)

        def condition(preview, plan, effect, invocation):
            rows = native_retained_condition_effects(preview, invocation.target_id)
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=-100, is_native_fighter=False),
                    "target": ConditionActor(
                        actor_id=invocation.target_id,
                        characteristics={
                            "WILLPOWER": preview.actors[
                                invocation.target_id
                            ].effect_stats[86]
                        },
                        retained_effect_ids=frozenset(row[0] for row in rows),
                    ),
                }
            )

        actor_authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1)},
            monsters={},
            decks={7: []},
            excluded_decks={7: []},
        )
        adapter = SimpleNamespace(actor_authority=actor_authority)

        def healing_events(preview, plan, replay, retention):
            return OrdinaryHealingEvents(
                adapter=adapter,
                preview=preview,
                plan=plan,
                replay=replay,
                retention=retention,
            )

        contexts = replace(
            fixture.contexts,
            condition=condition,
            stat=timing.stat,
            healing_events=healing_events,
        )
        property_actor_ids = []

        def properties(preview, target):
            property_actor_ids.append(target.id)
            return frozenset()

        class TestSummonAuthority(RegisteredSummonAuthority):
            def __init__(self):
                super().__init__(object())

            def properties(self, preview, target):
                return properties(preview, target)

        factory = NativeEffectRuntimeFactory(
            effects=fixture.effects,
            state_catalog=fixture.states,
            characteristic_registry=fixture.registry,
            action_id=1,
            contexts=contexts,
            summon_authority=TestSummonAuthority(),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        self.assertEqual(actor.mp, 3)
        with fight.effect_resolution():
            dispatcher.native_area_events.event(
                10001, actor.id, from_cell=(-1, 0, 0), to_cell=(0, 0, 0)
            )
        self.assertEqual(actor.mp, 2)  # no actor caster means native willpower is zero.
        rows = native_retained_condition_effects(fight, actor.id)
        self.assertIn(177623, {row[0] for row in rows})
        self.assertIn(5227, {entry.reference for entry in actor.state_ledger.entries})
        self.assertEqual(set(property_actor_ids), {actor.id})
        with fight.effect_resolution():
            dispatcher.native_area_events.event(
                10001, actor.id, from_cell=(-1, 0, 0), to_cell=(0, 0, 0)
            )
        self.assertEqual(actor.mp, 2)


class NativeBorderSelectionTests(unittest.TestCase):
    def test_all_pool_members_have_complete_native_proof(self):
        self.assertEqual(set(border_policy.native_proofs()), {46, 48})

    def test_selection_and_frozen_replay_are_exact(self):
        value = dict(version=1, pool=[46, 48])
        for reference in value["pool"]:
            receipt = border_policy.select(value, choice=lambda pool: reference)
            self.assertEqual(border_policy.validate(receipt), reference)
            self.assertEqual(border_policy.validate(copy.deepcopy(receipt)), reference)
            with self.assertRaises(ValueError):
                border_policy.validate(dict(receipt, native_sha256="changed"))

    def test_unqualified_or_duplicate_pool_is_rejected(self):
        for pool in ([], [46, 46], [46, 44], [194], [True]):
            with self.subTest(pool=pool), self.assertRaises(ValueError):
                border_policy.select(dict(version=1, pool=pool))

    def test_real_dispatcher_consumes_frozen_border_for_creation_and_join_context(self):
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        tree = ast.parse((root / "server" / "local_game_server.py").read_text())
        expected = ast.dump(ast.parse('arena["terrain_effect_id"]', mode="eval").body)
        calls = {"create_placement": [], "placement_messages": []}
        contexts = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in calls
            ):
                calls[node.func.id].extend(
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "terrain_effect_id"
                )
            if isinstance(node, ast.Dict):
                contexts.extend(
                    value
                    for key, value in zip(node.keys, node.values)
                    if isinstance(key, ast.Constant)
                    and key.value == "terrain_effect_id"
                )
        for name, values in calls.items():
            with self.subTest(call=name):
                self.assertTrue(values)
                self.assertTrue(all(ast.dump(value) == expected for value in values))
        self.assertTrue(contexts)
        self.assertTrue(all(ast.dump(value) == expected for value in contexts))

    def test_original_area_closure_is_merged_into_production_compiled_catalog(self):
        from wakfu_server.combat.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog

        compiled = compiled_runtime_catalog()
        source = area_effect_catalog()["effects"]
        for references in border_policy.VERIFIED.values():
            for identity in references[:3]:
                with self.subTest(effect=identity):
                    self.assertEqual(
                        compiled.source_effects[str(identity)], source[str(identity)]
                    )
