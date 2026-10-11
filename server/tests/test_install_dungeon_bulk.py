"""Atomic PostgreSQL tests for installation of reviewed dungeon bundles."""

import copy
import json
import unittest

from postgres_case import PostgresCase
from tools.install_dungeon_bulk import install_bundle, validate_bundle
from wakfu_server.dungeon_instances import _load_routes
from wakfu_server.paths import DATA_ROOT
from wakfu_server.maps.dungeon_runtime_config import prepare_configuration
from wakfu_server import native_catalog


def native_fixture_routes():
    sources = json.loads(
        native_catalog.read_text(
            DATA_ROOT / "native-generic-teleporters.json", encoding="utf8"
        )
    )
    routes = []
    entrances = set()
    for source in sources:
        for destination in source["destinations"]:
            if type(destination.get("cyZ")) is not int or destination["cyZ"] <= 0:
                continue
            route = {
                "key": f"bulk_{chr(ord('a') + len(routes))}",
                "definition_id": max(1, source["definition_id"]),
                "template_id": destination["cyZ"],
                "entry_map_id": source["map_id"],
                "entry_object_id": source["id"],
                "destination_id": destination["destination_id"],
                "start_map_id": destination["map_id"],
                "criterion": destination["criterion"],
            }
            entrance = (
                route["entry_map_id"],
                route["entry_object_id"],
                route["destination_id"],
            )
            if entrance in entrances:
                continue
            try:
                _load_routes([route])
            except RuntimeError:
                continue
            routes.append(route)
            entrances.add(entrance)
            if len(routes) == 3:
                return routes
    raise AssertionError(
        "Native teleporter catalog has fewer than three verified dungeon routes"
    )


def configuration(route, *, key=None, slug=None):
    route = copy.deepcopy(route)
    if key is not None:
        route["key"] = key
    key = route["key"]
    slug = slug or key
    monster = {
        "name": "Native Jalató",
        "ref_id": 5525,
        "count": 2,
        "role": "monster",
        "native_min_level": 1,
        "native_max_level": 5,
        "guide_min_level": None,
        "guide_max_level": None,
    }
    plan = {
        "slug": slug,
        "source_url": "https://example.invalid/guide",
        "source_sha256": "a" * 64,
        "document_sha256": "b" * 64,
        "definition_id": route["definition_id"],
        "template_id": route["template_id"],
        "asset_map_id": route["start_map_id"],
        "diagnostics": [],
        "roster_ready": True,
        "rooms": [{"order": 1, "diagnostics": [], "monsters": [monster]}],
    }
    topology = {
        "asset_map_id": route["start_map_id"],
        "rooms": [{"order": 1, "anchor": [0, 0, 0], "cells": [[0, 0, 0]]}],
        "doors": [],
    }
    return prepare_configuration(
        plan,
        topology,
        route,
        version=1,
        provenance=f"isolated PostgreSQL bulk fixture:{key}",
    )


def bundle(*configs):
    return {"schema_version": 1, "configurations": list(configs)}


class DungeonBulkInstallerPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.routes = native_fixture_routes()
        self.first = configuration(self.routes[0])
        self.second = configuration(self.routes[1])

    def setting(self, name):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE name=%s", (name,)
            ).fetchone()
        return None if row is None else row["value"]

    def stored_configuration(self, route_key, version=1):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations "
                "WHERE route_key=%s AND policy_version=%s",
                (route_key, version),
            ).fetchone()
        return None if row is None else row["configuration"]

    def assert_uninstalled(self, *route_keys):
        with self.store.connection() as db:
            for key in route_keys:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM dungeon_runtime_configurations "
                        "WHERE route_key=%s AND policy_version=1",
                        (key,),
                    ).fetchone()
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM dungeon_context_policy_versions WHERE route_key=%s",
                        (key,),
                    ).fetchone()
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM dungeon_context_active_policies WHERE route_key=%s",
                        (key,),
                    ).fetchone()
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM dungeon_runtime_active_configurations "
                        "WHERE route_key=%s",
                        (key,),
                    ).fetchone()
                )
            self.assertIsNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='dungeon_runtime_routes'"
                ).fetchone()
            )

    def test_install_and_replay_are_idempotent_with_sorted_route_registry(self):
        prepared = bundle(self.second, self.first)
        with self.store.connection() as db:
            first_result = install_bundle(db, prepared)
        with self.store.connection() as db:
            replay_result = install_bundle(db, prepared)
        self.assertEqual({"installed": 2, "registered_routes": 2}, first_result)
        self.assertEqual(first_result, replay_result)
        registry = self.setting("dungeon_runtime_routes")
        self.assertEqual(
            ["bulk_a", "bulk_b"], [route["key"] for route in registry["routes"]]
        )
        with self.store.connection() as db:
            config_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_runtime_configurations "
                "WHERE route_key IN ('bulk_a','bulk_b')"
            ).fetchone()["n"]
            context_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_context_policy_versions "
                "WHERE route_key IN ('bulk_a','bulk_b')"
            ).fetchone()["n"]
            active_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_runtime_active_configurations "
                "WHERE route_key IN ('bulk_a','bulk_b')"
            ).fetchone()["n"]
        self.assertEqual((2, 2, 2), (config_count, context_count, active_count))

    def test_duplicate_native_entrance_is_rejected_before_any_write(self):
        colliding = configuration(self.routes[0], key="bulk_c", slug="bulk_c")
        prepared = bundle(self.first, colliding)
        with self.assertRaisesRegex(
            ValueError, "Duplicate dungeon slug, route or native entrance"
        ):
            with self.store.connection() as db:
                install_bundle(db, prepared)
        self.assert_uninstalled("bulk_a", "bulk_c")

    def test_unvalidated_bundle_content_is_rejected_before_any_write(self):
        tampered = copy.deepcopy(self.first)
        tampered["compiled_plan"]["rooms"][0]["monsters"][0]["count"] += 1
        with self.assertRaisesRegex(
            ValueError, "Bundle contains unvalidated configuration"
        ):
            with self.store.connection() as db:
                install_bundle(db, bundle(tampered, self.second))
        self.assert_uninstalled("bulk_a", "bulk_b")

    def test_later_immutable_route_conflict_rolls_back_prior_bundle_entries(self):
        existing = configuration(self.routes[2], key="bulk_z_existing")
        with self.store.connection() as db:
            install_bundle(db, bundle(existing))
        before_registry = self.setting("dungeon_runtime_routes")

        new_route = configuration(self.routes[0], key="bulk_a_new")
        changed_identity = configuration(self.routes[1], key="bulk_z_existing")
        with self.assertRaisesRegex(ValueError, "route identity is immutable"):
            with self.store.connection() as db:
                install_bundle(db, bundle(changed_identity, new_route))

        self.assertEqual(before_registry, self.setting("dungeon_runtime_routes"))
        self.assertIsNone(self.stored_configuration("bulk_a_new"))
        self.assertIsNotNone(self.stored_configuration("bulk_z_existing"))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_context_policy_versions WHERE route_key='bulk_a_new'"
                ).fetchone()
            )

    def test_invalid_native_cyz_is_rejected_before_any_write(self):
        invalid_route = copy.deepcopy(self.routes[0])
        invalid_route["template_id"] += 10000
        invalid = configuration(invalid_route, key="bulk_invalid_cyz")
        with self.assertRaisesRegex(
            RuntimeError, "no longer matches the native teleporter catalog"
        ):
            with self.store.connection() as db:
                install_bundle(db, bundle(invalid))
        self.assert_uninstalled("bulk_invalid_cyz")

    def test_registry_failure_rolls_back_config_context_and_active_pointers(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_dungeon_route_registry() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "IF NEW.name='dungeon_runtime_routes' THEN "
                "RAISE EXCEPTION 'route registry rejected'; END IF; RETURN NEW; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_dungeon_route_registry BEFORE INSERT OR UPDATE "
                "ON settings FOR EACH ROW EXECUTE FUNCTION reject_dungeon_route_registry()"
            )
        with self.assertRaisesRegex(Exception, "route registry rejected"):
            with self.store.connection() as db:
                install_bundle(db, bundle(self.first, self.second))
        self.assert_uninstalled("bulk_a", "bulk_b")
        with self.store.connection() as db:
            db.execute("DROP TRIGGER reject_dungeon_route_registry ON settings")
            db.execute("DROP FUNCTION reject_dungeon_route_registry()")


if __name__ == "__main__":
    unittest.main()
