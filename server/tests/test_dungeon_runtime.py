"""Focused contracts for pinning native dungeon rooms to durable runs."""
import unittest
from unittest.mock import Mock, call, patch

from wakfu_server.maps import dungeon_runtime


class DungeonRuntimeTests(unittest.TestCase):
    def test_configuration_uses_persisted_context_columns_and_pinned_roster_hash(self):
        run = {
            "instance_id": 81,
            "party_id": 19,
            "context_route_key": "jalato_normal",
            "context_policy_version": 3,
        }
        digest = "a" * 64
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=Mock(return_value=run)),
            Mock(fetchone=Mock(return_value={"catalog_hash": digest})),
        ]
        config = {"topology": {"asset_map_id": 1086, "rooms": []}}

        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            return_value=config,
        ) as pinned:
            result = dungeon_runtime.configuration_for_instance(db, 81)

        self.assertEqual((run, config), result)
        self.assertEqual(
            call(db, "jalato_normal", 3, expected_plan_hash=digest), pinned.call_args
        )
        self.assertIn("dungeon_instances", db.execute.call_args_list[0].args[0])
        self.assertIn("dungeon_room_runs", db.execute.call_args_list[1].args[0])

    def test_missing_progress_hash_pins_current_configuration_without_hash(self):
        run = {
            "instance_id": 82,
            "context_route_key": "jalato_normal",
            "context_policy_version": 3,
        }
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=Mock(return_value=run)),
            Mock(fetchone=Mock(return_value=None)),
        ]
        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            return_value={"topology": {}},
        ) as pinned:
            dungeon_runtime.configuration_for_instance(db, 82)
        self.assertEqual(
            call(db, "jalato_normal", 3, expected_plan_hash=None), pinned.call_args
        )

    def test_pinned_roster_hash_mismatch_aborts_runtime_configuration(self):
        run = {
            "instance_id": 83,
            "context_route_key": "jalato_normal",
            "context_policy_version": 3,
        }
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=Mock(return_value=run)),
            Mock(fetchone=Mock(return_value={"catalog_hash": "c" * 64})),
        ]
        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            side_effect=ValueError("Pinned dungeon roster differs from existing run"),
        ) as pinned:
            with self.assertRaisesRegex(ValueError, "roster differs"):
                dungeon_runtime.configuration_for_instance(db, 83)
        self.assertEqual("c" * 64, pinned.call_args.kwargs["expected_plan_hash"])

    def test_current_room_spawn_geometry_excludes_adjacent_native_room(self):
        first = [(0, 0, 0), (1, 0, 0)]
        adjacent = [(10, 0, 0), (11, 0, 0)]
        config = {
            "level_policy": {"mode": "native_minimum"},
            "topology": {
                "asset_map_id": 1086,
                "rooms": [
                    {"order": 1, "anchor": first[0], "cells": first},
                    {"order": 2, "anchor": adjacent[0], "cells": adjacent},
                ],
            },
        }
        run = {
            "instance_id": 81,
            "context_route_key": "jalato_normal",
            "context_policy_version": 3,
        }
        progress = {"current_room": 1}
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=Mock(return_value=run)),
            Mock(fetchone=Mock(return_value={"catalog_hash": "b" * 64})),
            Mock(fetchone=Mock(return_value=progress)),
        ]
        geometry = {
            "map_id": 1086,
            "cells": first + adjacent,
            "edges": [
                [first[0], first[1]],
                [first[1], adjacent[0]],
                [adjacent[0], adjacent[1]],
            ],
            "metadata": "native",
        }
        expected = {"group": 1}

        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            return_value=config,
        ), patch.object(
            dungeon_runtime.dungeon_room_spawns,
            "ensure_room_group",
            return_value=expected,
        ) as ensure:
            result = dungeon_runtime.ensure_current_room(db, Mock(), 81, geometry)

        self.assertIs(result, expected)
        self.assertEqual(first[0], ensure.call_args.kwargs["anchor"])
        frozen_geometry = ensure.call_args.kwargs["geometry"]
        self.assertEqual(set(first), set(frozen_geometry["cells"]))
        self.assertEqual(((first[0], first[1]),), frozen_geometry["edges"])
        self.assertEqual("native", frozen_geometry["metadata"])

    def test_wrong_map_or_missing_frozen_terrain_fails_before_spawn(self):
        cell = (4, -12, 0)
        config = {
            "topology": {
                "asset_map_id": 1086,
                "rooms": [
                    {"order": 1, "anchor": cell, "cells": [cell]},
                ],
            }
        }
        db = Mock()
        db.execute.side_effect = [
            Mock(
                fetchone=Mock(
                    return_value={
                        "instance_id": 81,
                        "context_route_key": "jalato_normal",
                        "context_policy_version": 3,
                    }
                )
            ),
            Mock(fetchone=Mock(return_value=None)),
            Mock(fetchone=Mock(return_value={"current_room": 1})),
        ]
        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            return_value=config,
        ), patch.object(
            dungeon_runtime.dungeon_room_spawns, "ensure_room_group"
        ) as ensure:
            with self.assertRaisesRegex(ValueError, "geometry differs"):
                dungeon_runtime.ensure_current_room(
                    db, Mock(), 81, {"map_id": 77, "cells": [cell], "edges": []}
                )

        db.execute.side_effect = [
            Mock(
                fetchone=Mock(
                    return_value={
                        "instance_id": 81,
                        "context_route_key": "jalato_normal",
                        "context_policy_version": 3,
                    }
                )
            ),
            Mock(fetchone=Mock(return_value=None)),
            Mock(fetchone=Mock(return_value={"current_room": 1})),
        ]
        with patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "pinned_configuration",
            return_value=config,
        ), patch.object(
            dungeon_runtime.dungeon_room_spawns, "ensure_room_group"
        ) as ensure:
            with self.assertRaisesRegex(ValueError, "cells are absent"):
                dungeon_runtime.ensure_current_room(
                    db, Mock(), 81, {"map_id": 1086, "cells": [], "edges": []}
                )
            ensure.assert_not_called()

    def test_roster_freeze_precedes_first_room_spawn(self):
        run = {"instance_id": 81, "party_id": 19}
        config = {"topology": {"asset_map_id": 1086, "rooms": []}}
        order = []
        db = Mock()
        groups = Mock()
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(run, config)
        ), patch.object(
            dungeon_runtime.dungeon_runtime_config,
            "plan_from_configuration",
            return_value="frozen-plan",
        ), patch.object(
            dungeon_runtime.dungeon_progression,
            "initialize_run",
            side_effect=lambda *_: order.append("freeze"),
        ) as freeze, patch.object(
            dungeon_runtime,
            "ensure_current_room",
            side_effect=lambda *_args, **_kwargs: order.append("spawn") or "group",
        ) as spawn:
            result = dungeon_runtime.initialize_instance(
                db, {"instance_id": 81}, groups=groups, geometry={"map_id": 1086}
            )

        self.assertEqual(["freeze", "spawn"], order)
        freeze.assert_called_once_with(db, 81, 19, "frozen-plan")
        self.assertEqual((db, groups, 81, {"map_id": 1086}), spawn.call_args.args)
        self.assertEqual({"map_id": 1086}, spawn.call_args.args[3])
        self.assertEqual("group", result)

    def test_room_lookup_rejects_other_map_and_maps_only_its_native_cells(self):
        config = {
            "topology": {
                "asset_map_id": 1086,
                "rooms": [
                    {"order": 1, "cells": [(0, 0, 0)]},
                    {"order": 2, "cells": [(10, 0, 0)]},
                ],
            }
        }
        self.assertEqual(2, dungeon_runtime.room_for_position(config, 1086, 10, 0, 0))
        with self.assertRaisesRegex(ValueError, "another asset map"):
            dungeon_runtime.room_for_position(config, 7, 10, 0, 0)
        with self.assertRaisesRegex(ValueError, "does not identify one native room"):
            dungeon_runtime.room_for_position(config, 1086, 5, 0, 0)


if __name__ == "__main__":
    unittest.main()
