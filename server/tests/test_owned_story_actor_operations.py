"""Focused source and wire regression for native owned actor operations."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_actor_operations as operations


class NativeActorOperationTests(unittest.TestCase):
    def test_exact_native_action_and_original_disabled_mask(self):
        action = dict(d=446, aGJ=1, clx=67, clT="", getDuration=0, native_class="aMg")
        source = dict(
            scene_actors=[dict(role="helper", reference=2794)],
            actor_operations=[
                dict(
                    role="helper",
                    action_id=446,
                    consumer="healing",
                    native_action=action,
                    evidence="Exact original aMg record",
                )
            ],
        )
        with patch.object(
            operations.owned_story_mechanics, "sources", return_value=source
        ), patch.object(
            operations,
            "native_actions",
            return_value=[deepcopy(action), dict(action, d=447)],
        ):
            self.assertEqual(len(operations.declarations({})), 1)
            with patch.object(
                operations.npc_placements, "spawn_owned"
            ) as scoped, patch.object(
                operations.npc_placements, "_spawn", side_effect=lambda row: row
            ):
                result = operations.spawn(
                    dict(role="helper", reference_id=2794), character={}, selected={}
                )
                self.assertEqual(result["native_action_ids"], [447])
                scoped.assert_called_once()
            source["actor_operations"][0]["native_action"] = dict(action, clx=68)
            with self.assertRaisesRegex(ValueError, "original native breed"):
                operations.declarations({})

    def test_original_criterion_and_malformed_body(self):
        with patch.object(
            operations.owned_story_mechanics, "allowed", return_value=False
        ) as allowed:
            self.assertFalse(
                operations.allowed(
                    "db",
                    "store",
                    "owner",
                    {"native_action": {"clT": "GetInstanceId()!=536"}},
                )
            )
            allowed.assert_called_once_with(
                "db", "store", "owner", "GetInstanceId()!=536"
            )
        for body in (b"", b"\0" * 15, b"\0" * 17):
            session = SimpleNamespace(
                state=SimpleNamespace(
                    opcode=13222, character={"instance_id": 4}, body=body
                ),
                runtime=None,
            )
            self.assertFalse(operations.handle(session))


if __name__ == "__main__":
    unittest.main()
