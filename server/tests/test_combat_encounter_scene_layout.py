"""Reconstructed fight placement retains world origins and durable policy."""
import copy
import json
import struct
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.pq import TransactionStatus
from wakfu_server.combat_encounter_scene_layout import (
    prepare_encounter_scene,
    resolve_layout,
    scene_player_position,
)


class ScenePlacementTests(unittest.TestCase):
    def setUp(self):
        from encounter_role_fixture import role_database_fixture

        self.enterContext(role_database_fixture())
        self.character = dict(id=7, map_id=99, instance_id=71, x=20, y=20, z=0)
        self.members = [
            dict(id=-2, ref=900, map_id=99, instance_id=71, x=30, y=20, z=0)
        ]
        self.cells = {(x, 0, 0) for x in range(4)}
        self.layout = dict(
            map_id=99,
            policy="fixture.explicit-native-room.v1",
            authority="fixture",
            observation_url="fixture",
            original_world_coordinates=False,
            source=(0, 0, 0),
            caster_cell=(0, 0, 0),
            anchor=(3, 0, 0),
            cells=self.cells,
            edges={
                ((x, 0, 0), (y, 0, 0))
                for x in range(4)
                for y in range(4)
                if abs(x - y) == 1
            },
            glyph_cells=(),
            party_placement_cells=((2, 0, 0), (3, 0, 0)),
            boss_footprint=((0, 0, 0),),
            boss_direction=1,
        )
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
                return_value=object(),
            )
        )
        self.patches.enter_context(
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
                return_value={"fixture": True},
            )
        )
        self.patches.enter_context(
            patch(
                "wakfu_server.combat_qi_surface_selection.native_surface_indices",
                side_effect=lambda surfaces, cells: {(x, y): 0 for x, y, z in cells},
            )
        )

    def selected(self):
        return prepare_encounter_scene(
            self.character,
            self.members,
            dict(map_id=99, instance_id=123),
            layout=self.layout,
        )

    def test_normal_encounter_preserves_arena_without_loading_reconstruction(self):
        from wakfu_server import combat_encounter_roles as roles

        arena = dict(
            map_id=99,
            cell_masks=b"same-masks",
            wire=b"same-wire",
            placement_cells={0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        prepared = prepare_encounter_scene(self.character, self.members, arena)
        self.assertNotIn("native_encounter_roles", arena)
        for key in arena:
            self.assertIs(prepared[key], arena[key])
        record = prepared["native_encounter_roles"]
        scoped = roles.roles_from_record(record, map_id=99, monster_references=[900])
        self.assertEqual(
            (scoped.policy, scoped.player_team, scoped.npc_team),
            (roles.ORDINARY_POLICY, 0, 1),
        )
        self.assertIs(
            prepare_encounter_scene(self.character, self.members, prepared), prepared
        )
        with self.assertRaisesRegex(ValueError, "another map"):
            prepare_encounter_scene(
                dict(self.character, map_id=100), self.members, prepared
            )
        with self.assertRaisesRegex(ValueError, "another initial roster"):
            prepare_encounter_scene(
                self.character, [dict(self.members[0], ref=901)], prepared
            )
        with patch.object(
            roles, "role_assignment", side_effect=AssertionError("NPC-free role lookup")
        ):
            self.assertIs(prepare_encounter_scene(self.character, [], arena), arena)
        self.assertIsNone(
            resolve_layout(
                self.character,
                self.members,
                geometry_loader=lambda _: self.fail("Unexpected geometry load"),
            )
        )

    def test_reconstructed_singleton_cannot_be_bypassed_by_roster_order(self):
        character = dict(self.character, map_id=1332)
        ordinary, boss = {"ref": 900}, {"ref": 5306}
        for members in ([ordinary, boss], [boss, ordinary]):
            with self.subTest(members=members), self.assertRaisesRegex(
                ValueError, "singleton"
            ):
                resolve_layout(
                    character,
                    members,
                    geometry_loader=lambda _: self.fail("Unexpected geometry load"),
                )
        # The same references on an unrelated map retain ordinary placement.
        self.assertIsNone(
            resolve_layout(
                self.character,
                [ordinary, boss],
                geometry_loader=lambda _: self.fail("Unexpected geometry load"),
            )
        )

    def test_explicit_nox_roles_reencode_native_masks_and_survive_retry(self):
        from wakfu_server.combat_wire import arena
        from wakfu_server.combat_placement_policy import freeze

        character = dict(self.character, map_id=1435, x=3, y=0)
        members = [dict(self.members[0], ref=5664, map_id=1435, x=0, y=0)]
        selected = arena(
            1435,
            123,
            sorted(self.cells),
            {0: {(3, 0, 0)}, 1: {(0, 0, 0)}},
            surface_indices={(x, y): 5 for x, y, z in self.cells},
            obstacle_values=[(7, 1)],
        )
        selected.update(
            validated_cells=self.cells,
            valid_edges=self.layout["edges"],
            placement_cells={0: {(3, 0, 0)}, 1: {(0, 0, 0)}},
        )
        before = copy.deepcopy((character, members, selected))
        # Exercise role encoding on this explicit selected arena; full native
        # Nox scene reconstruction has separate production-binding coverage.
        with patch(
            "wakfu_server.combat_encounter_scene_layout.resolve_layout",
            return_value=None,
        ):
            prepared = prepare_encounter_scene(character, members, selected)
        self.assertEqual(
            prepared["native_encounter_roles"]["policy"], "wakemu-nox-player1-npc0-v1"
        )
        self.assertEqual(prepared["placement_cells"], {1: {(3, 0, 0)}, 0: {(0, 0, 0)}})
        self.assertEqual(prepared["cell_flags"][0], 0)
        self.assertEqual(prepared["cell_flags"][3], 1)
        self.assertEqual(prepared["cell_masks"], selected["cell_masks"])
        self.assertEqual(prepared["team_values"], selected["team_values"])
        self.assertEqual((character, members, selected), before)
        db = PlacementDB()
        kwargs = dict(
            account_id=1,
            generation=1,
            character_id=7,
            fight_id=12,
            map_id=1435,
            instance_id=71,
            selected_arena=prepared,
            seeds={0: [(3, 0, 0)], 1: [(0, 0, 0)]},
            db=db,
        )
        store = SimpleNamespace(lock_character=lambda *args: None)
        with patch("wakfu_server.combat_border_policy.choose", return_value=None):
            first = freeze(store, **kwargs)
            db.layout = json.loads(json.dumps(db.layout))
            prepared["native_encounter_roles"] = {}
            second = freeze(store, **kwargs)
        self.assertEqual(
            second["native_encounter_roles"], first["native_encounter_roles"]
        )
        self.assertIn((3, 0, 0), second["placement_cells"][1])
        self.assertIn((0, 0, 0), second["placement_cells"][0])
        self.assertEqual(db.inserts, 1)

    def test_reconstructed_wire_and_actor_position_keep_world_sources_unchanged(self):
        before = copy.deepcopy((self.character, self.members, self.layout))
        selected = self.selected()
        self.assertEqual(scene_player_position(self.character, selected), (3, 0, 0))
        self.assertEqual(selected["participant_positions"], [((30, 20, 0), (0, 0, 0))])
        self.assertEqual(selected["validated_cells"], self.cells)
        self.assertEqual(selected["native_encounter_scene_layout"]["source"], [0, 0, 0])
        self.assertEqual(selected["native_encounter_scene_layout"]["boss_direction"], 1)
        self.assertEqual((self.character, self.members, self.layout), before)
        with self.assertRaises(ValueError):
            scene_player_position(dict(self.character, x=21), selected)

    def test_invalid_reconstruction_cannot_publish_overlapping_placement(self):
        invalid = dict(self.layout, party_placement_cells=((0, 0, 0), (3, 0, 0)))
        with self.assertRaises(ValueError):
            prepare_encounter_scene(
                self.character,
                self.members,
                dict(map_id=99, instance_id=123),
                layout=invalid,
            )

    def test_declared_component_border_preserves_disconnected_platforms_on_retry(self):
        from wakfu_server.combat_arena_selection import cardinal_border_cells
        from wakfu_server.combat_battleground_border import (
            DECLARED_COMPONENT_POLICY,
            validate_border_component,
        )
        from wakfu_server.combat_placement_policy import freeze
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot

        board = {(x, y, 0) for x in range(5) for y in range(5)}
        island = (10, 10, 0)
        cells = board | {island}
        edges = {
            (a, b)
            for a in board
            for b in board
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        layout = dict(
            self.layout,
            cells=cells,
            edges=edges,
            source=(1, 1, 0),
            caster_cell=(1, 1, 0),
            boss_footprint=((1, 1, 0),),
            anchor=(2, 2, 0),
            party_placement_cells=((2, 1, 0), (2, 2, 0)),
            terrain_effect_id=909,
            native_border_policy=DECLARED_COMPONENT_POLICY,
            native_border_scope_cells=board,
            native_border_cells=cardinal_border_cells(board),
        )
        selected = prepare_encounter_scene(
            self.character,
            self.members,
            dict(map_id=99, instance_id=123),
            layout=layout,
        )
        self.assertEqual(validate_border_component(cells, edges, {island}), {island})
        for invalid in (board - {(0, 0, 0)}, cells):
            with self.assertRaises(ValueError):
                validate_border_component(cells, edges, invalid)
        db = PlacementDB()
        kwargs = dict(
            account_id=1,
            generation=1,
            character_id=7,
            fight_id=12,
            map_id=99,
            instance_id=71,
            selected_arena=selected,
            seeds={0: [(20, 20, 0)], 1: [(30, 20, 0)]},
            db=db,
        )
        store = SimpleNamespace(lock_character=lambda *args: None)
        first = freeze(store, **kwargs)
        db.layout = json.loads(json.dumps(db.layout))
        second = freeze(store, **kwargs)
        self.assertEqual({tuple(c) for c in second["native_border_scope_cells"]}, board)
        self.assertEqual(second["validated_cells"], cells)
        self.assertEqual(second["valid_edges"], edges)
        self.assertEqual(second["native_border_cells"], first["native_border_cells"])
        qi = NativeQISnapshot(second)
        self.assertTrue(qi.P(0, 0))
        self.assertFalse(qi.P(*island[:2]))

    def test_initial_glyph_authority_and_positions_survive_durable_retry(self):
        from wakfu_server.combat_placement_policy import freeze

        fields = dict(
            native_initial_glyphs=[dict(reference=1837, cell=[1, 0, 0], level=0)],
            native_initial_glyph_policy="fixture.native-point-glyph.v1",
            native_initial_glyph_authority="fixture published prototype",
            native_initial_glyph_source_url="fixture://observed-scene",
        )
        layout = dict(self.layout, **fields)
        selected = prepare_encounter_scene(
            self.character,
            self.members,
            dict(map_id=99, instance_id=123),
            layout=layout,
        )
        db = PlacementDB()
        kwargs = dict(
            account_id=1,
            generation=1,
            character_id=7,
            fight_id=12,
            map_id=99,
            instance_id=71,
            selected_arena=selected,
            seeds={0: [(20, 20, 0)], 1: [(30, 20, 0)]},
            db=db,
        )
        store = SimpleNamespace(lock_character=lambda *args: None)
        with patch("wakfu_server.combat_border_policy.choose", return_value=None):
            freeze(store, **kwargs)
            db.layout = json.loads(json.dumps(db.layout))
            selected["native_initial_glyphs"] = []
            restored = freeze(store, **kwargs)
        for key, value in fields.items():
            self.assertEqual(restored[key], value)
        for changed in (
            {"native_initial_glyph_authority": ""},
            {"native_initial_glyphs": [dict(reference=1837, cell=[99, 0, 0])]},
        ):
            with self.assertRaises(ValueError):
                prepare_encounter_scene(
                    self.character,
                    self.members,
                    dict(map_id=99, instance_id=123),
                    layout=dict(layout, **changed),
                )

    def test_durable_retry_reuses_exact_scene_and_does_not_regenerate_slots(self):
        from wakfu_server.combat_placement_policy import freeze

        db = PlacementDB()
        store = SimpleNamespace(lock_character=lambda *args: None)
        kwargs = dict(
            account_id=1,
            generation=1,
            character_id=7,
            fight_id=12,
            map_id=99,
            instance_id=71,
            selected_arena=self.selected(),
            seeds={0: [(20, 20, 0)], 1: [(30, 20, 0)]},
            db=db,
        )
        with patch(
            "wakfu_server.combat_border_policy.choose", return_value=None
        ), patch(
            "wakfu_server.combat_placement_policy.generate",
            side_effect=AssertionError("Explicit scene must preserve its slots"),
        ):
            first = freeze(store, **kwargs)
            # Simulate a JSONB read on a retry, independently of caller objects.
            db.layout = json.loads(json.dumps(db.layout))
            changed = copy.deepcopy(kwargs["selected_arena"])
            changed["native_encounter_scene_layout"]["anchor"] = [99, 99, 0]
            second = freeze(store, **dict(kwargs, selected_arena=changed))
        self.assertEqual(first["placement_cells"], second["placement_cells"])
        self.assertEqual(second["placement_cells"][0], {(2, 0, 0), (3, 0, 0)})
        self.assertEqual(scene_player_position(self.character, second), (3, 0, 0))
        self.assertEqual(db.inserts, 1)

    def test_real_bootstrap_uses_scene_positions_and_facing_before_serialization(self):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.monsters import owned_instance

        character = dict(
            self.character,
            map_id=1134,
            breed=2,
            level=1,
            hp=60,
            max_hp=60,
            account_id=1,
        )
        member = owned_instance(
            5525, 1, -200, map_id=1134, instance_id=71, x=30, y=20, z=0
        )
        scene = dict(self.layout, map_id=1134)
        arena = prepare_encounter_scene(
            character, [member], dict(map_id=1134, instance_id=123), layout=scene
        )
        fight, messages = create_placement(
            character,
            [member],
            arena,
            fight_id=12,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        self.assertEqual(fight.actors[7].position, (3, 0, 0))
        self.assertEqual(fight.actors[-200].position, (0, 0, 0))
        self.assertEqual(fight.actors[-200].direction, 1)
        self.assertEqual(messages[0][0], 13652)
        self.assertEqual(struct.unpack_from(">qiih", messages[0][1], 6), (7, 3, 0, 0))
        from wakfu_server.combat_wire import decode_bootstrap

        bootstrap = decode_bootstrap(messages[1][1])
        npc = next(row for row in bootstrap["participants"] if row["actor_id"] == -200)
        # Native pW format2: x/y/z, world identity, then facing byte.
        self.assertEqual(npc["myE"][19], 1)
        arena["native_encounter_scene_layout"]["anchor"][0] = 99
        self.assertEqual(fight.native_encounter_scene_layout["anchor"], [3, 0, 0])

    def test_declared_native_border_reference_survives_durable_retry(self):
        from wakfu_server.combat_placement_policy import freeze

        cells = {(x, y, 0) for x in range(5) for y in range(5)}
        borders = {cell for cell in cells if cell[0] in (0, 4) or cell[1] in (0, 4)}
        self.layout.update(
            cells=cells,
            edges={
                (a, b)
                for a in cells
                for b in cells
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            },
            source=(1, 1, 0),
            caster_cell=(1, 1, 0),
            anchor=(3, 3, 0),
            party_placement_cells=((3, 2, 0), (3, 3, 0)),
            boss_footprint=((1, 1, 0),),
            native_border_cells=borders,
            native_border_policy="wakemu.reconstructed-native-cardinal-perimeter-v1",
            terrain_effect_id=378,
        )
        selected = self.selected()
        db = PlacementDB()
        kwargs = dict(
            account_id=1,
            generation=1,
            character_id=7,
            fight_id=12,
            map_id=99,
            instance_id=71,
            selected_arena=selected,
            seeds={0: [(20, 20, 0)], 1: [(30, 20, 0)]},
            db=db,
        )
        with patch(
            "wakfu_server.combat_border_policy.choose",
            side_effect=AssertionError("Scene declares its native prototype"),
        ):
            first = freeze(SimpleNamespace(lock_character=lambda *args: None), **kwargs)
            db.layout = json.loads(json.dumps(db.layout))
            second = freeze(
                SimpleNamespace(lock_character=lambda *args: None), **kwargs
            )
        self.assertEqual(first["terrain_effect_id"], 378)
        self.assertEqual(second["terrain_effect_id"], 378)
        self.assertEqual(second["native_border_cells"], borders)
        self.assertEqual(scene_player_position(self.character, second), (3, 3, 0))
        self.assertEqual(db.inserts, 1)


class PlacementDB:
    def __init__(self):
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.layout = None
        self.scope = None
        self.inserts = 0

    def execute(self, sql, params=None):
        if sql.startswith("SELECT status FROM combat_fights"):
            result = {"status": "placement"}
        elif sql.startswith("SELECT 1 FROM combat_fight_participants"):
            result = {"present": 1}
        elif sql.startswith("SELECT map_id,instance_id,layout"):
            result = (
                None
                if self.layout is None
                else dict(
                    map_id=self.scope[0], instance_id=self.scope[1], layout=self.layout
                )
            )
        elif sql.startswith("SELECT value FROM settings"):
            result = {
                "value": dict(version=1, slots_per_team=12, variation_enabled=True)
            }
        elif sql.startswith("INSERT INTO fight_placement_layouts"):
            self.layout = copy.deepcopy(params[-1].obj)
            self.scope = params[1:3]
            self.inserts += 1
            result = None
        else:
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: result)
