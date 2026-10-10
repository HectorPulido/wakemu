import ast
import unittest
from types import SimpleNamespace
from pathlib import Path


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
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=106, phase="finished"),
            settlement_ready=False,
            sequence=9,
        )
        scope["publish_spectator_state"](
            shared, ((12727, b"death"), (12238, b"premature-end"))
        )
        self.assertEqual(
            published, [(106, {"revision": 9, "event_packets": ((12727, b"death"),)})]
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
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=106, phase="active"),
            participants={},
            sequence=5,
        )
        events = ((13091, b"summon"), (13624, b"movement"), (12588, b"spell"))
        scope["publish_spectator_state"](shared, events)
        self.assertEqual(invalidated, [106])
        self.assertEqual(published, [(106, {"revision": 5, "event_packets": events})])
        self.assertEqual(logs[0]["event"], "combat_spectator_snapshot_rejected")
        # A failed explicit entry refresh also fences an old snapshot when it
        # has no new action batch to publish.
        scope["publish_spectator_state"](shared)
        self.assertEqual(invalidated, [106, 106])
        self.assertEqual(len(published), 1)

    def test_placement_dispatch_drains_and_publishes_authoritative_positions(self):
        from wakfu_server.performance_profiler import PROFILER

        position_packet = (13652, b"new-authoritative-placement")
        owner = SimpleNamespace(account_id=1, character_id=16, generation="owner")
        shared = SimpleNamespace(fight=SimpleNamespace(id=106))
        sent, publications = [], []
        adapter = SimpleNamespace(
            dispatch_connected=lambda fight_id, deliver: deliver(
                owner, [SimpleNamespace(sequence=5, packets=(position_packet,))]
            ),
            registry=SimpleNamespace(lookup=lambda _: shared),
        )
        scope = {
            "PROFILER": PROFILER,
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
        self.assertEqual(publications, [(shared, (position_packet,))])


if __name__ == "__main__":
    unittest.main()
