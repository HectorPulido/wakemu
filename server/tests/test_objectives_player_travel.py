"""Native travel destinations require exact, non-stacked published floors."""
import hashlib
import json
import unittest
from unittest.mock import patch

from wakfu_server.objectives import player_travel


class _GeometryDB:
    def __init__(self, documents):
        self.documents = documents
        self.reads = []

    def execute(self, sql, params):
        revision, path = params
        self.reads.append((revision, path))
        document = self.documents.get((revision, path), self.documents.get(path))
        if document is None:
            return _Row(None)
        if "convert_from(raw" in sql:
            return _Row({"cells": document.get("cells", []), "verified": True})
        raw = json.dumps(document).encode()
        return _Row({"raw": raw, "sha256": hashlib.sha256(raw).hexdigest()})


class _Row:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class ObjectivesPlayerTravelTests(unittest.TestCase):
    def setUp(self):
        player_travel._CACHE.clear()
        player_travel._GEOMETRY_INDEXES.clear()
        player_travel._TARGETS.clear()

    def test_native_transport_accepts_integral_float_but_rejects_fraction_and_bool(
        self,
    ):
        self.assertEqual(player_travel._coordinates(41.0, 2.0, -3, 1.0), (41, 2, -3, 1))
        self.assertIsNone(player_travel._coordinates(41, 2.5, -3, 1))
        self.assertIsNone(player_travel._coordinates(True, 2, -3, 1))

    def test_native_approach_floor_can_differ_from_object_altitude(self):
        db = _GeometryDB({"combat-maps/527.json": {"cells": [[-245, -89, 0]]}})
        source = dict(
            map_id=527,
            x=-245,
            y=-90,
            z=2,
            approach_positions=[dict(x=-245, y=-89, z=0)],
        )
        self.assertIsNone(
            player_travel._target(db, "release", 527, -245, -90, 2, nearby=True)
        )
        target = player_travel._entrance_target(db, "release", source)
        self.assertEqual((target["x"], target["y"], target["z"]), (-245, -89, 0))

    def test_native_approach_skips_missing_fractional_and_stacked_floors(self):
        db = _GeometryDB(
            {"combat-maps/41.json": {"cells": [[1, 1, 0], [1, 1, 2], [2, 1, 0]]}}
        )
        source = dict(
            map_id=41,
            x=0,
            y=0,
            z=9,
            approach_positions=[
                dict(x=1.5, y=1, z=0),
                dict(x=10, y=10, z=0),
                dict(x=1, y=1, z=0),
                dict(x=2, y=1, z=0),
            ],
        )
        self.assertEqual(player_travel._entrance_target(db, "release", source)["x"], 2)
        source["approach_positions"] = source["approach_positions"][:-1]
        self.assertIsNone(player_travel._entrance_target(db, "release", source))

    def test_legacy_entrance_without_approach_uses_bounded_floor_fallback(self):
        db = _GeometryDB({"combat-maps/41.json": {"cells": [[2, 1, 0]]}})
        target = player_travel._entrance_target(
            db, "release", dict(map_id=41, x=1, y=1, z=0)
        )
        self.assertEqual(target["x"], 2)

    def test_dungeon_travel_needs_no_zaap_or_exploration_achievement(self):
        class DB(_GeometryDB):
            private_exterior = False

            def execute(self, sql, params=None):
                if "objectives_travel_cost" in sql:
                    return _Row(dict(value=500))
                if "dungeon_runtime_configurations" in sql:
                    return _Row(
                        [
                            dict(
                                route=dict(
                                    key="native-route",
                                    definition_id=77,
                                    entry_map_id=472,
                                    start_map_id=472 if self.private_exterior else 476,
                                    entry_object_id=2,
                                    destination_id=88,
                                )
                            )
                        ]
                    )
                if "native_catalog_active" in sql:
                    return _Row(dict(revision="release"))
                return super().execute(sql, params)

        db = DB(
            {
                "combat-maps/472.json": {"cells": [[1, 1, 0]]},
                "native-generic-teleporters.json": [
                    dict(
                        id=2,
                        map_id=472,
                        x=1,
                        y=1,
                        z=0,
                        destinations=[dict(destination_id=88, map_id=476)],
                    )
                ],
            }
        )
        rules = {
            "content-v1.dungeon.77": dict(key="content-v1.dungeon.77", title="Dungeon")
        }
        with patch.object(player_travel, "_eligible", return_value=rules):
            actions = player_travel.actions(db, {})
            self.assertEqual([a["action_key"] for a in actions], ["travel.dungeon.77"])
            self.assertEqual(actions[0]["target"]["map_id"], 472)
            self.assertEqual(actions[0]["cost_kamas"], 500)
            self.assertEqual(
                player_travel.actions(db, {}, "travel.dungeon.77"), actions
            )
            self.assertEqual(player_travel.actions(db, {}, "travel.map.472"), [])
            db.private_exterior = True
            self.assertEqual(player_travel.actions(db, {}), [])
            db.private_exterior = False
            player_travel._CACHE.clear()
            db.documents["native-generic-teleporters.json"][0]["destinations"][0][
                "destination_id"
            ] = 99
            self.assertEqual(player_travel.actions(db, {}), [])
            with self.assertRaisesRegex(ValueError, "unavailable"):
                player_travel.resolve(db, {}, "travel.dungeon.77")
        self.assertFalse(
            any(
                path in ("native-transports.json", "native-transport-objects.json")
                for _, path in db.reads
            )
        )

    def test_only_exact_single_height_floor_is_a_travel_target(self):
        db = _GeometryDB(
            {
                "combat-maps/41.json": {
                    "cells": [[2, -3, 1], [3, -3, 1], [4, -3, 0], [4, -3, 1]]
                }
            }
        )
        exact = player_travel._target(db, "fixture-release", 41, 2.0, -3, 1)
        self.assertEqual(
            exact, {"map_id": 41, "instance_id": 0, "x": 2, "y": -3, "z": 1}
        )
        self.assertIsNone(player_travel._target(db, "fixture-release", 41, 3, -3, 0))
        self.assertIsNone(player_travel._target(db, "fixture-release", 41, 4, -3, 1))
        self.assertIsNone(player_travel._target(db, "fixture-release", 42, 2, -3, 1))
        nearby = player_travel._target(db, "fixture-release", 41, 3, -3, 0, nearby=True)
        self.assertEqual(
            nearby, {"map_id": 41, "instance_id": 0, "x": 3, "y": -3, "z": 1}
        )
        exact_wins = player_travel._floor_target(
            {"cells": [[2, -3, 1], [3, -3, 1]]}, 41, 2, -3, 1, nearby=True
        )
        self.assertEqual((exact_wins["x"], exact_wins["z"]), (2, 1))

    def test_nearby_dungeon_floor_is_bounded_and_skips_stacked_cells(self):
        self.assertIsNone(
            player_travel._floor_target(
                {"cells": [[10, 0, 1]]}, 41, 5, 0, 1, nearby=True
            )
        )
        self.assertIsNone(
            player_travel._floor_target(
                {"cells": [[1, 0, 3]]}, 41, 1, 0, 1, nearby=True
            )
        )
        self.assertIsNone(
            player_travel._floor_target(
                {"cells": [[1, 0, 0], [1, 0, 1]]}, 41, 0, 0, 0, nearby=True
            )
        )
        tied = player_travel._floor_target(
            {"cells": [[1, 0, 1], [-1, 0, 1]]}, 41, 0, 0, 1, nearby=True
        )
        self.assertEqual((tied["x"], tied["y"], tied["z"]), (-1, 0, 1))

    def test_index_cache_invalidates_by_native_release_and_return_values_are_isolated(
        self,
    ):
        db = _GeometryDB(
            {
                ("release-a", "combat-maps/41.json"): {"cells": [[2, -3, 1]]},
                ("release-b", "combat-maps/41.json"): {"cells": [[2, -3, 0]]},
            }
        )
        first = player_travel._target(db, "release-a", 41, 2, -3, 1)
        first["x"] = 999
        second = player_travel._target(db, "release-a", 41, 2, -3, 1)
        changed_release = player_travel._target(db, "release-b", 41, 2, -3, 1)
        self.assertEqual(
            second, {"map_id": 41, "instance_id": 0, "x": 2, "y": -3, "z": 1}
        )
        self.assertIsNone(changed_release)
        self.assertEqual(
            db.reads,
            [
                ("release-a", "combat-maps/41.json"),
                ("release-b", "combat-maps/41.json"),
            ],
        )

    def test_geometry_and_target_lru_caches_stay_within_configured_limits(self):
        old_geometry_limit = player_travel._GEOMETRY_LIMIT
        old_column_limit = player_travel._GEOMETRY_COLUMN_LIMIT
        old_target_limit = player_travel._TARGET_LIMIT
        try:
            player_travel._GEOMETRY_LIMIT = 4
            player_travel._GEOMETRY_COLUMN_LIMIT = 5
            player_travel._TARGET_LIMIT = 3
            maps = {
                f"combat-maps/{map_id}.json": {"cells": [[1, 1, 0], [2, 1, 0]]}
                for map_id in range(1, 6)
            }
            db = _GeometryDB(maps)
            for map_id in range(1, 6):
                player_travel._target(db, "bounded-release", map_id, 1, 1, 0)
            self.assertLessEqual(len(player_travel._GEOMETRY_INDEXES), 4)
            self.assertLessEqual(
                sum(map(len, player_travel._GEOMETRY_INDEXES.values())), 5
            )
            for x in range(5):
                player_travel._target(db, "bounded-release", 1, x + 10, 0, 0)
            self.assertLessEqual(len(player_travel._TARGETS), 3)
        finally:
            player_travel._GEOMETRY_LIMIT = old_geometry_limit
            player_travel._GEOMETRY_COLUMN_LIMIT = old_column_limit
            player_travel._TARGET_LIMIT = old_target_limit


if __name__ == "__main__":
    unittest.main()
