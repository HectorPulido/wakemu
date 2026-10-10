"""Native party combat prompts never admit a character on their own."""
import ast
import struct
from pathlib import Path
import unittest
from contextlib import nullcontext
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock

from wakfu_server.combat.combat_party_prompt import (
    accepted_join_request,
    notify,
    packet,
)


class PartyCombatPromptTests(unittest.TestCase):
    def setUp(self):
        self.starter = dict(
            id=1, account_id=10, map_id=7, instance_id=4, x=0, y=0, z=3, hp=100
        )
        self.member = dict(
            id=2, account_id=20, map_id=7, instance_id=4, x=2, y=3, z=3, hp=100
        )
        actor = SimpleNamespace(
            id=1, controlled=True, hp=100, team=0, position=(0, 0, 3)
        )
        self.shared = SimpleNamespace(
            lock=RLock(),
            auto_locked=False,
            map_id=7,
            instance_id=4,
            participants={10: SimpleNamespace(character_id=1)},
            fight=SimpleNamespace(
                phase="placement",
                actors={1: actor},
                placement={0: {(0, 0, 3), (1, 0, 3)}},
            ),
        )
        self.db = Mock()
        self.db.execute.return_value.fetchall.return_value = [{"character_id": 2}]
        self.store = Mock()
        self.store.connection.side_effect = lambda: nullcontext(self.db)
        self.store.current_character_session.return_value = True
        self.world = Mock()
        self.identities = {
            1: ("starter-lease", self.starter),
            2: ("member-lease", self.member),
        }
        self.world.live_identity.side_effect = lambda **kw: self.identities.get(
            kw["character_id"]
        )
        self.world.send_to.return_value = True
        self.sessions = Mock()
        self.sessions.lookup_character.return_value = None

    def run_notify(self):
        return notify(self.store, self.world, self.sessions, self.shared, 1)

    def test_native_packet_and_existing_join_target(self):
        self.assertEqual(packet(1), (13599, struct.pack(">q", 1)))
        self.assertEqual(self.run_notify(), 1)
        self.world.send_to.assert_called_once_with(
            2, "member-lease", 13599, struct.pack(">q", 1)
        )
        self.sessions.join.assert_not_called()
        self.assertIn("source.party_id=m.party_id", self.db.execute.call_args[0][0])
        self.assertIn("NOT EXISTS", self.db.execute.call_args[0][0])

    def test_other_map_instance_distance_and_dead_characters_are_excluded(self):
        for changes in (
            {"map_id": 8},
            {"instance_id": 5},
            {"x": 26},
            {"hp": 0},
            {"health_dead": True},
            {"account_id": 10},
        ):
            with self.subTest(changes=changes):
                self.member.clear()
                self.member.update(
                    id=2, account_id=20, map_id=7, instance_id=4, x=2, y=3, z=3, hp=100
                )
                self.member.update(changes)
                self.assertEqual(self.run_notify(), 0)
        self.world.send_to.assert_not_called()

    def test_busy_offline_or_replaced_session_is_not_prompted(self):
        self.sessions.lookup_character.return_value = object()
        self.assertEqual(self.run_notify(), 0)
        self.sessions.lookup_character.return_value = None
        self.store.current_character_session.return_value = False
        self.assertEqual(self.run_notify(), 0)
        self.identities.pop(2)
        self.assertEqual(self.run_notify(), 0)
        self.world.send_to.assert_not_called()

    def test_active_locked_duel_and_full_team_are_not_prompted(self):
        self.shared.fight.phase = "active"
        self.assertEqual(self.run_notify(), 0)
        self.shared.fight.phase = "placement"
        self.shared.auto_locked = True
        self.assertEqual(self.run_notify(), 0)
        self.shared.auto_locked = False
        self.shared.is_duel = True
        self.assertEqual(self.run_notify(), 0)
        self.shared.is_duel = False
        self.shared.fight.placement[0] = {(0, 0, 3)}
        self.assertEqual(self.run_notify(), 0)
        self.world.send_to.assert_not_called()
        self.store.connection.assert_not_called()

    def test_transport_failure_does_not_admit_member(self):
        self.world.send_to.return_value = False
        self.assertEqual(self.run_notify(), 0)
        self.sessions.join.assert_not_called()

    def test_modal_acceptance_joins_without_locking_fight(self):
        from wakfu_server.combat.combat_multiplayer_wire import decode_join

        normalized = accepted_join_request(struct.pack(">qB", 1, 1))
        self.assertEqual(decode_join(normalized), {"target_id": 1, "auto_lock": False})

    def test_modal_refusal_or_timeout_does_not_generate_join_request(self):
        self.assertIsNone(accepted_join_request(struct.pack(">qB", 1, 0)))

    def test_modal_malformed_answers_are_rejected(self):
        for malformed in (b"", struct.pack(">qB", 1, 2), struct.pack(">qB", 0, 0)):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                accepted_join_request(malformed)

    def test_dispatcher_normalizes_acceptance_and_skips_refusal_and_timeout(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 12197
                    for value in test.comparators
                )
                for test in ast.walk(node.test)
            )
        )
        tail = ast.parse("handled.append((opcode, body))").body[0]
        harness = ast.Module(
            body=[
                ast.For(
                    target=ast.Name(id="step", ctx=ast.Store()),
                    iter=ast.List(elts=[ast.Constant(0)], ctx=ast.Load()),
                    body=[branch, tail],
                    orelse=[],
                )
            ],
            type_ignores=[],
        )
        code = compile(
            ast.fix_missing_locations(harness), "native-answer-routing", "exec"
        )
        for body, expected in (
            (struct.pack(">qB", 1, 1), [(13241, struct.pack(">qB", 1, 0))]),
            (struct.pack(">qB", 1, 0), []),
            (b"malformed", []),
        ):
            state = dict(
                opcode=12197,
                body=body,
                loaded=True,
                COMBAT_TEST=True,
                handled=[],
                record=Mock(),
            )
            exec(code, state)
            self.assertEqual(state["handled"], expected)

    def test_packet_rejects_invalid_actor_id(self):
        for actor_id in (0, -1, True, 2**63, "1"):
            with self.subTest(actor_id=actor_id), self.assertRaises(ValueError):
                packet(actor_id)


if __name__ == "__main__":
    unittest.main()
