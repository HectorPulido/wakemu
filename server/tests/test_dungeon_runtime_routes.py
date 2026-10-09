from contextlib import contextmanager
import copy
from dataclasses import asdict
import unittest
from unittest.mock import Mock

from wakfu_server import dungeon_instances


def native_route_payload(route):
    payload = asdict(route)
    if payload.get("native_template_id") is None:
        payload.pop("native_template_id", None)
    return payload


class RuntimeRouteTests(unittest.TestCase):
    def setUp(self):
        self.previous = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", self.previous)
        self.row = None
        self.store = Mock()
        self.store.connection = self.connection
        self.native = native_route_payload(
            dungeon_instances._load_routes()["jalato_normal"]
        )

    @contextmanager
    def connection(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = self.row
        yield db

    def install(self, routes):
        self.row = dict(value=dict(schema_version=1, routes=routes))
        return dungeon_instances.load_runtime_routes(self.store)

    def test_exact_native_identity_loaded_under_generic_key(self):
        route = dict(self.native, key="generic_route")
        self.install([route])
        self.assertEqual(
            route["template_id"], dungeon_instances.route("generic_route").template_id
        )
        self.assertEqual(
            "generic_route",
            dungeon_instances.route_for_entry(
                route["entry_map_id"], route["entry_object_id"], route["destination_id"]
            ).key,
        )
        with self.assertRaises(ValueError):
            dungeon_instances.route("jalato_normal")

    def test_absent_setting_restores_catalog_defaults(self):
        self.install([dict(self.native, key="temporary")])
        self.row = None
        dungeon_instances.load_runtime_routes(self.store)
        self.assertEqual("jalato_normal", dungeon_instances.route("jalato_normal").key)

    def test_bad_native_identity_never_publishes_partial_registry(self):
        original = dungeon_instances._ROUTES
        wrong = dict(self.native, key="bad", template_id=self.native["template_id"] + 1)
        with self.assertRaises(RuntimeError):
            self.install([wrong])
        self.assertIs(original, dungeon_instances._ROUTES)

    def test_duplicate_native_entrance_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Duplicate dungeon native entrance"):
            self.install([self.native, dict(self.native, key="other")])

    def test_malformed_and_empty_installed_setting_fail_closed(self):
        for value in [
            None,
            {},
            dict(schema_version=True, routes=[self.native]),
            dict(schema_version=1, routes=[]),
            dict(schema_version=1, routes=None),
        ]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.row = dict(value=value)
                dungeon_instances.load_runtime_routes(self.store)
