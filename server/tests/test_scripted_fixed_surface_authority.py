"""A complete source-qualified constructor keeps native deck scope and costs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_arena_selection import full_room_encounter
from wakfu_server.combat_encounter_scene_policy import prepare_scene, bind_scene
from wakfu_server.combat_fixed_actor_placement import member_positions
from wakfu_server.combat_scripted_fixed_surfaces import (
    complete_fixed_roster,
    npc_room_cells,
)
from wakfu_server.combat_sn_path import NativeSnColumns
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_walk_surface_policy import native_npc_walk_blocked_cells

PROFILE = (
    Path(__file__).resolve().parents[1]
    / "wakfu_server/maps/owned_story_profiles/zinit-reef-980.configuration.v2.json"
)
SHA = "a" * 64


class ScriptedFixedSurfaceAuthorityTests(unittest.TestCase):
    def scene(self, order=1):
        config = json.loads(PROFILE.read_text())
        room = config["topology"]["rooms"][order - 1]
        members = [
            dict(id=100 + i, ref=row["reference"])
            for i, row in enumerate(room["encounter_scene"]["fixed_actor_placements"])
        ]
        scene = prepare_scene(
            room["encounter_scene"],
            scope=dict(
                map_id=980,
                instance_id=939,
                group_id=1,
                room_order=order,
                policy_version=1,
                route_key=config["route"]["key"],
                evidence_hashes={},
            ),
            room_cells=room["cells"],
        )
        return config, room, members, scene

    def test_all_three_real_rosters_retain_native_floor_and_source_anchors(self):
        for order, count in ((1, 3), (2, 5), (3, 6)):
            with self.subTest(order=order):
                config, room, members, scene = self.scene(order)
                cells = set(map(tuple, room["cells"]))
                self.assertEqual(len(cells), 52)
                self.assertEqual(len(members), count)
                self.assertTrue(complete_fixed_roster(scene, members))
                fixed = member_positions(scene["descriptor"], members, room_cells=cells)
                origins = [
                    (1, -2, 0),
                    (1, -1, 0),
                    (2, -2, 0),
                    (2, -1, 0),
                    (3, -2, 0),
                    (3, -1, 0),
                ][:count]
                geometry_edges = [
                    edge
                    for edge in config["topology"]["exploration_geometry"]["edges"]
                    if tuple(edge[0]) in cells and tuple(edge[1]) in cells
                ]
                geometry = dict(map_id=980, cells=room["cells"], edges=geometry_edges)
                kwargs = dict(
                    member_radii=(0,) * count,
                    player_radius=0,
                    player_slots=6,
                    placement_ground_cells=cells,
                    fixed_member_positions=fixed,
                )
                with self.assertRaises(ValueError):
                    full_room_encounter(
                        geometry,
                        (1, -3, 0),
                        origins,
                        member_point_cells=set(),
                        **kwargs
                    )
                result = full_room_encounter(geometry, (1, -3, 0), origins, **kwargs)
                self.assertEqual(set(result["cells"]), cells)
                self.assertEqual(
                    [destination for _, destination in result["participant_positions"]],
                    [fixed[i] for i in range(count)],
                )
                self.assertFalse(
                    set(fixed.values()) & set(result["party_reserved_cells"])
                )
                partial = deepcopy(scene["descriptor"])
                partial["fixed_actor_placements"].pop()
                partial = prepare_scene(
                    partial, scope=scene["scope"], room_cells=room["cells"]
                )
                self.assertFalse(complete_fixed_roster(partial, members))
                tampered = deepcopy(scene)
                tampered["descriptor"]["fixed_actor_placements"][0]["cell"][0] += 1
                with self.assertRaisesRegex(ValueError, "source changed"):
                    complete_fixed_roster(tampered, members)
        self.assertFalse(complete_fixed_roster(None, []))

    def test_bound_initial_npc_paid_walk_and_planner_share_scoped_authority(self):
        _, room, members, scene = self.scene()
        cells = set(map(tuple, room["cells"]))
        fixed = member_positions(scene["descriptor"], members, room_cells=cells)
        actors = []
        for i, member in enumerate(members):
            actor = Actor(member["id"], 0, fixed[i], 100, 6, 3, 10, 1)
            actor.physical_radius = 0
            actor.native_death_status = {"actor_kind": "bje"}
            actor.native_world_properties = actor.native_fight_properties = frozenset()
            actors.append(actor)
        player = Actor(999, 1, (1, -3, 0), 100, 6, 3, 1, 1, 999, True)
        player.physical_radius = 0
        edges = {
            (c, (c[0] + dx, c[1] + dy, 0))
            for c in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (c[0] + dx, c[1] + dy, 0) in cells
        }
        fight = Fight(1, [*actors, player], cells, {0: cells, 1: cells}, edges)
        fight.native_qi_surface_provenance = dict(map_id=980, source_sha256=SHA)
        fight.native_map_id = 980
        from wakfu_server.combat_encounter_roles import _ordinary

        fight.native_encounter_roles = _ordinary(
            980, [member["ref"] for member in members]
        ).record()
        bind_scene(
            fight, {"native_encounter_scene": scene}, {m["id"]: m for m in members}
        )
        columns = NativeSnColumns(
            dict(
                schema="native-Sn-Vy-columns-v1",
                map_id=980,
                source_sha256=SHA,
                chunks=[
                    dict(
                        x=-5,
                        y=-5,
                        width=18,
                        height=18,
                        columns=[[x, y, [[0, 0, 0, 3, 0, False]]] for x, y, z in cells],
                    )
                ],
            ),
            map_id=980,
            source_sha256=SHA,
        )
        actor = actors[0]
        target = (3, -4, 0)
        fight.phase, fight.order, fight.turn_index = "active", [actor.id], 0
        with patch.object(
            NativeSnColumns, "from_published", return_value=columns
        ), patch("wakfu_server.combat_ground_support.supported", return_value=True):
            self.assertEqual(npc_room_cells(fight, actor), cells)
            self.assertEqual(
                native_npc_walk_blocked_cells(fight, actor, {target}), set()
            )
            result = fight.server_move(actor.id, [target])
            self.assertEqual((actor.position, actor.mp, result["cost"]), (target, 2, 1))
            saved = fight.native_encounter_scene
            fight.native_encounter_scene = None
            self.assertEqual(
                native_npc_walk_blocked_cells(fight, actor, {target}), {target}
            )
            before = (actor.position, actor.mp)
            with self.assertRaisesRegex(ValueError, "fight-sterile"):
                fight.server_move(actor.id, [(3, -3, 0)])
            self.assertEqual((actor.position, actor.mp), before)
            fight.native_encounter_scene = saved
            unbound = Actor(2000, 0, (3, -3, 0), 100, 6, 3, 10, 1)
            self.assertFalse(npc_room_cells(fight, unbound))
            self.assertFalse(npc_room_cells(fight, player))
            with patch(
                "wakfu_server.combat_ground_support.escape_prefix_cells",
                return_value=frozenset(),
            ), patch(
                "wakfu_server.combat_ground_support.supported", return_value=False
            ):
                self.assertEqual(
                    native_npc_walk_blocked_cells(fight, actor, {(3, -3, 0)}),
                    {(3, -3, 0)},
                )

    def test_public_voyage_admission_composes_fixed_originals_and_friendly_helper(self):
        from wakfu_server.combat_mission_allies import VOYAGE_POLICY, admit
        from wakfu_server.combat_encounter_scene_helpers import (
            prepare_scene_roster,
            adapt_helper_placement,
            apply_helper_constructor_roles,
        )
        from wakfu_server.combat_encounter_roles import role_assignment
        from wakfu_server.combat_terrain import prepare_terrain, local_arena
        from wakfu_server.combat_encounter_scene_policy import bind_scene
        from wakfu_server.combat_sn_path import NativeSnColumns
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_fixed_actor_placement import member_positions
        from wakfu_server.combat_scripted_fixed_surfaces import (
            complete_fixed_roster,
            npc_room_cells,
        )

        config = json.loads(PROFILE.read_text())
        room = config["topology"]["rooms"][0]
        fixed_scene = prepare_scene(
            room["encounter_scene"],
            scope=dict(
                map_id=980,
                instance_id=144115188075855939,
                group_id=288230376151894656,
                room_order=1,
                policy_version=1,
                route_key=config["route"]["key"],
                evidence_hashes={},
            ),
            room_cells=room["cells"],
        )
        char = dict(
            id=369,
            account_id=293,
            breed=8,
            level=15,
            hp=60,
            max_hp=60,
            map_id=980,
            instance_id=144115188075855939,
            x=1,
            y=-3,
            z=0,
            active_build_index=0,
        )
        original_ids = (-1125900078416384, -1125900078416385, -1125900078416386)
        from wakfu_server.monsters import owned_instance

        originals = tuple(
            owned_instance(
                3771,
                13,
                identity,
                map_id=980,
                instance_id=char["instance_id"],
                x=x,
                y=y,
                z=0,
                team=1,
            )
            for identity, (x, y) in zip(original_ids, ((1, -2), (1, -1), (2, -2)))
        )
        admission = admit(char, originals, policy=VOYAGE_POLICY, room=1)
        cells = set(map(tuple, room["cells"]))
        self.assertEqual(len(cells), 52)
        store = SimpleNamespace(connection=lambda: nullcontext(None))
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        native_actors = native_actor_catalog()
        with patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=900000
        ):
            members, manifest = prepare_scene_roster(
                store, char, originals, mission_allies=admission
            )
            self.assertEqual(
                [member["ref"] for member in members], [3771, 3771, 3771, 3781]
            )
            self.assertTrue(
                complete_fixed_roster(fixed_scene, members, helper_manifest=manifest)
            )
            self.assertFalse(complete_fixed_roster(fixed_scene, members))
            prepared = prepare_terrain(980)
            provenance = prepared.provenance
            fixed = member_positions(
                fixed_scene["descriptor"], members, room_cells=cells
            )
            radii = tuple(
                native_actors["npc_profiles"][str(member["ref"])]["physical_radius"]
                for member in members
            )
            arena = local_arena(
                980,
                char["instance_id"],
                (char["x"], char["y"], char["z"]),
                [(member["x"], member["y"], member["z"]) for member in members],
                prepared_terrain=prepared,
                allowed_cells=room["cells"],
                full_room_scope=True,
                fixed_member_positions=fixed,
                member_radii=radii,
                player_radius=native_actors["default_actor_radius"],
                ordinary_npc_placement=not complete_fixed_roster(
                    fixed_scene, members, helper_manifest=manifest
                ),
            )
            arena["native_encounter_scene_helpers"] = manifest
            arena = adapt_helper_placement(char, members, arena)

        self.assertEqual(set(arena["validated_cells"]), cells)
        self.assertEqual(
            [tuple(pair[1]) for pair in arena["participant_positions"][:3]],
            [
                tuple(row["cell"])
                for row in fixed_scene["descriptor"]["fixed_actor_placements"]
            ],
        )
        role_record = role_assignment(980, [row["ref"] for row in members]).record()
        actual_positions = {
            member["id"]: tuple(pair[1])
            for member, pair in zip(members, arena["participant_positions"])
        }
        player = Actor(
            char["id"], 0, (1, -3, 0), 100, 6, 3, 10, 15, char["account_id"], True
        )
        actors = []
        for member in members:
            team = 0 if member["ref"] == 3781 else 1
            actor = Actor(
                member["id"],
                team,
                actual_positions[member["id"]],
                100,
                6,
                3,
                1,
                member["level"],
            )
            actor.physical_radius = 0
            actor.native_death_status = {"actor_kind": "bje"}
            actor.native_world_properties = actor.native_fight_properties = frozenset()
            actors.append(actor)
        fight = Fight(
            804,
            [player, *actors],
            cells,
            arena["placement_cells"],
            arena["valid_edges"],
        )
        fight.native_map_id = 980
        fight.native_encounter_roles = role_record
        fight.native_scene_helper_manifest = manifest
        fight.native_qi_surface_provenance = provenance
        apply_helper_constructor_roles(
            char,
            members,
            {actor.id: actor for actor in actors},
            arena,
            fight_id=fight.id,
            player_team=0,
            npc_team=1,
        )
        bind_scene(
            fight,
            {"native_encounter_scene": fixed_scene},
            {member["id"]: member for member in members},
        )
        self.assertEqual(npc_room_cells(fight, actors[0]), frozenset(cells))

        native_columns = NativeSnColumns.from_published(980)
        fight.phase, fight.order, fight.turn_index = "active", [actors[0].id], 0
        walk_target = (2, -3, 0)
        result = fight.server_move(actors[0].id, [walk_target])
        self.assertEqual((actors[0].position, result["cost"]), (walk_target, 1))
