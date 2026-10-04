import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionCell,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeConditionsTests(unittest.TestCase):
    def setUp(self):
        self.context = ConditionContext(
            {
                "caster": ConditionActor(
                    frozenset({7647}), frozenset({6999, 4610}), frozenset({4610}), True
                ),
                "target": ConditionActor(frozenset(), is_player=False),
            }
        )

    def test_native_deck_default_exclusions_and_non_player(self):
        self.assertTrue(evaluate_condition("IsSpellInDeck(6999)", self.context))
        self.assertFalse(evaluate_condition("IsSpellInDeck(4610)", self.context))
        self.assertFalse(
            evaluate_condition('IsSpellInDeck(6999, "target")', self.context)
        )

    def test_native_state_explicit_actor_and_boolean_precedence(self):
        self.assertTrue(
            evaluate_condition(
                'HasState(7647, "CASTER") and not HasState(7647, "target")',
                self.context,
            )
        )
        self.assertTrue(evaluate_condition("False and False or True", self.context))
        self.assertFalse(evaluate_condition("(False or True) and False", self.context))
        self.assertTrue(evaluate_condition("", self.context))
        self.assertTrue(evaluate_condition("HasState(7647)", self.context))
        self.assertTrue(
            evaluate_condition(
                "HasState(7647)\r\nand IsSpellInDeck(6999)", self.context
            )
        )

    def test_unknown_never_becomes_supported_due_to_short_circuit(self):
        for expression in (
            'False and HasUnknownFightProperty("target", 11)',
            'True or IsUnknownSummon(7647, "target")',
            "HasState(7647, 2)",
            'GetUnknownTeamId("caster") <> GetUnknownTeamId("target")',
            '__import__("os")',
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, self.context)

    def test_character_kind_includes_npc_and_preserves_unknown(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_character=True, is_player=True),
                "target": ConditionActor(is_character=True, is_player=False),
            }
        )
        self.assertTrue(evaluate_condition("IsCharacter()", context))
        self.assertTrue(evaluate_condition('IsCharacter("target")', context))
        noncharacter = ConditionContext({"caster": ConditionActor(is_character=False)})
        self.assertFalse(evaluate_condition("IsCharacter()", noncharacter))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('not IsCharacter("target")', self.context)

    def test_effect_caster_is_current_criterion_actor_identity(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(actor_id=-7),
                "target": ConditionActor(actor_id=8),
            }
        )
        self.assertTrue(evaluate_condition("GetEffectCaster() == -7", context))
        self.assertFalse(evaluate_condition("GetEffectCaster() == 8", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetEffectCaster() == 0", self.context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetEffectCaster("target") == 8', context)

    def test_has_state_level_is_exact_first_match_not_threshold(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(state_levels=((3448, 3), (3448, 4))),
                "target": ConditionActor(state_levels=((3448, 4),)),
            }
        )
        self.assertTrue(evaluate_condition("HasState(3448, 3)", context))
        self.assertFalse(evaluate_condition('HasState(3448, 4, "caster")', context))
        self.assertTrue(evaluate_condition('HasState(3448, 4, "target")', context))
        self.assertFalse(evaluate_condition("HasState(9999, 0)", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('not HasState(3448, 4, "target")', self.context)

    def test_missing_context_is_not_false_and_negated_into_true(self):
        for expression in ("not IsSpellInDeck(6999)", 'not HasState(7647, "caster")'):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    expression,
                    ConditionContext({"caster": ConditionActor(is_player=True)}),
                )

    def test_state_source_uses_first_matching_effect_not_any_source(self):
        def context(sources):
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=10),
                    "target": ConditionActor(state_sources=sources),
                }
            )

        criterion = 'HasStateFromUser(7778, "target")'
        self.assertTrue(evaluate_condition(criterion, context(((7778, 10),))))
        self.assertFalse(
            evaluate_condition(criterion, context(((7778, 11), (7778, 10))))
        )
        self.assertFalse(
            evaluate_condition(criterion, context(((7778, None), (7778, 10))))
        )
        self.assertFalse(evaluate_condition(criterion, context(())))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(criterion, context(None))

    def test_cell_checks_terrain_obstacles_and_optional_strict_occupancy(self):
        def free(cell, strict=False):
            return evaluate_condition(
                "IsTargetCellFree(True)" if strict else "IsTargetCellFree()",
                ConditionContext({}, cell),
            )

        self.assertTrue(free(ConditionCell(True, False)))
        self.assertFalse(free(ConditionCell(False, False)))
        self.assertFalse(free(ConditionCell(True, True)))
        self.assertFalse(free(ConditionCell(True, False, (True,))))
        self.assertTrue(free(ConditionCell(True, False, (False,))))
        self.assertFalse(free(ConditionCell(True, False, (False,)), strict=True))
        with self.assertRaises(UnknownCondition):
            free(None)

    def test_carried_default_caster_and_target(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_carried=False),
                "target": ConditionActor(is_carried=True),
            }
        )
        self.assertFalse(evaluate_condition("IsCarried()", context))
        self.assertTrue(evaluate_condition('IsCarried("target")', context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('not IsCarried("target")', self.context)

    def test_native_distance_branches_require_explicit_current_distance(self):
        near = "GetDistanceBetweenCasterAndTarget() == 1"
        far = "GetDistanceBetweenCasterAndTarget() >= 2"
        for distance, expected in ((1, True), (2, False), (8, False)):
            context = ConditionContext({}, caster_target_distance=distance)
            self.assertEqual(evaluate_condition(near, context), expected)
            self.assertEqual(evaluate_condition(far, context), not expected)
        absent = ConditionContext({}, caster_target_distance=-1)
        self.assertFalse(evaluate_condition(near, absent))
        self.assertFalse(evaluate_condition(far, absent))
        self.assertFalse(
            evaluate_condition("GetDistanceBetweenCasterAndTarget() >= 0", absent)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(near, ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetDistanceBetweenCasterAndTarget(1) == 1", ConditionContext({})
            )

    def test_native_summon_counts_and_filtered_breed(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=2, summon_counts_by_breed={2011: 1}
                ),
                "target": ConditionActor(summon_count=0),
            }
        )
        self.assertTrue(
            evaluate_condition(
                'NbSummons("caster") > 0 and NbSummons("caster", 2011) >= 1', context
            )
        )
        self.assertTrue(
            evaluate_condition('NbSummons() == 2 and NbSummons("target") == 0', context)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('NbSummons("caster", 999) == 0', context)

    def test_breed_selector_precedes_variadic_ids(self):
        context = ConditionContext({"target": ConditionActor(breed_id=4559)})
        self.assertTrue(evaluate_condition('IsBreedId("target", 4559)', context))
        self.assertTrue(evaluate_condition('IsBreedId("target", 3795, 4559)', context))
        self.assertFalse(evaluate_condition('IsBreedId("target", 3795)', context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsBreedId(4559, "target")', context)

    def test_alignment_requires_verified_native_positions_result(self):
        self.assertTrue(
            evaluate_condition(
                "IsInAlignment()", ConditionContext({}, is_in_alignment=True)
            )
        )
        self.assertFalse(
            evaluate_condition(
                "IsInAlignment()", ConditionContext({}, is_in_alignment=False)
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("not IsInAlignment()", ConditionContext({}))

    def test_characteristic_comparisons_arithmetic_and_float_percentage(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    characteristics={"HP": 81, "AP": 3, "WP": 0, "ARMOR": None},
                    characteristic_maxima={"HP": 101},
                ),
                "target": ConditionActor(
                    characteristics={"HP": 50}, characteristic_maxima={"HP": 100}
                ),
            }
        )
        self.assertTrue(evaluate_condition('GetCharac("AP") * 2 - 1 == 5', context))
        self.assertTrue(
            evaluate_condition('GetCharacteristic("PA") / 2 == 1.5', context)
        )
        self.assertTrue(
            evaluate_condition('GetCharacInPct("HP", "caster") == 80', context)
        )
        self.assertTrue(
            evaluate_condition('GetCharacPct("HP", "target") == 50', context)
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharac("ARMOR") == -1 and GetCharac("WP") == 0', context
            )
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharacPct("HP") - GetCharacPct("HP", "target") >= 30', context
            )
        )

    def test_native_maximum_and_element_aliases_use_authoritative_snapshot(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    characteristics={"AP": 3, "DMG_FIRE_PERCENT": 42, "ARMOR": None},
                    characteristic_maxima={"AP": 7, "DMG_FIRE_PERCENT": 60},
                ),
                "target": ConditionActor(
                    characteristics={"HP": 10}, characteristic_maxima={"HP": 100}
                ),
            }
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharacMax("PA") == 7 and GetCharac("AP") == 3', context
            )
        )
        self.assertTrue(
            evaluate_condition('GetCharacteristicMax("HP", "target") == 100', context)
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharac("DMG_FIRE") == 42 and GetCharacMax("DMG_FIRE") == 60',
                context,
            )
        )
        self.assertTrue(evaluate_condition('GetCharacMax("ARMOR") == -1', context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetCharacMax("HP") == 0', context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetCharacMax("AP") == 3',
                ConditionContext({"caster": ConditionActor(characteristics={"AP": 3})}),
            )

    def test_own_summon_uses_native_chain_root_and_target_default(self):
        from dataclasses import replace

        caster = ConditionActor(
            actor_id=7, is_native_fighter=True, is_summon=False, summon_root_id=7
        )
        target = ConditionActor(
            actor_id=8,
            is_native_fighter=True,
            is_summon=True,
            summon_root_id=7,
            breed_id=42,
        )

        def context(candidate):
            return ConditionContext({"caster": caster, "target": candidate})

        self.assertTrue(evaluate_condition("IsOwnSummon()", context(target)))
        self.assertTrue(
            evaluate_condition('IsOwnSummon(42, "target")', context(target))
        )
        self.assertTrue(evaluate_condition("IsOwnSummon(65578)", context(target)))
        self.assertFalse(evaluate_condition("IsOwnSummon(41)", context(target)))
        self.assertFalse(evaluate_condition('IsOwnSummon("caster")', context(target)))
        self.assertFalse(
            evaluate_condition(
                "IsOwnSummon()", context(replace(target, summon_root_id=9))
            )
        )
        self.assertFalse(
            evaluate_condition(
                "IsOwnSummon()", context(replace(target, is_summon=False))
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsOwnSummon()", context(replace(target, summon_root_id=None))
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsOwnSummon("eventTarget")', context(target))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("True or IsOwnSummon(True)", context(target))

    def test_team_id_reads_signed_native_affiliation(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(fight_affiliation=-128),
                "target": ConditionActor(fight_affiliation=127),
            }
        )
        self.assertTrue(evaluate_condition("GetTeamId() == -128", context))
        self.assertTrue(
            evaluate_condition('GetTeamId("caster") <> GetTeamId("target")', context)
        )
        for expression in ("GetTeamId(0) == 0", 'GetTeamId("eventTarget") == 0'):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetTeamId() == 0", ConditionContext({"caster": ConditionActor()})
            )

    def test_effect_presence_uses_generic_id_and_native_int_narrowing(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(retained_effect_ids=frozenset()),
                "target": ConditionActor(retained_effect_ids=frozenset({308267})),
            }
        )
        self.assertTrue(
            evaluate_condition('HasEffectWithSpecificId("target",308267)', context)
        )
        self.assertTrue(
            evaluate_condition('HasEffectWithSpecificId("target",4295275563)', context)
        )
        self.assertFalse(
            evaluate_condition('HasEffectWithSpecificId("caster",308267)', context)
        )
        self.assertFalse(
            evaluate_condition('HasEffectWithSpecificId("target",400)', context)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'not HasEffectWithSpecificId("target",308267)',
                ConditionContext({"target": ConditionActor()}),
            )

    def test_fight_membership_defaults_to_caster_and_preserves_unknown(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(in_fight=True),
                "target": ConditionActor(in_fight=False),
            }
        )
        self.assertTrue(evaluate_condition("IsInFight()", context))
        self.assertFalse(evaluate_condition('IsInFight("target")', context))
        for expression in ("IsInFight(1)", 'IsInFight("eventTarget")'):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "not IsInFight()", ConditionContext({"caster": ConditionActor()})
            )

    def test_physical_radius_requires_native_selector_and_snapshot(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(physical_radius=0),
                "target": ConditionActor(physical_radius=2),
            }
        )
        self.assertTrue(evaluate_condition('GetPhysicalRadius("caster") == 0', context))
        self.assertTrue(
            evaluate_condition('GetPhysicalRadius("target") + 1 == 3', context)
        )
        for expression in (
            "GetPhysicalRadius() == 0",
            "GetPhysicalRadius(1) == 0",
            'GetPhysicalRadius("eventTarget") == 0',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetPhysicalRadius("caster") == 0',
                ConditionContext({"caster": ConditionActor()}),
            )

    def test_native_numbers_do_not_accept_missing_data_or_unverified_stats(self):
        for expression in (
            'GetCharac("AP") > 0',
            'GetCharac("INVENTED") == 0',
            'GetCharacInPct("HP") >= 0',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    expression, ConditionContext({"caster": ConditionActor()})
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("1 / 0 == 0", self.context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("True or GetRandomNumber(100) >= 0", self.context)


class EnemyConditionTests(unittest.TestCase):
    def test_native_enemy_aliases_compare_bcM_not_identity(self):
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        for alias in ("IsEnemy", "IsEnnemy"):
            caster = ConditionActor(actor_id=7, fight_affiliation=0)
            for target_team, expected in ((0, False), (1, True), (-1, True)):
                target = ConditionActor(actor_id=8, fight_affiliation=target_team)
                context = ConditionContext({"caster": caster, "target": target})
                self.assertEqual(evaluate_condition(alias + "()", context), expected)
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    alias + "()",
                    ConditionContext(
                        {"caster": caster, "target": ConditionActor(actor_id=-200)}
                    ),
                )
            with self.assertRaises(UnknownCondition):
                evaluate_condition(alias + '("caster")', ConditionContext({}))
            self.assertTrue(
                evaluate_condition(
                    alias + "()", ConditionContext({}, enemy_target_kind="null")
                )
            )
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    alias + "()",
                    ConditionContext({"caster": caster}, enemy_target_kind="cell"),
                )


class FightPropertyConditionTests(unittest.TestCase):
    def test_native_selector_and_signed_byte(self):
        caster = ConditionActor(fight_properties=frozenset({28}))
        target = ConditionActor(fight_properties=frozenset({1}))
        context = ConditionContext({"caster": caster, "target": target})
        self.assertTrue(evaluate_condition("HasFightProperty(28)", context))
        self.assertTrue(evaluate_condition('HasFightProperty("target", 1)', context))
        self.assertTrue(evaluate_condition("HasFightProperty(284)", context))
        self.assertFalse(evaluate_condition("HasFightProperty(13)", context))
        self.assertFalse(evaluate_condition("HasFightProperty(1)", context))

    def test_missing_properties_reject(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "HasFightProperty(1)", ConditionContext({"caster": ConditionActor()})
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('HasFightProperty(1,"target")', ConditionContext({}))
