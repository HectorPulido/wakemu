"""Hot Wheels observes an enemy on a genuinely created Microbot."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerMicrobotEnemyRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_hot_wheels_damages_actual_enemy_on_owned_microbot_at_turn_boundary(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observations = {}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6940,) if enabled else ())
                enemy_cell = data[2].actors[-7].position
                born = self.cast(data, 7008, target=enemy_cell)
                data = self.adopt(data, born.fight)
                self.assertTrue(
                    any(
                        row["reference"] == 978 and tuple(row["cell"]) == enemy_cell
                        for row in data[2].native_effect_areas.values()
                    )
                )
                before = data[2].actors[-7].hp
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (343998, 344433, 344434):
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                invocation.level,
                                result,
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    after = self.next_owned_turn(data)
                observations[enabled] = (before - after[2].actors[-7].hp, trace)
                if enabled:
                    self.assertTrue(
                        any(
                            ref == 343998 and target == -7 and ok
                            for ref, caster, target, level, ok in trace
                        ),
                        observations,
                    )
                    self.assertTrue(
                        any(
                            ref == 344433 and target == -7 and ok
                            for ref, caster, target, level, ok in trace
                        ),
                        observations,
                    )
                else:
                    self.assertFalse(any(ok for *_, ok in trace), observations)
        self.assertGreater(observations[True][0], observations[False][0], observations)

    def test_hot_wheels_observes_actual_enemy_entry_movement(self):
        import test_aniripsa_grant_summon_pipeline as turns
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observations = {}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6940,) if enabled else ())
                owner, enemy = data[2].actors[7].position, data[2].actors[-7].position
                # A native cardinal step towards the owner enters a genuinely
                # cast area; no actor.position or resource metadata is changed.
                dx = (owner[0] > enemy[0]) - (owner[0] < enemy[0])
                dy = 0 if dx else (owner[1] > enemy[1]) - (owner[1] < enemy[1])
                entry = (enemy[0] + dx, enemy[1] + dy, enemy[2])
                self.assertIn(entry, data[2].walkable)
                born = self.cast(data, 7008, target=entry)
                data = self.adopt(data, born.fight)
                lifecycle = turns.AniripsaGrantSummonPipelineTests()
                for _ in range(20):
                    if data[2].current.id == -7:
                        break
                    lifecycle.end_current_turn(data[2], data)
                self.assertEqual(data[2].current.id, -7)
                before = data[2].actors[-7].hp
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (343996, 343998, 344433):
                        trace.append(
                            (invocation.reference, invocation.target_id, result)
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    data[2].server_move(-7, [entry])
                    from wakfu_server.combat_area_transaction import (
                        prepare_area_movement,
                    )

                    preview, _ = prepare_area_movement(
                        data[0],
                        {-7: data[1]},
                        data[2],
                        data[3],
                        actor_id=-7,
                        action_id=30,
                        path=[entry],
                        origin=enemy,
                        rng=data[4],
                    )
                    data = self.adopt(data, preview)
                self.assertEqual(data[2].actors[-7].position, entry)
                observations[enabled] = (before - data[2].actors[-7].hp, trace)
                if enabled:
                    self.assertTrue(
                        any(ref == 344433 and ok for ref, _, ok in trace), observations
                    )
        self.assertGreater(observations[True][0], observations[False][0], observations)

    def test_hot_wheels_never_damages_its_owner_on_owned_movement_or_turn(self):
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        import test_combat_steamer_transition_limits_runtime as targets

        data = self.fixture((6940,))
        owner = data[2].actors[7].position
        choices = [
            row["target"]
            for row in targets.SteamerTransitionLimitsRuntimeTests().targets(
                data, 7008
            )["eligible"]
            if sum(abs(row["target"][i] - owner[i]) for i in (0, 1)) == 1
            and tuple(row["target"])
            not in {a.position for a in data[2].actors.values()}
        ]
        self.assertTrue(choices)
        born = self.cast(data, 7008, target=choices[0])
        data = self.adopt(data, born.fight)
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (343998, 344433, 344434):
                trace.append((invocation.reference, invocation.target_id, result))
            return result

        before = data[2].actors[7].hp
        with patch.object(EffectDispatcher, "execute", observe):
            data[2].move(3, 7, [choices[0]])
            preview, _ = prepare_area_movement(
                data[0],
                {-7: data[1]},
                data[2],
                data[3],
                actor_id=7,
                action_id=30,
                path=[choices[0]],
                origin=owner,
                rng=data[4],
            )
            data = self.next_owned_turn(self.adopt(data, preview))
        self.assertFalse(any(ok for _, _, ok in trace), trace)
        self.assertGreaterEqual(data[2].actors[7].hp, before, trace)
