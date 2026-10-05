from copy import deepcopy
from itertools import count
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    run_effect_transaction,
)
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_healing_handler import (
    NativeHealingHandler,
    HealingExecutionContext,
)
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_removal import _identity_fields


def definition(kind, parameters=(), children=()):
    return dict(
        effect_class=kind,
        parameters=[n for value in parameters for n in (value, 0)],
        children=list(children),
        native_effect_flags=[],
        criteria="",
        parameter_count=len(parameters),
        minimum_level=1,
        maximum_level=200,
        probability_base=100,
        probability_per_level=0,
        native_localization_enabled=True,
    )


class ValueTransferRuntimeTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        pc.hp = 20
        for actor in (pc, npc):
            actor.effect_stats = {92: 0, 97: 0, 100: 0, 32: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        pc.effect_stats[100] = 15
        npc.effect_stats.update({97: 20, 92: 30})
        npc.effect_maxima[92] = 30
        self.effects = {
            "90": definition(865, (50, 0, 0, -1), (91, 92)),
            "91": definition(1, (101,)),
            "92": definition(25, (1,)),
        }
        self.outbox = []

    def factory(self, preview):
        uids = count(100)
        damage = NativeDamageHandler(
            preview,
            self.outbox,
            action_id=1,
            allocate_uid=lambda: next(uids),
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
            rng=lambda: 0.99,
        )
        heal = NativeHealingHandler(
            preview,
            self.outbox,
            action_id=1,
            allocate_uid=lambda: next(uids),
            context=lambda *args: HealingExecutionContext(
                False, True, False, False, 0, 0, False, 0, 1000, True
            ),
            rng=lambda: 0.99,
        )
        retention = object.__new__(NativeRetainedRuntime)
        retention.fight = preview
        retention.plan = {"native_retained_container": {"present": True, "level": 1}}
        # Only immediate child execution/context is tested here; retained wire is separate.
        retention.begin_group = lambda *args: None
        retention.finish_group = lambda *args: None
        retention.is_subscription = lambda *args: False
        return EffectDispatcher(
            self.effects,
            {1: damage, 25: heal},
            resolve=lambda effect, inv: (inv,),
            condition_context=lambda inv: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda actor: preview.actors[actor].position,
            group_retention=retention,
            transfer_probability=lambda fraction: False,
        )

    def test_damage_value_transfers_to_heal_not_actual_hp_loss(self):
        before = deepcopy(self.fight)
        preview, outcomes = run_effect_transaction(
            self.fight, [EffectInvocation(90, 1, 7, -7, (9, 9, 0))], self.factory
        )
        self.assertEqual(outcomes, (True,))
        self.assertEqual(preview.actors[-7].hp, 64)  # HP loss36, runner value101.
        self.assertEqual(preview.actors[7].hp, 70)  # Floor(101*50%)=50, not18.
        self.assertEqual(
            [_identity_fields(packet[1][19:])[4] for packet in self.outbox], [101, 50]
        )
        self.assertEqual(
            (self.fight.actors[7].hp, self.fight.actors[-7].hp),
            (before.actors[7].hp, before.actors[-7].hp),
        )

    def test_later_unsupported_child_rolls_back_first_real_damage(self):
        self.effects["92"] = definition(987654)
        with self.assertRaisesRegex(ValueError, "No handler"):
            run_effect_transaction(
                self.fight, [EffectInvocation(90, 1, 7, -7, (1, 0, 0))], self.factory
            )
        self.assertEqual(
            (self.fight.actors[-7].hp, self.fight.actors[7].effect_stats[100]),
            (100, 15),
        )
