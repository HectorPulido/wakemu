from copy import deepcopy
from dataclasses import replace
import json
import struct
import unittest
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
            (DATA_ROOT / "effect-characteristic-registry.json").read_text()
        )

    def setUp(self):
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
        self.effects = dict(self.spells["effects"])
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
        )

    def test_real_spell6266_native_resolver_and_damage_share_costs_preview_uid_and_outbox(
        self,
    ):
        body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)
        transaction = prepare_spell_transaction(
            body,
            dict(id=7, breed=15, level=1),
            self.fight,
            3,
            encode_deck([6266]),
            wp_current=6,
            action_id=1,
            line_of_sight=lambda *a: True,
            runtime_factory=self.factory(),
        )
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
                (13497, 400),
                (13560, 400),
                (13560, 310),
                (12613, 310),
                (13497, 400),
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
        dispatcher, packets = self.factory(effects=effects, states=states)(preview, {})
        with self.assertRaisesRegex(UnsupportedEffectExecution, "Recursive"):
            dispatcher.execute(EffectInvocation(900001, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(dispatcher._active_ancestors, ())
