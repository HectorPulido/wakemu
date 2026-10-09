"""Joined owned fighters enter the existing native PV/QI population."""
import ast
import struct
import unittest
from pathlib import Path

from wakfu_server.combat_global_pv_collections import (
    global_fighter_guards,
    global_fighter_registered,
    initialize_global_pv_collections,
)
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.placement_deadline import Deadline


class JoinedNativeFighterRegistrationTests(unittest.TestCase):
    def fixture(self):
        first = Actor(7, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True)
        monster = Actor(-7, 1, (4, 0, 0), 40, 4, 2, 10, 1)
        for actor in (first, monster):
            actor.physical_radius = 0
            actor.native_physical_position = actor.position
        fight = Fight(
            99,
            [first, monster],
            {(x, 0, 0) for x in range(5)},
            {0: {(0, 0, 0), (1, 0, 0), (2, 0, 0)}, 1: {(4, 0, 0)}},
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=5, height=1, cell_masks=[128] * 5
        )
        initialize_global_pv_collections(fight, (7, -7))
        fresh = prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        install_fresh_actor_slots(fight, fresh)
        first_session = Session(1, 7, "first", 1134, 0)
        joiner_session = Session(2, 8, "joiner", 1134, 0)
        live = {first_session, joiner_session}
        registry = Registry(lambda session: session in live)
        shared = registry.register(
            fight,
            first_session,
            runtime=None,
            join_context={"leaders": {0: 7, 1: -7}},
        )
        joined_actor = Actor(8, 0, (3, 0, 0), 55, 6, 3, 90, 1, 2, True)
        joined_actor.physical_radius = 0
        joined_actor.native_physical_position = joined_actor.position
        return registry, shared, first_session, joiner_session, joined_actor

    @staticmethod
    def join(registry, session, actor, persist_member=None):
        return registry.join(
            session,
            struct.pack(">qB", 7, 0),
            actor,
            actor_payload=lambda *_: (b"joined-stats", b"joined-effects"),
            bootstrap_packets=lambda *_: [(12847, b"placement")],
            persist_member=persist_member,
        )

    def test_join_registers_global_pv_and_qi_before_either_ready_order(self):
        for order in ((0, 1), (1, 0)):
            with self.subTest(ready_order=order):
                registry, shared, first, joiner, actor = self.fixture()
                self.join(registry, joiner, actor)
                joined = shared.fight.actors[8]
                self.assertEqual(joined.position, (1, 0, 0))
                self.assertEqual(joined.native_physical_position, (1, 0, 0))
                self.assertTrue(global_fighter_registered(shared.fight, 8))
                self.assertEqual(
                    global_fighter_guards(shared.fight, 8),
                    {"baF": True, "baG": False, "baK": False},
                )
                qi = current_registry(shared.fight)
                self.assertEqual(joined.native_obstacle_id, 2)
                self.assertEqual(
                    qi.slots[2],
                    dict(
                        identity=["actor", 8],
                        position=[1, 0],
                        radius=0,
                        indexed=True,
                        movement_blocking=True,
                    ),
                )
                sessions = (first, joiner)
                for index in order:
                    registry.ready(99, sessions[index], True, lambda *_: ())
                    if index != order[-1]:
                        self.assertEqual(shared.fight.phase, "placement")
                self.assertEqual(shared.fight.phase, "active")
                self.assertIn(8, shared.fight.order)
                current_registry(shared.fight)

    def test_join_persistence_failure_does_not_publish_pv_or_qi_registration(self):
        registry, shared, _, joiner, actor = self.fixture()
        original = shared.fight

        def fail_persistence(*_):
            raise ValueError("injected participant persistence failure")

        with self.assertRaisesRegex(ValueError, "persistence failure"):
            self.join(registry, joiner, actor, persist_member=fail_persistence)

        self.assertIs(shared.fight, original)
        self.assertNotIn(8, shared.fight.actors)
        self.assertNotIn(8, registry.by_character)
        self.assertNotIn(
            "8", shared.fight.native_global_pv_collections["fighter_status"]
        )
        self.assertEqual(len(current_registry(shared.fight).slots), 127)

    def test_joined_roster_deadline_expires_once_then_both_ready_owners_start(self):
        registry, shared, first, joiner, actor = self.fixture()
        self.join(registry, joiner, actor)
        deadlines = (Deadline(), Deadline())
        for deadline in deadlines:
            deadline.start(shared.fight.id, 1000, 10.0)

        self.assertFalse(deadlines[0].take_expired(shared.fight, 10.999))
        self.assertTrue(deadlines[0].take_expired(shared.fight, 11.0))
        self.assertFalse(deadlines[0].take_expired(shared.fight, 12.0))
        self.assertTrue(deadlines[1].take_expired(shared.fight, 11.0))
        for session in (first, joiner):
            registry.ready(99, session, True, lambda *_: ())
        self.assertEqual(shared.fight.phase, "active")
        self.assertEqual(set(shared.fight.order), {7, 8, -7})

    def test_real_join_dispatch_starts_deadline_after_membership_commit(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        join_branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13241 and loaded and COMBAT_TEST"
        )
        join_call = next(
            node
            for node in ast.walk(join_branch)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "COMBAT_SESSIONS.join"
        )
        deadline_call = next(
            node
            for node in ast.walk(join_branch)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "placement_deadline.start"
        )
        self.assertLess(join_call.lineno, deadline_call.lineno)
        self.assertEqual(
            [ast.unparse(argument) for argument in deadline_call.args],
            ["fight.id", "context['duration_ms']", "fight_started_at"],
        )


if __name__ == "__main__":
    unittest.main()
