"""Exercise the production ecology preparation loop without a live database."""
import ast
import json
import pathlib
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from wakfu_server import monster_wander as wander


class CohesionPipelineTests(unittest.TestCase):
    def test_one_group_decision_and_search_replaces_eight_member_searches(self):
        source = pathlib.Path(__file__).parents[1] / "wakfu_server/maps/ecology_mobs.py"
        tree = ast.parse(source.read_text())
        prepare = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "prepare"
        )
        loop = next(
            node
            for node in ast.walk(prepare)
            if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "wander_groups"
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
            str(source),
            "exec",
        )
        members = [dict(id=-i - 1, x=i % 4, y=i // 4, z=0) for i in range(8)]
        moved = [dict(member, y=member["y"] + 1) for member in members]
        packets = [
            wander.movement_packet(
                before["id"], wander.point(before), wander.point(after)
            )
            for before, after in zip(members, moved)
        ]
        planner = Mock(return_value=dict(members=moved, packets=packets))
        roll = Mock(return_value=0)
        namespace = dict(
            wander_groups=[dict(group_id=1, status="available", members=members)],
            time=time,
            plan_deadline=time.monotonic() + 60,
            excluded=set(),
            moved_member_count=0,
            packet_bytes=0,
            scope_occupied={wander.point(m) for m in members},
            MAX_WANDER_BATCH_MOVED_MEMBERS=40,
            MAX_WANDER_BATCH_PACKET_BYTES=65536,
            MAX_WANDER_BATCH_JSON_BYTES=65536,
            MAX_WANDER_BATCH_GROUPS=8,
            random=SimpleNamespace(random=roll),
            configuration=dict(move_probability=1, radius=20, min_steps=1, max_steps=3),
            wander=SimpleNamespace(point=wander.point, plan_group_path=planner),
            scoped=[dict(x=10, y=10, z=0)],
            indexed=(set(), {}),
            habitat_destination_allowed=lambda *_: True,
            scope=(527, 0),
            moves=[],
            epoch="test",
            json=json,
        )
        exec(code, namespace)
        self.assertEqual(roll.call_count, 1)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(planner.call_args.args[0], members)
        self.assertEqual(namespace["moved_member_count"], 8)
        self.assertEqual(len(namespace["moves"]), 1)
        self.assertEqual(len(namespace["moves"][0]["packets"]), 8)
        self.assertEqual(namespace["moves"][0]["moved_members"], moved)
