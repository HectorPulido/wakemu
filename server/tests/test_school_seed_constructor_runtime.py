"""Native School seed constructor on the reviewed courtyard floor."""
import json
import struct
from pathlib import Path
import unittest
from unittest.mock import patch

import wakfu_server.combat_morph_handler as morph_handler


ROOT = Path(__file__).parents[1]
ARCHETYPES = ROOT.parent / ".runtime/quest-archetypes"
PROFILE_FILE = ARCHETYPES / "school-player-morph-profiles.json"
LAYOUT_FILE = ARCHETYPES / "school-seed-reviewed-native-layout.json"
CONFIG_FILE = ARCHETYPES / "huppermage-seed-1018-draft.configuration.json"


class SchoolSeedConstructorRuntimeTests(unittest.TestCase):
    def test_original_seed_constructor_spawns_native_point_actors_on_reviewed_floor(
        self,
    ):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from jondo_native_support_probe import build_fixture
        from wakfu_server.combat_encounter_scene_policy import prepare_scene
        from wakfu_server.combat_native_area_metadata import native_point_area_metadata
        from wakfu_server.combat_encounter_roles import role_assignment

        layout = json.loads(LAYOUT_FILE.read_text())
        config = json.loads(CONFIG_FILE.read_text())
        room = config["topology"]["rooms"][0]
        room_cells = [tuple(cell) for cell in layout["cells"]]
        self.assertEqual(
            config["compiled_plan"]["rooms"][0]["monsters"][0]["ref_id"], 3907
        )
        self.assertEqual(
            room["encounter_scene"]["fixed_actor_placements"][0]["cell"],
            list(layout["seed"]),
        )
        self.assertEqual(len(room_cells), 259)

        descriptor = room["encounter_scene"]
        source_scope = dict(
            map_id=1018,
            instance_id=0,
            group_id=1,
            room_order=1,
            policy_version=1,
            route_key="huppermage-seed-1018",
            evidence_hashes=config["evidence_hashes"],
        )
        scene = prepare_scene(descriptor, scope=source_scope, room_cells=room_cells)
        profile_source = json.loads(PROFILE_FILE.read_text())
        profile = profile_source["profiles"]["3907"]
        lifecycle = []

        def observe(stage, fight, monsters):
            lifecycle.append(
                (
                    stage,
                    fight.actors[-7].direction,
                    tuple(fight.actors[-7].position),
                    tuple(
                        sorted(
                            (identity, monsters[identity]["ref"])
                            for identity in monsters
                            if identity in fight.actors
                        )
                    ),
                )
            )

        with patch.object(
            morph_handler, "native_morph_profiles", return_value={"3907": profile}
        ), original_bootstrap_publication():
            case = build_fixture(
                3907,
                1,
                map_id=1018,
                player_position=tuple(layout["hero"]),
                npc_position=tuple(layout["seed"]),
                allowed_cells=room_cells,
                full_room_scope=True,
                fixed_member_positions={0: tuple(layout["seed"])},
                encounter_scene_record=scene,
                lifecycle_observer=observe,
                role_record=role_assignment(1018, (3907,)).record(),
            )

        fight = case.fight
        seed = fight.actors[-7]
        self.assertEqual(tuple(seed.position), tuple(layout["seed"]))
        player = fight.actors[7]
        self.assertIn(4072, {entry.reference for entry in player.state_ledger.entries})
        morph = fight.native_morph_spellbooks[7]
        self.assertEqual(morph["profile_id"], 3907)
        self.assertEqual(morph["levels"], {5599: 1})
        self.assertFalse(morph["own_level"])
        self.assertEqual(morph["removed_raw_uids"], set())
        self.assertEqual(
            [(stage, direction) for stage, direction, _, _ in lifecycle],
            [
                ("create_placement", layout["seed_direction"]),
                ("initialize_fight_snapshots", layout["seed_direction"]),
                ("before_fight_start_events", layout["seed_direction"]),
                ("prepare_server_initialization", layout["seed_direction"]),
            ],
            f"Seed direction changed during setup: {lifecycle!r}",
        )
        self.assertIn(4071, {entry.reference for entry in seed.state_ledger.entries})
        registrations = fight.native_summon_registrations
        summoned = [
            fight.actors[identity]
            for identity in registrations
            if identity in fight.actors
            and fight.actors[identity].native_summon_source.get("ref") in (3908, 3909)
        ]
        self.assertEqual(len(fight.actors), 13)
        self.assertEqual(len(summoned), 11)
        self.assertEqual(
            {actor.native_summon_source["ref"] for actor in summoned},
            {3908, 3909},
        )
        self.assertEqual(
            {
                tuple(actor.position)
                for actor in summoned
                if actor.native_summon_source["ref"] == 3908
            },
            {tuple(cell) for cell in layout["native_red_points"]},
        )
        self.assertEqual(
            {
                tuple(actor.position)
                for actor in summoned
                if actor.native_summon_source["ref"] == 3909
            },
            {tuple(cell) for cell in layout["native_blue_points"]},
        )

        areas = native_point_area_metadata()
        for area_id, offsets, expected in (
            (173588, layout["native_red_points"], 7),
            (173589, layout["native_blue_points"], 4),
        ):
            record = areas[str(area_id)]
            self.assertEqual(len(record["native_area_points"]), expected)
            self.assertEqual(len(offsets), expected)

        # Reach the actual seed through paid client movement and its ordinary
        # area callback provider; no actor coordinates or HP are injected.
        target = seed
        movement_steps = 0
        while True:
            fight = case.fight
            player = fight.actors[player.id]
            target = fight.actors[target.id]
            if tuple(player.position) in {
                cell
                for cell in fight.walkable
                if cell[2] == target.position[2]
                and abs(cell[0] - target.position[0])
                + abs(cell[1] - target.position[1])
                == 1
            }:
                break
            if movement_steps >= 128:
                self.fail(
                    "Player did not reach the original seed within 128 movement/turn operations: "
                    f"pos={player.position} mp={player.mp} hp={player.hp} "
                    f"phase={fight.phase} current={None if fight.current is None else fight.current.id}"
                )
            if case.fight.phase != "active":
                self.fail(f"Fight ended before seed collection: {case.fight.phase}")
            if case.fight.current.id != player.id:
                case.advance()
                movement_steps += 1
                continue
            if case.fight.actors[player.id].mp <= 0:
                case.advance()
                movement_steps += 1
                continue
            path = case.path_to(
                player.id,
                lambda cell: cell[2] == target.position[2]
                and abs(cell[0] - target.position[0])
                + abs(cell[1] - target.position[1])
                == 1,
            )
            if not path or not case.player_move_prefix(player.id, path):
                self.fail(
                    "Ordinary paid movement could not advance toward the original seed: "
                    f"actor={player.id} pos={case.fight.actors[player.id].position} "
                    f"mp={case.fight.actors[player.id].mp} current="
                    f"{None if case.fight.current is None else case.fight.current.id} "
                    f"path={path!r} steps={movement_steps}"
                )
            movement_steps += 1

        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        fight = case.fight
        player = fight.actors[player.id]
        seed = fight.actors[seed.id]
        seed_hp_before_cast = seed.hp
        native_areas = tuple(fight.native_effect_areas.values())
        self.assertTrue(
            {
                (173602, 1022),
                (173604, 1023),
                (173606, 1024),
                (173608, 1025),
            }.issubset(
                {(row["effect_reference"], row["reference"]) for row in native_areas}
            ),
            f"Movement did not execute all native seed area creators: "
            f"{[(row['effect_reference'], row['reference']) for row in native_areas]!r}",
        )
        body = struct.pack(">qqiih", player.id, 5599, *seed.position)
        try:
            tx = prepare_server_spell(
                body,
                case.characters[player.id],
                case.monsters,
                fight,
                player.owner_id,
                case.decks[player.id],
                action_id=case.runtime.action_id + 1,
                critical=False,
                line_of_sight=lambda source_cell, target_cell, candidate: authoritative_visible(
                    case.map_id,
                    source_cell,
                    target_cell,
                    candidate,
                    blocking_footprints={
                        actor.id: footprint(actor.position, actor.physical_radius)
                        for actor in candidate.actors.values()
                        if actor.hp > 0
                    },
                ),
                **case.common,
            )
        except ValueError as error:
            self.fail(
                f"Native seed collection cast failed: {error}; player={player.position} "
                f"seed={seed.position} current={None if fight.current is None else fight.current.id} "
                f"phase={fight.phase} morph={fight.native_morph_spellbooks.get(player.id)} "
                f"steps={movement_steps}"
            )
        commit_spell_transaction(case.runtime, tx, stats_serializer=case.stats)
        killed_seed = tx.fight.actors[seed.id]
        self.assertEqual(killed_seed.hp, 0)
        self.assertTrue(registered_ordinary_death(tx.fight, killed_seed))
        self.assertTrue(
            any(
                event.get("kind") == "kill_hp_minimum_update"
                and event.get("generic_effect") == 173894
                and event.get("source_id") == player.id
                and event.get("target_id") == seed.id
                for event in tx.fight.events
            )
        )
        self.assertEqual(
            tx.fight.phase,
            "finished",
            f"Correct seed died but fight did not reach terminal: winner={tx.fight.winner}; "
            f"alive={[(actor.id, actor.team, actor.hp, getattr(actor, 'native_summon_source', {}).get('ref')) for actor in tx.fight.actors.values() if actor.hp > 0]}; "
            f"events={[event.get('kind') for event in tx.fight.events[-30:]]!r}",
        )
        self.assertEqual(tx.fight.winner, player.team)
        alive_enemies = [
            actor
            for actor in tx.fight.actors.values()
            if actor.team != player.team and tx.fight._in_play(actor)
        ]
        self.assertFalse(
            alive_enemies,
            f"Enemy actors survived native seed owner-death cleanup: "
            f"{[(actor.id, getattr(actor, 'native_summon_source', {}).get('ref')) for actor in alive_enemies]!r}",
        )
        self.assertEqual(fight.actors[seed.id].hp, seed_hp_before_cast)
        self.assertEqual(fight.phase, "active")
        self.assertTrue(any(row["kind"] == "player_movement" for row in case.payments))


if __name__ == "__main__":
    unittest.main()
