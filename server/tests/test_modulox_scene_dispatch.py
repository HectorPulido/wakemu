"""Exercise actual private scene hydration after a haven-bag transition."""

import ast
from contextlib import nullcontext
from copy import deepcopy
from source_view import WorldSourcePath as Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import haven_bag_native_scene, haven_ranch_portal, modulox_npc


class ModuloSceneDispatchTests(unittest.TestCase):
    def hydrate(self, owner):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        function = deepcopy(
            next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "sync_static_world"
            )
        )
        function.decorator_list = []
        for i, node in enumerate(function.body):
            if isinstance(node, ast.Nonlocal):
                function.body[i] = ast.Global(names=node.names)
        sent = []
        character = {
            "id": 40,
            "account_id": 7,
            "map_id": 9,
            "instance_id": 901,
            "x": 3,
            "y": 3,
            "z": 0,
        }
        bag = SimpleNamespace(is_owner=owner, owns=lambda c: c is character)
        db = object()
        ns = dict(
            character=character,
            fight=None,
            static_sync_pending=True,
            static_sync_due=0,
            static_sync_attempts=0,
            account_id=7,
            generation=12,
            ranch_session=None,
            bag_session=bag,
            STORE=SimpleNamespace(
                current_session=lambda *a: True, connection=lambda: nullcontext(db)
            ),
            active_private_session=lambda: bag,
            connection=object(),
            service="world",
            send=lambda c, s, *packet: sent.append(packet),
            record=lambda **event: None,
            world_static=SimpleNamespace(objects=lambda m: []),
        )
        with patch.object(
            haven_ranch_portal, "config_message", return_value=(1, b"config")
        ), patch.object(
            haven_bag_native_scene, "packets", return_value=[(13984, b"bag")]
        ), patch.object(
            modulox_npc, "scene_packet", return_value=(12608, b"modulo")
        ) as scene:
            exec(
                compile(
                    ast.fix_missing_locations(
                        ast.Module(body=[function], type_ignores=[])
                    ),
                    str(source),
                    "exec",
                ),
                ns,
            )
            ns["sync_static_world"](force=True)
        return sent, scene, bag, character, db

    def test_owner_receives_modulo_after_map_scene_is_hydrated(self):
        sent, scene, bag, character, db = self.hydrate(True)
        scene.assert_called_once_with(db, bag, character)
        self.assertLess(sent.index((13984, b"bag")), sent.index((12608, b"modulo")))

    def test_guest_does_not_receive_owners_modulo(self):
        sent, scene, *_ = self.hydrate(False)
        scene.assert_not_called()
        self.assertNotIn((12608, b"modulo"), sent)


if __name__ == "__main__":
    unittest.main()
