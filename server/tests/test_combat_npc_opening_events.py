"""Native NPC opening subscribers use the actual startup transaction."""
import sys
import struct
import unittest
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_recorded_instance_fixture import original_bootstrap_publication
import validate_monster_spell_activation as validator
from native_witness_fixture import legal_witness_cell, native_level200_fixture
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.combat_actor_snapshot import native_npc_creation_values
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_effect_removal import _identity_fields


class NativeNpcOpeningEventsTests(unittest.TestCase):
    def test_real_ogrest_and_neoogrest_start_creates_native_area_and_phase_states(self):
        for reference in (4378, 5806):
            with self.subTest(reference=reference):
                enemy, placement = legal_witness_cell()
                native_fixture, fixture_facts = native_level200_fixture(validator)
                with original_bootstrap_publication():
                    fight, character, monsters, deck = native_fixture(
                        reference, 230, enemy, native_lifecycle=False
                    )
                self.assertEqual(character["level"], 200)
                self.assertEqual(fight.actors[7].effective_level, 200)
                self.assertEqual(fight.turn_id, 1)
                self.assertEqual(fight.actors[-200].effect_stats[4], 0)
                self.assertEqual(
                    fight.actors[-200].effect_maxima[4],
                    native_npc_creation_values(reference, 230)[4]["maximum"],
                )
                self.assertIn(-200, fight.native_npc_initialization_receipts)
                before = snapshot(fight)
                self.assertFalse(
                    any(
                        e.reference in range(5003, 5009)
                        for e in fight.actors[-200].state_ledger.entries
                    )
                )
                preview, packets = prepare_server_initialization(
                    character,
                    monsters,
                    fight,
                    character["account_id"],
                    deck,
                    action_id=1,
                    rng=Random(0),
                    fight_start=True,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertTrue(preview.native_start_event_delivered)
                self.assertTrue(
                    set(range(5003, 5009))
                    <= {e.reference for e in preview.actors[-200].state_ledger.entries}
                )
                areas = [
                    a
                    for a in preview.native_effect_areas.values()
                    if a["reference"] == 1254
                    and a["owner_id"] == -200
                    and a["effect_reference"] == 238853
                ]
                self.assertEqual(len(areas), 1)
                area_packets = []
                for opcode, body in packets:
                    if (
                        opcode == 12613
                        and len(body) >= 19
                        and struct.unpack_from(">i", body, 13)[0] == 315
                    ):
                        size = struct.unpack_from(">h", body, 17)[0]
                        fields = _identity_fields(body[19 : 19 + size])
                        if fields.get(3) == 238853:
                            area_packets.append(fields)
                self.assertEqual(len(area_packets), 1)
                self.assertEqual(area_packets[0][1], areas[0]["effect_uid"])
                checkpoint = snapshot(preview)
                with self.assertRaises(ValueError):
                    prepare_server_initialization(
                        character,
                        monsters,
                        preview,
                        character["account_id"],
                        deck,
                        action_id=2,
                        rng=Random(0),
                        fight_start=True,
                    )
                self.assertEqual(snapshot(preview), checkpoint)
