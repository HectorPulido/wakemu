import importlib.util
from pathlib import Path
from unittest.mock import Mock
import unittest

from wakfu_server.dungeon_instances import _load_routes
from wakfu_server.maps.dungeon_runtime_config import prepare_configuration

SPEC = importlib.util.spec_from_file_location(
    "installer_native_guard",
    Path(__file__).resolve().parents[1] / "tools/install_dungeon_bulk.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def native_route_payload(route):
    from dataclasses import asdict

    payload = asdict(route)
    if payload.get("native_template_id") is None:
        payload.pop("native_template_id", None)
    return payload


class NativeBulkGuardTests(unittest.TestCase):
    def test_consistent_but_non_native_route_rejected_before_database_access(self):
        route = native_route_payload(_load_routes()["jalato_normal"])
        route["template_id"] += 100
        plan = dict(
            slug="fixture",
            roster_ready=True,
            diagnostics=[],
            definition_id=route["definition_id"],
            template_id=route["template_id"],
            asset_map_id=route["start_map_id"],
            rooms=[
                dict(
                    order=1,
                    diagnostics=[],
                    monsters=[
                        dict(ref_id=1, count=1, native_min_level=1, native_max_level=2)
                    ],
                )
            ],
        )
        topology = dict(
            asset_map_id=route["start_map_id"],
            rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]])],
            doors=[],
        )
        config = prepare_configuration(
            plan, topology, route, version=1, provenance="fixture"
        )
        db = Mock()
        with self.assertRaisesRegex(RuntimeError, "native teleporter"):
            MODULE.install_bundle(db, dict(schema_version=1, configurations=[config]))
        db.execute.assert_not_called()
