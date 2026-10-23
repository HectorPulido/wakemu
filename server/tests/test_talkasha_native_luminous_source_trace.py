"""Read-only trace of the initial native luminous-cell producer chain."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch


class TalKashaNativeLuminousSourceTraceTests(unittest.TestCase):
    def test_capture_initial_luminous_producer_without_idle_turn_loop(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        refs = {378799, 378813, 378814, 379295, 379940, 379951, 379952, 379953}
        rows = []
        original = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference not in refs:
                return original(dispatcher, invocation, **kwargs)
            row = dict(
                reference=invocation.reference,
                level=invocation.level,
                caster=invocation.caster_id,
                target=invocation.target_id,
                cell=invocation.cell,
                native_trigger_context=invocation.native_trigger_context,
                native_explicit_target=invocation.native_explicit_target,
                native_preselected_target=invocation.native_preselected_target,
                fresh=invocation.wakemu_fresh_child_selection,
                rebound=invocation.wakemu_rebound_child_selection,
            )
            rows.append(row)
            result = original(dispatcher, invocation, **kwargs)
            row["result"] = bool(result)
            return result

        helper = FulMoonTalKashaNativeBootstrapTests()
        with patch.object(EffectDispatcher, "execute", observe):
            fight, scene, children = helper._started(
                5500, 155, 1400, reconstructed_talkasha_scene
            )
        receipt = dict(
            scope="read_only_initial_producer_diagnostic_not_gameplay_qualification",
            rows=rows,
            actors={
                i: dict(
                    position=a.position,
                    team=a.team,
                    states=[
                        dict(reference=e.reference, level=e.level)
                        for e in a.state_ledger.entries
                    ],
                )
                for i, a in fight.actors.items()
            },
            areas=[
                dict(reference=row["reference"], cell=row["cell"])
                for row in fight.native_effect_areas.values()
            ],
        )
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021/talkasha-initial-luminous-source-trace.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertTrue(rows)
        self.assertIn(5579, children.values())
