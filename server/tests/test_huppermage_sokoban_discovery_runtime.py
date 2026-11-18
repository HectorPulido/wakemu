"""Actual native constructor, push spell, goal glyphs, and victory on Sokoban 1019."""

import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import wakfu_server.combat_class_initialization as class_initialization
import wakfu_server.combat_morph_dependencies as morph_dependencies
import wakfu_server.combat_morph_handler as morph_handler
import wakfu_server.combat_server_spell as server_spell


ROOT = Path(__file__).parents[1]
CONFIG = (
    ROOT / "wakfu_server/maps/owned_story_profiles/"
    "huppermage-sokoban-discovery-1019.configuration.json"
)
FIXTURE = ROOT / "tests/fixtures/huppermage_sokoban_3891_cast.json"


class HuppermageSokobanDiscoveryRuntimeTests(unittest.TestCase):
    def test_native_pushes_solve_reviewed_board_and_finish_from_real_goal_glyphs(self):
        from jondo_native_support_probe import build_fixture
        from wakfu_server.combat_encounter_roles import role_assignment
        from wakfu_server.combat_encounter_scene_policy import prepare_scene

        configuration = json.loads(CONFIG.read_text())
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(
            fixture["native_source_receipt_sha256"],
            "e3e580fa654496409412878aef94691ebb16384145f11d158267c209c0b9d05b",
        )
        self.assertEqual(
            fixture["source_graph_sha256"],
            "0d8ca67e2ee427b6de56a79f704845170b243b340130a4dd368e1bee4170cecd",
        )
        expected_spells = {5589, 5620}
        self.assertEqual(
            {row["reference"] for row in fixture["profiles"]["3891"]["abilities"]},
            expected_spells,
        )
        roots = {
            reference
            for spell in map(str, expected_spells)
            for _, _, references in fixture["level_zero"]["casting"][spell]["levels"]
            for reference in references
        }
        closure = set()
        pending = list(roots)
        while pending:
            reference = pending.pop()
            if reference in closure:
                continue
            closure.add(reference)
            pending.extend(fixture["effects"][str(reference)].get("children", ()))
        self.assertEqual(closure, {int(reference) for reference in fixture["effects"]})
        room = configuration["topology"]["rooms"][0]
        cells = [tuple(cell) for cell in room["cells"]]
        scope = dict(
            map_id=1019,
            instance_id=1,
            group_id=1,
            room_order=1,
            policy_version=1,
            route_key=configuration["slug"],
            evidence_hashes=configuration["evidence_hashes"],
        )
        scene = prepare_scene(room["encounter_scene"], scope=scope, room_cells=cells)
        base_compiled = server_spell.compiled_runtime_catalog()
        candidate_compiled = base_compiled.with_effect_sources(
            {int(key): value for key, value in fixture["effects"].items()}
        )
        class_initialization.level_zero_catalog.cache_clear()

        try:
            with (
                patch.object(
                    morph_handler,
                    "native_morph_profiles",
                    return_value=fixture["profiles"],
                ),
                patch.object(
                    morph_dependencies,
                    "zero_catalog",
                    return_value=fixture["level_zero"],
                ),
                patch.object(
                    server_spell,
                    "compiled_runtime_catalog",
                    return_value=candidate_compiled,
                ),
            ):
                case = build_fixture(
                    3889,
                    1,
                    allies=((3889, 1, (2, 47, -1)),),
                    map_id=1019,
                    player_position=(3, 47, -1),
                    npc_position=(2, 46, -1),
                    allowed_cells=cells,
                    full_room_scope=True,
                    fixed_member_positions={0: (2, 46, -1), 1: (2, 47, -1)},
                    encounter_scene_record=scene,
                    terrain_instance_id=10000,
                    instance_id=1,
                    role_record=role_assignment(1019, (3889, 3889)).record(),
                )
                fight = case.fight
                player = fight.actors[7]
                boxes = {
                    actor.id: actor for actor in fight.actors.values() if actor.id < 0
                }
                self.assertEqual(set(boxes), {-7, -8})
                self.assertIn(
                    4063, {row.reference for row in player.state_ledger.entries}
                )
                self.assertTrue(
                    all(
                        4062 in {row.reference for row in actor.state_ledger.entries}
                        for actor in boxes.values()
                    )
                )
                self.assertEqual(
                    set(fight.native_morph_spellbooks[7]["levels"]),
                    {5589, 5620},
                )
                self.assertEqual(fight.native_morph_spellbooks[7]["levels"][5620], 0)

                from wakfu_server.combat_los import authoritative_visible
                from wakfu_server.combat_obstacle_condition import footprint
                from wakfu_server.combat_spell_commit import commit_spell_transaction

                native_transactions = []

                def cast_native_spell(spell_id, target):
                    preview = case.fight
                    actor = preview.actors[7]
                    body = struct.pack(">qqiih", 7, spell_id, *target)
                    transaction = server_spell.prepare_server_spell(
                        body,
                        case.characters[7],
                        case.monsters,
                        preview,
                        actor.owner_id,
                        case.decks[7],
                        action_id=case.runtime.action_id + 1,
                        critical=False,
                        line_of_sight=lambda source, target_cell, candidate: authoritative_visible(
                            1019,
                            source,
                            target_cell,
                            candidate,
                            blocking_footprints={
                                current.id: footprint(
                                    current.position, current.physical_radius
                                )
                                for current in candidate.actors.values()
                                if current.hp > 0
                            },
                        ),
                        **case.common,
                    )
                    native_transactions.append((spell_id, transaction))
                    commit_spell_transaction(
                        case.runtime, transaction, stats_serializer=case.stats
                    )
                    case.runtime.fight = transaction.fight

                def paid_step(direction):
                    current = case.fight.actors[7].position
                    delta = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[
                        direction.upper()
                    ]
                    destination = (
                        current[0] + delta[0],
                        current[1] + delta[1],
                        current[2],
                    )
                    self.assertTrue(
                        case.player_move_prefix(7, [destination]),
                        f"Ordinary paid step {direction} failed from {current}",
                    )

                paid_step("N")
                first_box = case.fight.actors[-7]
                cast_native_spell(5589, tuple(first_box.position))
                paid_step("W")
                player_cell = tuple(case.fight.actors[7].position)
                cast_native_spell(5620, player_cell)
                undo = native_transactions[-1][1]
                self.assertEqual(
                    case.fight.actors[7].position,
                    (3, 46, -1),
                    "native Undo outcomes=%r caster_states=%r box_states=%r"
                    % (
                        undo.outcomes,
                        [
                            (entry.reference, entry.uid)
                            for entry in case.fight.actors[7].state_ledger.entries
                        ],
                        [
                            (entry.reference, entry.uid)
                            for entry in case.fight.actors[-7].state_ledger.entries
                        ],
                    ),
                )
                self.assertEqual(case.fight.actors[-7].position, (2, 46, -1))
                paid_step("S")

                for symbol in "NwESSWnWne":
                    if symbol.isupper():
                        paid_step(symbol)
                        continue
                    player_position = case.fight.actors[7].position
                    dx, dy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[
                        symbol
                    ]
                    box_cell = (
                        player_position[0] + dx,
                        player_position[1] + dy,
                        player_position[2],
                    )
                    box = next(
                        (
                            actor
                            for actor in case.fight.actors.values()
                            if actor.id < 0 and tuple(actor.position) == box_cell
                        ),
                        None,
                    )
                    self.assertIsNotNone(
                        box, f"No native box for push {symbol} at {box_cell}"
                    )
                    vacated = tuple(box.position)
                    cast_native_spell(5589, box_cell)
                    if case.fight.phase != "finished":
                        paid_step(symbol)
                        self.assertEqual(case.fight.actors[7].position, vacated)

                final = case.fight
                self.assertEqual(final.phase, "finished")
                self.assertEqual(final.winner, final.actors[7].team)
                self.assertEqual(
                    {
                        tuple(actor.position)
                        for actor in final.actors.values()
                        if actor.id < 0
                    },
                    {(1, 45, -1), (3, 46, -1)},
                )
                self.assertTrue(
                    all(
                        actor.hp == 0 for actor in final.actors.values() if actor.id < 0
                    )
                )
                receipt = getattr(final, "native_box_goal_receipt", None)
                self.assertIsNotNone(
                    receipt,
                    f"Native goal receipt missing; phase={final.phase} winner={final.winner} "
                    f"boxes={[(row.id, tuple(row.position), row.hp) for row in final.actors.values() if row.id < 0]} "
                    f"scene={final.native_encounter_scene!r} "
                    f"events={final.events[-12:]!r}",
                )
                self.assertEqual(receipt["spell_id"], 5589)
                self.assertEqual(receipt["winner"], final.winner)
                self.assertEqual(len(receipt["goal_uids"]), 2)
                self.assertEqual(
                    {tuple(row["cell"]) for row in receipt["boxes"]},
                    {(1, 45, -1), (3, 46, -1)},
                )
                self.assertEqual(
                    {row["generic_effect"] for row in receipt["native_goal_deaths"]},
                    {173367},
                )
                self.assertEqual(
                    {row["actor_id"] for row in receipt["native_goal_deaths"]},
                    {-7, -8},
                )
                terminal_events = [
                    row for row in final.events if row.get("kind") == "finished"
                ]
                self.assertEqual(len(terminal_events), 1)
                self.assertEqual(terminal_events[0]["winner"], final.winner)
        finally:
            class_initialization.level_zero_catalog.cache_clear()


if __name__ == "__main__":
    unittest.main()
