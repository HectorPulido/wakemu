"""Actual shared registry/public runtime accept human-controlled ordinary NPCs."""
from types import SimpleNamespace
import struct
import unittest

from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_controller_registry import transfer_native_controller
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections


class DeferredWork:
    def __init__(self):
        self.jobs = []

    def submit(self, key, operation):
        self.jobs.append(operation)
        return "submitted"


class SceneHelperSharedInputTests(unittest.TestCase):
    def fixture(self):
        session = Session(1, 10, "owner", 1134, 0)
        wrong = Session(2, 20, "other", 1134, 0)
        live = {session, wrong}
        registry = Registry(lambda supplied: supplied in live)
        actors = [
            Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
            Actor(-300, 0, (1, 0, 0), 30, 6, 3, 200, 1),
            Actor(-200, 1, (4, 0, 0), 50, 6, 3, 1, 1),
        ]
        fight = Fight(
            99,
            actors,
            {(x, 0, 0) for x in range(5)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(4, 0, 0)}},
        )
        for actor in actors:
            actor.native_controlled_by_ai = actor.id == -200
            actor.physical_radius = 0
            actor.native_jump_height = 1
            actor.effect_stats = {7: 0, 8: 0, 2: actor.ap, 3: actor.mp}
        from test_combat_tackle_movement import Authority
        from dataclasses import replace

        class MovementAuthority(Authority):
            def __call__(self, current_fight, current_actor):
                return replace(
                    super().__call__(current_fight, current_actor),
                    is_player=current_actor.controlled,
                )

        fight.native_rail_movement_authority = MovementAuthority()
        initialize_global_pv_collections(
            fight, tuple(fight.actors), controller_registration=True
        )
        transfer_native_controller(fight, -300, 10)
        shared = registry.register(fight, session)
        fight.ready(1)
        self.assertEqual(fight.current.id, -300)
        runtime = RuntimeMessages(fight, turn_duration_ms=100, clock=lambda: 0)
        runtime.turn_started()
        shared.runtime = runtime
        registry.drain(99, session)
        return registry, shared, session, wrong, live

    def test_actual_shared_move_resource_action_pass_and_ack_preserve_npc_identity(
        self,
    ):
        registry, shared, session, _, _ = self.fixture()

        def move(candidate, runtime):
            candidate.move(1, -300, [(2, 0, 0)])
            return [(12502, b"owned-move")]

        registry.execute(99, session, -300, move)
        self.assertEqual(shared.fight.actors[-300].position, (2, 0, 0))
        registry.execute(
            99,
            session,
            -300,
            lambda candidate, runtime: (candidate.spend(1, -300, ap=1), ())[1],
        )
        self.assertEqual(shared.fight.actors[-300].ap, 5)
        turn = shared.fight.turn_id
        registry.execute(
            99,
            session,
            -300,
            lambda candidate, runtime: runtime.end_turn(1, -300, turn),
        )
        self.assertIsNone(shared.fight.actors[-300].owner_id)
        self.assertFalse(shared.fight.actors[-300].controlled)
        self.assertEqual(shared.ack.turn, turn)
        self.assertTrue(
            registry.acknowledge(
                99,
                session,
                struct.pack(">i", turn),
                lambda candidate, runtime, body: runtime.acknowledge_turn(body),
            )
        )
        self.assertIsNone(shared.ack.turn)

    def test_wrong_session_hostile_npc_stale_turn_and_dead_helper_reject(self):
        registry, shared, session, wrong, live = self.fixture()
        for supplied, actor_id in ((wrong, -300), (session, -200)):
            with self.assertRaises(ValueError):
                registry.execute(
                    99, supplied, actor_id, lambda *args: (), require_turn=False
                )
        with self.assertRaises(ValueError):
            registry.execute(99, session, 10, lambda *args: ())
        shared.fight.actors[-300].hp = 0
        with self.assertRaises(ValueError):
            registry.execute(99, session, -300, lambda *args: ())
        live.remove(session)
        with self.assertRaises(ValueError):
            registry.execute(99, session, -300, lambda *args: ())

    def test_shared_idle_expiry_claims_actual_human_owner_once_and_ack(self):
        registry, shared, session, _, _ = self.fixture()
        shared.runtime.turn_deadline = -1
        shared.runtime.deadline_turn = shared.fight.turn_id
        work = DeferredWork()
        self.assertEqual(
            registry.poll_expired_turn(99, session, now_ms=1, work=work), (False, None)
        )
        self.assertEqual(len(work.jobs), 1)
        work.jobs[0]()
        self.assertEqual(shared.fight.turn_id, 2)
        self.assertEqual(shared.ack.turn, 1)
        self.assertEqual(
            registry.expire_current_turn(99, session, now_ms=2), (False, None)
        )
        self.assertTrue(
            registry.acknowledge(
                99,
                session,
                struct.pack(">i", 1),
                lambda candidate, runtime, body: runtime.acknowledge_turn(body),
            )
        )
        self.assertIsNone(shared.ack.turn)


if __name__ == "__main__":
    unittest.main()
