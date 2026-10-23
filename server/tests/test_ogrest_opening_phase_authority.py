"""Bounded native opening diagnostic; not a complete Ogrest encounter witness."""
import json
from pathlib import Path
import unittest


class OgrestOpeningPhaseAuthorityTests(unittest.TestCase):
    def test_native_opening_reveals_phase_marker_and_artifact_premises(self):
        from xelor_multiowner_fixture import TwoXelorFixture

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            native_target_ref=4378,
            native_target_level=230,
            caster_breed=8,
            second_player_breed=8,
            level=200,
            enemy_position=(-5, -7, -1),
            compact_arena=False,
        )
        boss = fight.actors[-7]
        states = [(entry.reference, entry.level) for entry in boss.state_ledger.entries]
        receipt = dict(
            scope="Actual native opening only on existing diagnostic map1134; no original scene, phase or victory qualification",
            reference=4378,
            hp=boss.hp,
            maximum_hp=boss.max_hp,
            states=states,
            phase_flags={
                str(ref): [level for state, level in states if state == ref]
                for ref in range(5003, 5009)
            },
            actors={
                str(key): dict(
                    hp=actor.hp,
                    position=actor.position,
                    states=[
                        (entry.reference, entry.level)
                        for entry in actor.state_ledger.entries
                    ],
                )
                for key, actor in fight.actors.items()
            },
            areas=[
                dict(reference=area["reference"], cell=area["cell"])
                for area in fight.native_effect_areas.values()
            ],
            native_start_event_delivered=fight.native_start_event_delivered,
        )
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/parallel-readiness-20261021/ogrest-actual-opening-phase-authority.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertEqual((boss.hp, boss.max_hp), (50000000, 50000000))
        self.assertTrue({4894, 4979, 5022, 7998} <= {state for state, _ in states})
        self.assertTrue(fight.native_start_event_delivered)
