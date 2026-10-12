"""Native Ranch portal permissions for Haven Bag visitors and owners."""
import ast
import struct
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server.haven_ranch_authority import biome_target, portal_target
from wakfu_server.haven_ranch_portal import validate_exit


class RanchVisitorAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.owner = dict(
            id=10,
            account_id=2,
            map_id=1134,
            instance_id=0,
            x=-9,
            y=-4,
            z=-1,
            haven_bag={"owner_id": 10, "rooms": []},
        )
        self.guest = dict(
            id=11,
            account_id=3,
            map_id=1134,
            instance_id=0,
            x=-8,
            y=-4,
            z=-1,
            haven_bag={"owner_id": 11, "rooms": []},
        )
        self.bag = HavenBagSession(self.guest, owner=self.owner)
        self.actor = self.bag.move(self.bag.inside, {"x": -8, "y": 5, "z": 4})
        self.entrance = dict(id=36028, type="RanchEntrance", map_id=9, x=-9, y=5, z=4)
        self.geometry = dict(map_id=9, cells=[[-8, 5, 4], [28, 6, 4]])
        self.lease = Mock()
        self.entitlement = Mock()

    def _portal(self, action):
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[self.entrance],
        ):
            return portal_target(
                self.actor,
                self.bag,
                struct.pack(">qHH", 36028, action, 0),
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
                geometry=self.geometry,
            )

    def test_guest_native_activate_enters_host_ranch_without_own_entitlement(self):
        target = self._portal(0)
        self.assertEqual(target["map_id"], 1440)
        self.assertEqual(target["biome_id"], 1)
        self.entitlement.assert_not_called()
        self.lease.assert_called_once_with()

    def test_owner_default_choice_and_guest_biome_choice_reject(self):
        owner_bag = HavenBagSession(self.owner)
        owner_actor = owner_bag.move(owner_bag.inside, {"x": -8, "y": 5, "z": 4})
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[self.entrance],
        ):
            with self.assertRaises(ValueError):
                portal_target(
                    owner_actor,
                    owner_bag,
                    struct.pack(">qHH", 36028, 0, 0),
                    validate_lease=self.lease,
                    validate_entitlement=self.entitlement,
                    geometry=self.geometry,
                )
        with self.assertRaisesRegex(ValueError, "only enter the host ranch"):
            self._portal(35)

    def test_guest_cannot_forge_biome_switch_but_can_use_native_return_portal(self):
        target = self._portal(0)
        child = RanchSession(
            self.bag, self.actor, target, lease="guest-lease", now_ms=1000
        )
        with self.assertRaisesRegex(ValueError, "active owned ranch"):
            biome_target(
                child.inside,
                child,
                struct.pack(">i", 1),
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
            )

        exit_object = dict(id=36029, type="RanchExit", map_id=1440, x=28, y=6, z=4)
        with patch(
            "wakfu_server.haven_ranch_portal._objects", return_value=[exit_object]
        ):
            self.assertEqual(
                validate_exit(
                    child.inside,
                    child,
                    struct.pack(">qHH", 36029, 18, 0),
                    validate_lease=self.lease,
                ),
                36029,
            )
        self.entitlement.assert_not_called()

    def test_main_dispatch_routes_native_action18_to_owned_exit_validator(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        ranch_dispatch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "opcode in (12380, 13982)" in ast.unparse(node.test)
            and "opcode == 12870" in ast.unparse(node.test)
        )
        branch_text = ast.unparse(ranch_dispatch)
        self.assertIn("struct.unpack_from('>H', body, 8)[0] == 18", branch_text)
        self.assertIn(
            "from wakfu_server.haven_ranch_portal import validate_exit", branch_text
        )
        self.assertIn("validate_exit(character, ranch_session, body", branch_text)


if __name__ == "__main__":
    unittest.main()
