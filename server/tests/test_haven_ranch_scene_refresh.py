"""Actual per-recipient Ranch idle refresh, without a native catalog load."""
import ast
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from wakfu_server.world import World


class RanchSceneRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.path.read_text())
        cls.function = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "deliver_ranch_scene_refresh"
        )
        cls.clear_line = max(
            n.lineno
            for n in ast.walk(cls.function)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Constant)
            and n.value.value is None
        )

    def fixture(
        self, *, owns=True, combat=None, pending=True, error_stage=None, on_mark=None
    ):
        actor = dict(id=41, account_id=7, map_id=1440, instance_id=17)
        peer = SimpleNamespace(ranch_scene_refresh=None)
        world = World(Mock(), Mock(), Mock())
        world.players[41] = ("lease", peer, actor)
        if pending:
            world.request_ranch_scene_refresh(1440, 17)
        sent, events = [], []
        bootstrap = Mock(
            return_value=[(13256, b""), (13864, b"host7"), (13974, b"actor41")]
        )
        if error_stage == "bootstrap":
            bootstrap.side_effect = ValueError("read failure")

        def send(*args):
            sent.append(args[2:])
            if error_stage == "send":
                raise OSError("write failure")

        mark = Mock(side_effect=on_mark)
        if error_stage == "mark":
            mark.side_effect = ValueError("retry scheduling failure")
        ns = dict(
            connection=peer,
            character=actor,
            generation="lease",
            WORLD=world,
            ranch_session=SimpleNamespace(owns=lambda current: owns),
            fight=object() if combat == "fight" else None,
            combat_session=object() if combat == "combat" else None,
            spectator_session=object() if combat == "spectator" else None,
            pending_combat_return=object() if combat == "return" else None,
            combat_return_bootstrap=bootstrap,
            mark_static_sync_pending=mark,
            send=send,
            service="world",
            record=lambda **event: events.append(event),
        )
        code = compile(
            ast.fix_missing_locations(
                ast.Module(body=[cls_copy(self.function)], type_ignores=[])
            ),
            str(self.path),
            "exec",
        )
        exec(code, ns)
        return SimpleNamespace(
            run=ns["deliver_ranch_scene_refresh"],
            ns=ns,
            peer=peer,
            world=world,
            bootstrap=bootstrap,
            mark=mark,
            sent=sent,
            events=events,
        )

    def test_own_bootstrap_order_and_capture_are_preserved(self):
        fixture = self.fixture()
        fixture.run()
        self.assertEqual(
            fixture.sent, [(13256, b""), (13864, b"host7"), (13974, b"actor41")]
        )
        fixture.mark.assert_called_once()
        self.assertIsNone(fixture.peer.ranch_scene_refresh)
        self.assertEqual(fixture.events[-1]["actor_id"], 41)
        fixture.run()
        fixture.bootstrap.assert_called_once()

    def test_stale_actor_lease_scope_or_capability_is_discarded(self):
        for index, value in ((0, 42), (1, "old"), (2, 527), (3, 99)):
            fixture = self.fixture()
            pending = list(fixture.peer.ranch_scene_refresh)
            pending[index] = value
            fixture.peer.ranch_scene_refresh = tuple(pending)
            fixture.run()
            self.assertIsNone(fixture.peer.ranch_scene_refresh)
            fixture.bootstrap.assert_not_called()
        fixture = self.fixture(owns=False)
        fixture.run()
        fixture.bootstrap.assert_not_called()
        self.assertIsNone(fixture.peer.ranch_scene_refresh)

    def test_combat_or_pending_return_defers_without_consuming(self):
        for combat in ("fight", "combat", "spectator", "return"):
            fixture = self.fixture(combat=combat)
            pending = fixture.peer.ranch_scene_refresh
            fixture.run()
            self.assertEqual(fixture.peer.ranch_scene_refresh, pending)
            fixture.bootstrap.assert_not_called()
            self.assertFalse(fixture.sent)

    def test_failure_retains_captured_request_for_retry(self):
        for stage in ("bootstrap", "send", "mark"):
            fixture = self.fixture(error_stage=stage)
            pending = fixture.peer.ranch_scene_refresh
            with self.assertRaises((ValueError, OSError)):
                fixture.run()
            self.assertEqual(fixture.peer.ranch_scene_refresh, pending)
            self.assertFalse(fixture.events)

    def test_newer_request_during_success_is_not_consumed(self):
        fixture = self.fixture()
        fixture.mark.side_effect = lambda: fixture.world.request_ranch_scene_refresh(
            1440, 17
        )
        first = fixture.peer.ranch_scene_refresh
        fixture.run()
        self.assertGreater(fixture.peer.ranch_scene_refresh[4], first[4])

    def test_newer_request_between_compare_and_clear_is_not_lost(self):
        fixture = self.fixture()
        paused, release, producer_started, producer_done = (
            threading.Event() for _ in range(4)
        )
        errors = []

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code.co_name == "deliver_ranch_scene_refresh"
                and frame.f_lineno == self.clear_line
            ):
                paused.set()
                if not release.wait(2):
                    raise AssertionError("Timed out releasing idle worker")
            return trace

        def consume():
            sys.settrace(trace)
            try:
                fixture.run()
            except BaseException as error:
                errors.append(error)
            finally:
                sys.settrace(None)

        def produce():
            producer_started.set()
            fixture.world.request_ranch_scene_refresh(1440, 17)
            producer_done.set()

        consumer = threading.Thread(target=consume)
        producer = threading.Thread(target=produce)
        consumer.start()
        try:
            self.assertTrue(paused.wait(2))
            producer.start()
            self.assertTrue(producer_started.wait(2))
            producer_done.wait(0.1)
        finally:
            release.set()
            consumer.join(2)
            if producer.ident is not None:
                producer.join(2)
        self.assertFalse(errors)
        self.assertFalse(consumer.is_alive())
        self.assertFalse(producer.is_alive())
        self.assertIsNotNone(fixture.peer.ranch_scene_refresh)
        self.assertGreater(fixture.peer.ranch_scene_refresh[4], 1)


def cls_copy(node):
    from copy import deepcopy

    return deepcopy(node)
