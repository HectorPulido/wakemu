"""Opaque actor getters cannot escape constructor scope cleanup."""
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_summon_initialization import (
    detached_summon_scope,
    detached_actors,
)
from test_detached_membership_scope import DetachedMembershipScopeTests, authority


class LateIdentityFailure(Actor):
    def __getattribute__(self, name):
        if name == "id":
            fields = object.__getattribute__(self, "__dict__")
            if fields.get("_observe_identity"):
                fields["_identity_reads"] += 1
                if fields["_identity_reads"] == 7:
                    raise RuntimeError("identity getter failed")
        return object.__getattribute__(self, name)


class DetachedScopeCustomSetupTests(unittest.TestCase):
    def test_custom_identity_failure_does_not_leak_construction_context(self):
        owner, fight = DetachedMembershipScopeTests().fixture()
        actor = LateIdentityFailure(-1, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        actor.team = -1
        actor._observe_identity = True
        actor._identity_reads = 0
        with self.assertRaisesRegex(RuntimeError, "identity getter failed"):
            with detached_summon_scope(fight, actor, authority(-1)):
                self.assertIs(detached_actors(fight)[0], actor)
                self.assertEqual(actor._identity_reads, 6)
                actor.id
        self.assertEqual(detached_actors(fight), ())
        self.assertEqual(owner.detached_actors, {})


if __name__ == "__main__":
    unittest.main()
