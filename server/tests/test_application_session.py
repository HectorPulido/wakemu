"""Exercise extracted production routing, transport and live session callbacks.

Domain operation spies isolate routing decisions; actual network framing and
Session.run execute without a database, World bootstrap or background workers.
"""

from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import runpy
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import Mock, patch

from wakfu_server.application.dispatch_result import DispatchResult
from wakfu_server.application.network_delivery import (
    NetworkDelivery,
    PendingSessionWork,
)
from wakfu_server.application.session import Session
from wakfu_server.application.transport import Connection


def frame(opcode, body=b""):
    return struct.pack(">IH", 6 + len(body), opcode) + body


def session_fixture(**state):
    session = object.__new__(Session)
    session.runtime = SimpleNamespace(
        COMBAT_TEST=True,
        GUILD_REQUEST_OPCODES=frozenset(),
        record=Mock(),
    )
    session.state = SimpleNamespace(
        opcode=65500,
        body=b"",
        service="world",
        loaded=True,
        account_id=1,
        generation="selected-generation",
        character={"id": 7},
        fight=None,
        fight_messages=None,
        aborted_native_return=None,
        pve_withdrawal_pending=None,
        spectator_terminal_pending=None,
        artifact_action_request=False,
        ranch_session=None,
        encounter_world_action=None,
        rift_start_run=None,
    )
    vars(session.state).update(state)
    return session


class SessionRoutingTests(unittest.TestCase):
    def assert_route(self, session, expected, alternatives=()):
        selected = Mock(return_value=DispatchResult.FALLTHROUGH)
        setattr(session, expected, selected)
        for name in alternatives:
            setattr(
                session, name, Mock(side_effect=AssertionError("wrong route: " + name))
            )
        self.assertIs(session.dispatch_request(), DispatchResult.FALLTHROUGH)
        selected.assert_called_once_with()

    def test_direction_routes_to_fight_before_loaded_world_requirements(self):
        self.assert_route(
            session_fixture(opcode=13655),
            "handle_world_direction",
            ("handle_fight_direction",),
        )
        self.assert_route(
            session_fixture(opcode=13655, loaded=False, fight=object()),
            "handle_fight_direction",
            ("handle_world_direction",),
        )
        unloaded = session_fixture(opcode=13655, loaded=False)
        self.assertIs(unloaded.dispatch_request(), DispatchResult.FALLTHROUGH)
        self.assertEqual(
            unloaded.runtime.record.call_args.kwargs["event"], "request_rejected"
        )

    def test_return_ack_preserves_abort_withdrawal_spectator_and_fight_priority(self):
        names = (
            "handle_aborted_return_ack",
            "handle_withdrawal_ack",
            "handle_spectator_return_ack",
            "handle_combat_return_ack",
        )
        fields = (
            "aborted_native_return",
            "pve_withdrawal_pending",
            "spectator_terminal_pending",
            "fight_messages",
        )
        for index, expected in enumerate(names):
            with self.subTest(expected=expected):
                state = {
                    name: object() if i >= index else None
                    for i, name in enumerate(fields)
                }
                self.assert_route(
                    session_fixture(opcode=12925, **state),
                    expected,
                    tuple(name for name in names if name != expected),
                )
        self.assert_route(
            session_fixture(
                opcode=12925,
                loaded=False,
                spectator_terminal_pending=object(),
                fight_messages=object(),
            ),
            "handle_combat_return_ack",
            ("handle_spectator_return_ack",),
        )

    def test_shared_completion_opcode_uses_exact_stage_and_payload_length(self):
        cases = (
            (8, "handle_craft_station"),
            (3, "handle_resource_complete"),
            (2, "handle_harvest_complete"),
            (6, "handle_harvest_complete"),
        )
        for stage, expected in cases:
            with self.subTest(stage=stage):
                self.assert_route(
                    session_fixture(opcode=13429, body=struct.pack(">Bh", 2, stage)),
                    expected,
                )
        for body in (b"", b"\x02\x00", b"\x02\x00\x08\x00", struct.pack(">Bh", 1, 2)):
            with self.subTest(body=body):
                session = session_fixture(opcode=13429, body=body)
                self.assertIs(session.dispatch_request(), DispatchResult.FALLTHROUGH)
                self.assertEqual(
                    session.runtime.record.call_args.kwargs["event"], "request_rejected"
                )

    def test_handshake_precedes_dispatcher_catchall(self):
        self.assert_route(
            session_fixture(opcode=574, service="dispatcher"),
            "handle_handshake",
            ("handle_dispatcher",),
        )
        self.assert_route(
            session_fixture(opcode=23664, service="dispatcher"),
            "handle_dispatcher",
            ("handle_character_select",),
        )

    def test_encounter_assignment_preserves_short_circuit_and_rejection_fallback(self):
        prepared = {"encounter": 11}
        session = session_fixture(opcode=13222)
        session.prepare_native_encounter_world_action = Mock(return_value=prepared)
        session.prepare_rift_start = Mock(side_effect=AssertionError("wrong condition"))
        session.try_native_monster_destroy = Mock(
            side_effect=AssertionError("fallthrough")
        )
        self.assert_route(session, "handle_encounter_start")
        self.assertIs(session.state.encounter_world_action, prepared)
        session.prepare_rift_start.assert_not_called()

        session = session_fixture(opcode=13130)
        session.prepare_native_encounter_world_action = Mock(
            side_effect=AssertionError("must short circuit")
        )
        session.prepare_rift_start = Mock(
            side_effect=AssertionError("must short circuit")
        )
        self.assert_route(session, "handle_encounter_start")
        self.assertIsNone(session.state.encounter_world_action)

        session = session_fixture(opcode=13222, encounter_world_action=prepared)
        session.prepare_native_encounter_world_action = Mock(return_value=None)
        session.try_native_monster_destroy = Mock(return_value=False)
        self.assert_route(session, "handle_world_dialogue")
        self.assertIsNone(session.state.encounter_world_action)

    def test_rift_assignment_and_disabled_combat_do_not_call_wrong_producers(self):
        prepared = {"run": 12}
        session = session_fixture(opcode=12870)
        session.prepare_rift_start = Mock(return_value=prepared)
        self.assert_route(session, "handle_encounter_start")
        self.assertIs(session.state.rift_start_run, prepared)
        session = session_fixture(opcode=12870)
        session.runtime.COMBAT_TEST = False
        session.prepare_rift_start = Mock(side_effect=AssertionError("combat disabled"))
        self.assert_route(session, "handle_world_interaction")

    def test_real_ping_continues_without_entering_travel_or_combat(self):
        session = session_fixture(
            opcode=33, body=b"ping", connection=object(), active_request=Mock()
        )
        trace = session.state.active_request
        session.runtime.send = Mock()
        session.committed_travel_holds_request = Mock(
            side_effect=AssertionError("keepalive must precede travel")
        )
        self.assertIs(session.prepare_request(), DispatchResult.CONTINUE)
        self.assertEqual(
            [call.args[2:] for call in session.runtime.send.call_args_list],
            [(23, b"\x01ping"), (309, struct.pack(">I", 12345))],
        )
        trace.finish.assert_called_once_with()
        self.assertIsNone(session.state.active_request)

    def test_zero_step_movement_continues_but_handshake_falls_through(self):
        session = session_fixture(opcode=13331, position={"x": 0, "y": 0, "z": 0})
        session.runtime.PLANTINGS = Mock()
        session.runtime.HARVESTS = Mock()
        session.runtime.decode_body = Mock(
            return_value=dict(
                steps=(), mode_id=0, start_position=dict(session.state.position)
            )
        )
        self.assertIs(session.handle_world_movement(), DispatchResult.CONTINUE)
        self.assertEqual(
            session.runtime.record.call_args.kwargs["event"],
            "movement_zero_step_ignored",
        )
        with patch.object(Path, "read_bytes", return_value=b"test-public-key"):
            session.runtime.RUNTIME = Path("/unused-fixture")
            session.runtime.send = Mock()
            session.state.connection = object()
            self.assertIs(session.handle_handshake(), DispatchResult.FALLTHROUGH)


class SessionOwnershipTests(unittest.TestCase):
    def test_constructor_binds_stable_callbacks_to_each_live_session(self):
        runtime = SimpleNamespace(
            SceneSync=Mock(), OWNED_HERO_TEMPLATE=b"", CHARACTERS=()
        )
        with patch(
            "psycopg.connect",
            side_effect=AssertionError("unexpected database connection"),
        ), patch.object(
            threading.Thread, "start", side_effect=AssertionError("unexpected worker")
        ):
            first = Session(runtime, Mock(), ("fixture", 0), "world", Mock())
            second = Session(runtime, Mock(), ("fixture", 1), "world", Mock())
        for name in (
            "current_combat_stats",
            "area_boundary_provider",
            "area_movement_provider",
        ):
            with self.subTest(name=name):
                callback = getattr(first, name)
                self.assertIs(callback, getattr(first, name))
                self.assertIs(callback.__self__, first)
                self.assertIsNot(callback, getattr(second, name))
                self.assertIs(deepcopy(callback).__self__, first)
        self.assertIs(
            first.state.native_area_movement_provider, first.area_movement_provider
        )
        self.assertIs(
            second.state.native_area_movement_provider, second.area_movement_provider
        )
        self.assertIs(
            first.state.native_area_movement_provider,
            first.state.native_area_movement_provider,
        )

    def test_copied_callback_keeps_exact_live_session_and_socket_owner(self):
        session = session_fixture(connection=socket.socket())
        self.addCleanup(session.state.connection.close)
        session.state.position = {"x": 1}
        copied = deepcopy({"stats": session.current_combat_stats, "session": session})
        self.assertIs(copied["session"], session)
        self.assertIs(copied["stats"].__self__, session)
        session.state.position["x"] = 9
        self.assertEqual(copied["session"].state.position["x"], 9)

    def test_ai_context_provides_current_state_bound_methods_and_runtime(self):
        session = session_fixture()
        context = session.ai_world_context()
        self.assertEqual(set(context), {"globals", "scopes"})
        self.assertIs(context["globals"], vars(session.runtime))
        (scope,) = context["scopes"]
        self.assertIs(scope["character"], session.state.character)
        self.assertIs(scope["current_combat_stats"].__self__, session)
        self.assertIs(scope["checkpoint_fight"].__self__, session)
        session.state.character = {"id": 8}
        self.assertIs(
            session.ai_world_context()["scopes"][0]["character"],
            session.state.character,
        )
        self.assertEqual(scope["character"]["id"], 7)

    def test_importing_application_does_not_start_world_or_workers(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, threading; before=threading.active_count(); from wakfu_server.application.session import Session; assert 'wakfu_server.application.bootstrap' not in sys.modules; assert threading.active_count()==before",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hub_forwards_prewarm_receipt_before_starting_the_one_application(self):
        from wakfu_server import application

        name = "wakfu_server.application.bootstrap"
        bootstrap = ModuleType(name)
        prewarm = {"details": {"generation": "fixture-generation"}, "elapsed_ms": 12}
        bootstrap.main = Mock(
            side_effect=lambda: self.assertIs(
                bootstrap._COMBAT_STARTUP_PREWARM, prewarm
            )
        )
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        with patch.dict(sys.modules, {name: bootstrap}), patch.object(
            application, "bootstrap", bootstrap, create=True
        ):
            runpy.run_path(
                str(source),
                run_name="__main__",
                init_globals={"_COMBAT_STARTUP_PREWARM": prewarm},
            )
        bootstrap.main.assert_called_once_with()


class NetworkDeliveryTests(unittest.TestCase):
    def runtime(self):
        runtime = SimpleNamespace(
            NATIVE_PLANTING_BONUS=False,
            COMBAT_WIRE_TRACE=False,
            PROFILER=SimpleNamespace(span=lambda *args: nullcontext()),
            record=Mock(),
        )
        delivery = NetworkDelivery(runtime)
        runtime.record_combat_wire_effect = delivery.record_combat_wire_effect
        runtime.publish_item_spell_updates = delivery.publish_item_spell_updates
        return runtime, delivery

    def test_real_socket_frames_preserve_batch_order_and_native_fight_tracking(self):
        runtime, delivery = self.runtime()
        writer, reader = socket.socketpair()
        self.addCleanup(writer.close)
        self.addCleanup(reader.close)
        reader.settimeout(1)
        connection = Connection(writer, runtime=runtime)
        packets = (
            (12847, struct.pack(">i", 19)),
            (23, b"first"),
            (12847, struct.pack(">i", 20)),
        )
        delivery.send_batch(connection, "dispatcher", packets)
        expected = b"".join(frame(*packet) for packet in packets)
        self.assertEqual(delivery.receive(reader, len(expected)), expected)
        self.assertEqual(connection.native_fight_id, 20)
        self.assertEqual(
            [call.kwargs["opcode"] for call in runtime.record.call_args_list],
            [12847, 23, 12847],
        )

    def test_partial_receive_idle_retry_and_eof_are_preserved(self):
        _, delivery = self.runtime()
        connection = Mock(objectives_updates=None)
        connection.recv.side_effect = [b"ab", socket.timeout(), b"cd"]
        idle = Mock(return_value=True)
        self.assertEqual(delivery.receive(connection, 4, idle), b"abcd")
        idle.assert_called_once_with()
        connection.recv.side_effect = [socket.timeout()]
        with self.assertRaisesRegex(ValueError, "Session expired"):
            delivery.receive(connection, 1, lambda: False)
        connection.recv.side_effect = [b""]
        with self.assertRaises(EOFError):
            delivery.receive(connection, 1)

    def test_pending_work_interrupts_only_an_empty_frame_header(self):
        _, delivery = self.runtime()
        connection = Mock(objectives_updates=None)
        queued = []
        source_attack = struct.pack(">qHH", 24139, 0, 0)

        def idle():
            queued.append(source_attack)
            return True

        connection.recv.side_effect = [socket.timeout(), b"must-not-be-read"]
        with self.assertRaises(PendingSessionWork):
            delivery.receive(
                connection,
                4,
                idle,
                pending_work=lambda: bool(queued),
            )
        self.assertEqual(queued, [source_attack])
        connection.recv.assert_called_once_with(4)

        connection = Mock(objectives_updates=None)
        queued = []
        connection.recv.side_effect = [b"\x00\x00", socket.timeout(), b"\x00\x08"]
        header = delivery.receive(
            connection,
            4,
            lambda: (queued.append(source_attack) or True),
            pending_work=lambda: bool(queued),
        )
        self.assertEqual(header, b"\x00\x00\x00\x08")
        self.assertEqual(connection.recv.call_count, 3)

    def test_actual_session_dispatches_idle_queued_source_attack_without_client_frame(
        self,
    ):
        session = session_fixture(
            loaded=False,
            account_id=None,
            service="diagnostic",
            active_request=None,
            pending_guardian_attack=None,
            connection_trace_id="fixture-connection",
            peer=("local", 0),
        )
        runtime, delivery = self.runtime()
        runtime.COMBAT_TEST = True
        runtime.GUILD_REQUEST_OPCODES = frozenset()
        runtime.STOPPING = threading.Event()
        runtime.CONNECTIONS = Mock()
        runtime.CONNECTIONS.register.return_value = True
        runtime.Connection = lambda raw: raw
        runtime.receive = delivery.receive
        runtime.send = delivery.send
        runtime.ECOLOGY_BRIDGE = None
        runtime.REQUEST_STATE_DETAIL = False
        runtime.state_summary = Mock(return_value={})
        runtime.exception_frames = Mock(return_value=[])
        runtime.safe_snapshot = lambda operation: operation()
        runtime.write_records = Mock()
        runtime.RequestTrace = lambda **_kwargs: Mock()
        session.runtime = runtime
        raw = Mock()
        raw.objectives_updates = None
        raw.is_bot_peer = False
        raw.trace_id = None
        raw.recv.side_effect = [socket.timeout(), b""]
        raw.version.return_value = "fixture-TLS"
        session.state.raw = raw
        session.state.context = SimpleNamespace(
            wrap_socket=lambda *args, **kwargs: nullcontext(raw)
        )
        session.release_completed_combat_action_results = Mock()
        idle_calls = []
        marker = struct.pack(">qHH", 24139, 0, 0)

        def idle():
            idle_calls.append(True)
            if len(idle_calls) == 2:
                session.state.pending_guardian_attack = marker
            return True

        session.idle = idle
        session.checkpoint_fight = Mock()
        session.close = Mock()
        session.prepare_request = Mock(return_value=DispatchResult.FALLTHROUGH)
        session.dispatch_request = Mock(return_value=DispatchResult.CONTINUE)

        session.run()

        session.dispatch_request.assert_called_once_with()
        self.assertEqual(
            (session.state.route, session.state.opcode, session.state.body),
            (0, 13130, marker),
        )
        self.assertEqual(raw.recv.call_count, 2)
        session.checkpoint_fight.assert_not_called()
        session.close.assert_called_once_with()

    def test_failed_socket_write_invalidates_publication_and_unlocks(self):
        runtime, _ = self.runtime()
        raw = Mock()
        raw.sendall.side_effect = OSError("closed socket")
        connection = Connection(raw, runtime=runtime)
        connection.instance_publications.lease.current = ("valid-before-write",)
        connection.marker_publications.phases[9] = 1
        connection.interactive_publication = Mock()
        connection.interactive_publication.transform.side_effect = (
            lambda data, scope: data
        )
        with self.assertRaises(OSError):
            connection.sendall(frame(23, b"payload"))
        self.assertIsNone(connection.instance_publications.lease.current)
        self.assertEqual(connection.marker_publications.phases, {})
        connection.interactive_publication.clear.assert_called_once_with()
        self.assertEqual(connection.interactive_trace, [])
        acquired = []

        def acquire_after_failure():
            owned = connection.write_lock.acquire(blocking=False)
            acquired.append(owned)
            if owned:
                connection.write_lock.release()

        worker = threading.Thread(target=acquire_after_failure)
        worker.start()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(acquired, [True])

    def test_invalid_batch_is_rejected_before_any_socket_write(self):
        _, delivery = self.runtime()
        for packets in (((True, b"x"),), ((1, bytearray(b"x")),), ((65536, b"x"),)):
            with self.subTest(packets=packets):
                connection = Mock(is_bot_peer=False)
                with self.assertRaises(ValueError):
                    delivery.send_batch(connection, "world", packets)
                connection.sendall.assert_not_called()

    def test_encoded_batch_failure_does_not_acknowledge_item_spell_delivery(self):
        runtime, delivery = self.runtime()
        raw = Mock(is_bot_peer=False)
        raw.sendall.side_effect = OSError("closed socket")
        connection = Connection(raw, runtime=runtime)
        body = struct.pack(">qiqh", 19, 7, 9001, 1)
        with self.assertRaises(OSError):
            delivery.send_batch(connection, "world", ((12503, body),))
        self.assertEqual(connection.item_spell_uids, set())
        runtime.record.assert_not_called()


class SessionLoopTests(unittest.TestCase):
    def test_astrub_story_callback_publishes_committed_move_once_through_shared_state(
        self,
    ):
        from contextlib import nullcontext

        from wakfu_server.application.session_world import WorldSessionMixin
        from wakfu_server.application.session_travel import TravelSessionMixin

        session = object.__new__(
            type("CatStorySession", (WorldSessionMixin, TravelSessionMixin), {})
        )
        character = {
            "id": 7,
            "account_id": 2,
            "map_id": 312,
            "instance_id": 99,
            "x": 1,
            "y": 2,
            "z": 0,
        }
        saved = {**character, "x": 3, "y": 4, "z": 0}
        marker = (99, 23927)
        result = {
            "character": saved,
            "packets": [(13530, b"move"), (13259, b"actor"), (13411, b"scene")],
            "pending_event": marker,
        }
        connection = SimpleNamespace(pending_astrub_cat_story=(99, 23926))
        positions = SimpleNamespace(
            account_barrier=lambda _account_id: nullcontext(), attach=Mock()
        )
        runtime = SimpleNamespace(
            POSITIONS=positions,
            WORLD=SimpleNamespace(update=Mock()),
            STORE=object(),
            flush_positions=Mock(),
            Movement=lambda position: dict(position),
        )
        session.runtime = runtime
        session.state = SimpleNamespace(
            account_id=2,
            generation="generation",
            character=character,
            body=struct.pack(">i", 23926),
            connection=connection,
            service="world",
            fight=None,
            combat_session=None,
            position={"x": 1, "y": 2, "z": 0},
            movement_state=None,
        )
        session.mark_static_sync_pending = Mock()
        session.publish_settled_quest_packets = Mock()
        with patch(
            "wakfu_server.intro_cinematic.callback_id", return_value=23926
        ), patch(
            "wakfu_server.achievements.astrub_cat_story.callback",
            return_value=result,
        ) as callback, patch.object(
            session, "publish_astrub_cat_story", wraps=session.publish_astrub_cat_story
        ) as publish:
            session.handle_world_loaded()

        callback.assert_called_once()
        publish.assert_called_once_with(result)
        self.assertIs(session.state.character, saved)
        self.assertEqual(session.state.position, {"x": 3, "y": 4, "z": 0})
        positions.attach.assert_called_once_with(2, "generation", saved)
        self.assertEqual(
            [call.args[2] for call in runtime.WORLD.update.call_args_list],
            [13530, 13259],
        )
        self.assertEqual(connection.pending_astrub_cat_story, marker)
        self.assertIs(connection.pending_astrub_cat_story_bootstrap, False)

        session.publish_astrub_cat_story(
            {"character": saved, "packets": (), "pending_event": marker}
        )
        positions.attach.assert_called_once()
        runtime.WORLD.update.assert_has_calls(
            [
                unittest.mock.call(
                    "generation", saved, 13530, b"move", include_sender=False
                ),
                unittest.mock.call(
                    "generation", saved, 13259, b"actor", include_sender=False
                ),
            ]
        )
        self.assertEqual(runtime.WORLD.update.call_count, 2)

    def test_rii_fall_callback_uses_generic_road_bootstrap_before_arrival_scene(self):
        from contextlib import nullcontext

        from wakfu_server.application.session_world import WorldSessionMixin
        from wakfu_server.application.session_travel import TravelSessionMixin

        session = object.__new__(
            type("ArrivalSession", (WorldSessionMixin, TravelSessionMixin), {})
        )
        character = {
            "id": 7,
            "account_id": 2,
            "map_id": 1385,
            "instance_id": 0,
            "x": 8,
            "y": -20,
            "z": 5,
        }
        saved = {**character, "map_id": 895, "x": -8, "y": -1, "z": 18}
        connection = SimpleNamespace(
            pending_rii_zaap_scene=7,
            pending_astrub_arrival=None,
            pending_astrub_arrival_callback=None,
        )
        sent = []
        positions = SimpleNamespace(
            account_barrier=lambda _account_id: nullcontext(), attach=Mock()
        )
        runtime = SimpleNamespace(
            POSITIONS=positions,
            WORLD=SimpleNamespace(leave=Mock(), join=Mock()),
            STORE=SimpleNamespace(),
            Movement=lambda position: dict(position),
            flush_positions=Mock(),
            owned_native_bootstrap=Mock(
                return_value=[(13256, b"map"), (13974, b"road")]
            ),
            join_world=Mock(),
            transports=SimpleNamespace(bootstrap=Mock(side_effect=KeyError("packets"))),
            send=lambda _connection, _service, opcode, body: sent.append(
                (opcode, body)
            ),
            send_batch=lambda _connection, _service, packets: sent.extend(packets),
            record=Mock(),
        )
        session.runtime = runtime
        session.state = SimpleNamespace(
            account_id=2,
            generation="generation",
            character=character,
            body=struct.pack(">i", 22534),
            connection=connection,
            service="world",
            fight=None,
            combat_session=None,
            position={"x": 8, "y": -20, "z": 5},
            movement_state=None,
        )
        session.cancel_crafting = Mock()
        session.mark_static_sync_pending = Mock()
        session.publish_settled_quest_packets = Mock()
        route = {
            "direction": 3,
            "destination": {"map_id": 895, "instance_id": 0, "x": -8, "y": -1, "z": 18},
        }
        packets = [(13832, b"progress"), (13411, b"arrival-scene")]
        with patch(
            "wakfu_server.intro_cinematic.callback_id", return_value=22534
        ), patch(
            "wakfu_server.rii_zaap_scene.finish",
            return_value=(saved, packets, route),
        ):
            session.handle_world_loaded()

        runtime.transports.bootstrap.assert_not_called()
        runtime.owned_native_bootstrap.assert_called_once_with(saved, direction=3)
        self.assertEqual(
            [packet for packet in sent if packet[0] in (13974, 13411)],
            [(13974, b"road"), (13411, b"arrival-scene")],
        )
        self.assertEqual(connection.pending_astrub_arrival, 7)
        self.assertEqual(connection.pending_astrub_arrival_callback, 17029)
        positions.attach.assert_called_once_with(2, "generation", saved)
        self.assertEqual(session.state.position, {"x": -8, "y": -1, "z": 18})

    def test_actual_loop_keeps_ping_outside_checkpoint_and_closes_after_eof(self):
        session = session_fixture(
            loaded=False,
            account_id=None,
            service="diagnostic",
            active_request=None,
            pending_guardian_attack=None,
            connection_trace_id="fixture-connection",
            peer=("local", 0),
        )
        runtime, delivery = NetworkDeliveryTests().runtime()
        runtime.COMBAT_TEST = True
        runtime.GUILD_REQUEST_OPCODES = frozenset()
        runtime.STOPPING = threading.Event()
        runtime.CONNECTIONS = Mock()
        runtime.CONNECTIONS.register.return_value = True
        runtime.Connection = lambda raw: raw
        runtime.receive = delivery.receive
        runtime.send = delivery.send
        runtime.ECOLOGY_BRIDGE = None
        runtime.REQUEST_STATE_DETAIL = False
        runtime.state_summary = Mock(return_value={})
        runtime.exception_frames = Mock(return_value=[])
        runtime.safe_snapshot = lambda operation: operation()
        runtime.write_records = Mock()
        traces = []
        runtime.RequestTrace = lambda **kwargs: traces.append(Mock()) or traces[-1]
        session.runtime = runtime
        raw = Mock()
        raw.objectives_updates = None
        raw.is_bot_peer = False
        raw.trace_id = None
        inbound = bytearray(
            struct.pack(">IBH", 7, 3, 65500) + struct.pack(">IBH", 8, 3, 33) + b"p"
        )

        def receive(count):
            chunk = bytes(inbound[:count])
            del inbound[:count]
            return chunk

        raw.recv.side_effect = receive
        raw.version.return_value = "fixture-TLS"
        session.state.raw = raw
        session.state.context = SimpleNamespace(
            wrap_socket=lambda *args, **kwargs: nullcontext(raw)
        )
        session.release_completed_combat_action_results = Mock()
        session.idle = Mock(return_value=True)
        session.checkpoint_fight = Mock()
        session.close = Mock()
        # Domain preflight is isolated for the unknown opcode; real ping preflight runs.
        original_preflight = session.prepare_request
        session.prepare_request = lambda: (
            original_preflight()
            if session.state.opcode == 33
            else DispatchResult.FALLTHROUGH
        )
        session.run()
        self.assertEqual(session.checkpoint_fight.call_count, 1)
        self.assertEqual(len(traces), 2)
        for trace in traces:
            trace.finish.assert_called_once_with()
        self.assertEqual(
            [call.args[0] for call in raw.sendall.call_args_list],
            [frame(23, b"\x01p"), frame(309, struct.pack(">I", 12345))],
        )
        self.assertEqual(
            [
                call.kwargs["event"]
                for call in runtime.record.call_args_list
                if "event" in call.kwargs
            ],
            ["tls_connected", "request_rejected", "disconnected"],
        )
        session.close.assert_called_once_with()
