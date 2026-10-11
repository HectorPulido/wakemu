"""Actual Ecaflip turns and cards qualify passive threshold branches."""
import os
import random
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as native_fixture
import test_ecaflip_hand_passives_pipeline as hand
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipDicePassiveSemanticsTests(unittest.TestCase):
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn
    cast = hand.EcaflipHandPassivesPipelineTests.cast
    cards = staticmethod(hand.EcaflipHandPassivesPipelineTests.cards)
    level = staticmethod(hand.EcaflipHandPassivesPipelineTests.level)

    def fixture(
        self,
        *,
        passives=(),
        seed=7,
        active_spells=None,
        full_health=False,
        caster_aptitudes=()
    ):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            6,
            200,
            native_qi=True,
            target_hp=20000,
            variation_seed=17,
            full_health=full_health,
            caster_aptitudes=caster_aptitudes,
        )
        deck = encode_deck(active_spells or (2050, 2042, 2067, 2073, 2078), passives)
        rng = random.Random(seed)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng

    def test_generous_dice_does_not_invent_good_star_on_initial_movement(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = hand.EcaflipHandPassivesPipelineTests.fixture(
                    self, seed=7, passives=(7958,) if equipped else ()
                )
                actor = data[2].actors[7]
                before_heal = actor.effect_stats[114]
                before_damage = actor.effect_stats[48]
                data = (
                    data[0],
                    data[1],
                    hand.EcaflipHandPassivesPipelineTests.move_one_step(self, data),
                    data[3],
                    data[4],
                )
                actor = data[2].actors[7]
                contribution = self.level(data[2], 7999)
                self.assertEqual(contribution, 0)
                # Native361061/361058 derive Buena Estrella7999, produced by
                # movement event1005 via359750→361064, not Racha3683.
                # This fresh character has no qualifying characteristic9 excess;
                # an ordinary move must not manufacture the disabled dice bonus.
                self.assertEqual(
                    actor.effect_stats[114] - before_heal,
                    contribution // 2 if equipped else 0,
                )
                self.assertEqual(
                    actor.effect_stats[48] - before_damage,
                    0 if equipped else contribution // 2,
                )
                from wakfu_server.combat_retained_runtime import (
                    native_retained_condition_effects,
                )

                self.assertNotIn(
                    359897,
                    {r[0] for r in native_retained_condition_effects(data[2], 7)},
                )

    def test_actual_battle_gain_below_threshold_does_not_create_good_star(self):
        import test_aniripsa_grant_summon_pipeline as lifecycle
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture(
                    passives=(7958,) if equipped else (),
                    active_spells=(2049,),
                    seed=7,
                    full_health=True,
                )
                before_heal = data[2].actors[7].effect_stats[114]
                before_damage = data[2].actors[7].effect_stats[48]
                observed = []
                for _ in range(12):
                    actor = data[2].actors[7]
                    before_heal = actor.effect_stats[114]
                    before_damage = actor.effect_stats[48]
                    from wakfu_server.combat_effect_dispatch import EffectDispatcher

                    original_execute = EffectDispatcher.execute
                    branches = []

                    def observe(dispatcher, invocation, **kwargs):
                        result = original_execute(dispatcher, invocation, **kwargs)
                        if invocation.reference in (
                            162490,
                            169494,
                            359810,
                            412837,
                            359750,
                            361064,
                        ):
                            branches.append(
                                (
                                    invocation.reference,
                                    invocation.caster_id,
                                    invocation.target_id,
                                    result,
                                )
                            )
                        return result

                    with patch.object(EffectDispatcher, "execute", observe):
                        cast = self.cast(data, 2049, owned=True, allow_ineligible=True)
                    if cast is not None:
                        data = cast
                        current_actor = data[2].actors[7]
                        observed.append(
                            dict(
                                current=current_actor.effect_stats[9],
                                minimum=current_actor.effect_minima.get(9),
                                maximum=current_actor.effect_maxima.get(9),
                                good_star=self.level(data[2], 7999),
                                branches=branches,
                            )
                        )
                        if any(
                            ref in (359810, 412837) and result
                            for ref, _, _, result in branches
                        ):
                            break
                        continue
                    lifecycle.AniripsaGrantSummonPipelineTests.next_player_turn(
                        self, data[2], data
                    )
                level = self.level(data[2], 7999)
                self.assertTrue(
                    any(
                        ref in (359810, 412837) and result
                        for row in observed
                        for ref, _, _, result in row["branches"]
                    ),
                    observed,
                )
                self.assertTrue(
                    all(row["current"] <= 100 for row in observed), observed
                )
                self.assertTrue(
                    all(row["good_star"] == 0 for row in observed), observed
                )
                self.assertEqual(level, 0)
                # Actual Batalla gain runs, but this fresh build stays below100.
                # Its duration2 does not justify accumulation across20 turns.
                # No qualifying excess means no7999-derived healing/damage.
                self.assertEqual(
                    data[2].actors[7].effect_stats[114] - before_heal,
                    level // 2 if equipped else 0,
                )
                self.assertEqual(
                    data[2].actors[7].effect_stats[48] - before_damage,
                    0 if equipped else level // 2,
                )
                self.assertNotIn(
                    359897,
                    {r[0] for r in native_retained_condition_effects(data[2], 7)},
                )

    def test_cross_i_win_threshold_is_reached_by_actual_turns_then_card(self):
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        for seed in range(24):
            data = self.fixture(passives=(2076, 7957), seed=seed)
            if 7944 in self.cards(data[2]):
                break
        else:
            self.fail("No naturally drawn Miaumiau card")
        before = data[2].actors[7].effect_stats[27]
        self.assertLess(self.level(data[2], 3683), 100)
        self.assertNotIn(
            371526, {r[0] for r in native_retained_condition_effects(data[2], 7)}
        )
        import test_aniripsa_grant_summon_pipeline as lifecycle

        # Real incoming attacks/turn events accumulate the capped streak.
        # Dado's old +50 groups359819/359820 are native False branches.
        for _ in range(12):
            if self.level(data[2], 3683) >= 100:
                break
            lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn(
                self, data[2], data
            )
            for _ in range(20):
                if data[2].current.id == 7:
                    break
                lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn(
                    self, data[2], data
                )
            self.assertEqual(data[2].current.id, 7)
        self.assertEqual(self.level(data[2], 3683), 100)
        self.assertIn(7944, self.cards(data[2]))
        data = self.cast(data, 7944)
        # The real card spends Racha100. Native371526 then sees <100 at1025
        # and supplies its once-only +50 resistance before cleanup.
        self.assertEqual(data[2].actors[7].effect_stats[27] - before, 50)
        self.assertIn(
            371528, {r[0] for r in native_retained_condition_effects(data[2], 7)}
        )

    def test_cross_i_win_fight_start_converts_actual_dodge(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        results = {}
        for aptitude_points in (0, 10):
            for equipped in (False, True):
                with self.subTest(points=aptitude_points, equipped=equipped):
                    (
                        character,
                        monster,
                        fight,
                    ) = native_fixture.SpellTransactionTests().native_server_fixture(
                        6,
                        200,
                        native_qi=True,
                        target_hp=20000,
                        caster_aptitudes=((19, aptitude_points),),
                        variation_seed=17,
                    )
                    before = fight.actors[7].effect_stats[8]
                    deck = encode_deck((2050,), (7957,) if equipped else ())
                    executions = []
                    original = EffectDispatcher.execute

                    def observe(dispatcher, invocation, **kwargs):
                        result = original(dispatcher, invocation, **kwargs)
                        if invocation.reference in (371530, 371531):
                            executions.append(
                                (invocation.reference, invocation.level, result)
                            )
                        return result

                    with patch.object(EffectDispatcher, "execute", observe):
                        preview, _ = prepare_server_initialization(
                            character,
                            {-7: monster},
                            fight,
                            3,
                            deck,
                            action_id=1,
                            rng=random.Random(7),
                            fight_start=True,
                        )
                    results[aptitude_points, equipped] = (
                        before,
                        preview.actors[7].effect_stats[8],
                        executions,
                    )
                    self.assertEqual(fight.actors[7].effect_stats[8], before)
                    if not equipped:
                        self.assertEqual(preview.actors[7].effect_stats[8], before)
                        self.assertFalse(any(ref == 371531 for ref, _, _ in executions))
                    elif before > 0:
                        # Native913 copies actual DODGE into child level;176
                        # removes that amount at the real fight-start1003.
                        self.assertTrue(
                            any(
                                ref == 371531 and level == before and result
                                for ref, level, result in executions
                            ),
                            results,
                        )
                        self.assertEqual(preview.actors[7].effect_stats[8], 0, results)
                    else:
                        self.assertFalse(
                            any(ref == 371531 for ref, _, _ in executions), results
                        )
        self.assertGreater(results[10, False][0], results[0, False][0], results)

    def test_generous_dice_converts_actual_equipped_critical_excess(self):
        from wakfu_server import equipment_stats
        from wakfu_server.wire import proto_field
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        # Published normal equipment, native slots/requirements validated by
        # effective_character before actor PA and Ready are initialized.
        equipment = (
            (23924, 4),
            (31319, 13),
            (19146, 15),
            (20151, 16),
            (19746, 10),
            (20278, 3),
            (18005, 5),
            (23975, 0),
            (30353, 12),
            (22126, 17),
        )
        effective = equipment_stats.effective_character

        def equipped_character(character, *args, **kwargs):
            if character.get("id") == 7:
                character = dict(character)
                character["inventory_items"] = [
                    dict(uid=90000 + i, character_id=7, reference=ref, quantity=1)
                    for i, (ref, _) in enumerate(equipment)
                ]
                builds = {
                    key: dict(value) for key, value in character["builds"].items()
                }
                builds[0]["equipment"] = b"".join(
                    proto_field(10, proto_field(8, 90000 + i) + proto_field(16, slot))
                    for i, (_, slot) in enumerate(equipment)
                ).hex()
                character["builds"] = builds
            return effective(character, *args, **kwargs)

        results = {}
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                with patch.object(
                    equipment_stats, "effective_character", equipped_character
                ):
                    data = self.fixture(
                        passives=(7958,) if equipped else (),
                        full_health=True,
                        caster_aptitudes=((9, 20),),
                    )
                actor = data[2].actors[7]
                self.assertGreater(actor.effect_stats[9], 100)
                before = (actor.effect_stats[114], actor.effect_stats[48])
                before_star = self.level(data[2], 7999)
                executions = []
                original = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = original(dispatcher, invocation, **kwargs)
                    if invocation.reference in (361064, 361061, 361058):
                        executions.append(
                            (invocation.reference, invocation.level, result)
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    preview = hand.EcaflipHandPassivesPipelineTests.move_one_step(
                        self, data
                    )
                actor = preview.actors[7]
                star = self.level(preview, 7999)
                results[equipped] = dict(
                    critical=actor.effect_stats[9],
                    star=star,
                    before_star=before_star,
                    before_stats=before,
                    healing=actor.effect_stats[114] - before[0],
                    damage=actor.effect_stats[48] - before[1],
                    trace=executions,
                )
                self.assertEqual(star, actor.effect_stats[9] - 100, results)
                self.assertGreater(star, 0, results)
                self.assertTrue(
                    any(ref == 361064 and result for ref, _, result in executions),
                    results,
                )
                # Native state7999 is permanent and derives these modifiers from
                # its current level. First-round initialization can already
                # install the same excess; movement refreshes it, never stacks.
                derived_delta = star // 2 - before_star // 2
                self.assertEqual(
                    results[equipped]["healing"],
                    derived_delta if equipped else 0,
                    results,
                )
                self.assertEqual(
                    results[equipped]["damage"],
                    0 if equipped else derived_delta,
                    results,
                )
                self.assertGreaterEqual(
                    actor.effect_stats[114 if equipped else 48], star // 2, results
                )

    def test_destiny_draw_distribution_tracks_real_round_and_owned_passive(self):
        from wakfu_server import combat_random_group
        import test_ecaflip_tarot_pipeline as tarot

        authority_call = combat_random_group.RandomGroupAuthority.__call__
        weighted = combat_random_group.weighted_children
        observations = []

        def observe(authority, preview, plan, effect, values, invocation, children):
            def draw(candidates, count, *, draw_integer):
                rows = tuple(candidates)
                chosen = weighted(rows, count, draw_integer=draw_integer)
                states = {}
                for reference, probability in rows:
                    child = authority.effects[str(reference)]
                    if child["effect_class"] == 304:
                        state = int(child["parameters"][0])
                        if 7961 <= state <= 7973:
                            states[state] = probability
                if states:
                    observations.append(
                        dict(
                            table=preview.native_table_turn,
                            candidates=states,
                            chosen=chosen,
                            count=count,
                            present={
                                state
                                for state in range(7961, 7974)
                                if self.level(preview, state) > 0
                            },
                        )
                    )
                return chosen

            with patch.object(combat_random_group, "weighted_children", draw):
                return authority_call(
                    authority, preview, plan, effect, values, invocation, children
                )

        for equipped in (False, True):
            with self.subTest(passive=equipped):
                observations.clear()
                with patch.object(
                    combat_random_group.RandomGroupAuthority, "__call__", observe
                ):
                    data = tarot.EcaflipTarotPipelineTests.fixture(
                        self, seed=7, passives=(7961, 5250) if equipped else (7961,)
                    )
                initial = list(observations)
                self.assertGreaterEqual(len(initial), 3, initial)
                first = initial[0]
                expected = {
                    state
                    for state in range(7961, 7971)
                    if (state - 7961) % 2 == first["table"] % 2
                }
                if equipped and first["table"] % 2 == 0:
                    expected.add(7973)
                self.assertEqual(set(first["candidates"]), expected, initial)
                self.assertEqual(set(first["candidates"].values()), {100.0}, initial)
                self.assertEqual(len(self.cards(data[2])), 3)
                for _ in range(2):
                    lifecycle.AniripsaGrantSummonPipelineTests.next_player_turn(
                        self, data[2], data
                    )
                    if data[2].native_table_turn % 2 != first["table"] % 2:
                        break
                self.assertNotEqual(data[2].native_table_turn % 2, first["table"] % 2)
                observations.clear()
                with patch.object(
                    combat_random_group.RandomGroupAuthority, "__call__", observe
                ):
                    data = self.cast(data, 2060, owned=True)
                self.assertEqual(len(observations), 3, observations)
                for row in observations:
                    expected = {
                        state
                        for state in range(7961, 7971)
                        if (state - 7961) % 2 == row["table"] % 2
                    }
                    # Native359554 permits Destiny only with5250 on even rounds.
                    if equipped and row["table"] % 2 == 0:
                        expected.add(7973)
                    # Each native35954x also requires not HasState(card,target).
                    # Earlier draws in this same three-draw action can install
                    # a level2 carrier and exclude it from subsequent draws.
                    expected -= row["present"]
                    self.assertEqual(set(row["candidates"]), expected, row)
                    self.assertTrue(
                        all(
                            (state - 7961) % 2 == row["table"] % 2
                            for state in row["candidates"]
                        ),
                        row,
                    )
                    self.assertEqual(set(row["candidates"].values()), {100.0}, row)
                    self.assertEqual(len(row["chosen"]), 1, row)
