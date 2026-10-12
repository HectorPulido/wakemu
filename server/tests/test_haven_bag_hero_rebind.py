"""Owned hero handoff preserves transient bag scene and exterior storage."""
import copy
import unittest
from wakfu_server.haven_bag import HavenBagSession


class HavenBagHeroRebindTests(unittest.TestCase):
    def outside(self, identity=3, account=2):
        return dict(
            id=identity,
            account_id=account,
            map_id=1134,
            instance_id=0,
            x=7,
            y=14,
            z=-1,
            name="Hero",
            level=6,
            haven_bag={"owner_id": 3, "rooms": []},
        )

    def test_owned_switch_preserves_scene_new_stats_and_exact_return_point(self):
        original = self.outside()
        session = HavenBagSession(original)
        prior = session.move(session.inside, dict(x=-4, y=2, z=0))
        prior["haven_bag"] = {"owner_id": 3, "rooms": ["updated-layout"]}
        selected = dict(self.outside(4), level=25, builds={"active": 1})
        rebound = session.rebind(prior, selected)
        self.assertTrue(session.owns(rebound))
        self.assertFalse(session.owns(prior))
        self.assertEqual(
            tuple(rebound[k] for k in ("map_id", "instance_id", "x", "y", "z")),
            (9, 3, -4, 2, 0),
        )
        self.assertEqual((rebound["id"], rebound["level"]), (4, 25))
        self.assertEqual(rebound["haven_bag"], prior["haven_bag"])
        self.assertFalse(rebound["haven_bag_visitor"])
        self.assertEqual(session.exterior_actor_id, original["id"])
        self.assertEqual(session.leave(rebound), selected)
        self.assertEqual(selected["map_id"], 1134)
        moved = session.move(rebound, dict(x=4, y=3, z=0))
        self.assertEqual(session.leave(moved), selected)

    def test_guest_switch_keeps_foreign_layout_and_denies_ownership(self):
        owner = dict(
            self.outside(10, 9), haven_bag={"owner_id": 10, "rooms": ["foreign"]}
        )
        session = HavenBagSession(self.outside(), owner=owner)
        selected = self.outside(4)
        rebound = session.rebind(session.inside, selected)
        self.assertTrue(session.owns(rebound))
        self.assertFalse(session.is_owner)
        self.assertIsNone(session.exterior_actor_id)
        self.assertTrue(rebound["haven_bag_visitor"])
        self.assertEqual(rebound["haven_bag"], owner["haven_bag"])
        self.assertEqual(rebound["instance_id"], 10)
        self.assertEqual(session.leave(rebound), selected)

    def test_rejects_foreign_stale_wrong_bag_or_persisted_interior_without_mutation(
        self,
    ):
        session = HavenBagSession(self.outside())
        previous = copy.deepcopy(session.__dict__)
        for selected in [
            self.outside(4, 8),
            dict(self.outside(4), map_id=9),
            dict(self.outside(4), haven_bag={"owner_id": 55}),
            dict(self.outside(4), x=None),
        ]:
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                session.rebind(session.inside, selected)
            self.assertEqual(session.__dict__, previous)
        with self.assertRaises(ValueError):
            session.rebind(dict(session.inside, id=99), self.outside(4))
        self.assertEqual(session.__dict__, previous)
