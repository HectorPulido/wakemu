"""Native menu disable list and session/proximity exit authority regressions."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.haven_ranch_portal import config_message, validate_exit


class RanchPortalTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=42, account_id=7, map_id=1440, instance_id=42, x=10, y=11, z=4
        )
        self.session = SimpleNamespace(owns=lambda actor: actor is self.character)
        self.source = dict(id=22, type="RanchExit", map_id=1440, x=10, y=12, z=4)
        self.lease = Mock()
        self.body = struct.pack(">qHH", 22, 18, 0)

    def invoke(self, body=None):
        return validate_exit(
            self.character,
            self.session,
            self.body if body is None else body,
            validate_lease=self.lease,
        )

    def test_config_disables_unqualified_biomes_only(self):
        key, value = b"ranch.biomes.forbidden", b"2|3|4|5|6"
        self.assertEqual(
            config_message(),
            (
                22318,
                struct.pack(">I", len(key))
                + key
                + struct.pack(">I", len(value))
                + value,
            ),
        )

    def test_installed_exit_checks_lease_without_entry_entitlement(self):
        with patch(
            "wakfu_server.haven_ranch_portal._objects", return_value=(self.source,)
        ):
            self.assertEqual(self.invoke(), 22)
        self.lease.assert_called_once_with()

    def test_foreign_session_and_malformed_requests_reject(self):
        for body in (
            b"",
            self.body[:-1],
            self.body + b"\0",
            struct.pack(">qHH", 22, 35, 0),
            struct.pack(">qHH", 22, 18, 1),
            struct.pack(">qHH", 23, 18, 0),
        ):
            with self.subTest(body=body), patch(
                "wakfu_server.haven_ranch_portal._objects", return_value=(self.source,)
            ):
                with self.assertRaises(ValueError):
                    self.invoke(body)
        self.session = SimpleNamespace(owns=lambda actor: False)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wrong_map_height_distance_and_type_reject(self):
        for change in (
            dict(map_id=9),
            dict(z=5),
            dict(y=14),
            dict(type="RanchEntrance"),
        ):
            with self.subTest(change=change), patch(
                "wakfu_server.haven_ranch_portal._objects",
                return_value=({**self.source, **change},),
            ):
                with self.assertRaises(ValueError):
                    self.invoke()

    def test_expired_lease_rejects_before_using_object(self):
        self.lease.side_effect = ValueError("Expired actor lease")
        with self.assertRaises(ValueError):
            self.invoke()
