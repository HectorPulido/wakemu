"""Native item PL, explicit SELF and null PS remain separate from outer spell."""
from types import SimpleNamespace
import unittest
from wakfu_server.combat_copied_equipment_execution import (
    equipment_effect_definitions,
    equipment_initializer,
)
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon import RegisteredSummonAuthority


class CopiedEquipmentExecutionTests(unittest.TestCase):
    def root(self):
        return dict(
            reference=91,
            effect_class=20,
            parameters=[1, 0],
            parameter_count=1,
            variant=2,
            minimum_level=0,
            maximum_level=200,
            children=[],
            child_definitions=[],
            criterion_raw="",
            metadata=dict(
                target_masks=[None] * 7,
                native_target_selector=dict(**{"class": "fcE"}, mask=1),
                native_effect_flags=[],
                native_definition_class="eVy",
                area_class="anD",
                area_native="point",
                probability_base=100,
                probability_per_level=0,
            ),
        )

    def test_missing_native_variant_is_not_filled_from_an_outer_spell(self):
        row = self.root()
        del row["variant"]
        with self.assertRaisesRegex(ValueError, "closure"):
            equipment_effect_definitions(dict(roots=[row]))

    def test_wrong_group_child_order_rejects_before_execution(self):
        row = self.root()
        row.update(
            children=[4, 91], child_definitions=[dict(reference=91), dict(reference=4)]
        )
        with self.assertRaisesRegex(ValueError, "child order"):
            equipment_effect_definitions(dict(roots=[row]))

    def test_actual_registered_metadata_item_container_and_repeated_self_calls(self):
        actor = SimpleNamespace(id=229, position=(-23, -142, 70), hp=42, max_hp=42)
        fight = SimpleNamespace(actors={229: actor}, native_active_spell_id=4603)
        metadata = NativeActorAuthority(
            targeting={},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=3251,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
            is_summon=True,
            native_in_play=True,
        )

        class Authority(RegisteredSummonAuthority):
            def __call__(self, preview, value):
                if preview is not fight or value is not actor:
                    raise AssertionError("Wrong actual registered PV")
                return metadata

        authority = object.__new__(Authority)
        invocations = []
        plans = []

        class Factory:
            summon_authority = authority
            effects = {}
            state_catalog = dict(states={}, effects={})

            def __call__(self, preview, plan):
                plans.append(plan)
                return SimpleNamespace(execute=invocations.append), []

        container = dict(
            present=True, type=12, id=12, level=60, is_spell=False, native_kind="item"
        )
        source = dict(
            source_actor_id=7,
            dsK=12,
            native_plan=dict(
                roots=[self.root(), self.root()], native_retained_container=container
            ),
        )
        equipment_initializer(Factory())(fight, actor, source)
        self.assertEqual([call.reference for call in invocations], [91, 91])
        self.assertTrue(
            all(
                call.caster_id == call.target_id == 229
                and call.native_explicit_target
                and call.native_trigger_context is None
                and call.native_value_scope is None
                and call.level == 60
                for call in invocations
            )
        )
        self.assertEqual(plans, [dict(native_retained_container=container)])
        self.assertEqual(fight.native_active_spell_id, 4603)
        self.assertEqual(actor.native_applied_equipment_calls[0]["roots"], [91, 91])

    def test_later_native_forced_maximum_replaces_preceding_item_maximum(self):
        from wakfu_server.combat_force_characteristic import (
            forced_parameters,
            forced_transition,
        )

        # Native eYO's set-maximum flag replaces PA.or's input, irrespective
        # of any preceding item maximum gain. It does not add to that gain.
        value, maximum, percent = forced_parameters(
            [1, 1, 1, 0], 420, caster_current=2105, target_maximum=821, rng=lambda: 0
        )
        self.assertEqual((value, maximum, percent), (421, True, False))
        for previous in (421, 621, 821):
            result = forced_transition(
                value=value,
                set_maximum=maximum,
                current=previous,
                raw=previous,
                maximum=previous,
                minimum=0,
                raw_min=0,
                percent=0,
                low=0,
                high=2147483647,
                over_max_current=False,
            )
            self.assertEqual(result, (421, 421, 421))
