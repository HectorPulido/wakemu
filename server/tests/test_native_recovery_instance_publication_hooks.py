"""Pure actual Connection AST and publication lifecycle regressions."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import struct
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_instance_publication import (
    InstancePublicationTracker,
    require_current_publication,
)
from wakfu_server.maps.proto_dungeon import encode

HERE = Path(__file__).parent / "fixtures/native_monster_recovery"
SCOPE = (7, "session-generation", 17, 1385, 0)


def frames(level=2, opcode=13974, instance=0):
    context = encode({"difficulty_level": level})
    if opcode == 13974:
        payload = b"".join(
            struct.pack(">H", len(b)) + b
            for b in (b"actual-entity", b"", b"\0\0", context)
        )
    else:
        payload = struct.pack(">qi", instance, len(context)) + context
    return struct.pack(">IH", 6 + len(payload), opcode) + payload


def fight():
    return SimpleNamespace(
        actors={17: SimpleNamespace(id=17), 99: SimpleNamespace(id=99)}
    )


class PublicationHookTests(unittest.TestCase):
    def setUp(self):
        self.tracker = InstancePublicationTracker()

    def bind(self, f):
        return self.tracker.bind_encounter(f, SCOPE, npc_ids=(99,), player_id=17)

    def test_no_publication_means_no_default_snapshot(self):
        f = fight()
        self.assertFalse(self.bind(f))
        self.assertFalse(hasattr(f, "native_instance_difficulty_snapshots"))
        with self.assertRaises(ValueError):
            require_current_publication(f)

    def test_bootstrap_binds_real_two_and_player_explicit_empty(self):
        self.tracker.after_write(frames(), SCOPE)
        f = fight()
        self.assertTrue(self.bind(f))
        require_current_publication(f)
        self.assertEqual(f.native_instance_difficulty_snapshots[99].difficulty, 2)
        self.assertIsNone(f.native_instance_difficulty_snapshots[17].difficulty)

    def test_context_update_revokes_original_and_deepcopied_encounter(self):
        self.tracker.after_write(frames(), SCOPE)
        f = fight()
        self.bind(f)
        copy = deepcopy(f)
        require_current_publication(copy)
        self.tracker.after_write(frames(7, 13339), SCOPE)
        for candidate in (f, copy):
            with self.assertRaises(ValueError):
                require_current_publication(candidate)

    def test_generation_character_map_instance_change_revokes(self):
        for index, value in ((0, 8), (1, "replaced"), (2, 18), (3, 527), (4, 42)):
            t = InstancePublicationTracker()
            t.after_write(frames(), SCOPE)
            f = fight()
            t.bind_encounter(f, SCOPE, npc_ids=(99,), player_id=17)
            changed = list(SCOPE)
            changed[index] = value
            t.synchronize(tuple(changed))
            with self.assertRaises(ValueError):
                require_current_publication(f)

    def test_disconnect_revokes_lease(self):
        self.tracker.after_write(frames(), SCOPE)
        f = fight()
        self.bind(f)
        self.tracker.invalidate()
        with self.assertRaises(ValueError):
            require_current_publication(f)

    def test_same_payload_new_publication_has_distinct_nonce(self):
        self.tracker.after_write(frames(), SCOPE)
        one = self.tracker.lease.current
        self.tracker.after_write(frames(), SCOPE)
        two = self.tracker.lease.current
        self.assertNotEqual(one, two)
        self.assertEqual(one[3], two[3])

    def test_noncontext_batch_preserves_current_publication(self):
        self.tracker.after_write(frames(), SCOPE)
        original = self.tracker.lease.current
        self.tracker.after_write(struct.pack(">IH", 6, 12318), SCOPE)
        self.assertEqual(self.tracker.lease.current, original)

    def test_wrong_instance_or_partial_frame_revokes(self):
        for data in (frames(7, 13339, 42), frames()[:-1]):
            self.tracker.after_write(frames(), SCOPE)
            with self.assertRaises(ValueError):
                self.tracker.after_write(data, SCOPE)
            self.assertIsNone(self.tracker.lease.current)

    def test_actor_binding_must_cover_exact_serialized_roster(self):
        self.tracker.after_write(frames(), SCOPE)
        with self.assertRaises(ValueError):
            self.tracker.bind_encounter(fight(), SCOPE, npc_ids=(98,), player_id=17)

    def test_actual_connection_class_captures_only_after_successful_write(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        cls = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "Connection"
        )
        module = ModuleType("wakfu_server.combat_instance_publication")
        module.InstancePublicationTracker = InstancePublicationTracker
        namespace = {
            "threading": threading,
            "PROFILER": SimpleNamespace(span=lambda *a: nullcontext()),
        }
        with patch.dict(
            sys.modules, {"wakfu_server.combat_instance_publication": module}
        ):
            exec(
                compile(
                    ast.Module(body=[cls], type_ignores=[]),
                    "<actual-private-Connection>",
                    "exec",
                ),
                namespace,
            )
            socket = SimpleNamespace(sendall=lambda data: None)
            connection = namespace["Connection"](socket)
            connection.native_instance_scope = lambda: SCOPE
            connection.sendall(frames())
            self.assertIsNotNone(connection.instance_publications.lease.current)

            def failed(data):
                raise OSError("actual socket failure")

            socket.sendall = failed
            with self.assertRaises(OSError):
                connection.sendall(frames(7))
            self.assertIsNone(connection.instance_publications.lease.current)

    def test_original_bootstrap_ast_unchanged_and_hook_precedes_passives(self):
        original_dump = (HERE / "owned-native-bootstrap.ast").read_text()
        private = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )

        def function(tree, name):
            return next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name
            )

        self.assertEqual(
            original_dump, ast.dump(function(private, "owned_native_bootstrap"))
        )
        session = function(private, "session")
        binds = [
            n.lineno
            for n in ast.walk(session)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "bind_encounter"
        ]
        initials = [
            n.lineno
            for n in ast.walk(session)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "initialize_fight_snapshots"
        ]
        self.assertEqual(len(binds), 1)
        self.assertTrue(any(line > binds[0] for line in initials))


if __name__ == "__main__":
    unittest.main()
