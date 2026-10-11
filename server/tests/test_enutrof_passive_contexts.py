"""Actual deposit protection and companion inheritance contextual branches."""
import os
import unittest
from collections import deque
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher
import test_enutrof_runtime as enutrof
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native integration opt-in"
)
class EnutrofPassiveContextTests(unittest.TestCase):
    fixture = enutrof.EnutrofRuntimeTests.fixture

    @staticmethod
    def level(actor, reference):
        return sum(
            row.level
            for row in actor.state_ledger.entries
            if row.reference == reference
        )

    @staticmethod
    def path_to_deposit(fight):
        actor = fight.actors[7]
        occupied = {a.position for a in fight.actors.values() if a.id != 7 and a.hp > 0}
        areas = {
            tuple(r["cell"]): r
            for r in fight.native_effect_areas.values()
            if r["owner_id"] == 7 and r["reference"] in (202, 203, 204, 205)
        }
        queue = deque([(actor.position, [])])
        seen = {actor.position}
        while queue:
            cell, path = queue.popleft()
            if cell in areas:
                return path, areas[cell]
            if len(path) >= actor.mp:
                continue
            for next_cell in sorted(fight.walkable):
                if next_cell in seen or next_cell in occupied:
                    continue
                if sum(abs(next_cell[i] - cell[i]) for i in (0, 1)) != 1:
                    continue
                if fight.edges is not None:
                    if (cell, next_cell) not in fight.edges:
                        continue
                elif next_cell[2] != cell[2]:
                    continue
                seen.add(next_cell)
                queue.append((next_cell, path + [next_cell]))
        raise AssertionError("No actual deposit reachable with ordinary MP")

    def test_mineral_protection_requires_actual_deposit_and_consumes_it(self):
        for passive, on_deposit in ((False, True), (True, False), (True, True)):
            with self.subTest(passive=passive, on_deposit=on_deposit):
                data = self.fixture(passives=(8277,) if passive else ())
                fight = data[2]
                path, deposit = self.path_to_deposit(fight)
                if on_deposit and path:
                    fight.move(3, 7, path)
                if not on_deposit:
                    self.assertFalse(
                        any(
                            tuple(r["cell"]) == fight.actors[7].position
                            for r in fight.native_effect_areas.values()
                            if r["reference"] in (202, 203, 204, 205)
                        )
                    )
                before = dict(fight.actors[7].effect_stats)
                trace = []
                observed = []
                original_execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = original_execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (386098, 386099, 386101, 386102, 386103):
                        actor = dispatcher.native_retention.fight.actors[7]
                        observed.append(
                            (
                                invocation.reference,
                                {
                                    entry.reference: entry.level
                                    for entry in actor.state_ledger.entries
                                },
                                dict(actor.effect_stats),
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    with combat_diagnostic_scope(
                        lambda **r: trace.append(r), limit=8192
                    ):
                        turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                            fight, data
                        )
                completed = {
                    r.get("effect_reference")
                    for r in trace
                    if r.get("status") == "completed"
                }
                if passive and on_deposit:
                    self.assertIn(386098, completed)
                    self.assertNotIn(
                        deposit["uid"],
                        fight.native_effect_areas,
                        {
                            "caster_cell": fight.actors[7].position,
                            "deposit": deposit["cell"],
                            "removal_trace": [
                                r for r in trace if r.get("effect_reference") == 386100
                            ],
                        },
                    )
                    state = {202: 8589, 203: 8586, 204: 8587, 205: 8588}[
                        deposit["reference"]
                    ]
                    application = next(
                        row for row in observed if row[1].get(state) == 1
                    )
                    resistance = next(row for row in observed if row[0] == 386098)[2]
                    deltas = {
                        key: value - before.get(key, 0)
                        for key, value in resistance.items()
                        if value != before.get(key, 0)
                    }
                    self.assertIn(
                        100, deltas.values(), {"native_resistance_delta": deltas}
                    )
                    # Native duration1/endtick expires after1002/1037 in
                    # RuntimeMessages._end_owned; observe application first.
                    self.assertEqual(application[1][state], 1)
                    self.assertEqual(self.level(fight.actors[7], state), 0)
                else:
                    self.assertNotIn(386098, completed)
                    self.assertIn(deposit["uid"], fight.native_effect_areas)

    def test_inheritance_real_companion_enemy_range_controls_regeneration_death(self):
        # Native state3614→3862161037 checks controller deck then386217
        # kills only when an actual enemy is within2 of the companion.
        for passive, near in ((False, True), (True, False), (True, True)):
            with self.subTest(passive=passive, near=near):
                data = self.fixture(
                    passives=(8280,) if passive else (),
                    target_distance=2 if near else 3,
                )
                fight = data[2]
                companion = next(
                    a
                    for a in fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                self.assertEqual(self.level(companion, 3614), 1)
                # Move with real turn ownership and actual MP, never alter
                # position or state. Select a native cell with desired range.
                for _ in range(20):
                    if fight.current.id == companion.id:
                        break
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        fight, data
                    )
                self.assertEqual(fight.current.id, companion.id)
                distance = sum(
                    abs(companion.position[i] - fight.actors[-7].position[i])
                    for i in (0, 1)
                )
                self.assertEqual(
                    distance <= 2,
                    near,
                    "Fixture must establish actual native enemy range",
                )
                trace = []
                with combat_diagnostic_scope(lambda **r: trace.append(r), limit=8192):
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        fight, data
                    )
                completed = {
                    r.get("effect_reference")
                    for r in trace
                    if r.get("status") == "completed"
                }
                if passive and near:
                    self.assertIn(386217, completed)
                    self.assertEqual(companion.hp, 0)
                else:
                    self.assertNotIn(386217, completed)
                    self.assertGreater(companion.hp, 0)
