import unittest
from wakfu_server.combat_displacement_collision import (
    apply_collision,
    collision_event_sources,
)
from wakfu_server.combat_event_replay import NativeCloneAuthority
from wakfu_server.combat_effect_dispatch import EffectInvocation


class CollisionEventTests(unittest.TestCase):
    def setUp(self):
        self.invocation = EffectInvocation(100, 1, 7, 8, (3, 0, 0))
        self.args = dict(
            invocation=self.invocation,
            uid=20,
            value=2,
            displaced_id=8,
            collider_id=9,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
        )

    def test_exact_native_roles_rebinding_and_order(self):
        sources = collision_event_sources(**self.args, collider_uid=21)
        self.assertEqual(
            [(s.channel, s.manager_actor_id, s.target_id) for s in sources],
            [(30, 7, 8), (3, 8, 8), (30, 7, 9), (3, 9, 9)],
        )
        self.assertTrue(
            all(s.event_ids == (204,) for s in sources)
            and [s.uid for s in sources] == [20, 20, 21, 21]
        )

    def test_full_loss_precedes_replay_and_callbacks_are_required(self):
        events = []
        authority = NativeCloneAuthority(lambda *a: True, lambda *a: None)
        apply_collision(
            **self.args,
            loss_ap=True,
            ap_loss_executor=lambda a, b: events.append(("ap", b)),
            replay=lambda s, **kw: events.append(("event", s.manager_actor_id)),
            clone_authority=authority,
            allocate_clone_uid=lambda: 21
        )
        self.assertEqual(
            events,
            [
                ("ap", 8),
                ("ap", 9),
                ("event", 7),
                ("event", 8),
                ("event", 7),
                ("event", 9),
            ],
        )
        events.clear()
        with self.assertRaisesRegex(ValueError, "full eVZ"):
            apply_collision(
                **self.args,
                loss_ap=True,
                ap_loss_executor=None,
                replay=lambda *a, **k: events.append(1),
                clone_authority=authority,
                allocate_clone_uid=lambda: 21
            )
        self.assertEqual(events, [])

    def test_wall_collision_without_ap_still_replays(self):
        self.args["collider_id"] = None
        sources = []
        apply_collision(
            **self.args,
            loss_ap=False,
            ap_loss_executor=None,
            replay=lambda s, **kw: sources.append(s),
            clone_authority=NativeCloneAuthority(lambda *a: True, lambda *a: None)
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual([s.channel for s in sources], [30, 3])


if __name__ == "__main__":
    unittest.main()
