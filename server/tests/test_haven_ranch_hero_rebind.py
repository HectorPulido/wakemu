"""Ranch hero handoff retains host identity and nested return capabilities."""
import copy
import unittest
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession


class RanchHeroRebindTests(unittest.TestCase):
    def saved(self, identity=10, account=2, bag=10):
        return dict(
            id=identity,
            account_id=account,
            map_id=1134,
            instance_id=0,
            x=5,
            y=8,
            z=0,
            level=6,
            haven_bag={"owner_id": bag, "rooms": []},
        )

    def child(self, outside, owner=None):
        bag = HavenBagSession(outside, owner=owner)
        bag.move(bag.inside, dict(x=-8, y=5, z=4))
        child = RanchSession(
            bag,
            bag.inside,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease="generation",
            now_ms=1000,
        )
        return bag, child

    def test_owned_hero_rebind_retains_ranch_position_and_nested_return(self):
        bag, child = self.child(self.saved())
        prior = child.move(child.inside, dict(x=29, y=6, z=4))
        selected = dict(self.saved(11), level=50)
        active = child.rebind(prior, selected)
        self.assertFalse(child.owns(prior))
        self.assertTrue(child.owns(active))
        self.assertEqual(
            (active["map_id"], active["instance_id"], active["x"], active["level"]),
            (1440, 10, 29, 50),
        )
        child.validate_lease("generation")
        insidebag = child.leave(active)
        self.assertEqual(
            (insidebag["id"], insidebag["x"], insidebag["map_id"]), (11, -8, 9)
        )
        self.assertEqual(bag.leave(insidebag), selected)
        self.assertEqual(bag.exterior_actor_id, 10)

    def test_guest_hero_rebind_preserves_host_layout_and_visitor_policy(self):
        host = self.saved(20, 3, 20)
        bag, child = self.child(self.saved(), owner=host)
        selected = self.saved(11)
        active = child.rebind(child.inside, selected)
        self.assertEqual(active["instance_id"], 20)
        self.assertTrue(active["haven_bag_visitor"])
        self.assertEqual(active["haven_bag"], host["haven_bag"])
        self.assertIsNone(bag.exterior_actor_id)
        self.assertEqual(bag.leave(child.leave(active)), selected)

    def test_closed_or_orphan_parent_and_foreign_actor_reject_without_mutation(self):
        bag, child = self.child(self.saved())
        before = copy.deepcopy(child.inside)
        with self.assertRaises(ValueError):
            child.rebind(child.inside, self.saved(12, 9))
        self.assertEqual(child.inside, before)
        with self.assertRaises(ValueError):
            child.validate_lease("replaced-generation")
        bag.rebind(child.return_point, self.saved(11))
        self.assertFalse(child.owns(child.inside))
        with self.assertRaises(ValueError):
            child.validate_lease("generation")
        with self.assertRaises(ValueError):
            child.rebind(child.inside, self.saved(12))
        bag, child = self.child(self.saved())
        active = child.inside
        child.leave(active)
        with self.assertRaises(ValueError):
            child.rebind(active, self.saved(11))
