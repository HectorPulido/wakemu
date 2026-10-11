"""Actual ally gift, owned turn/movement and recipient attack; no state injection."""
import gc

gc.disable()
import json, os, sys
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import test_combat_eliotrope_mode_passives_runtime as test
import test_combat_aptitude_healing_runtime as arena
import wakfu_server.combat_spell_transaction as transaction
import wakfu_server.combat_server_spell as server
from wakfu_server.combat_ordinary_authority import native_facing
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_effect_dispatch import EffectDispatcher

candidate = transaction.prepare_spell_transaction
suite = test.EliotropeModePassiveRuntimeTests()
original_arena = arena.AptitudeHealingRuntimeTests.fixture
original_execute = EffectDispatcher._execute
trace = []


def full_arena(self, **kwargs):
    kwargs["compact_arena"] = False
    return original_arena(self, **kwargs)


def observe(self, invocation, **kwargs):
    result = original_execute(self, invocation, **kwargs)
    if invocation.reference in (159742, 159743, 351766, 351710, 351699):
        trace.append(
            dict(
                ref=invocation.reference,
                caster=invocation.caster_id,
                target=invocation.target_id,
                result=result,
            )
        )
    return result


def run_cases():
    results = []
    with patch.object(
        arena.AptitudeHealingRuntimeTests, "fixture", full_arena
    ), patch.object(EffectDispatcher, "_execute", observe):
        for back in (False, True):
            for passive in (False, True):
                trace.clear()
                try:
                    data = suite.allied_fixture(
                        passives=(4686, 4687) if passive else (4686,),
                        ally_spells=(4785,),
                        target_distance=2,
                    )
                    data[2].move(data[6][7]["account_id"], 7, [(-8, -8, -1)])
                    with patch.object(server, "prepare_spell_transaction", candidate):
                        gift = suite.allied_cast(data, 7813)
                    data = (*data[:2], gift.fight, *data[3:])
                    gifted = [
                        (s.reference, s.level, s.caster_id)
                        for s in data[2].actors[8].state_ledger.entries
                    ]
                    assert any(row[0] == 3671 for row in gifted), gifted
                    suite.advance_to(data, 8)
                    fight = data[2]
                    actor = fight.actors[8]
                    enemy = fight.actors[-7]
                    queue = [(actor.position, ())]
                    seen = {actor.position}
                    path = None
                    occupied = {
                        a.position
                        for a in fight.actors.values()
                        if a.id != 8 and a.hp > 0
                    }
                    while queue:
                        cell, steps = queue.pop(0)
                        if abs(cell[0] - enemy.position[0]) + abs(
                            cell[1] - enemy.position[1]
                        ) == 1 and native_facing(
                            SimpleNamespace(position=cell), enemy
                        ) == (
                            "BACK" if back else "FRONT"
                        ):
                            path = steps
                            break
                        if len(steps) >= actor.mp:
                            continue
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nxt = (cell[0] + dx, cell[1] + dy, cell[2])
                            if (
                                nxt in fight.walkable
                                and nxt not in seen
                                and nxt not in occupied
                                and (fight.edges is None or (cell, nxt) in fight.edges)
                            ):
                                seen.add(nxt)
                                queue.append((nxt, (*steps, nxt)))
                    assert path is not None, (
                        actor.position,
                        enemy.position,
                        actor.mp,
                        back,
                    )
                    if path:
                        fight.move(data[6][8]["account_id"], 8, list(path))
                    hp = enemy.hp
                    tx = suite.allied_cast(
                        data, 4785, target=enemy.position, actor_id=8, action_id=200
                    )
                    ally_damage = hp - tx.fight.actors[-7].hp
                    data = (*data[:2], tx.fight, *data[3:])
                    if not back:
                        ally = data[2].actors[8]
                        occupied_now = {
                            a.position
                            for a in data[2].actors.values()
                            if a.id != 8 and a.hp > 0
                        }
                        exits = [
                            (
                                ally.position[0] + dx,
                                ally.position[1] + dy,
                                ally.position[2],
                            )
                            for dx, dy in ((1, 0), (-1, 0), (0, -1), (0, 1))
                        ]
                        exits = [
                            cell
                            for cell in exits
                            if cell in data[2].walkable
                            and cell not in occupied_now
                            and (
                                data[2].edges is None
                                or (ally.position, cell) in data[2].edges
                            )
                        ]
                        assert exits and ally.mp >= 1, (ally.position, ally.mp, exits)
                        data[2].move(data[6][8]["account_id"], 8, [exits[0]])
                    suite.advance_to(data, 7)
                    fight = data[2]
                    actor = fight.actors[7]
                    enemy = fight.actors[-7]
                    queue = [(actor.position, ())]
                    seen = {actor.position}
                    giver_paths = []
                    occupied = {
                        a.position
                        for a in fight.actors.values()
                        if a.id != 7 and a.hp > 0
                    }
                    while queue:
                        cell, steps = queue.pop(0)
                        distance = abs(cell[0] - enemy.position[0]) + abs(
                            cell[1] - enemy.position[1]
                        )
                        if 1 <= distance <= 3 and native_facing(
                            SimpleNamespace(position=cell), enemy
                        ) == ("BACK" if back else "FRONT"):
                            giver_paths.append(steps)
                        if len(steps) >= actor.mp:
                            continue
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nxt = (cell[0] + dx, cell[1] + dy, cell[2])
                            if (
                                nxt in fight.walkable
                                and nxt not in seen
                                and nxt not in occupied
                                and (fight.edges is None or (cell, nxt) in fight.edges)
                            ):
                                seen.add(nxt)
                                queue.append((nxt, (*steps, nxt)))
                    failures = []
                    hp = enemy.hp
                    tx = None
                    for giver_path in giver_paths:
                        branch = deepcopy(fight)
                        branch_data = (*data[:2], branch, *data[3:])
                        try:
                            if giver_path:
                                branch.move(
                                    data[6][7]["account_id"], 7, list(giver_path)
                                )
                            tx = suite.allied_cast(
                                branch_data,
                                4692,
                                target=branch.actors[-7].position,
                                actor_id=7,
                                action_id=300,
                            )
                            break
                        except Exception as exc:
                            failures.append((giver_path, str(exc)))
                    assert tx is not None, (
                        actor.position,
                        enemy.position,
                        actor.mp,
                        back,
                        failures,
                    )
                    result = dict(
                        gifted=gifted,
                        ally_path=path,
                        ally_damage=ally_damage,
                        giver_path=giver_path,
                        giver_damage=hp - tx.fight.actors[-7].hp,
                        trace=list(trace),
                        recipient_states=[
                            (s.reference, s.level)
                            for s in tx.fight.actors[8].state_ledger.entries
                        ],
                    )
                except Exception as exc:
                    result = dict(
                        error=type(exc).__name__ + ": " + str(exc), trace=list(trace)
                    )
                results.append(dict(back=back, passive=passive, result=result))
    return results


import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeCeladaAcquisitionPipelineTests(unittest.TestCase):
    def test_actual_gift_ally_cast_and_giver_attack_matches_native_front_back_branches(
        self,
    ):
        from wakfu_server.storage import native_catalog

        revision = native_catalog.release()
        self.assertTrue(revision)
        self.assertEqual(native_catalog.release(), revision)
        suite.setUpClass()
        rows = run_cases()
        self.assertEqual(native_catalog.release(), revision)
        self.assertEqual(len(rows), 4)
        expected = {
            (False, False): 127,
            (False, True): 97,
            (True, False): 160,
            (True, True): 178,
        }
        for row in rows:
            with self.subTest(back=row["back"], passive=row["passive"]):
                result = row["result"]
                self.assertNotIn("error", result, result)
                self.assertEqual(
                    result["giver_damage"], expected[(row["back"], row["passive"])]
                )
                self.assertEqual(result["ally_damage"], 141 if row["back"] else 113)
                self.assertIn((3671, 1, 7), result["gifted"])
                self.assertIn((3671, 1), result["recipient_states"])
                executed = lambda ref: any(
                    item["ref"] == ref
                    and item["result"]
                    and item["caster"] == 7
                    and item["target"] == -7
                    for item in result["trace"]
                )
                self.assertEqual(executed(159743), not row["passive"])
                self.assertEqual(executed(351766), row["back"] and row["passive"])
                self.assertFalse(
                    any(
                        item["ref"] == 351699 and item["result"]
                        for item in result["trace"]
                    )
                )
        print("CELADA_ACTUAL_CASES", json.dumps(rows), flush=True)

    def test_current_native_carrier_is_infinite_and_alternate_cleanup_requires_meditation(
        self,
    ):
        # These are published-source contracts, not a fabricated carrier expiry.
        from wakfu_server.storage import native_catalog

        revision = native_catalog.release()
        self.assertTrue(revision)
        from wakfu_server.paths import DATA_ROOT

        self.assertEqual(
            native_catalog.release(),
            revision,
        )
        state = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "states", "3671"
        )
        self.assertIsNotNone(state)
        self.assertTrue(all(level["duration"] == -1 for level in state["levels"]))
        parent = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", "395996"
        )
        self.assertIsNotNone(parent)
        self.assertEqual(parent["criteria"], "IsSpellInDeck(7720)")
        self.assertEqual(parent["native_target_selector"], {"class": "fcE", "mask": 2})
        self.assertIn(395998, parent["children"])
