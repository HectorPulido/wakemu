"""Only genuine committed native endpoints produce entrance mission facts."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import achievements
from wakfu_server.achievements import native_transport_objectives as module


class NativeTransportObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.source = dict(id=7, account_id=2, map_id=527, instance_id=0)
        self.saved = dict(self.source, map_id=888, x=0, y=0, z=0)
        self.target = dict(destination_id=2004, map_id=888, x=0, y=0, z=0, cyZ=-1)
        self.native = dict(id=23616, definition_id=1856, destinations=[self.target])
        self.route = dict(
            source_map=527,
            interactive_element_id=23616,
            destination_id=2004,
            native_definition_id=1856,
            destination=dict(map_id=888, x=0, y=0, z=0, instance_id=0),
        )
        self.lookup = Mock(return_value=self.native)
        self.settle = Mock(return_value=[(13832, b"earned")])
        for target, name, value in (
            (wakfu_server, "generic_transports", SimpleNamespace(source=self.lookup)),
            (achievements, "mission_toolkit", SimpleNamespace(settle=self.settle)),
        ):
            manager = patch.object(target, name, value, create=True)
            manager.start()
            self.addCleanup(manager.stop)

    def test_committed_native_endpoint_emits_exact_destination_event(self):
        result = module.on_transition(
            "db", "store", self.source, self.saved, self.route
        )
        self.assertEqual(result, [(13832, b"earned")])
        self.lookup.assert_called_once_with(527, 23616)
        args, kwargs = self.settle.call_args
        self.assertEqual(args, ("db", "store", self.saved))
        self.assertEqual(kwargs["kind"], "transport_entered")
        self.assertEqual(kwargs["reference"], 2004)
        self.assertTrue(kwargs["token"].startswith("native-transport-entry:"))

    def test_admin_arrivals_foreign_owners_and_nonpublic_contexts_emit_nothing(self):
        cases = [
            ({}, self.source, self.saved),
            (self.route, dict(self.source, instance_id=99), self.saved),
            (self.route, self.source, dict(self.saved, instance_id=99)),
            (self.route, self.source, dict(self.saved, id=8)),
            (self.route, self.source, dict(self.saved, account_id=3)),
            (dict(self.route, source_map=1), self.source, self.saved),
        ]
        for route, source, saved in cases:
            with self.subTest(route=route, source=source, saved=saved):
                self.assertEqual(
                    module.on_transition(None, None, source, saved, route), []
                )
        self.settle.assert_not_called()

    def test_forged_native_identity_and_wrong_actual_position_do_not_qualify(self):
        mutations = [
            dict(self.route, destination_id=999),
            dict(self.route, native_definition_id=0),
            dict(self.route, destination=dict(self.route["destination"], x=1)),
        ]
        for route in mutations:
            self.assertEqual(
                module.on_transition(None, None, self.source, self.saved, route), []
            )
        self.assertEqual(
            module.on_transition(
                None, None, self.source, dict(self.saved, x=1), self.route
            ),
            [],
        )
        self.native["destinations"].append(deepcopy(self.target))
        self.assertEqual(
            module.on_transition(None, None, self.source, self.saved, self.route), []
        )
        self.settle.assert_not_called()

    def test_settlement_failure_propagates_to_enclosing_movement_transaction(self):
        self.settle.side_effect = ValueError("invalid native mission reward")
        with self.assertRaisesRegex(ValueError, "invalid native mission reward"):
            module.on_transition(None, None, self.source, self.saved, self.route)


if __name__ == "__main__":
    unittest.main()
