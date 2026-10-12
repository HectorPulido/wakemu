"""Private hero handoff restores native movement roles without scene resets."""
import unittest
from unittest.mock import patch
from wakfu_server.haven_bag import HavenBagSession, entry_result
from wakfu_server.haven_ranch import RanchSession
from wakfu_server.characters.private_scene_heroes import messages


class PrivateSceneHeroTests(unittest.TestCase):
    def setUp(self):
        self.owner = dict(
            id=10,
            account_id=2,
            map_id=527,
            instance_id=0,
            x=0,
            y=0,
            z=0,
            name="Owner",
            haven_bag={"owner_id": 1},
        )

    def test_owner_bag_rebinds_new_selected_actor_without_map_reset(self):
        bag = HavenBagSession(self.owner)
        selected = bag.rebind(bag.inside, {**self.owner, "id": 15, "name": "Hero"})
        self.assertEqual(
            messages(bag, selected, generation="lease"),
            ((13307, entry_result(success=True)),),
        )
        self.assertEqual(bag.owner["id"], 10)
        self.assertEqual(selected["id"], 15)

    def test_guest_retains_real_host_model_and_visitor_role(self):
        guest = {**self.owner, "id": 20, "account_id": 3}
        bag = HavenBagSession(guest, owner=self.owner)
        selected = bag.rebind(bag.inside, {**guest, "id": 21})
        with patch(
            "wakfu_server.haven_bag.own_bag", return_value=b"real-host-model"
        ) as encode:
            packets = messages(bag, selected, generation="lease")
        self.assertEqual(
            packets, ((13307, b"\x01\x00\x00\x00\x00\x00real-host-model"),)
        )
        encode.assert_called_once_with(bag.owner)
        self.assertTrue(selected["haven_bag_visitor"])

    def test_ranch_keeps_entry_cleared_bag_filter_without_duplicate_leave(self):
        for visitor in (False, True):
            guest = {**self.owner, "id": 20, "account_id": 3} if visitor else self.owner
            bag = HavenBagSession(guest, owner=self.owner if visitor else None)
            ranch = RanchSession(
                bag,
                bag.inside,
                dict(biome_id=1, map_id=1440, x=9, y=-8, z=0),
                lease="lease",
                now_ms=1,
            )
            selected = ranch.rebind(ranch.inside, {**guest, "id": 21})
            self.assertEqual(messages(ranch, selected, generation="lease"), ())
            with self.assertRaises(ValueError):
                messages(ranch, selected, generation="stale")
            self.assertTrue(ranch.owns(selected))
            self.assertEqual(selected["haven_bag_visitor"], visitor)

    def test_foreign_character_rejects_and_exterior_emits_nothing(self):
        bag = HavenBagSession(self.owner)
        with self.assertRaises(ValueError):
            messages(bag, {**bag.inside, "id": 99}, generation="lease")
        with self.assertRaises(ValueError):
            messages(object(), bag.inside, generation="lease")
        self.assertEqual(messages(None, self.owner, generation="lease"), ())
