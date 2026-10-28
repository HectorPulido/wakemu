from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import struct
import unittest
from unittest.mock import patch
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import catalog, states_catalog
from wakfu_server.spells import encode_deck
from wakfu_server.combat_conditions import ConditionContext, ConditionActor
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    run_effect_transaction,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_effect_resolver import EffectResolutionContext
from wakfu_server.combat_effect_runtime import (
    NativeEffectRuntimeFactory,
    NativeRuntimeContexts,
)
from wakfu_server.combat_damage_handler import DamageExecutionContext
from wakfu_server.combat_healing_handler import HealingExecutionContext
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_state_handler import StateCarrierContext
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server import native_catalog


def definition(effect_class, parameters, *, selector=1, children=()):
    return dict(
        effect_class=effect_class,
        parameters=parameters,
        parameter_count=len(parameters) // 2,
        children=list(children),
        minimum_level=0,
        maximum_level=200,
        variant=0,
        criteria="",
        probability_base=100,
        probability_per_level=0,
        target_masks=[None] * 7,
        native_target_selector={"class": "fcE", "mask": selector},
        area_class="anD",
        area_native="point",
        native_effect_flags=[],
        native_localization_enabled=False,
    )


class NativeRuntimeFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spells = catalog()
        cls.states = states_catalog()
        cls.registry = json.loads(
            native_catalog.read_text(DATA_ROOT / "effect-characteristic-registry.json")
        )

    def setUp(self, *, effects=None):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(8, 0, (0, 1, 0), 40, 6, 3, 8, 1),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        self.fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        self.fight.ready(3)
        for actor in actors:
            # This fresh fixture has no retained AP-cost modifier effects.
            actor.spell_ap_cost_modifiers = {}
            # The isolated cast fixture has an explicit fresh eHl snapshot.
            actor.spell_range_modifiers = {}
            actor.effect_stats = {
                1: actor.hp,
                2: 6,
                3: 3,
                4: 6,
                20: 0,
                32: 0,
                92: 0,
                97: 0,
                100: 0,
            }
            actor.effect_minima = {key: 0 for key in actor.effect_stats}
            actor.effect_maxima = {
                1: actor.max_hp,
                2: 6,
                3: 3,
                4: 6,
                20: 1000,
                32: 1000,
                92: 0,
                97: 1000,
                100: 1000,
            }
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        self.effects = dict(self.spells["effects"]) if effects is None else effects
        self.contexts = NativeRuntimeContexts(
            # This fixture authoritatively scopes transmitted actor targets.
            actor_candidates=lambda p, plan, e, i: (p.actors[i.target_id],)
            if i.target_id is not None
            else tuple(p.actors.values()),
            resolution=lambda p, plan, e, i: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
            native_targets=lambda p, plan, e, i: {
                actor.id: dict(
                    bEe=True,
                    is_amO=True,
                    is_eGj=True,
                    is_Qq=False,
                    is_eHH=True,
                    UNTARGETTABLE_BY_OTHER=False,
                    buX=False,
                )
                for actor in p.actors.values()
            },
            cell_eligible=lambda p, plan, e, i: False,
            condition=self.condition,
            probability=lambda p, plan, value, i: value == 100,
            group_cells=lambda p, plan, e, i: (),
            damage=lambda p, plan, e, i: DamageExecutionContext(
                bool(e["variant"] & 1), True, False, True, 11, False
            ),
            healing=lambda p, plan, e, i: HealingExecutionContext(
                bool(e["variant"] & 1),
                True,
                False,
                33 in e["native_effect_flags"],
                0,
                0,
                False,
                0,
                1000,
                True,
            ),
            stat=lambda p, plan, e, i: StatExecutionContext(
                True, True, None, True, None
            ),
            state=lambda p, plan, e, i: StateCarrierContext(
                -1, 0, False, None, 100, False, False, False, 0, None
            ),
            rounding=lambda p, plan: 0.99,
            uid_start=lambda p, plan: 200
            if p.native_effect_uid_next is None
            else p.native_effect_uid_next,
        )

    def condition(self, preview, plan, effect, invocation):
        source = preview.actors[invocation.caster_id]
        target = preview.actors.get(invocation.target_id)
        distance = (
            None
            if target is None
            else sum(
                abs(a - b) for a, b in zip(source.position[:2], target.position[:2])
            )
        )
        actor = ConditionActor(
            actor_id=source.id,
            effective_level=source.effective_level,
            is_player=True,
            deck_spell_ids=frozenset({6266}),
            excluded_deck_spell_ids=frozenset(),
            summon_count=0,
            state_levels=tuple(
                (entry.reference, entry.level) for entry in source.state_ledger.entries
            ),
            state_ids=frozenset(
                entry.reference for entry in source.state_ledger.entries
            ),
            characteristics={"RANGE": 0},
            is_carried=False,
            fight_properties=frozenset(),
        )
        return ConditionContext(
            {"caster": actor, "target": actor}, caster_target_distance=distance
        )

    def factory(self, **overrides):
        return NativeEffectRuntimeFactory(
            effects=overrides.get("effects", self.effects),
            state_catalog=overrides.get("states", self.states),
            characteristic_registry=self.registry,
            action_id=1,
            contexts=overrides.get("contexts", self.contexts),
            displacement_authority=overrides.get("displacement_authority"),
            compiled_effects=overrides.get("compiled_effects"),
        )

    def cast_context(self, request, fight):
        source = fight.actors[request["actor_id"]]
        return ConditionContext(
            {
                "caster": ConditionActor(
                    actor_id=source.id,
                    characteristics={"RANGE": 0},
                    is_carried=False,
                    fight_properties=frozenset(),
                )
            }
        )

    def test_real_spell6266_native_resolver_and_damage_share_costs_preview_uid_and_outbox(
        self,
    ):
        from unittest.mock import patch
        from contextlib import nullcontext
        from wakfu_server.combat_native_spell_casting import (
            definition as casting_definition,
        )
        from wakfu_server.combat_spell_usage import validate_usage

        body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)
        character = dict(id=7, breed=15, level=1)
        deck = encode_deck([6266])
        context = self.cast_context(dict(actor_id=7), self.fight)
        rule = casting_definition(6266, 1, context, {})
        self.assertEqual(rule["costs"]["ap"], 4)
        plan = dict(
            actor_id=7,
            spell_uid=(7 << 32) | 6266,
            target=(1, 0, 0),
            target_id=-7,
            spell_id=6266,
            evaluation_level=1,
            costs=dict(rule["costs"], extra_resource_deltas={}),
            effect_ids=tuple(rule["roots"]),
            native_usage=validate_usage(
                self.fight, self.fight.actors[7], 6266, 1, (1, 0, 0), context
            ),
        )
        # This unit isolates already-validated casting from transaction/runtime
        # costs, native effects and private outbox. Real QI/LOS casting has its
        # own source-backed integration fixtures; no production gate is bypassed.
        los = lambda *args: True
        with patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_cast",
            return_value=plan,
        ) as prepare, patch(
            "wakfu_server.combat_spell_transaction.cast_event_scope",
            side_effect=lambda dispatcher, selected: nullcontext(),
        ) as boundary:
            transaction = prepare_spell_transaction(
                body,
                character,
                self.fight,
                3,
                deck,
                wp_current=6,
                action_id=1,
                line_of_sight=los,
                runtime_factory=self.factory(),
                conditional_context=self.cast_context,
            )
        prepare.assert_called_once()
        # The focused factory has no owned retained-listener clone authority.
        # External cast observers are exercised by the real server fixtures.
        boundary.assert_called_once()
        self.assertIs(boundary.call_args.args[1], plan)
        args, kwargs = prepare.call_args
        self.assertIs(args[0], body)
        self.assertIs(args[1], character)
        self.assertIsNot(args[2], self.fight)
        self.assertIs(args[2], transaction.fight)
        self.assertEqual(args[3], 3)
        self.assertIs(args[4], deck)
        self.assertEqual(kwargs["wp"], 6)
        self.assertIs(kwargs["line_of_sight"], los)
        self.assertEqual(kwargs["conditional_context"], self.cast_context)
        self.assertLess(transaction.fight.actors[-7].hp, 20)
        self.assertEqual(transaction.fight.actors[8].hp, 40)
        self.assertEqual(transaction.fight.actors[7].ap, 2)
        self.assertEqual(transaction.fight.native_effect_uid_next, 201)
        self.assertEqual(
            [opcode for opcode, payload in transaction.packets], [12588, 12678, 12613]
        )
        self.assertEqual(
            (
                self.fight.actors[7].ap,
                self.fight.actors[-7].hp,
                self.fight.native_effect_uid_next,
            ),
            (6, 20, None),
        )

    def test_real_healing166935_targets_ally_and_preserves_source_scope(self):
        preview = deepcopy(self.fight)
        preview.actors[8].hp = 30
        dispatcher, packets = self.factory()(preview, {})
        dispatcher.execute(EffectInvocation(166935, 1, 7, 8, (0, 1, 0)))
        self.assertEqual(preview.actors[8].hp, 34)
        self.assertEqual(preview.actors[7].hp, 60)
        self.assertEqual([opcode for opcode, payload in packets], [12613])

    def test_shared_factory_routes_all_native_setters_and_owned_removal(self):
        from wakfu_server.combat_set_current_characteristic import (
            FAMILIES,
            set_current_registry,
        )
        from wakfu_server.combat_stat_handler import NativeStatHandler

        preview = deepcopy(self.fight)
        stat = set_current_registry()["560"]["fixed_stat_id"]
        target = preview.actors[8]
        target.effect_stats[stat] = 10
        target.effect_minima[stat] = -5000
        target.effect_maxima[stat] = 50000
        preview.actors[7].effect_stats[stat] = 30
        effects = dict(self.effects)
        effects["900001"] = definition(560, [100, 0])
        dispatcher, packets = self.factory(effects=effects)(preview, {})
        self.assertTrue(
            all(
                dispatcher.handlers[family] is dispatcher.handlers[560]
                for family in FAMILIES
            )
        )
        dispatcher.execute(EffectInvocation(900001, 1, 7, 8, target.position))
        self.assertEqual(target.effect_stats[stat], 100)
        uid = next(iter(preview.owned_stat_effects))
        target.effect_stats[stat] = 70
        remover = NativeStatHandler(
            preview,
            packets,
            registry=self.registry,
            action_id=1,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        remover.remove(uid)
        self.assertEqual(target.effect_stats[stat], -20)
        self.assertNotIn(uid, preview.owned_stat_effects)
        self.assertEqual(packets[-1][0], 13560)

    def test_shared_factory_hp_restore_assignment_frozen_and_cannot_raise(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler

        effects = dict(self.effects)
        effects["900196"] = definition(196, [])
        for frozen, properties, forced, expected in (
            (False, {}, None, 1),
            (False, {}, "30054801", 5),
            (True, {}, None, 20),
            (False, {66: 1}, None, 20),
        ):
            with self.subTest(frozen=frozen, properties=properties):
                preview = deepcopy(self.fight)
                target = preview.actors[8]
                target.hp = target.effect_stats[1] = 20
                target.effect_frozen = frozenset({1}) if frozen else frozenset()
                authority = SimpleNamespace(property_counts=lambda *args: properties)
                dispatcher, packets = self.factory(
                    effects=effects, displacement_authority=authority
                )(preview, {})
                dispatcher.execute(
                    EffectInvocation(
                        900196, 1, 7, 8, target.position, native_context_hex=forced
                    )
                )
                self.assertEqual(
                    (target.hp, target.effect_stats[1]), (expected, expected)
                )
                if properties:
                    self.assertEqual(packets, [])
                else:
                    uid = next(iter(preview.owned_stat_effects))
                    remover = NativeStatHandler(
                        preview,
                        packets,
                        registry=self.registry,
                        action_id=1,
                        allocate_uid=lambda: 999,
                        context=lambda *args: None,
                    )
                    remover.remove(uid)
                    self.assertEqual(target.hp, expected)
                    self.assertEqual(packets[-1][0], 13560)

    def test_shared_factory_affiliation_uses_signed_native_byte_and_restores(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler

        preview = deepcopy(self.fight)
        effects = dict(self.effects)
        effects["9001030"] = definition(1030, [130, 0])
        target = preview.actors[8]
        original_team = target.team
        authority = lambda *args: SimpleNamespace(targeting={"is_amO": True})
        dispatcher, packets = self.factory(
            effects=effects, displacement_authority=authority
        )(preview, {})
        dispatcher.execute(EffectInvocation(9001030, 1, 7, 8, target.position))
        self.assertEqual(target.native_fight_affiliation, -126)
        self.assertEqual(target.team, original_team)
        uid = next(iter(preview.owned_stat_effects))
        remover = NativeStatHandler(
            preview,
            packets,
            registry=self.registry,
            action_id=1,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        remover.remove(uid)
        self.assertEqual(target.native_fight_affiliation, original_team)
        self.assertEqual(packets[-1][0], 13560)

    def test_shared_factory_kill_removal_preserves_permanent_resource_changes(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler

        preview = deepcopy(self.fight)
        target = preview.actors[8]
        target.effect_stats[14] = 3
        target.effect_minima[14] = 0
        target.effect_maxima[14] = 10
        target.effect_base_minima = dict(target.effect_minima)
        target.effect_base_maxima = dict(target.effect_maxima)
        target.effect_percentages = {stat: 0 for stat in target.effect_stats}
        effects = dict(self.effects)
        effects["900002"] = definition(28, [0, 0])
        dispatcher, packets = self.factory(effects=effects)(preview, {})
        dispatcher.execute(EffectInvocation(900002, 1, 7, 8, target.position))
        self.assertEqual(
            (target.hp, target.effect_stats[14], target.effect_maxima[14]), (0, 0, 0)
        )
        uid = next(iter(preview.owned_stat_effects))
        remover = NativeStatHandler(
            preview,
            packets,
            registry=self.registry,
            action_id=1,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        remover.remove(uid)
        self.assertEqual(
            (target.hp, target.effect_stats[14], target.effect_maxima[14]), (0, 0, 0)
        )
        self.assertNotIn(uid, preview.owned_stat_effects)
        self.assertEqual(packets[-1][0], 13560)

    def test_factory_protected_kill_keeps_native_in_play_turn_and_qi_after_chain(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            global_fighter_guards,
        )
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_qi_registry import NativeQIRegistry

        preview = deepcopy(self.fight)
        # Explicit fresh synthetic QI: registration order is the fixture's
        # constructor order, not reconstructed final occupancy.
        terrain = dict(x=0, y=0, width=2, height=2, cell_masks=[0] * 4)
        registry = NativeQIRegistry(terrain, [None] * 127)
        registry.capture_fresh_cell_topology([])
        for actor in preview.actors.values():
            actor.native_obstacle_id = registry.register(
                dict(
                    identity=["actor", actor.id],
                    position=list(actor.position[:2]),
                    radius=0,
                    indexed=False,
                    movement_blocking=True,
                )
            )
        preview.native_qi_snapshot = terrain
        preview.native_qi_slots = registry.serialized_slots()
        preview.native_qi_touched_cells = registry.serialized_cells()
        preview.native_qi_byte_topology = registry.serialized_byte_topology()
        initialize_global_pv_collections(preview, tuple(preview.actors))
        target = preview.actors[-7]  # Sole opposing fighter: HP0 must not end it.
        target.effect_stats[14] = 3
        target.effect_minima[14] = 0
        target.effect_maxima[14] = 10
        target.effect_base_minima = dict(target.effect_minima)
        target.effect_base_maxima = dict(target.effect_maxima)
        target.effect_percentages = {stat: 0 for stat in target.effect_stats}
        target.native_fight_property_counts = {}
        before_order = tuple(preview.order)
        before_slots = deepcopy(preview.native_qi_slots)
        before_topology = deepcopy(preview.native_qi_byte_topology)
        effects = dict(self.effects)
        effects["900003"] = definition(332, [])
        authority = SimpleNamespace(
            property_counts=lambda fight, actor: actor.native_fight_property_counts
        )
        dispatcher, packets = self.factory(
            effects=effects, displacement_authority=authority
        )(preview, {})
        with preview.effect_resolution():
            dispatcher.execute(EffectInvocation(900003, 1, 7, -7, target.position))
        self.assertEqual(target.hp, 0)
        self.assertEqual(
            global_fighter_guards(preview, target.id),
            dict(baF=True, baG=False, baK=False),
        )
        self.assertEqual(preview.phase, "active")
        self.assertEqual(tuple(preview.order), before_order)
        self.assertEqual(preview.native_qi_slots, before_slots)
        self.assertEqual(preview.native_qi_byte_topology, before_topology)
        self.assertEqual(
            current_registry(preview).ordered_U(1, 0), (target.native_obstacle_id,)
        )

    def test_real_state3442_roots_and_owned_null_child_remove_before_replaced_carrier(
        self,
    ):
        preview = deepcopy(self.fight)
        factory = self.factory()
        dispatcher, packets = factory(preview, {})
        # Native159412: state3442, level=effect-level, independent chance-1.
        invocation = EffectInvocation(159412, 20, 7, 7, (0, 0, 0))
        dispatcher.execute(invocation)
        dispatcher.execute(invocation)
        self.assertEqual(set(preview.owned_stat_effects), {203})
        self.assertEqual(preview.owned_stat_effects[203]["state_uid"], 202)
        self.assertEqual(preview.native_effect_uid_next, 204)
        classes = [
            struct.unpack(">i", payload[13:17] if opcode == 12613 else payload[12:16])[
                0
            ]
            for opcode, payload in packets
        ]
        self.assertEqual(
            list(zip([opcode for opcode, payload in packets], classes)),
            [
                (12613, 310),
                (12613, 400),
                (13560, 400),
                (13560, 310),
                (12613, 310),
                (12613, 400),
            ],
        )

    def test_empty_cell_requires_authoritative_policy_and_never_fabricates_actor(self):
        self.effects["900002"] = definition(330, [0, 0, 0, 0, 0, 0], children=[])
        visited = []
        contexts = replace(
            self.contexts,
            resolution=lambda p, plan, e, i: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "cell", True
            ),
            cell_eligible=lambda p, plan, e, i: i.cell in p.walkable
            and not any(a.hp > 0 and a.position == i.cell for a in p.actors.values()),
            group_cells=lambda p, plan, e, i: visited.append(i.cell) or (i.cell,),
        )
        preview = deepcopy(self.fight)
        preview.walkable.add((2, 2, 0))
        dispatcher, packets = self.factory(contexts=contexts)(preview, {})
        self.assertFalse(
            dispatcher.execute(EffectInvocation(900002, 1, 7, None, (2, 2, 0)))
        )
        self.assertEqual(visited, [(2, 2, 0)])
        self.assertFalse(
            dispatcher.execute(EffectInvocation(900002, 1, 7, None, (99, 99, 0)))
        )
        self.assertEqual(packets, [])

    def test_later_unsupported_effect_rolls_back_damage_uid_and_owned_outbox(self):
        self.effects["900002"] = definition(987654, [])
        factory = self.factory()
        outboxes = []

        def bind(preview):
            dispatcher, packets = factory(preview, {})
            outboxes.append(packets)
            return dispatcher

        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                self.fight,
                [
                    EffectInvocation(339526, 1, 7, -7, (1, 0, 0)),
                    EffectInvocation(900002, 1, 7, -7, (1, 0, 0)),
                ],
                bind,
            )
        self.assertEqual(self.fight.actors[-7].hp, 20)
        self.assertIsNone(self.fight.native_effect_uid_next)
        self.assertEqual(
            len(outboxes[0]), 1
        )  # Failed preview's private, uncommitted outbox.

    def test_unknown_uid_start_and_collision_reject_before_execution(self):
        for value in (None, True, 0, -1, 1 << 63):
            contexts = replace(self.contexts, uid_start=lambda p, plan, v=value: v)
            with self.assertRaises(ValueError):
                self.factory(contexts=contexts)(deepcopy(self.fight), {})
        preview = deepcopy(self.fight)
        preview.owned_stat_effects[200] = {"state_uid": None}
        with self.assertRaisesRegex(ValueError, "conflicts with owned"):
            self.factory()(preview, {})

    def test_candidates_from_original_fight_rejected_in_preview(self):
        contexts = replace(
            self.contexts,
            actor_candidates=lambda p, plan, e, i: (self.fight.actors[-7],),
        )
        dispatcher, packets = self.factory(contexts=contexts)(deepcopy(self.fight), {})
        with self.assertRaisesRegex(ValueError, "same authoritative preview"):
            dispatcher.execute(EffectInvocation(339526, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(packets, [])

    def test_mixed_group_state_cycle_and_ancestor_restoration(self):
        states = dict(self.states, effects=dict(self.states["effects"]))
        states["effects"]["150327"] = definition(330, [], children=[900001])
        effects = {
            "900001": definition(330, [], children=[900002]),
            "900002": definition(304, [3442, 0, 20, 0, -1, 0], selector=2),
        }
        preview = deepcopy(self.fight)
        # Synthetic cycle nodes need their declared native direct-target policy.
        from wakfu_server.combat_direct_target import native_direct_target_policies

        policies = dict(native_direct_target_policies())
        policies.update(
            {
                "900001": [330, False, False],
                "900002": [304, False, False],
                "150327": [330, False, False],
            }
        )
        with patch(
            "wakfu_server.combat_direct_target.native_direct_target_policies",
            return_value=policies,
        ):
            dispatcher, packets = self.factory(effects=effects, states=states)(
                preview, {}
            )
        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "Effect recursion limit exceeded"
        ):
            dispatcher.execute(EffectInvocation(900001, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(dispatcher._active_ancestors, ())
