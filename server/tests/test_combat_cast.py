import struct
import unittest
from types import SimpleNamespace
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_conditional_costs import ConditionalCostContext
from wakfu_server.combat_cast import (
    decode_cast,
    normal_damage_profile,
    prepare_cast,
    prepare_spell_cast,
)
from wakfu_server.spells import encode_deck


def cast_context(*, states=(), deck=(), range_value=0, carried=False, properties=()):
    """Complete live caster authority for native cast selection and range."""
    caster = ConditionActor(
        state_ids=None if states is None else frozenset(states),
        deck_spell_ids=frozenset(deck),
        excluded_deck_spell_ids=frozenset(),
        is_player=True,
        is_carried=carried,
        fight_properties=frozenset(properties),
        characteristics={"RANGE": range_value},
    )
    return ConditionContext({"caster": caster})


def cast_authority(*, states=(), deck=(), ap_modifiers=None):
    context = cast_context(states=states, deck=deck)
    return lambda *args: ConditionalCostContext(context, ap_modifiers)


class CastValidationTests(unittest.TestCase):
    def test_simple_spell_ap_modifiers_apply_before_resource_validation(self):
        from wakfu_server.combat_conditional_costs import native_catalog
        from wakfu_server.combat_conditions import UnknownCondition

        category = native_catalog()["spell_categories"]["6260"][0]
        self.actor.spell_ap_cost_modifiers = {category: -2}
        self.actor.ap = 1
        plan = prepare_spell_cast(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6260]),
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
        )
        self.assertEqual(plan["costs"]["ap"], 1)
        self.assertEqual(self.actor.ap, 1)
        self.actor.spell_ap_cost_modifiers = {category: 2}
        with self.assertRaises(ValueError):
            prepare_spell_cast(
                self.body,
                self.character,
                self.fight,
                3,
                encode_deck([6260]),
                wp=6,
                line_of_sight=lambda *a: True,
                conditional_context=cast_authority(
                    ap_modifiers=self.actor.spell_ap_cost_modifiers
                ),
            )
        self.actor.spell_ap_cost_modifiers = None
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                self.body,
                self.character,
                self.fight,
                3,
                encode_deck([6260]),
                wp=6,
                line_of_sight=lambda *a: True,
                conditional_context=cast_authority(
                    ap_modifiers=self.actor.spell_ap_cost_modifiers
                ),
            )

    def test_conditional_cost_callback_uses_live_state_and_native_modifier_snapshot(
        self,
    ):
        from wakfu_server.combat_conditions import UnknownCondition

        self.target.position = (3, 0, 0)
        character = dict(self.character, breed=8, level=200)
        self.actor.effective_level = 200
        body = struct.pack(">qqiih", 7, (7 << 32) | 4785, 3, 0, 0)
        context = cast_context(states=[6117])
        args = dict(wp=6, line_of_sight=lambda *a: True)
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([4785]),
                conditional_context=lambda *unused: ConditionalCostContext(
                    cast_context(states=None), {}
                ),
                **args
            )
        calls = []

        def authority(request, fight):
            calls.append((request["spell_uid"], fight.current.ap))
            # Enrich the tested state authority with complete range inputs.
            return ConditionalCostContext(context, {})

        plan = prepare_spell_cast(
            body,
            character,
            self.fight,
            3,
            encode_deck([4785]),
            conditional_context=authority,
            **args
        )
        self.assertEqual(plan["costs"]["ap"], 3)
        self.assertEqual(calls, [((7 << 32) | 4785, 6)])
        self.assertEqual(self.actor.ap, 6)
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([4785]),
                conditional_context=lambda *a: ConditionalCostContext(context, None),
                **args
            )

    def setUp(self):
        self.character = dict(id=7, breed=15, level=1)
        self.actor = SimpleNamespace(
            id=7,
            owner_id=3,
            controlled=True,
            hp=60,
            ap=6,
            mp=3,
            team=0,
            effective_level=1,
            position=(0, 0, 0),
            turn_count=0,
            physical_radius=0,
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
        )
        self.target = SimpleNamespace(
            id=-7, hp=20, team=1, position=(2, 0, 0), physical_radius=0
        )
        self.fight = SimpleNamespace(
            id=77,
            phase="active",
            current=self.actor,
            actors={7: self.actor, -7: self.target},
            walkable={(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)},
            native_table_turn=0,
        )
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6260, 2, 0, 0)

    def prepare(self, **options):
        args = dict(
            complete=False,
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
            select_effect=lambda *a: True,
            mitigate=lambda damage, *a: damage,
        )
        args.update(options)
        return prepare_cast(
            self.body, self.character, self.fight, 3, encode_deck([6260]), **args
        )

    def test_own_normal_cast_and_native_profiles(self):
        p = self.prepare()
        self.assertEqual((p["damage"], p["costs"]["ap"], p["target_id"]), (3, 3, -7))
        self.assertEqual(normal_damage_profile(6261, 1)["maximum"], 1)
        self.assertGreater(normal_damage_profile(6260, 200)["damage"], 3)

    def test_common_validation_accepts_self_spells_across_classes(self):
        self.actor.effective_level = 200
        for breed, spell in [(1, 6983), (8, 4779), (15, 7551)]:
            character = dict(self.character, breed=breed, level=200)
            body = struct.pack(">qqiih", 7, (7 << 32) | spell, 0, 0, 0)
            plan = prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([spell]),
                wp=6,
                line_of_sight=lambda *args: True,
                conditional_context=cast_authority(ap_modifiers={}),
            )
            self.assertEqual(plan["target_id"], self.actor.id)
            self.assertEqual(plan["spell_id"], spell)
            self.assertTrue(plan["effect_ids"])
        self.assertEqual(self.actor.ap, 6)  # Validation never spends resources.

    def test_common_validation_keeps_empty_cell_target(self):
        self.actor.effective_level = 200
        character = dict(self.character, level=200)
        body = struct.pack(">qqiih", 7, (7 << 32) | 7551, 1, 0, 0)
        plan = prepare_spell_cast(
            body,
            character,
            self.fight,
            3,
            encode_deck([7551]),
            wp=6,
            line_of_sight=lambda *args: True,
            conditional_context=cast_authority(ap_modifiers={}),
        )
        self.assertIsNone(plan["target_id"])
        self.assertEqual(plan["target"], (1, 0, 0))

    def test_reject_unknown_branch_los_and_resources(self):
        for opts in [
            dict(select_effect=lambda *a: None),
            dict(line_of_sight=lambda *a: False),
        ]:
            with self.assertRaises(ValueError):
                self.prepare(**opts)
        self.actor.ap = 2
        with self.assertRaises(ValueError):
            self.prepare()

    def test_complete_cast_rejects_omitted_mp_effect(self):
        with self.assertRaises(ValueError):
            self.prepare(complete=True)

    def test_reject_uid_owner_deck_and_exact_length(self):
        self.body = struct.pack(">qqiih", 7, (8 << 32) | 6260, 2, 0, 0)
        with self.assertRaises(ValueError):
            self.prepare()
        with self.assertRaises(ValueError):
            decode_cast(self.body + b"\0")

    def test_bare_selector_native_close_branch_and_unknown_states(self):
        from wakfu_server.combat_bare_effects import bare_damage_selector

        selector = bare_damage_selector(
            critical_chance=0, running_effects=[], summons=[], bonuses={}
        )
        self.assertTrue(
            selector(
                6260,
                normal_damage_profile(6260, 1),
                self.actor,
                self.target,
                self.fight,
            )
        )
        self.assertFalse(
            selector(
                6266,
                normal_damage_profile(6266, 1),
                self.actor,
                self.target,
                self.fight,
            )
        )
        self.target.position = (1, 0, 0)
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)
        plan = prepare_cast(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6266]),
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
            select_effect=selector,
            mitigate=lambda damage, *a: damage,
        )
        self.assertEqual(
            (plan["generic_effect"], plan["damage"], plan["pending_side_effects"]),
            (339526, 5, None),
        )
        with self.assertRaises(ValueError):
            bare_damage_selector(
                critical_chance=0, running_effects=None, summons=[], bonuses={}
            )
