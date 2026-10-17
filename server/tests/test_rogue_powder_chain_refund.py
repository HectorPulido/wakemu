"""Paid bomb chains refund one Powder per retired owned bomb, not per variant."""
from collections import Counter
import os
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RoguePowderChainRefundTests(unittest.TestCase):
    def run_chain(self, *, critical):
        from test_guide_rogue_fogger_cra_runtime import PaidSequence, distance

        seq = PaidSequence(self, 13, two_owners=True, active=(6463, 6468, 6473))

        def cast_paid(reference, cell, *, critical=False):
            if not critical:
                return seq.cast(7, reference, cell)
            before = snapshot(seq.fight)
            tx = prepare_server_spell(
                struct.pack(">qqiih", 7, seq.uid(7, reference), *cell),
                seq.characters[7],
                {-7: seq.monster},
                seq.fight,
                seq.characters[7]["account_id"],
                seq.decks[7],
                action_id=seq.action,
                line_of_sight=seq.los,
                critical=True,
                **seq.common
            )
            self.assertEqual(snapshot(seq.fight), before)
            self.assertTrue(
                any(tx.outcomes),
                "A supported critical elemental placement must execute",
            )
            seq.runtime.fight = tx.fight
            seq.action += 1
            return tx

        self.assertEqual(seq.state(7, 7919), 3)
        seq.reach(7)

        def free_cell(cell):
            return not any(
                a.hp > 0 and a.position == cell for a in seq.fight.actors.values()
            )

        own_cells = [c for c in seq.targets(7, 6473, free_cell) if free_cell(c)]
        self.assertTrue(own_cells)
        own_cell = own_cells[0]
        first = cast_paid(6473, own_cell, critical=critical)
        self.assertGreater(first.plan["costs"]["ap"], 0)
        self.assertEqual(seq.state(7, 7919), 2)
        bomb_a = seq.summons(7, (3795, 3796, 3797))[0]
        seq.reach(8)

        def foreign_candidate(cell):
            return (
                free_cell(cell)
                and distance(cell, own_cell) >= 5
                and 1 <= distance(seq.fight.actors[7].position, cell) <= 7
            )

        foreign_cells = [
            c for c in seq.targets(8, 6473, foreign_candidate) if foreign_candidate(c)
        ]
        self.assertTrue(foreign_cells)
        seq.cast(8, 6473, foreign_cells[0])
        foreign = seq.summons(8, (3795, 3796, 3797))[0]
        seq.reach(7)

        def adjacent_candidate(cell):
            return (
                free_cell(cell)
                and 0 < distance(cell, own_cell) <= 2
                and distance(cell, foreign.position) > 2
            )

        second_cells = [
            c for c in seq.targets(7, 6468, adjacent_candidate) if adjacent_candidate(c)
        ]
        self.assertTrue(second_cells)
        second = cast_paid(6468, second_cells[0], critical=critical)
        self.assertGreater(second.plan["costs"]["ap"], 0)
        own_ids = {a.id for a in seq.summons(7, (3795, 3796, 3797))}
        self.assertEqual(len(own_ids), 2)
        self.assertEqual(seq.state(7, 7919), 1)
        self.assertEqual(seq.state(8, 7919), 2)
        foreign_before = snapshot(seq.fight)["actors"][str(foreign.id)]
        rejected = seq.reject(7, 6495, foreign.position)
        self.assertEqual(rejected.native_casting_result, "twV")
        refunds = []
        original = NativeStateHandler.__call__

        def observe(handler, effect, values, invocation):
            result = original(handler, effect, values, invocation)
            if invocation.reference in (417862, 417863) and result:
                refunds.append((invocation.reference, invocation.target_id))
            return result

        before = snapshot(seq.fight)
        with patch.object(NativeStateHandler, "__call__", observe):
            tx = prepare_server_spell(
                struct.pack(">qqiih", 7, seq.uid(7, 6495), *bomb_a.position),
                seq.characters[7],
                {-7: seq.monster},
                seq.fight,
                seq.characters[7]["account_id"],
                seq.decks[7],
                action_id=seq.action,
                line_of_sight=seq.los,
                critical=False,
                **seq.common
            )
        self.assertEqual(snapshot(seq.fight), before)
        self.assertTrue(
            any(tx.outcomes), "Normal Detonación must execute the owned chain"
        )
        seq.runtime.fight = tx.fight
        self.assertEqual(tx.plan["costs"]["ap"], 1)
        self.assertTrue(all(seq.fight.actors[i].hp == 0 for i in own_ids))
        self.assertFalse(seq.summons(7, (3795, 3796, 3797)))
        self.assertEqual(Counter(owner for _, owner in refunds), Counter({7: 2}))
        self.assertEqual(seq.state(7, 7919), 3)
        self.assertEqual(seq.fight.actors[7].effect_stats[57], 3)
        self.assertEqual(seq.state(8, 7919), 2)
        self.assertEqual(snapshot(seq.fight)["actors"][str(foreign.id)], foreign_before)
        seq.action += 1
        seq.reject(7, 6495, bomb_a.position)
        self.assertEqual(seq.state(7, 7919), 3)

    def test_paid_normal_chain_refunds_each_bomb_once_and_preserves_foreign_owner(self):
        self.run_chain(critical=False)

    def test_paid_critical_bomb_creation_then_normal_chain_refunds_each_bomb_once(self):
        self.run_chain(critical=True)
