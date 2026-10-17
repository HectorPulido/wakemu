"""Neutral range glyphs use real viewer affiliation without changing gameplay."""
from copy import deepcopy
import ast
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.combat_bootstrap import placement_messages
from wakfu_server.combat_battleground_border import POLICY
from wakfu_server.combat_environment_glyphs import (
    environment_sections,
    ensure_environment_glyphs,
    prepare_environment_glyphs,
)
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_wire import arena, decode_bootstrap


class EnvironmentalGlyphVisibilityTests(unittest.TestCase):
    def fixture(self):
        cells = {(x, y, 0) for x in range(5) for y in range(5)}
        actors = [
            Actor(7, 0, (1, 1, 0), 60, 6, 3, 100, 1, 1, True),
            Actor(8, 1, (3, 3, 0), 60, 6, 3, 10, 1, 2, True),
        ]
        fight = Fight(
            11, actors, cells, {0: {actors[0].position}, 1: {actors[1].position}}
        )
        initialize_global_pv_collections(fight, (7, 8))
        terrain = arena(1134, 1, sorted(cells), {0: (1, 1, 0), 1: (3, 3, 0)})
        terrain.update(
            native_border_policy=POLICY,
            native_border_cells={c for c in cells if c[0] in (0, 4) or c[1] in (0, 4)},
        )
        prepare_environment_glyphs(fight, terrain, -100)
        ensure_environment_glyphs(fight)
        return fight, terrain

    def test_both_teams_receive_real_owner_header_with_identical_area_identity(self):
        fight, _ = self.fixture()
        before = deepcopy(fight.native_effect_areas)
        constructors = deepcopy(fight.native_environment_glyph_constructors)
        neutral = environment_sections(fight)[0]
        self.assertEqual(struct.unpack_from(">q", neutral, 26)[0], 0)
        for viewer in (7, 8):
            with self.subTest(viewer=viewer):
                projected = environment_sections(fight, viewer_id=viewer)[0]
                self.assertEqual(struct.unpack_from(">q", projected, 26)[0], viewer)
                self.assertEqual(projected[:26], neutral[:26])
                self.assertEqual(projected[34:], neutral[34:])
        self.assertEqual(fight.native_effect_areas, before)
        self.assertEqual(fight.native_environment_glyph_constructors, constructors)
        self.assertIsNone(before[-101]["owner_id"])
        self.assertEqual(before[-101]["native_fight_affiliation"], -1)
        self.assertEqual(environment_sections(fight), [neutral])

    def test_foreign_viewer_cannot_be_bound_as_native_owner(self):
        fight, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, "not a fight actor"):
            environment_sections(fight, viewer_id=99)

    def test_initial_and_joined_placement_bind_each_actual_recipient(self):
        fight, terrain = self.fixture()
        payloads = {actor.id: (b"stats", b"") for actor in fight.actors.values()}
        shared = SimpleNamespace(
            join_context=dict(
                arena=terrain,
                terrain_effect_id=46,
                terrain_instance_id=-100,
                leaders={0: 7, 1: 8},
                duration_ms=60000,
                actor_payload=lambda *args: (b"stats", b""),
            )
        )
        for viewer in (7, 8):
            initial = placement_messages(
                fight,
                terrain,
                payloads,
                terrain_effect_id=46,
                terrain_instance_id=-100,
                leaders={0: 7, 1: 8},
                viewer_id=viewer,
            )
            joined = CombatSessionAdapter.placement_bootstrap(
                fight, shared, SimpleNamespace(character_id=viewer)
            )
            for packets in (initial, joined):
                bootstrap = decode_bootstrap(
                    next(body for op, body in packets if op == 12847)
                )
                self.assertIn(
                    viewer, {p["actor_id"] for p in bootstrap["participants"]}
                )
                self.assertEqual(
                    struct.unpack_from(">q", bootstrap["myK"][0], 26)[0], viewer
                )

    def test_retired_area_is_not_recreated_by_viewer_projection(self):
        fight, _ = self.fixture()
        del fight.native_effect_areas[-101]
        self.assertEqual(environment_sections(fight, viewer_id=7), [])
        self.assertEqual(environment_sections(fight), [])

    def test_active_reconnect_uses_recipient_owner_without_replaying_gameplay(self):
        from test_combat_reconnect_summon_timeline import fixture
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot

        fight, _, shared = fixture(True)
        # The original summon fixture occupies every walkable cell. Add one
        # native arena cell so an environmental constructor can actually exist.
        fight.walkable = set(fight.walkable) | {(4, 0, 0)}
        shared.join_context["arena"]["width"] = 5
        shared.join_context["arena"]["cell_masks"] = [0] * 5
        prepare_environment_glyphs(
            fight, dict(native_border_policy=POLICY, native_border_cells=set()), -1000
        )
        fight.native_environment_glyphs_installed = False
        initialize_global_pv_collections(fight, tuple(fight.actors))
        ensure_environment_glyphs(fight)
        before = deepcopy(fight.native_effect_areas)
        resources = {
            actor.id: (actor.hp, actor.ap, actor.mp) for actor in fight.actors.values()
        }
        packets = owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=1, character_id=100),
            actor_payload=lambda *args: (b"owned-stats", b"\x00\x00"),
        )
        bootstrap = decode_bootstrap(next(body for op, body in packets if op == 12847))
        self.assertEqual(struct.unpack_from(">q", bootstrap["myK"][0], 26)[0], 100)
        self.assertEqual(fight.native_effect_areas, before)
        self.assertEqual(
            {
                actor.id: (actor.hp, actor.ap, actor.mp)
                for actor in fight.actors.values()
            },
            resources,
        )

    def test_world_npc_initialization_rebuild_preserves_actual_recipient_binding(self):
        fight, terrain = self.fixture()
        terrain["terrain_effect_id"] = 46
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "placement_messages"
        ]
        self.assertEqual(len(calls), 1)
        expression = ast.Expression(body=calls[0])
        packets = eval(
            compile(ast.fix_missing_locations(expression), str(source), "eval"),
            dict(
                placement_messages=placement_messages,
                candidate=fight,
                arena=terrain,
                actor_payloads={a.id: (b"stats", b"") for a in fight.actors.values()},
                terrain_instance_id=-100,
                character={"id": 7},
                TEST_MONSTERS=[{"id": 8}],
                placement_duration=60000,
            ),
        )
        bootstrap = decode_bootstrap(next(body for op, body in packets if op == 12847))
        self.assertEqual(struct.unpack_from(">q", bootstrap["myK"][0], 26)[0], 7)
