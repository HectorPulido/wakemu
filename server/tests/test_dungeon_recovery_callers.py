"""Execute the actual World recovery callers without booting another server."""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def caller(name, namespace):
    source = Path(
        os.environ.get(
            "WAKFU_RECOVERY_DISPATCH_SOURCE",
            Path(__file__).resolve().parents[1] / "local_game_server.py",
        )
    )
    module = ast.parse(source.read_text())
    node = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    closure_names = sorted(
        {
            name
            for statement in ast.walk(node)
            if isinstance(statement, ast.Nonlocal)
            for name in statement.names
        }
    )
    if closure_names:
        factory = ast.parse("def factory():\n    pass\n").body[0]
        factory.body = [
            ast.Assign(
                [ast.Name(name, ast.Store())], ast.Name("INITIAL_" + name, ast.Load())
            )
            for name in closure_names
        ]
        factory.body.extend([node, ast.Return(ast.Name(name, ast.Load()))])
        code = ast.Module(body=[factory], type_ignores=[])
        ast.fix_missing_locations(code)
        exec(compile(code, str(source), "exec"), namespace)
        return namespace["factory"]()
    code = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(code)
    exec(compile(code, str(source), "exec"), namespace)
    return namespace[name]


class DungeonRecoveryCallerTests(unittest.TestCase):
    def test_changed_position_baseline_retries_before_any_world_or_packet_mutation(
        self,
    ):
        from wakfu_server.position_buffer import PositionBaselineChanged

        old = dict(id=10, map_id=527, instance_id=0, x=0, y=1, z=0)
        fresh = dict(old, map_id=1086, instance_id=90, x=4)
        plan = SimpleNamespace(
            character=fresh, packets=((13256, b"scene"), (13974, b"map"))
        )
        namespace = dict(
            INITIAL_character=old,
            INITIAL_position=dict(x=0, y=1, z=0),
            INITIAL_movement_state=None,
            dungeon_hydration=Mock(prepare_transition=Mock(return_value=plan)),
            STORE=Mock(),
            account_id=1,
            generation="current",
            fixture=Mock(),
            POSITIONS=Mock(),
            WORLD=Mock(),
            cancel_crafting=Mock(),
            Movement=Mock(),
            send=Mock(),
            connection=object(),
            service="world",
            join_world=Mock(),
            mark_static_sync_pending=Mock(),
            publish_entry_inventory=Mock(),
        )
        bootstrap = caller("bootstrap_dungeon_event", namespace)
        namespace["POSITIONS"].attach.side_effect = PositionBaselineChanged("changed")
        self.assertFalse(bootstrap({"transition_kind": "door"}))
        namespace["WORLD"].leave.assert_not_called()
        namespace["send"].assert_not_called()
        namespace["cancel_crafting"].assert_not_called()
        namespace["join_world"].assert_not_called()
        namespace["POSITIONS"].attach.side_effect = None
        self.assertTrue(bootstrap({"transition_kind": "door"}))
        namespace["WORLD"].leave.assert_called_once_with(10, "current")
        self.assertEqual(namespace["send"].call_count, 2)
        namespace["join_world"].assert_called_once_with(
            "current", namespace["connection"], fresh
        )

    def test_deferred_main_room_hydration_preserves_successful_group_settlement(self):
        from wakfu_server import (
            dungeon_progression,
            dungeon_room_handoff,
            dungeon_runtime,
            monster_corpses,
        )

        order = []
        outcome = dict(applied=True, packets=[])
        namespace = dict(
            group_lease=((1086, 90, 25), "lease"),
            COMBAT_GROUPS=Mock(),
            finish_developer_test_group=Mock(return_value=None),
            fight=SimpleNamespace(id=91),
            DUNGEON_ROOM_RUNTIME_AVAILABLE=True,
            STORE=Mock(),
            reward_monsters=[],
            finish_world_group=Mock(
                side_effect=lambda *args, **kwargs: order.append("finish") or outcome
            ),
        )
        settle = caller("shared_group_settlement", namespace)
        db = Mock()
        with patch.object(
            dungeon_progression,
            "lock_encounter_run",
            side_effect=lambda *_: order.append("lock"),
        ), patch.object(
            dungeon_progression,
            "settle_encounter",
            side_effect=lambda *_: order.append("settle")
            or dict(victory=True, instance_id=90, encounter_scope="main"),
        ), patch.object(
            dungeon_room_handoff,
            "prepare",
            side_effect=lambda *args, **kwargs: order.append("handoff")
            or dict(ready=False, state="pending"),
        ) as prepare, patch.object(
            dungeon_runtime, "ensure_current_room"
        ) as direct, patch.object(
            monster_corpses, "retain"
        ):
            self.assertIs(settle(db, 1, 10, True), outcome)
        self.assertEqual(order, ["lock", "finish", "settle", "handoff"])
        self.assertEqual(prepare.call_args.kwargs["instance_id"], 90)
        self.assertEqual(prepare.call_args.kwargs["fight_id"], 91)
        direct.assert_not_called()
