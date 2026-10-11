"""Recirculation changes actual turret state accumulation through native branches."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerTurretRecirculationRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_recirculation_changes_native_turret_accumulation_to_fixed_one(self):
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_state_handler import NativeStateHandler

        for passive in (None, 6939):
            with self.subTest(passive=passive):
                fixture = self.fixture(
                    () if passive is None else (passive,), actives=(6902,)
                )
                from wakfu_server.combat_server_spell import server_runtime
                from wakfu_server.combat_spell_grant import granted_spells
                from tools.class_spell_eligible_targets import eligible_cast_targets

                character, monster, fight, deck, rng = fixture
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                import tools.class_spell_eligible_targets as target_selector

                enemy_position = fight.actors[-7].position
                owner_position = fight.actors[7].position
                owner_enemy_distance = sum(
                    abs(owner_position[i] - enemy_position[i]) for i in (0, 1)
                )
                cells, total = target_selector.candidate_cells(fight, 7, limit=256)

                # Prioritize the fixture's desired context before the selector's
                # bounded early exit. Every cell still passes full native validation.
                def preferred(cell):
                    adjacent = (
                        sum(abs(cell[i] - enemy_position[i]) for i in (0, 1)) == 1
                    )
                    beyond = (
                        sum(abs(cell[i] - owner_position[i]) for i in (0, 1))
                        > owner_enemy_distance
                    )
                    return not (adjacent and beyond)

                cells = sorted(cells, key=preferred)
                with patch.object(
                    target_selector, "candidate_cells", return_value=(cells, total)
                ):
                    targets = eligible_cast_targets(
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
                beyond = [
                    row["target"]
                    for row in targets["eligible"]
                    if not preferred(row["target"])
                ]
                self.assertTrue(beyond, targets)
                born = self.cast(fixture, 7700, target=beyond[0])
                fixture = self.adopt(fixture, born.fight)
                seen = []
                execute = Fight.apply_state
                interpreted = []
                apply_reference = NativeStateHandler.apply_reference

                def interpret(handler, effect, invocation, reference, level, **kwargs):
                    if reference == 7684:
                        interpreted.append(
                            (invocation.reference, invocation.level, level)
                        )
                    return apply_reference(
                        handler, effect, invocation, reference, level, **kwargs
                    )

                def observe(current, caster_id, target_id, reference, level, **kwargs):
                    change = execute(
                        current, caster_id, target_id, reference, level, **kwargs
                    )
                    # Capture the actual clamped carrier before its duration-zero
                    # resource children execute and remove it via344366.
                    if reference == 7684 and change.applied is not None:
                        seen.append((reference, target_id, change.applied.level))
                    return change

                with patch.object(Fight, "apply_state", observe), patch.object(
                    NativeStateHandler, "apply_reference", interpret
                ):
                    attack = self.cast(
                        fixture,
                        6902,
                        target=fixture[2].actors[-7].position,
                        action_id=3,
                    )
                    self.next_owned_turn(self.adopt(fixture, attack.fight))
                relevant = seen
                self.assertTrue(relevant, seen)
                self.assertTrue(all(row[1] == 7 for row in relevant), seen)
                # Native304 [7684,0,0,1] scales with the nested ability's
                # execution level, not the owner character level200. This
                # actual turret ability executes at level1.6939 selects the
                # distinct [7684,0,1,0] fixed-one branch.
                expected_refs = {344355, 345027} if passive else {344354, 345030}
                self.assertTrue(interpreted)
                self.assertTrue(
                    all(row[0] in expected_refs for row in interpreted), interpreted
                )
                self.assertTrue(
                    all(row[2] == (1 if passive else row[1]) for row in interpreted),
                    interpreted,
                )
                self.assertTrue(all(row[1] == 1 for row in interpreted), interpreted)
                self.assertTrue(all(row[2] == 1 for row in relevant), seen)
