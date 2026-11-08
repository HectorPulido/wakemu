import ast
from threading import Event, RLock, Thread
import unittest
from types import ModuleType, SimpleNamespace
from pathlib import Path
from unittest.mock import patch


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _function(tree, name):
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, got {len(matches)}")
    return matches[0]


class SpectatorTerminalDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf8")
        cls.tree = ast.parse(cls.source)
        cls.session = _function(cls.tree, "session")
        cls.idle = _function(cls.tree, "idle")

    def test_poll_preserves_terminal_identity_before_subscription_cleanup(self):
        poll_calls = [
            node
            for node in ast.walk(self.idle)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "poll"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "SPECTATORS"
        ]
        self.assertEqual(len(poll_calls), 1)
        poll_line = poll_calls[0].lineno
        close_line = next(
            node.lineno
            for node in ast.walk(self.idle)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "record"
            and any(
                keyword.arg == "event"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "combat_spectator_subscription_closed"
                for keyword in node.keywords
            )
        )
        self.assertLess(poll_line, close_line)
        self.assertIn("spectator_terminal_pending", self.source)
        self.assertIn("TerminalAck(", self.source)

    def test_finished_preview_delivers_lethal_events_but_waits_for_committed_cleanup(
        self,
    ):
        published = []
        registry = SimpleNamespace(
            fights={106: SimpleNamespace(revision=4)},
            publish_events=lambda fight_id, **kwargs: published.append(
                (fight_id, kwargs)
            ),
        )
        from wakfu_server.performance_profiler import PROFILER

        scope = {
            "COMBAT_TEST": True,
            "PROFILER": PROFILER,
            "SPECTATORS": registry,
        }
        function = _function(self.tree, "publish_spectator_state")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        abandon = ModuleType("wakfu_server.combat_abandon")
        abandon.committed_abandon_team = lambda _: None
        abandon.aborted_terminal_packets = lambda *args, **kwargs: ()
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=106, phase="finished"),
            settlement_ready=False,
            sequence=9,
            lock=RLock(),
        )
        with patch.dict("sys.modules", {"wakfu_server.combat_abandon": abandon}):
            scope["publish_spectator_state"](
                shared, ((12727, b"death"), (12238, b"premature-end"))
            )
            self.assertEqual(
                published,
                [(106, {"revision": 9, "event_packets": ((12727, b"death"),)})],
            )
            scope["publish_spectator_state"](shared)
        self.assertEqual(len(published), 1)

    def test_terminal_ack_route_validates_lease_and_refreshes_world_without_participant_state(
        self,
    ):
        branches = [
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and ast.dump(node.test)
            == ast.dump(
                ast.parse(
                    "opcode == 12925 and loaded and spectator_terminal_pending is not None",
                    mode="eval",
                ).body
            )
        ]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        calls = [
            node.func.id
            for node in ast.walk(branch)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertIn("refresh_owned_world_after_spectating", calls)
        self.assertIn("record", calls)
        self.assertIn("pending_ack.validate", self.source)
        self.assertIn("STORE.current_session(account_id, generation)", self.source)
        participant_branch = next(
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and ast.dump(node.test)
            == ast.dump(
                ast.parse(
                    "opcode == 12925 and fight_messages is not None",
                    mode="eval",
                ).body
            )
        )
        self.assertGreater(participant_branch.lineno, branch.lineno)

    def test_rejected_refresh_keeps_committed_actions_and_invalidates_cached_entry(
        self,
    ):
        from wakfu_server.performance_profiler import PROFILER

        published, invalidated, logs = [], [], []
        registry = SimpleNamespace(
            fights={106: SimpleNamespace(revision=4)},
            invalidate_snapshot=lambda fight_id: invalidated.append(fight_id),
            has_subscribers=lambda fight_id: True,
            publish_events=lambda fight_id, **kwargs: published.append(
                (fight_id, kwargs)
            ),
        )

        def reject(_shared):
            raise ValueError("Unverified native remote effect container absence")

        scope = {
            "COMBAT_TEST": True,
            "PROFILER": PROFILER,
            "SPECTATORS": registry,
            "spectator_waiting_for_ack": lambda _: False,
            "spectator_snapshot": reject,
            "ObserverSession": lambda *a: a,
            "record": lambda **kw: logs.append(kw),
        }
        function = _function(self.tree, "publish_spectator_state")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        abandon = ModuleType("wakfu_server.combat_abandon")
        abandon.committed_abandon_team = lambda _: None
        abandon.aborted_terminal_packets = lambda *args, **kwargs: ()
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=106, phase="active"),
            participants={},
            sequence=5,
            lock=RLock(),
        )
        events = ((13091, b"summon"), (13624, b"movement"), (12588, b"spell"))
        with patch.dict("sys.modules", {"wakfu_server.combat_abandon": abandon}):
            scope["publish_spectator_state"](shared, events)
        self.assertEqual(invalidated, [106])
        self.assertEqual(published, [(106, {"revision": 5, "event_packets": events})])
        self.assertEqual(logs[0]["event"], "combat_spectator_snapshot_rejected")
        # A failed explicit entry refresh also fences an old snapshot when it
        # has no new action batch to publish.
        with patch.dict("sys.modules", {"wakfu_server.combat_abandon": abandon}):
            scope["publish_spectator_state"](shared)
        self.assertEqual(invalidated, [106, 106])
        self.assertEqual(len(published), 1)

    def test_unobserved_updates_skip_snapshot_and_fresh_entries_resume_publications(
        self,
    ):
        from wakfu_server.combat_spectators import ObserverSession, SpectatorRegistry
        from wakfu_server.performance_profiler import PROFILER
        from test_combat_spectators import native_snapshot

        owner = ObserverSession(1, 10, "owner", 1134, 7)
        observer = ObserverSession(2, 20, "observer", 1134, 7)
        registry = SpectatorRegistry(lambda session: session in (owner, observer))
        registry.publish_fight(
            900,
            map_id=1134,
            instance_id=7,
            participant_sessions=(owner,),
            revision=1,
            snapshot_packets=(native_snapshot(900),),
            visible=True,
        )
        snapshots = []

        def snapshot(shared):
            snapshots.append(shared.sequence)
            return (native_snapshot(900, marker=str(shared.sequence).encode()),)

        scope = dict(
            COMBAT_TEST=True,
            PROFILER=PROFILER,
            SPECTATORS=registry,
            spectator_waiting_for_ack=lambda _: False,
            spectator_snapshot=snapshot,
            ObserverSession=ObserverSession,
            record=lambda **kwargs: self.fail(str(kwargs)),
        )
        function = _function(self.tree, "publish_spectator_state")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=900, phase="placement"),
            participants={1: owner},
            sequence=2,
            map_id=1134,
            instance_id=7,
            lock=RLock(),
        )
        publish = scope["publish_spectator_state"]
        for sequence in range(2, 32):
            shared.sequence = sequence
            publish(shared, ((13624, b"movement"),))
        self.assertEqual(snapshots, [])
        with self.assertRaisesRegex(ValueError, "snapshot is not current"):
            registry.enter(observer, 900, authorize=lambda *_: True)
        publish(shared, force_snapshot=True)
        entered = registry.enter(observer, 900, authorize=lambda *_: True)
        self.assertEqual(entered.revision, 31)
        shared.sequence = 32
        event = ((13624, b"observed-movement"),)
        publish(shared, event)
        self.assertEqual([batch.packets for batch in registry.poll(observer)], [event])
        registry.leave(observer, 900)
        shared.sequence = 33
        publish(shared)
        self.assertEqual(snapshots, [31, 32])
        registry.defer_enter(observer, 900, authorize=lambda *_: True)
        publish(shared)
        self.assertEqual(snapshots, [31, 32, 33])
        delivery = registry.poll(observer)
        self.assertEqual(len(delivery), 1)
        self.assertTrue(delivery[0].is_snapshot)
        self.assertEqual(delivery[0].revision, 33)

    def test_initial_and_update_spectator_publications_serialize_under_shared_lock(
        self,
    ):
        from wakfu_server.performance_profiler import PROFILER

        first_snapshot_entered = Event()
        release_first_snapshot = Event()
        second_snapshot_entered = Event()
        errors = []

        class Registry:
            def __init__(self):
                self.fights = {}
                self.publications = []

            def publish_fight(self, fight_id, **payload):
                if fight_id in self.fights:
                    raise AssertionError("Duplicate initial spectator publication")
                self.fights[fight_id] = SimpleNamespace(revision=payload["revision"])
                self.publications.append(("initial", payload["revision"], ()))

            def has_subscribers(self, fight_id):
                return True

            def publish_update(self, fight_id, **payload):
                current = self.fights[fight_id]
                if payload["revision"] <= current.revision:
                    raise AssertionError("Spectator update revision did not advance")
                current.revision = payload["revision"]
                self.publications.append(
                    ("update", payload["revision"], payload["event_packets"])
                )

        registry = Registry()

        def snapshot(_shared):
            if not first_snapshot_entered.is_set():
                first_snapshot_entered.set()
                if not release_first_snapshot.wait(2):
                    raise AssertionError("First publication was not released")
            else:
                second_snapshot_entered.set()
            return ("snapshot",)

        scope = {
            "COMBAT_TEST": True,
            "PROFILER": PROFILER,
            "SPECTATORS": registry,
            "spectator_waiting_for_ack": lambda _: False,
            "spectator_snapshot": snapshot,
            "ObserverSession": lambda *values: values,
            "record": lambda **values: None,
        }
        function = _function(self.tree, "publish_spectator_state")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        abandon = ModuleType("wakfu_server.combat_abandon")
        abandon.committed_abandon_team = lambda _: None
        abandon.aborted_terminal_packets = lambda *args, **kwargs: ()
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=106, phase="placement"),
            participants={},
            sequence=1,
            map_id=527,
            instance_id=0,
            lock=RLock(),
        )

        def publish(event_packets=()):
            try:
                scope["publish_spectator_state"](shared, event_packets)
            except BaseException as error:
                errors.append(error)

        first = Thread(target=publish)
        action = ((12588, b"committed-owner-action"),)
        second = Thread(target=publish, args=(action,))
        with patch.dict("sys.modules", {"wakfu_server.combat_abandon": abandon}):
            first.start()
            self.assertTrue(first_snapshot_entered.wait(2))
            second.start()
            self.assertFalse(second_snapshot_entered.wait(0.05))
            release_first_snapshot.set()
            first.join(2)
            second.join(2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(
            registry.publications,
            [("initial", 1, ()), ("update", 2, action)],
        )

    def test_placement_dispatch_drains_authoritative_positions_without_public_events(
        self,
    ):
        from wakfu_server.performance_profiler import PROFILER

        position_packet = (13652, b"new-authoritative-placement")
        owner = SimpleNamespace(account_id=1, character_id=16, generation="owner")
        shared = SimpleNamespace(fight=SimpleNamespace(id=106))
        sent, publications = [], []
        adapter = SimpleNamespace(
            dispatch_connected=lambda fight_id, deliver, **_kwargs: deliver(
                owner,
                [
                    SimpleNamespace(
                        sequence=5, packets=(position_packet,), public_events=()
                    )
                ],
            ),
            registry=SimpleNamespace(lookup=lambda _: shared),
        )
        scope = {
            "PROFILER": PROFILER,
            # This isolated placement path is healthy and does not exercise
            # the raced-expiry branch. Preserve the wrapped body while leaving
            # expiry behavior to test_combat_reconnect_expiry_dispatch.
            "combat_reconnect_expiry_boundary": lambda operation: operation,
            "recover_expired_combat_presentation": lambda **kwargs: False,
            "combat_session": owner,
            "fight": shared.fight,
            "COMBAT_SESSIONS": adapter,
            "publish_external_marker": lambda _: None,
            "publish_spectator_state": lambda current, packets: publications.append(
                (current, packets)
            ),
            "send_batch": lambda connection, service, packets: sent.append(packets),
            "connection": None,
            "service": None,
        }
        function = _function(self.tree, "drain_shared_combat")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        placement = next(
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and ast.dump(node.test)
            == ast.dump(
                ast.parse("opcode == 12806 and fight is not None", mode="eval").body
            )
        )
        calls = [
            node.func.id
            for node in ast.walk(placement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertIn("drain_shared_combat", calls)
        scope["drain_shared_combat"]()
        self.assertEqual(sent, [(position_packet,)])
        self.assertEqual(publications, [])


if __name__ == "__main__":
    unittest.main()
