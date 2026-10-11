"""Actual tree and doll passive branches from published native class closures."""
import os
import unittest
from unittest.mock import patch

import test_sadida_grant_pipeline as grants
import test_sadida_doll_actions_pipeline as dolls
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaSelectedPassiveSemanticsTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast
    born = dolls.SadidaDollActionsPipelineTests.born

    def test_wild_cycle_selects_actual_tree_counter_branch(self):
        from wakfu_server.combat_state_handler import NativeStateHandler
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_effect_resolver import NativeEffectResolver

        for passive in (None, 8155):
            with self.subTest(passive=passive):
                data = self.fixture(passives=() if passive is None else (passive,))
                seeded = self.cast(data, 8137)
                data = (*data[:2], seeded.fight, *data[3:])
                cell = next(
                    a["cell"]
                    for a in data[2].native_effect_areas.values()
                    if a["reference"] == 1835
                )
                applications = []
                branches = []
                dispatch = EffectDispatcher.execute
                candidate = NativeEffectResolver.candidate_invocations
                candidates = []
                import wakfu_server.combat_effect_dispatch as dispatcher_module

                evaluate = dispatcher_module.evaluate_condition
                conditions = []
                import wakfu_server.combat_effect_runtime as runtime_module

                state_level = runtime_module.native_state_group_level
                level_sources = []
                apply = NativeStateHandler.apply_reference

                def observe(handler, effect, invocation, reference, level, **kwargs):
                    if reference == 8225:
                        applications.append(
                            (invocation.reference, invocation.level, level)
                        )
                    return apply(
                        handler, effect, invocation, reference, level, **kwargs
                    )

                def trace(dispatcher, invocation, *args, **kwargs):
                    result = dispatch(dispatcher, invocation, *args, **kwargs)
                    if invocation.reference in (378650, 378181, 378652, 379615):
                        branches.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                bool(result),
                                invocation.level,
                            )
                        )
                    return result

                def select(resolver, effect, invocation, **kwargs):
                    result = candidate(resolver, effect, invocation, **kwargs)
                    if invocation.reference in (379615, 378652):
                        population = tuple(resolver.actors(effect, invocation))
                        native = resolver.native_context(effect, invocation)
                        candidates.append(
                            dict(
                                reference=invocation.reference,
                                cell=invocation.cell,
                                explicit=invocation.native_explicit_target,
                                target=invocation.target_id,
                                selected=[r.target_id for r in result],
                                actors=[
                                    dict(
                                        id=a.id,
                                        position=a.position,
                                        properties={
                                            k: native[a.id].get(k)
                                            for k in (
                                                "is_eGj",
                                                "dTE",
                                                "dpu_id",
                                                "baG",
                                                "baK",
                                                "bEe",
                                                "is_amO",
                                            )
                                        },
                                    )
                                    for a in population
                                ],
                            )
                        )
                    return result

                def condition(criteria, context):
                    result = evaluate(criteria, context)
                    if "IsOwnSummon(5577)" in criteria:
                        conditions.append(
                            (
                                criteria,
                                result,
                                {
                                    key: None
                                    if actor is None
                                    else {
                                        field: getattr(actor, field, None)
                                        for field in (
                                            "id",
                                            "breed_id",
                                            "summon_root_id",
                                            "is_summon",
                                            "is_native_fighter",
                                        )
                                    }
                                    for key, actor in context.actors.items()
                                },
                            )
                        )
                    return result

                def source_level(effect, values, invocation, fight, **kwargs):
                    result = state_level(effect, values, invocation, fight, **kwargs)
                    if invocation.reference == 378650:
                        from wakfu_server.combat_native_actor_lookup import native_actor
                        from wakfu_server.combat_state_managers import (
                            registered_area_pv,
                        )

                        parameters = values["parameters"]
                        identity = (
                            invocation.caster_id
                            if parameters[7] == 1
                            else invocation.target_id
                        )
                        actor = native_actor(fight, identity) or registered_area_pv(
                            fight, identity
                        )
                        entries = (
                            []
                            if actor.state_ledger is None
                            else actor.state_ledger.entries
                        )
                        levels = [
                            e.level for e in entries if e.reference == parameters[6]
                        ]
                        level_sources.append((list(parameters), levels, result))
                    return result

                with patch.object(
                    runtime_module, "native_state_group_level", source_level
                ), patch.object(
                    dispatcher_module, "evaluate_condition", condition
                ), patch.object(
                    NativeStateHandler, "apply_reference", observe
                ), patch.object(
                    EffectDispatcher, "execute", trace
                ), patch.object(
                    NativeEffectResolver, "candidate_invocations", select
                ):
                    tx = self.cast(data, 8137, target=cell, action_id=11)
                tree = next(
                    a
                    for a in tx.fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                    and actor_action_book(a)["profile"] == 5577
                    and a.hp > 0
                )
                self.assertIn(8217, {s.reference for s in tree.state_ledger.entries})
                selected = [r for r in applications if r[0] in (378652, 379615)]
                self.assertTrue(level_sources)
                for parameters, source_levels, computed in level_sources:
                    # eYr.d scans target Qf for state3624; factor1/constant0.
                    # With no matching state (or native level0), SP=floor(0).
                    self.assertEqual(parameters[6:10], [3624, 0, 1, 0])
                    self.assertTrue(
                        not source_levels or source_levels[0] == 0, level_sources
                    )
                    self.assertEqual(computed, 0, level_sources)
                if passive is None:
                    # Dynamic state-group844/378650 supplies child level0.
                    # 378652 begins at
                    # level1, so its baseline counter is intentionally absent;
                    # 379615 permits level0 and adds the passive's fixed3.
                    self.assertTrue(
                        any(r[0] == 378181 and r[4] == 0 for r in branches), branches
                    )
                    self.assertFalse(
                        selected, (applications, branches, candidates, conditions)
                    )
                    continue
                self.assertTrue(
                    selected, (applications, branches, candidates, conditions)
                )
                self.assertTrue(
                    all(r[0] == (379615 if passive else 378652) for r in selected),
                    applications,
                )
                self.assertTrue(
                    all(r[2] == r[1] + (3 if passive else 0) for r in selected),
                    applications,
                )

    def test_vegetal_communication_requires_owned_doll_source(self):
        for passive in (None, 8156):
            with self.subTest(passive=passive):
                data, doll_id = self.born(
                    918, 3749, passives=() if passive is None else (passive,)
                )
                helper = turns.AniripsaGrantSummonPipelineTests()
                for _ in range(20):
                    if data[2].current.id == 7:
                        break
                    helper.end_current_turn(data[2], data[:5])
                self.assertEqual(data[2].current.id, 7)
                tx = self.cast(
                    data, 918, target=data[2].actors[doll_id].position, action_id=30
                )
                data = (*data[:2], tx.fight, *data[3:])
                doll = data[2].actors[doll_id]
                self.assertIn(8200, {s.reference for s in doll.state_ledger.entries})
                helper.end_current_turn(data[2], data[:5])
                has_bonus = 8230 in {s.reference for s in doll.state_ledger.entries}
                self.assertEqual(has_bonus, passive is not None)
                self.assertNotIn(
                    8230, {s.reference for s in data[2].actors[-7].state_ledger.entries}
                )

    def test_explodoll_uses_actual_voodoll_damage_and_death_route(self):
        import test_sadida_voodoll_death_pipeline as death
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        for passive in (None, 933):
            with self.subTest(passive=passive):
                observed = []
                execute = EffectDispatcher.execute
                fixture = self.fixture

                def owned_fixture(_helper):
                    return fixture(passives=() if passive is None else (passive,))

                def observe(dispatcher, invocation, *args, **kwargs):
                    result = execute(dispatcher, invocation, *args, **kwargs)
                    if invocation.reference == 379641:
                        observed.append(bool(result))
                    return result

                # Reuse the actual7962 lethal hit and coherent one-HP fixture,
                # preserving its owner-survival and native QI release assertions.
                with patch.object(
                    death.SadidaVoodollDeathPipelineTests, "fixture", owned_fixture
                ), patch.object(EffectDispatcher, "execute", observe):
                    death.SadidaVoodollDeathPipelineTests().test_actual_npc_kill_releases_vudul_slot_without_owner_death()
                self.assertTrue(observed, observed)
                self.assertEqual(any(observed), passive is not None)
