"""Production selects one separate TCP service and never falls back to HTTP."""
import os
from contextlib import ExitStack
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock, patch

from wakfu_ai.bridge import world_entry
from wakfu_ai.bridge.world_entry import context_transport
from wakfu_ai.transport.framed_context import FramedContextTransport


class AiTransportSelectionTests(unittest.TestCase):
    def test_tcp_transport_is_lazy_for_both_owner_budgets(self):
        for first, timeout in ((False, 10), (True, 20)):
            with self.subTest(first_turn=first):
                transport = context_transport("tcp://ai:8090", first_turn=first)
                try:
                    self.assertIs(type(transport), FramedContextTransport)
                    self.assertEqual(transport.channel.address, ("ai", 8090))
                    self.assertEqual(transport.channel.timeout, timeout)
                    self.assertEqual(transport.channel.tcp_opens, 0)
                finally:
                    transport.close()

    def test_legacy_http_address_and_retired_selector_still_select_tcp_only(self):
        with patch.dict(os.environ, {"WAKFU_AI_SOCKET_URL": "http://retired:9999"}):
            transport = context_transport("http://ai:8090")
            try:
                self.assertEqual(transport.channel.address, ("ai", 8090))
            finally:
                transport.close()

    def test_ipv6_tcp_endpoint_preserves_host_and_port(self):
        transport = context_transport("tcp://[::1]:8090/")
        try:
            self.assertEqual(transport.channel.address, ("::1", 8090))
        finally:
            transport.close()

    def test_invalid_endpoint_never_falls_back_or_opens_channel(self):
        invalid = (
            "https://ai:8090",
            "tcp://ai",
            "tcp://:8090",
            "tcp://ai:0",
            "tcp://ai:65536",
            "tcp://ai:wrong",
            "tcp://user@ai:8090",
            "tcp://user:password@ai:8090",
            "tcp://ai:8090/path",
            "tcp://ai:8090?option=1",
            "tcp://ai:8090#fragment",
        )
        for endpoint in invalid:
            with self.subTest(endpoint=endpoint), patch(
                "socket.create_connection"
            ) as connect:
                with self.assertRaises(ValueError):
                    context_transport(endpoint)
                connect.assert_not_called()

    def test_actual_entry_defaults_to_tcp_and_closes_both_first_turn_budgets(self):
        closed = Mock()
        factory = Mock(
            side_effect=lambda *args, **kwargs: SimpleNamespace(close=closed)
        )
        authority = dict(
            characters={}, monsters={}, decks={}, excluded_decks={}, registrations={}
        )
        calls = []

        def runner(runtime, **kwargs):
            calls.append(kwargs)
            return iter(())

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            stack.enter_context(
                patch(
                    "wakfu_ai.transport.framed_context.FramedContextTransport", factory
                )
            )
            for name, value in (
                ("load_authorities", authority),
                ("encounter_profiles", {None: {"policy": {}, "identity": "test"}}),
                ("NativeStats", object()),
                ("native_exporter", object()),
            ):
                stack.enter_context(patch.object(world_entry, name, return_value=value))
            stack.enter_context(
                patch.object(world_entry, "run_turn", side_effect=runner)
            )
            for count in (1, 2):
                runtime = SimpleNamespace(
                    fight=SimpleNamespace(
                        id=41,
                        current=SimpleNamespace(id=-71, turn_count=count),
                        native_timeline_round=1,
                    )
                )
                list(
                    world_entry._run_npc_turn(
                        runtime,
                        store=None,
                        viewer_character={"id": 1, "map_id": 527},
                        monsters={},
                        stats_serializer=None,
                    )
                )
        self.assertEqual([item["budget_seconds"] for item in calls], [20, 10])
        self.assertEqual(
            [call.args for call in factory.call_args_list], [("ai", 8090), ("ai", 8090)]
        )
        self.assertEqual(
            [call.kwargs for call in factory.call_args_list],
            [{"timeout": 20}, {"timeout": 10}],
        )
        self.assertEqual(closed.call_count, 2)

    def test_production_main_binds_one_tcp_listener_and_closes_on_exit(self):
        from wakfu_ai.transport import framed_server
        from wakfu_ai.http import server as http

        listener = Mock()
        with patch.dict(os.environ, {}, clear=True), patch.object(
            framed_server, "FramedServer", return_value=listener
        ) as constructor, patch.object(http, "BoundedHTTPServer") as old_http:
            framed_server.main()
        constructor.assert_called_once_with(("0.0.0.0", 8090))
        listener.serve_forever.assert_called_once_with()
        listener.server_close.assert_called_once_with()
        old_http.assert_not_called()

    def test_stable_http_main_delegates_without_binding_http(self):
        from wakfu_ai.http import server as http

        with patch("wakfu_ai.transport.framed_server.main") as main, patch.object(
            http, "BoundedHTTPServer"
        ) as old_http:
            http.main()
        main.assert_called_once_with()
        old_http.assert_not_called()

    def test_invalid_listener_port_fails_before_binding_any_service(self):
        from wakfu_ai.transport import framed_server

        for port in ("0", "65536", "invalid"):
            with self.subTest(port=port), patch.dict(
                os.environ, {"WAKFU_AI_PORT": port}
            ), patch.object(framed_server, "FramedServer") as constructor:
                with self.assertRaises(ValueError):
                    framed_server.main()
                constructor.assert_not_called()
