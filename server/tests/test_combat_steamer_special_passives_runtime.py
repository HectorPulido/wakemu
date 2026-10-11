"""Steamer special passives through owned spells, native states and cast events."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerSpecialPassivesRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def observed_cast(self, data, spell, target=None, *, advance=False):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        execute = EffectDispatcher.execute
        trace = []

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            trace.append(
                (
                    invocation.reference,
                    invocation.caster_id,
                    invocation.target_id,
                    result,
                )
            )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            result = self.cast(data, spell, target=target)
            if advance:
                self.next_owned_turn(self.adopt(data, result.fight))
        return result, trace

    def test_mechanical_companion_uses_actual_elemental_cast_boundary(self):
        counts = {}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6931,) if enabled else (), actives=(6912,))
                result, trace = self.observed_cast(data, 6912)
                companions = [
                    a
                    for a in result.fight.actors.values()
                    if any(s.reference == 6288 for s in a.state_ledger.entries)
                ]
                counts[enabled] = len(companions)
                if enabled:
                    self.assertTrue(
                        any(r == 344157 and ok for r, _, _, ok in trace), trace
                    )
                    self.assertGreater(counts[enabled], 0, trace)
                else:
                    self.assertFalse(any(r == 344157 for r, *_ in trace), trace)
                    self.assertEqual(counts[enabled], 0)

    def test_ambush_dormant_damage_preserves_actual_turret_swap_in_both_decks(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6942,) if enabled else (), actives=(6920,))
                born = self.cast(data, 7700)
                data = self.next_owned_turn(self.adopt(data, born.fight))
                from wakfu_server.combat_server_spell import server_runtime
                from tools.class_spell_eligible_targets import eligible_cast_targets
                import tools.class_spell_eligible_targets as selector

                character, monster, fight, deck, rng = data
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                enemy = fight.actors[-7].position
                cells, total = selector.candidate_cells(fight, 7, limit=256)
                distance = lambda cell: sum(abs(cell[i] - enemy[i]) for i in (0, 1))
                with patch.object(
                    selector,
                    "candidate_cells",
                    return_value=(sorted(cells, key=distance), total),
                ):
                    targets = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        (7 << 32) | 6920,
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        actor_id=7,
                        limit=256,
                        maximum_eligible=16,
                    )
                self.assertTrue(targets["eligible"], targets)
                result, trace = self.observed_cast(
                    data, 6920, target=targets["eligible"][0]["target"], advance=True
                )
                executed = {r for r, _, _, ok in trace if ok}
                # Native7726's only producer343443 has literalFalse.
                # The enabled enemy-target branch instead marks/selects the
                # owned turret and swaps it with the selected enemy.
                self.assertIn(395015, executed, trace)
                self.assertNotIn(343443, executed, trace)
                self.assertFalse(executed & {345100, 345106, 345097, 345103}, trace)
                turret = next(
                    a
                    for a in result.fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                self.assertEqual(turret.position, enemy, trace)
                self.assertNotEqual(result.fight.actors[-7].position, enemy, trace)

    def test_microbot_damage_specialization_consumes_actual_armed_sp_context(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6933, 6935) + ((6940,) if enabled else ()))
                actor = data[2].actors[7]
                cycles = actor.effect_maxima[123] - actor.effect_stats[123] + 1
                self.assertGreater(cycles, 0)
                self.assertLessEqual(cycles, 256)
                for _ in range(cycles):
                    data = self.next_owned_turn(data)
                    if any(
                        s.reference == 7677
                        for s in data[2].actors[7].state_ledger.entries
                    ):
                        break
                self.assertTrue(
                    any(
                        s.reference == 7677
                        for s in data[2].actors[7].state_ledger.entries
                    )
                )
                result, trace = self.observed_cast(data, 7008)
                executed = {r for r, _, _, ok in trace if ok}
                if enabled:
                    self.assertIn(343860, executed, trace)
                    self.assertIn(343861, executed, trace)
                else:
                    self.assertNotIn(343860, executed, trace)
                    self.assertNotIn(343861, executed, trace)
                self.assertEqual(
                    len(result.fight.native_microbot_networks[7]["microbot_ids"]), 1
                )

    def test_turret_earth_damage_invokes_specialization_heal_only_when_owned(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets
        import tools.class_spell_eligible_targets as selector
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6929,) if enabled else (), actives=(6910,))
                # Let the actual opening environment/turn callbacks settle
                # before choosing the turret's cardinal firing position.
                data = self.next_owned_turn(data)
                character, monster, fight, deck, rng = data
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                enemy, owner = fight.actors[-7].position, fight.actors[7].position
                distance = lambda a, b: sum(abs(a[i] - b[i]) for i in (0, 1))
                preferred = lambda cell: distance(cell, enemy) == 1 and distance(
                    cell, owner
                ) > distance(enemy, owner)
                cells, total = selector.candidate_cells(fight, 7, limit=256)
                with patch.object(
                    selector,
                    "candidate_cells",
                    return_value=(sorted(cells, key=lambda c: not preferred(c)), total),
                ):
                    candidates = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        granted_spells(fight, 7)[7700]["uid"],
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        actor_id=7,
                        limit=256,
                        maximum_eligible=16,
                    )
                positions = [
                    row["target"]
                    for row in candidates["eligible"]
                    if preferred(row["target"])
                ]
                self.assertTrue(positions, candidates)
                born = self.cast(data, 7700, target=positions[0])
                data = self.next_owned_turn(self.adopt(data, born.fight))
                upgraded = self.cast(data, 7700, target=positions[0])
                data = self.next_owned_turn(self.adopt(data, upgraded.fight))
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    trace.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                            result,
                        )
                    )
                    return result

                from wakfu_server.combat_effect_resolver import NativeEffectResolver

                candidate_calls = []
                resolve_candidates = NativeEffectResolver.candidate_invocations

                def inspect_candidates(resolver, effect, invocation, **kwargs):
                    result = resolve_candidates(resolver, effect, invocation, **kwargs)
                    if invocation.reference in (344144, 343494):
                        candidate_calls.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                invocation.cell,
                                invocation.wakemu_fresh_child_selection,
                                invocation.native_explicit_target,
                                [
                                    (row.caster_id, row.target_id, row.cell)
                                    for row in result
                                ],
                                [
                                    (a.id, a.team, a.position, a.physical_radius)
                                    for a in resolver.actors(effect, invocation)
                                ],
                                {
                                    key: effect.get(key)
                                    for key in (
                                        "native_shape",
                                        "area_class",
                                        "area_native",
                                        "native_shape_class",
                                        "native_target_selector",
                                    )
                                },
                                resolver.native_context(effect, invocation),
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe), patch.object(
                    NativeEffectResolver, "candidate_invocations", inspect_candidates
                ):
                    attack = self.cast(
                        data, 6910, target=data[2].actors[-7].position, action_id=3
                    )
                    final = self.next_owned_turn(self.adopt(data, attack.fight))
                executed = {r for r, _, _, ok in trace if ok}
                self.assertIn(343660, executed, trace)
                if enabled:
                    self.assertIn(
                        346194, executed, dict(trace=trace, candidates=candidate_calls)
                    )
                else:
                    self.assertNotIn(346194, executed, trace)

    def test_turret_upgrade_caps_actual_owned_state_only_with_passive(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6937,) if enabled else ())
                born = self.cast(data, 7700)
                data = self.adopt(data, born.fight)
                turret = next(
                    a
                    for a in data[2].actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                levels = []
                for _ in range(3):
                    data = self.next_owned_turn(data)
                    upgraded = self.cast(data, 7700, target=turret.position)
                    data = self.adopt(data, upgraded.fight)
                    turret = data[2].actors[turret.id]
                    levels.append(
                        next(
                            (
                                s.level
                                for s in turret.state_ledger.entries
                                if s.reference == 7649
                            ),
                            0,
                        )
                    )
                if enabled:
                    self.assertEqual(levels[-1], 2, levels)
                    self.assertLessEqual(max(levels), 2, levels)
                else:
                    self.assertGreater(levels[-1], 2, levels)

    def test_water_turret_specialization_selects_actual_half_damage_state(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets
        import tools.class_spell_eligible_targets as selector
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6942,) if enabled else (), actives=(6914,))
                # Let the actual opening environment/turn callbacks settle
                # before choosing the turret's cardinal firing position.
                data = self.next_owned_turn(data)
                character, monster, fight, deck, rng = data
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                enemy, owner = fight.actors[-7].position, fight.actors[7].position
                distance = lambda a, b: sum(abs(a[i] - b[i]) for i in (0, 1))
                preferred = lambda cell: distance(cell, enemy) == 1 and distance(
                    cell, owner
                ) > distance(enemy, owner)
                cells, total = selector.candidate_cells(fight, 7, limit=256)
                with patch.object(
                    selector,
                    "candidate_cells",
                    return_value=(sorted(cells, key=lambda c: not preferred(c)), total),
                ):
                    candidates = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        granted_spells(fight, 7)[7700]["uid"],
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        actor_id=7,
                        limit=256,
                        maximum_eligible=16,
                    )
                positions = [
                    row["target"]
                    for row in candidates["eligible"]
                    if preferred(row["target"])
                ]
                self.assertTrue(positions, candidates)
                born = self.cast(data, 7700, target=positions[0])
                data = self.next_owned_turn(self.adopt(data, born.fight))
                upgraded = self.cast(data, 7700, target=positions[0])
                data = self.next_owned_turn(self.adopt(data, upgraded.fight))
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    trace.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                            result,
                        )
                    )
                    return result

                from wakfu_server.combat_effect_resolver import NativeEffectResolver

                candidate_calls = []
                resolve_candidates = NativeEffectResolver.candidate_invocations

                def inspect_candidates(resolver, effect, invocation, **kwargs):
                    result = resolve_candidates(resolver, effect, invocation, **kwargs)
                    if invocation.reference in (344144, 343494):
                        candidate_calls.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                invocation.cell,
                                invocation.wakemu_fresh_child_selection,
                                invocation.native_explicit_target,
                                [
                                    (row.caster_id, row.target_id, row.cell)
                                    for row in result
                                ],
                                [
                                    (a.id, a.team, a.position, a.physical_radius)
                                    for a in resolver.actors(effect, invocation)
                                ],
                                {
                                    key: effect.get(key)
                                    for key in (
                                        "native_shape",
                                        "area_class",
                                        "area_native",
                                        "native_shape_class",
                                        "native_target_selector",
                                    )
                                },
                                resolver.native_context(effect, invocation),
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe), patch.object(
                    NativeEffectResolver, "candidate_invocations", inspect_candidates
                ):
                    attack = self.cast(
                        data, 6914, target=data[2].actors[-7].position, action_id=3
                    )
                    final = self.next_owned_turn(self.adopt(data, attack.fight))
                executed = {r for r, _, _, ok in trace if ok}
                self.assertIn(343665, executed, trace)
                positive = {346072, 346106, 346115, 346121}
                baseline = {346069, 346103, 346112, 346118}
                self.assertTrue(
                    executed & (positive if enabled else baseline),
                    dict(trace=trace, candidates=candidate_calls),
                )
                self.assertFalse(executed & (baseline if enabled else positive), trace)
