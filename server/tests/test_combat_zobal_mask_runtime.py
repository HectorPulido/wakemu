"""Zobal's native mask grants, primary states and turn-derived charges."""
import importlib.util
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
@patch.dict(
    os.environ,
    {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"},
)
class ZobalMaskRuntimeTests(unittest.TestCase):
    def test_mask_bonus_switches_on_nearby_player_allies_only(self):
        import test_combat_aptitude_healing_runtime as allied_fixture
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells

        allied_fixture.AptitudeHealingRuntimeTests.setUpClass()
        for passive, sequence in (
            ((), ((7081, 6614), (7082, 6615), (7083, 6616))),
            ((7104,), ((7226, 6614), (7082, 6615))),
        ):
            with self.subTest(passive=passive):
                (
                    fight,
                    characters,
                    monster,
                    decks,
                ) = allied_fixture.AptitudeHealingRuntimeTests().fixture(
                    active_spells=(7066,),
                    passive_spells=passive,
                    injury=0,
                    level=90,
                    caster_breed=14,
                    third_player_position=(-8, -1, -1),
                    compact_arena=False,
                )
                self.assertIn((-8, -1, -1), fight.walkable)
                self.assertEqual(fight.current.id, 7)
                owner_cell = fight.actors[7].position
                ally_cell = fight.actors[8].position
                outside_cell = fight.actors[9].position
                self.assertLessEqual(
                    abs(owner_cell[0] - ally_cell[0])
                    + abs(owner_cell[1] - ally_cell[1]),
                    4,
                )
                self.assertGreater(
                    abs(owner_cell[0] - outside_cell[0])
                    + abs(owner_cell[1] - outside_cell[1]),
                    4,
                )
                granted = granted_spells(fight, 7)
                for spell, expected_bonus in sequence:
                    self.assertIn(spell, granted)
                    request = struct.pack(
                        ">qqiih", 7, granted[spell]["uid"], *owner_cell
                    )
                    transaction = prepare_server_spell(
                        request,
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=fight.actors[7].turn_count + spell,
                        line_of_sight=lambda source, target, preview: authoritative_visible(
                            1134, source, target, preview
                        ),
                        critical=False,
                        rng=random.Random(17),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    fight = transaction.fight
                    state_refs = {
                        actor_id: {
                            state.reference for state in actor.state_ledger.entries
                        }
                        for actor_id, actor in fight.actors.items()
                    }
                    self.assertIn(expected_bonus, state_refs[8])
                    self.assertNotIn(expected_bonus, state_refs[7])
                    self.assertNotIn(expected_bonus, state_refs[9])
                    self.assertNotIn(expected_bonus, state_refs[-7])
                    competing = {6614, 6615, 6616} - {expected_bonus}
                    self.assertTrue(competing.isdisjoint(state_refs[8]), state_refs[8])
                    if expected_bonus in (6615, 6616):
                        self.assertIn(
                            13560,
                            [opcode for opcode, _payload in transaction.packets],
                            "switch should emit native state removal for prior bonus",
                        )

    def test_native_mask_grants_and_turn_charges_with_and_without_erosion(self):
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import ACTIVE_SLOT_LEVELS, available_spells

        tool = Path(__file__).parents[1] / "tools/audit_ready_start.py"
        spec = importlib.util.spec_from_file_location("zobal_mask_ready_tool", tool)
        ready = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(tool.parent), *sys.path]):
            spec.loader.exec_module(ready)

        active = sorted(
            row["id"] for row in available_spells(14, 90) if row["kind"] == "active"
        )[: sum(90 >= threshold for threshold in ACTIVE_SLOT_LEVELS)]

        def mark_passive(character, breed, level, passive):
            character["_zobal_has_erosion"] = passive == 7104

        def exercise(runtime, character, monster, deck, initial_packets, stats):
            del initial_packets
            actor_id = character["id"]
            branch = deepcopy(runtime)
            actor = branch.fight.actors[actor_id]
            # The Ready fixture's native player is not always first in
            # initiative. Reach its real turn through normal turn handlers.
            for _ in range(max(2, len(branch.fight.actors) * 4)):
                current = branch.fight.current
                if current and current.id == actor_id and branch.awaiting_ack is None:
                    break
                if current is None:
                    raise AssertionError("missing current actor before mask cast")
                packets = (
                    branch.end_turn(current.owner_id, current.id, current.turn_count)
                    if current.controlled
                    else branch.end_server_turn(current.id, branch.fight.turn_id)
                )
                ack = branch.awaiting_ack
                if ack is not None:
                    packets += branch.acknowledge_turn(struct.pack(">i", ack))
            else:
                raise AssertionError("could not reach the Zobal's actual turn")

            has_erosion = bool(character.get("_zobal_has_erosion"))
            grants = granted_spells(branch.fight, actor_id)
            first_spell, first_state = (7226, 6888) if has_erosion else (7081, 6611)
            self.assertIn(first_spell, grants)
            self.assertNotIn(7081 if has_erosion else 7226, grants)
            self.assertTrue({7082, 7083}.issubset(grants))

            sequence = ((first_spell, first_state), (7082, 6612), (7083, 6613))
            observations = []
            for spell, primary_state in sequence:
                actor = branch.fight.actors[actor_id]
                grant = granted_spells(branch.fight, actor_id)[spell]
                request = struct.pack(">qqiih", actor_id, grant["uid"], *actor.position)
                visible = lambda source, target, fight: authoritative_visible(
                    character["map_id"],
                    source,
                    target,
                    fight,
                    blocking_footprints={
                        candidate.id: {candidate.position[:2]}
                        for candidate in fight.actors.values()
                        if candidate.hp > 0
                    },
                )
                with combat_diagnostic_scope(lambda **event: None, limit=4096):
                    transaction = prepare_server_spell(
                        request,
                        character,
                        {monster["id"]: monster},
                        branch.fight,
                        actor.owner_id,
                        deck,
                        action_id=branch.action_id + 1,
                        line_of_sight=visible,
                        critical=False,
                        rng=random.Random(17),
                    )
                packets = commit_spell_transaction(
                    branch, transaction, stats_serializer=stats
                )
                states = {
                    entry.reference: entry
                    for entry in branch.fight.actors[actor_id].state_ledger.entries
                }
                self.assertIn(primary_state, states)
                observations.append(
                    {
                        "spell": spell,
                        "state_refs": sorted(states),
                        "packet_ops": [op for op, _ in packets],
                    }
                )

            primary_states = {first_state, 6612, 6613}
            self.assertTrue(
                primary_states.issubset(
                    {
                        entry.reference
                        for entry in branch.fight.actors[actor_id].state_ledger.entries
                    }
                )
            )
            # Advance through actual turns so the native state listeners, not
            # test-injected state, create their corresponding charges.
            start_table = branch.fight.native_table_turn
            seen_owner_turn = False
            for _ in range(max(8, len(branch.fight.actors) * 8)):
                current = branch.fight.current
                if current is None:
                    raise AssertionError("missing current actor during charge cycle")
                if current.id == actor_id:
                    if seen_owner_turn and branch.fight.native_table_turn > start_table:
                        break
                    seen_owner_turn = True
                    packets = branch.end_turn(
                        current.owner_id, current.id, current.turn_count
                    )
                elif current.controlled:
                    packets = branch.end_turn(
                        current.owner_id, current.id, current.turn_count
                    )
                else:
                    packets = branch.end_server_turn(current.id, branch.fight.turn_id)
                ack = branch.awaiting_ack
                if ack is not None:
                    packets += branch.acknowledge_turn(struct.pack(">i", ack))
            else:
                raise AssertionError("native turn cycle did not complete")

            refs = {
                entry.reference
                for entry in branch.fight.actors[actor_id].state_ledger.entries
            }
            self.assertTrue({9247, 9248, 9249}.issubset(refs), sorted(refs))
            self.assertTrue(snapshot(branch.fight)["actors"])
            self.assertNotEqual(snapshot(runtime.fight), snapshot(branch.fight))
            return {
                "status": "mask_sequence_committed",
                "has_erosion": has_erosion,
                "grants": sorted(grants),
                "steps": observations,
                "post_turn_state_refs": sorted(refs),
            }

        with tempfile.TemporaryDirectory(prefix="wakemu-zobal-mask-") as temp:
            output = Path(temp) / "ready.json"
            report = ready.run(
                output,
                basics_only=True,
                turn_cycle=True,
                turn_steps=0,
                cases_override=[(14, 90, None), (14, 90, 7104)],
                active_deck_provider=lambda breed, level, passive: active,
                character_fixture_provider=mark_passive,
                on_runtime=exercise,
            )

        self.assertTrue(report["finished"])
        self.assertTrue(report["source_stable"])
        self.assertTrue(report["ready_gate_passed"])
        self.assertEqual(report["completed_cases"], 2)
        for row in report["rows"]:
            self.assertEqual(row["status"], "ready_started")
            self.assertEqual(row["runtime_access"]["status"], "mask_sequence_committed")
            self.assertTrue(row["runtime_access"]["steps"])
