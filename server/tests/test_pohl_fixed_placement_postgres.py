"""Actual native Pohl placement and Ready; no AI turns or victory claim.

The normal owned player build is a fixture premise. The fixed position is an
explicit user-reference reconstruction, not a recovered native actor prefab.
"""
import gzip
import json
import os
import random
from copy import deepcopy
from pathlib import Path

from postgres_case import PostgresCase


class PohlFixedPlacementPostgresTests(PostgresCase):
    def test_native_room_group_and_ready_preserve_fixed_body_across_approaches(self):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            persisted_party_character,
        )
        from wakfu_server.combat_actor_snapshot import (
            initialize_fight_snapshots,
            native_actor_catalog,
        )
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_encounter_scene_policy import (
            prepare_scene,
            arena_scene,
            bind_scene,
            scene_state_declarations,
        )
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            declared_environment_blockers,
        )
        from wakfu_server.combat_fixed_actor_placement import member_positions
        from wakfu_server.combat_placement_footprints import covered_cells
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_terrain import local_arena, map_geometry
        from wakfu_server.dungeon_encounters import room_members
        from wakfu_server.dungeon_runtime_config import (
            level_selector,
            prepare_configuration,
        )
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.fight_store import create as create_fight
        from wakfu_server.combat_placement_policy import freeze
        from wakfu_server.combat_group_store import PersistentGroups

        path = Path(
            os.environ.get(
                "POHL_FIXED_CONFIGURATION",
                str(
                    Path(__file__).parent
                    / "fixtures/pohl-fixed-placement/configuration184v8.json.gz"
                ),
            )
        )
        config = json.loads(
            gzip.decompress(path.read_bytes())
            if path.suffix == ".gz"
            else path.read_text()
        )
        original = deepcopy(config)
        prepared = prepare_configuration(
            config["compiled_plan"],
            config["topology"],
            config["route"],
            version=config["version"],
            provenance=config["provenance"],
            level_policy=config.get("level_policy"),
        )
        self.assertEqual(prepared, config)
        self.assertEqual(config, original)
        room = next(row for row in config["topology"]["rooms"] if row["order"] == 2)
        compiled = next(
            row for row in config["compiled_plan"]["rooms"] if row["order"] == 2
        )
        descriptor = room["encounter_scene"]
        cells = set(map(tuple, room["cells"]))
        fixed = descriptor["fixed_actor_placements"]
        expected = tuple(fixed[0]["cell"])
        geometry = map_geometry(1369)
        blockers = declared_environment_blockers(
            descriptor.get("native_initial_glyphs", ())
        )
        section = dict(
            geometry,
            cells=tuple(cells),
            edges=tuple(
                (tuple(a), tuple(b))
                for a, b in geometry["edges"]
                if tuple(a) in cells and tuple(b) in cells
            ),
        )
        roster = [
            dict(
                ref_id=r["ref_id"],
                count=r["count"],
                min_level=r["native_min_level"],
                max_level=r["native_max_level"],
                role=r["role"],
            )
            for r in compiled["monsters"]
        ]
        catalog = native_actor_catalog()
        body = covered_cells(
            expected, catalog["npc_profiles"]["5376"]["physical_radius"], cells
        )
        self.assertEqual(len(body), 9)
        self.assertFalse(body & blockers)
        anchor = tuple(room["anchor"])
        approaches = [
            anchor,
            next(
                tuple(b)
                for a, b in geometry["edges"]
                if tuple(a) == anchor
                and tuple(b) in cells
                and tuple(b) not in blockers | body
            ),
        ]
        character, generation, deck, _, _ = persisted_party_character(
            self.store,
            native_endgame_iop_build(),
            name="fixed-pohl-native",
            map_id=1369,
            position=anchor,
        )
        instance_id = (1 << 57) + 1369
        for index, approach in enumerate(approaches):
            with self.subTest(approach=approach, reversed_members=bool(index)):
                group_id = 990184 + index
                run = dict(
                    status="active",
                    current_room=2,
                    instance_id=instance_id,
                    rooms=[dict(order=2, monsters=roster)],
                )
                members = list(
                    room_members(
                        run,
                        asset_map_id=1369,
                        anchor=anchor,
                        geometry=section,
                        group_id=group_id,
                        select_level=level_selector(config, room_order=2),
                        occupied=blockers,
                        player_slots=6,
                        actor_id_base=100000 + 16 * group_id,
                        fixed_actor_placements=fixed,
                    )
                )
                self.assertEqual(
                    next(
                        tuple(m[k] for k in ("x", "y", "z"))
                        for m in members
                        if m["ref"] == 5376
                    ),
                    expected,
                )
                registry = PersistentGroups(self.store)
                registry.register(1369, instance_id, group_id, members)
                members = list(
                    next(
                        g["members"]
                        for g in PersistentGroups(self.reopen()).available(
                            1369, instance_id
                        )
                        if g["key"][2] == group_id
                    )
                )
                self.assertEqual(
                    next(m for m in members if m["ref"] == 5376)[
                        "fixed_actor_placement"
                    ],
                    fixed[0],
                )
                if index:
                    members.reverse()
                actor = dict(
                    character,
                    instance_id=instance_id,
                    x=approach[0],
                    y=approach[1],
                    z=approach[2],
                )
                positions = member_positions(descriptor, members, room_cells=cells)
                radii = [
                    catalog["npc_profiles"][str(m["ref"])]["physical_radius"]
                    for m in members
                ]
                arena = local_arena(
                    1369,
                    actor["id"],
                    approach,
                    [tuple(m[k] for k in ("x", "y", "z")) for m in members],
                    allowed_cells=cells,
                    full_room_scope=True,
                    ordinary_npc_placement=True,
                    initial_obstacle_cells=blockers,
                    fixed_member_positions=positions,
                    member_radii=radii,
                    player_radius=catalog["default_actor_radius"],
                    variation_seed=17 + index * 66,
                )
                arena = prepare_encounter_scene(actor, members, arena)
                source = prepare_scene(
                    descriptor,
                    scope=dict(
                        map_id=1369,
                        instance_id=instance_id,
                        group_id=group_id,
                        room_order=2,
                        policy_version=config["version"],
                        route_key=config["route"]["key"],
                        evidence_hashes=config["evidence_hashes"],
                    ),
                    room_cells=cells,
                )
                arena = arena_scene(source, arena, actor, members)
                fight_id = create_fight(
                    self.store, actor["account_id"], generation, actor["id"]
                )
                arena = freeze(
                    self.store,
                    account_id=actor["account_id"],
                    generation=generation,
                    character_id=actor["id"],
                    fight_id=fight_id,
                    map_id=1369,
                    instance_id=instance_id,
                    selected_arena=arena,
                    seeds={
                        0: [approach],
                        1: [tuple(m[k] for k in ("x", "y", "z")) for m in members],
                    },
                )
                resources = combat_resources(actor)
                fight, packets = create_placement(
                    actor,
                    members,
                    arena,
                    fight_id=fight_id,
                    player_ap=resources["ap"],
                    player_mp=resources["mp"],
                    player_wp=resources["wp"],
                    player_initiative=resources["initiative"],
                    terrain_effect_id=arena["terrain_effect_id"],
                    terrain_instance_id=group_id,
                )
                monsters = {m["id"]: m for m in members}
                bind_scene(fight, arena, monsters)
                boss = next(fight.actors[m["id"]] for m in members if m["ref"] == 5376)
                self.assertEqual(boss.position, expected)
                self.assertEqual(boss.direction, 3)
                for other in fight.actors.values():
                    if other.id != boss.id:
                        self.assertFalse(
                            body
                            & covered_cells(
                                other.position, other.physical_radius or 0, cells
                            )
                        )
                self.assertTrue(packets)
                prepare_environment_glyphs(fight, arena, group_id)
                initialize_fight_snapshots(
                    fight,
                    characters={actor["id"]: actor},
                    monsters=monsters,
                    wp_resources={
                        actor["id"]: (resources["wp"], resources["wp"]),
                        **{
                            i: (m["wp"], m.get("max_wp", m["wp"]))
                            for i, m in monsters.items()
                        },
                    },
                    running_effects={i: () for i in fight.actors},
                    initial_effect_uid=1,
                    scene_state_declarations=scene_state_declarations(fight, monsters),
                )
                fight.ready(actor["account_id"])
                fight, _ = prepare_server_initialization(
                    actor,
                    monsters,
                    fight,
                    actor["account_id"],
                    deck,
                    action_id=1,
                    rng=random.Random(17 + index * 66),
                    fight_start=True,
                    player_characters={actor["id"]: actor},
                    deck_blobs={actor["id"]: deck},
                )
                self.assertEqual(fight.phase, "active")
                self.assertEqual(fight.actors[boss.id].position, expected)
                self.assertEqual(fight.actors[boss.id].direction, 3)
