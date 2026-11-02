"""Physical encounter-component admission at the public dungeon combat boundary."""
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_optional_encounters, dungeon_runtime
from wakfu_server import combat_geometry

MAP_ID = 149
INSTANCE_ID = 77
GROUP_ID = 5001
SEGMENTS = (
    ((0, 0, 0), (1, 0, 0)),
    ((10, 0, 0), (11, 0, 0)),
    ((20, 0, 0), (21, 0, 0)),
    ((30, 0, 0), (31, 0, 0)),
)
ALL_CELLS = frozenset(cell for segment in SEGMENTS for cell in segment)
NATIVE_GEOMETRY = {
    "map_id": MAP_ID,
    "cells": tuple(ALL_CELLS),
    "edges": tuple(
        edge for segment in SEGMENTS for edge in (segment, tuple(reversed(segment)))
    ),
}


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _ReadOnlyReceiptDB:
    def execute(self, query, args=()):
        if not query.lstrip().startswith("SELECT"):
            raise AssertionError("encounter-component admission must remain read-only")
        if "SELECT current_room,status" in query:
            return _Result({"current_room": 1, "status": "active"})
        if "FROM dungeon_room_spawn_receipts" in query:
            return _Result({"asset_map_id": MAP_ID, "group_id": GROUP_ID})
        raise AssertionError(("unexpected SQL", query))


def _room(anchor, *, component=1):
    return {
        "order": 1,
        "anchor": anchor,
        "cells": tuple(ALL_CELLS),
        "encounter_component": component,
    }


def _combat_cells(room, player, members):
    topology = {
        "asset_map_id": MAP_ID,
        "policy": "native_physical_room_policy",
        "rooms": [room],
        "doors": [],
        "branch_routes": [],
    }
    config = {"topology": topology, "version": 1}
    run = {"instance_id": INSTANCE_ID, "catalog_hash": "test-fixture"}
    with (
        patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(run, config)
        ),
        patch.object(dungeon_optional_encounters, "combat_cells", return_value=None),
        patch.object(
            combat_geometry, "published_geometry", return_value=NATIVE_GEOMETRY
        ),
    ):
        return dungeon_runtime.combat_room_cells(
            _ReadOnlyReceiptDB(), (MAP_ID, INSTANCE_ID, GROUP_ID), player, members
        )


class DungeonEncounterComponentBoundaryTests(unittest.TestCase):
    def test_each_bound_native_component_accepts_its_anchor_and_member(self):
        for segment in SEGMENTS:
            with self.subTest(anchor=segment[0]):
                selected = _combat_cells(_room(segment[0]), segment[0], [segment[1]])
                self.assertEqual(selected, frozenset(segment))

    def test_transit_components_are_rejected_and_unbound_legacy_room_is_unchanged(self):
        for owned, foreign in zip(SEGMENTS, reversed(SEGMENTS)):
            with self.subTest(owned=owned[0], foreign=foreign[0]):
                with self.assertRaisesRegex(
                    ValueError, "outside its physical encounter component"
                ):
                    _combat_cells(_room(owned[0]), foreign[0], [foreign[1]])

        # Without explicit component evidence the old selected-room behavior
        # remains intact, including disconnected room cells already in the room.
        legacy = _room(SEGMENTS[0][0])
        legacy.pop("encounter_component")
        self.assertEqual(
            _combat_cells(legacy, SEGMENTS[0][0], [SEGMENTS[3][1]]), ALL_CELLS
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
