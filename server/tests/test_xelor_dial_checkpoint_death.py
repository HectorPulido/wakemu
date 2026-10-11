"""Actual owned dial replacement and its death-driven hour cleanup."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers


class XelorDialCheckpointDeathTests(unittest.TestCase):
    def test_checkpoint_then_lawful_recast_retires_only_original_owned_clock(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture()
        first = helper.cast(data, 5345, (-11, -7, -1))
        old_summons = set(first.fight.actors) - set(data[2].actors)
        self.assertEqual(len(old_summons), 1)
        old_summon = next(iter(old_summons))
        old_hours = {
            uid
            for uid, row in first.fight.native_effect_areas.items()
            if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1558
        }
        self.assertGreaterEqual(len(old_hours), 12)
        import json
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot

        saved = snapshot(first.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        for uid in old_hours:
            self.assertEqual(
                restored["native_effect_areas"][str(uid)],
                json.loads(json.dumps(saved["native_effect_areas"]))[str(uid)],
            )
            self.assertEqual(
                json.loads(json.dumps(saved["native_effect_areas"]))[str(uid)][
                    "owner_id"
                ],
                7,
            )
        data = helper.next_owned_turn(helper.adopt(data, first.fight))
        self.assertGreater(data[2].actors[old_summon].hp, 0)
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (313166, 313167, 313313, 313314, 313315, 313276):
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
            # The native free-cell gate excludes the old occupied dial cell.
            # A different real range3 column exercises the same replacement.
            second = helper.cast(data, 5345, (-8, -4, -1), action_id=30)
        fight = second.fight
        self.assertEqual(fight.actors[old_summon].hp, 0, trace)
        self.assertTrue(old_hours.isdisjoint(fight.native_effect_areas), trace)
        hours = {
            uid: row
            for uid, row in fight.native_effect_areas.items()
            if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1557
        }
        self.assertEqual(
            {row["reference"] for row in hours.values()}, set(range(1546, 1558)), trace
        )
        self.assertEqual(helper.states(fight.actors[7])[6759], 12, trace)
        self.assertEqual(len(set(fight.actors) - set(data[2].actors)), 1, trace)
        successful = {reference for reference, _, _, result in trace if result}
        self.assertTrue({313166, 313167, 313314, 313315, 313276} <= successful, trace)
