"""Light common conditions+real adapter; no large combat catalogs."""
import unittest
from dataclasses import replace
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_runtime_adapter import (
    NativeActorAuthority,
    NativeCastAuthority,
    NativeServerRuntimeAdapter,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state import Actor, Fight


class ReadyAreaConditionTests(unittest.TestCase):
    def setUp(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (2, 0, 0), 20, 6, 3, 5, 1),
        ]
        self.fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position}},
        )
        self.fight.ready(3)
        for actor in self.fight.actors.values():
            actor.physical_radius = 0
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_minima = {}
            actor.effect_frozen = frozenset()
        self.fight.native_effect_areas = {
            901: dict(
                uid=901,
                reference=1546,
                cell=(0, 0, 0),
                owner_id=7,
                native_hour_contract=True,
            ),
            902: dict(
                uid=902,
                reference=1546,
                cell=(2, 0, 0),
                owner_id=-7,
                native_hour_contract=True,
            ),
        }

        def authority(preview, actor):
            return NativeActorAuthority(
                {"is_eGj": True},
                actor.controlled,
                frozenset(),
                frozenset(),
                False,
                3 if actor.controlled else 1,
                0,
                {},
                True,
                is_summon=False,
                summon_root_id=actor.id,
                native_controller_id=actor.id,
            )

        noop = lambda *a: None
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=authority, cast=NativeCastAuthority(*([noop] * 10))
        )
        self.invocation = EffectInvocation(1, 1, 7, -7, (2, 0, 0))

    def context(self, source=None):
        return self.adapter.condition(
            self.fight,
            {},
            None,
            replace(self.invocation, native_trigger_context=source),
        )

    def test_base_id_counts_all_or_exact_selected_owner(self):
        context = self.context({"caster_id": 7, "target_id": -7})
        self.assertTrue(evaluate_condition("NbAreasWithBaseId(1546)==2", context))
        self.assertTrue(
            evaluate_condition('NbAreasWithBaseId(1546,"caster")==1', context)
        )
        self.assertTrue(
            evaluate_condition('NbAreasWithBaseId(1546,"triggeringTarget")==1', context)
        )
        self.assertTrue(evaluate_condition("NbAreasWithBaseId(901)==0", context))
        self.assertTrue(
            evaluate_condition('NbAreasWithBaseId(1546,"unrecognized")==0', context)
        )
        null = self.context({"caster_id": 7, "target_id": None})
        self.assertTrue(
            evaluate_condition('NbAreasWithBaseId(1546,"triggeringTarget")==0', null)
        )

    def test_specific_area_geometry_and_own_or_team_filter(self):
        context = self.context()
        for expression in (
            'IsOnSpecificEffectArea("target",1546)',
            'IsOnSpecificEffectArea("target",1546,True)',
            'IsOnSpecificEffectArea("target",1546,"teamAreas")',
        ):
            self.assertTrue(evaluate_condition(expression, context))
        self.fight.native_effect_areas[902]["owner_id"] = 7
        self.assertFalse(
            evaluate_condition(
                'IsOnSpecificEffectArea("target",1546,"ownAreas")', context
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsOnSpecificEffectArea("target",1546,"teamAreas")', context
            )
        )
        self.assertTrue(
            evaluate_condition(
                'IsOnSpecificEffectArea("target",1546,"unknownMode")', context
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsOnSpecificEffectArea("unknownSelector",1546)', context
            )
        )

    def test_own_summon_accepts_triggering_selector_and_known_null(self):
        self.assertFalse(
            evaluate_condition(
                'IsOwnSummon("triggeringTarget")', self.context({"target_id": None})
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsOwnSummon("triggeringTarget")', self.context({"target_id": -7})
            )
        )
        actor = ConditionActor(
            is_native_fighter=True, breed_id=42, is_summon=True, summon_root_id=7
        )
        source = ConditionActor(is_native_fighter=True, summon_root_id=7)
        context = ConditionContext(
            {"caster": source}, own_summon_actor_query=lambda selector: actor
        )
        self.assertTrue(
            evaluate_condition('IsOwnSummon(65578,"triggeringTarget")', context)
        )
        self.assertFalse(
            evaluate_condition('IsOwnSummon(41,"triggeringTarget")', context)
        )

    def test_state_from_user_adapter_empty_ledger_and_known_null(self):
        self.assertFalse(
            evaluate_condition(
                'HasStateFromUser(8200,"triggeringTarget")',
                self.context({"target_id": -7}),
            )
        )
        self.assertFalse(
            evaluate_condition(
                'HasStateFromUser(8200,"triggeringTarget")',
                self.context({"target_id": None}),
            )
        )
        with self.assertRaisesRegex((ValueError, UnknownCondition), "Unregistered"):
            evaluate_condition(
                'HasStateFromUser(8200,"triggeringTarget")',
                self.context({"target_id": 999}),
            )

    def test_missing_manager_and_unknown_relationship_never_fake_empty(self):
        context = self.context()
        self.fight.native_effect_areas = None
        with self.assertRaisesRegex(UnknownCondition, "area manager"):
            evaluate_condition("NbAreasWithBaseId(1546)==0", context)
        self.fight.native_effect_areas = {}
        with self.assertRaisesRegex(UnknownCondition, "source relationship"):
            evaluate_condition(
                'IsOwnSummon("triggeringTarget")', self.context({"caster_id": 7})
            )
