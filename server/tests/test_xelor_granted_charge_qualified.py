"""Actual native Xelor gameplay regression, staged outside the server freeze."""
import unittest
import json
import test_xelor_runtime_pipeline as helpers


class XelorGrantedChargeRuntimeTests(unittest.TestCase):
    def test_granted_7794_consumes_real_rollover_charge_with_exact_scaling(self):
        h = helpers.XelorRuntimePipelineTests()
        rows = []
        for charged in (False, True):
            data = h.fixture()
            dial = h.dial(data)
            data = h.adopt(data, dial.fight)
            if charged:
                for n in range(4):
                    tx = h.cast(data, 2839, action_id=60 + n)
                    data = h.adopt(data, tx.fight)
                    if n < 3:
                        data = h.next_owned_turn(data)
            before = h.states(data[2].actors[7])
            charge = before.get(6779, 0)
            assert charge == (1 if charged else 0), before
            mechanisms = [a for a in data[2].actors.values() if a.id not in (7, -7)]
            assert len(mechanisms) == 1, mechanisms
            assert h.states(mechanisms[0]).get(7887, 0) == charge, h.states(
                mechanisms[0]
            )
            tx = h.cast(data, 7794, action_id=71)
            after = h.states(tx.fight.actors[7])
            # Current ordinary349446 factor and constant are each1+.025*200=6.
            assert after.get(6744) == 6 + 6 * charge, (before, after)
            assert 6779 not in after, after
            assert all(
                7887 not in h.states(a)
                for a in tx.fight.actors.values()
                if a.id not in (7, -7)
            )
            rows.append(
                {
                    "charged": charged,
                    "before": before,
                    "after": after,
                    "wp": tx.fight.actors[7].effect_stats[4],
                }
            )
        print(json.dumps(rows))
