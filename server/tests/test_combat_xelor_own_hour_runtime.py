"""Own-current-hour passive through real placement, movement and turns."""
from collections import deque
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers


class XelorOwnHourRuntimeTests(unittest.TestCase):
    @staticmethod
    def path(fight, goal):
        origin = fight.actors[7].position
        occupied = {a.position for a in fight.actors.values() if a.id != 7 and a.hp > 0}
        parents = {origin: None}
        queue = deque([origin])
        by_xy = {}
        for cell in fight.walkable:
            by_xy.setdefault(cell[:2], []).append(cell)
        while queue:
            cell = queue.popleft()
            if cell == goal:
                result = []
                while parents[cell] is not None:
                    result.append(cell)
                    cell = parents[cell]
                return result[::-1]
            x, y, _ = cell
            for xy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                for target in sorted(by_xy.get(xy, ())):
                    if target in parents or target in occupied:
                        continue
                    if fight.edges is not None:
                        if (cell, target) not in fight.edges:
                            continue
                    elif cell[2] != target[2]:
                        continue
                    parents[target] = cell
                    queue.append(target)
        raise AssertionError(("No real native path to current hour", origin, goal))

    def test_owned_current_hour_entry_requires_owned_passive(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = helper.fixture(passives=(7187,) if enabled else ())
                tx = helper.cast(data, 5345, (-11, -7, -1))
                data = helper.adopt(data, tx.fight)
                self.assertNotIn(7789, helper.states(data[2].actors[7]))
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (
                        349669,
                        349670,
                        349671,
                        349672,
                        349673,
                        349674,
                    ):
                        trace.append(
                            (invocation.reference, invocation.target_id, result)
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    for _ in range(8):
                        fight = data[2]
                        current = [
                            tuple(r["cell"])
                            for r in fight.native_effect_areas.values()
                            if r.get("owner_id") == 7 and r["reference"] == 1558
                        ]
                        self.assertEqual(len(current), 1, trace)
                        if fight.actors[7].position == current[0]:
                            break
                        path = self.path(fight, current[0])
                        from wakfu_server.combat_area_transaction import (
                            prepare_area_movement,
                        )

                        origin = fight.actors[7].position
                        steps = path[: fight.actors[7].mp]
                        fight.move(3, 7, steps)
                        preview, _ = prepare_area_movement(
                            data[0],
                            {-7: data[1]},
                            fight,
                            data[3],
                            actor_id=7,
                            action_id=40,
                            path=steps,
                            origin=origin,
                            rng=data[4],
                        )
                        data = helper.adopt(data, preview)
                        fight = preview
                        if fight.actors[7].position != current[0]:
                            data = helper.next_owned_turn(data)
                    else:
                        self.fail(
                            ("Real movement never reached own current hour", trace)
                        )
                # Actual1001 positive occurs only after reaching the current hour.
                with patch.object(EffectDispatcher, "execute", observe):
                    data = helper.next_owned_turn(data)
                granted = any(ref == 349671 and ok for ref, _, ok in trace)
                self.assertEqual(granted, enabled, trace)
