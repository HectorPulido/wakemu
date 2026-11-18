"""Owned-turn Coney evolution preserves the same affiliation as its owner."""

import unittest
import struct
from pathlib import Path
import sys
from unittest.mock import patch

import test_aniripsa_grant_summon_pipeline as summon_pipeline


class ConeyEvolutionPipelineTests(unittest.TestCase):
    def test_normal_and_dark_coney_evolve_on_the_next_owner_turn(self):
        helper = summon_pipeline.AniripsaGrantSummonPipelineTests()
        for dark, initial_ref, evolved_ref in ((False, 182, 1775), (True, 5528, 5533)):
            with self.subTest(dark=dark):
                fixture = helper.fixture(level=31)
                if dark:
                    fixture = helper.adopt(fixture, helper.cast(fixture, 7977).fight)
                fixture = helper.adopt(
                    fixture, helper.cast(fixture, 7978, (-8, -6, -1)).fight
                )
                summons = [
                    actor
                    for actor in fixture[2].actors.values()
                    if actor.hp > 0
                    and (getattr(actor, "native_summon_source", None) or {}).get(
                        "caster_id"
                    )
                    == 7
                ]
                self.assertEqual(len(summons), 1)
                initial = summons[0]
                self.assertEqual(initial.native_summon_source["ref"], initial_ref)
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
                import combat_audit_turns

                delivered = []
                advance = combat_audit_turns.advance_actual_turn

                def collect(runtime):
                    packets = advance(runtime)
                    delivered.extend(packets)
                    return packets

                with patch.object(combat_audit_turns, "advance_actual_turn", collect):
                    helper.next_player_turn(fixture[2], fixture)
                living = [
                    actor
                    for actor in fixture[2].actors.values()
                    if actor.hp > 0
                    and fixture[2]._in_play(actor)
                    and (getattr(actor, "native_summon_source", None) or {}).get(
                        "caster_id"
                    )
                    == 7
                ]
                self.assertEqual(len(living), 1)
                self.assertEqual(living[0].native_summon_source["ref"], evolved_ref)
                self.assertEqual(living[0].team, fixture[2].actors[7].team)
                self.assertEqual(living[0].native_controller_id, 7)
                self.assertEqual(initial.hp, 0)
                self.assertEqual(
                    sum(
                        opcode == 12613 and struct.unpack_from(">i", body, 13)[0] == 307
                        for opcode, body in delivered
                    ),
                    1,
                )
                self.assertEqual(
                    [
                        struct.unpack(">qB", body[-9:])
                        for opcode, body in delivered
                        if opcode == 12727
                        and struct.unpack(">qB", body[-9:])[0] == initial.id
                    ],
                    [(initial.id, 2)],
                )
                self.assertEqual(
                    initial.native_death_status["last_writer"], "owned.aTS.F.type2"
                )
