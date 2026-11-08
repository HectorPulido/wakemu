"""QA observer projection only: no Fight restoration or live gameplay."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(1, str(ROOT / "server" / "tools"))
import rift_tls_party_e2e as runner


def observer_projection():
    tree = ast.parse((ROOT / "server/tools/rift_tls_party_e2e.py").read_text())
    observe = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "observe"
    )
    script = next(
        node.value.value
        for node in observe.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "script"
            for target in node.targets
        )
    )
    function = next(
        node
        for node in ast.parse(script).body
        if isinstance(node, ast.FunctionDef) and node.name == "saved_movement_blocked"
    )
    namespace = {"SimpleNamespace": SimpleNamespace}
    exec(
        compile(
            ast.Module(body=[function], type_ignores=[]),
            "<actual QA observer projection>",
            "exec",
        ),
        namespace,
    )
    return namespace["saved_movement_blocked"]


def saved_scene(*, radius=0):
    from wakfu_server.combat_qi_registry import NativeQIRegistry

    arena = dict(x=0, y=0, width=5, height=5, cell_masks=[0] * 25)
    slots = [None] * 127
    for slot, identity, point, body in ((0, 7, [1, 1], radius), (1, 8, [3, 1], 0)):
        slots[slot] = dict(
            identity=["actor", identity],
            position=point,
            radius=body,
            indexed=True,
            movement_blocking=True,
        )
    registry = NativeQIRegistry(arena, slots)
    registry.capture_fresh_cell_topology([0, 1])
    cells = [[x, y, 0] for x in range(5) for y in range(5)]
    edges = [
        [a, b] for a in cells for b in cells if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
    ]
    return dict(
        native_qi_snapshot=arena,
        native_qi_slots=registry.serialized_slots(),
        native_qi_touched_cells=registry.serialized_cells(),
        native_qi_byte_topology=registry.serialized_byte_topology(),
        native_qi_movement_override=False,
        native_qi_ignored_slots=[],
        actors={
            "7": dict(
                id=7,
                native_obstacle_id=0,
                physical_radius=radius,
                position=[1, 1, 0],
                hp=20,
                max_hp=100,
                mp=10,
            ),
            "8": dict(
                id=8, native_obstacle_id=1, physical_radius=0, position=[3, 1, 0], hp=50
            ),
        },
        walkable=cells,
        edges=edges,
    )


class SavedPassabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = staticmethod(observer_projection())
        cls.runner = runner

    def test_masks_precede_override_and_native_ignored_slots_and_own_body(self):
        saved = saved_scene()
        self.assertIn((3, 1, 0), set(map(tuple, self.project(saved, 7))))
        self.assertNotIn((1, 1, 0), set(map(tuple, self.project(saved, 7))))
        saved["native_qi_ignored_slots"] = [1]
        self.assertNotIn((3, 1, 0), set(map(tuple, self.project(saved, 7))))
        saved["native_qi_ignored_slots"] = []
        saved["native_qi_movement_override"] = True
        self.assertNotIn((3, 1, 0), set(map(tuple, self.project(saved, 7))))
        saved["native_qi_snapshot"]["cell_masks"][1 * 5 + 3] = 256
        self.assertIn((3, 1, 0), set(map(tuple, self.project(saved, 7))))

    def test_large_body_checks_off_anchor_blocker_and_arena_edge(self):
        saved = saved_scene(radius=1)
        blocked = set(map(tuple, self.project(saved, 7)))
        self.assertIn((2, 1, 0), blocked)
        self.assertIn((0, 1, 0), blocked)
        self.assertNotIn((1, 1, 0), blocked)

    def test_combat_and_healing_take_native_mask_detour(self):
        saved = saved_scene()
        saved["native_qi_snapshot"]["cell_masks"][1 * 5 + 2] = 512
        blocked = set(map(tuple, self.project(saved, 7)))
        checkpoint = dict(
            saved,
            phase="active",
            current_actor_id=7,
            runtime={"awaiting_ack": None},
            movement_actor_id=7,
            movement_blocked_cells=[list(cell) for cell in blocked],
            healing_orbs=[
                dict(
                    reference=1574,
                    native_area_contract="faY",
                    native_qq_bhi=False,
                    cell=[3, 2, 0],
                )
            ],
        )
        geometry = {"cells": saved["walkable"], "edges": saved["edges"]}
        heal = self.runner.healing_orb_route(checkpoint, geometry, 7)
        attack = self.runner.combat_route(
            geometry,
            (1, 1, 0),
            (3, 2, 0),
            blocked,
            10,
            minimum_range=0,
            maximum_range=0,
        )
        for route in (heal, attack):
            self.assertTrue(route)
            self.assertEqual(route[-1], (3, 2, 0))
            self.assertFalse(set(route) & blocked)
        with self.assertRaisesRegex(ValueError, "actor-specific"):
            self.runner.route_blocked_cells(checkpoint, 8)

    def test_unknown_pointer_or_incomplete_saved_schema_fails_closed(self):
        for field in (
            "native_qi_snapshot",
            "native_qi_slots",
            "native_qi_touched_cells",
            "native_qi_byte_topology",
        ):
            saved = saved_scene()
            del saved[field]
            with self.assertRaisesRegex(ValueError, "complete saved"):
                self.project(saved, 7)
        saved = saved_scene()
        saved["native_pointer_checkpoint"] = {"schema": "not-a-bound-owner"}
        with self.assertRaisesRegex(ValueError, "canonical pointer"):
            self.project(saved, 7)
        saved = saved_scene()
        del saved["actors"]["7"]["physical_radius"]
        with self.assertRaisesRegex(ValueError, "physical radius"):
            self.project(saved, 7)
