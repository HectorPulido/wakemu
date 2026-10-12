"""In-memory fences for canceling prepared ecology planting work."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server import ecology_admin_runtime


class EcologyAdminRuntimeTests(unittest.TestCase):
    def test_nuke_scope_cancels_only_monster_work_in_target_region(self):
        tickets = {
            "target-monster": {
                "prepared": {
                    "definition": {"monster_resource": True},
                    "character": {"map_id": 1000, "instance_id": 0},
                    "request": {"x": 5, "y": 6},
                }
            },
            "neighboring-region": {
                "prepared": {
                    "definition": {"monster_resource": True},
                    "character": {"map_id": 1000, "instance_id": 0},
                    "request": {"x": 50, "y": 60},
                }
            },
            "flora": {
                "prepared": {
                    "definition": {"monster_resource": False},
                    "character": {"map_id": 1000, "instance_id": 0},
                    "request": {"x": 5, "y": 6},
                }
            },
            "other-map": {
                "prepared": {
                    "definition": {"monster_resource": True},
                    "character": {"map_id": 1001, "instance_id": 0},
                    "request": {"x": 5, "y": 6},
                }
            },
            "private-instance": {
                "prepared": {
                    "definition": {"monster_resource": True},
                    "character": {"map_id": 1000, "instance_id": 42},
                    "request": {"x": 5, "y": 6},
                }
            },
        }

        class Plantings:
            pending = tickets.copy()

            def __init__(self):
                self.cancelled = []

            def cancel(self, identity):
                self.cancelled.append(identity)

        plantings = Plantings()
        with patch(
            "wakfu_server.territory_cells.region_at",
            side_effect=lambda _map, x, _y: 7 if x < 20 else 8,
        ):
            count = ecology_admin_runtime.cancel_plantings(
                plantings,
                {"scopes": [(1000, 0, 7)]},
            )

        self.assertEqual(count, 1)
        self.assertEqual(plantings.cancelled, ["target-monster"])

    def test_global_reset_cancels_monsters_across_regions_but_keeps_flora(self):
        tickets = {
            "monster": {
                "prepared": {
                    "definition": {"monster_resource": True},
                    "character": {"map_id": 1000, "instance_id": 0},
                    "request": {"x": 50, "y": 60},
                }
            },
            "flora": {
                "prepared": {
                    "definition": {"monster_resource": False},
                    "character": {"map_id": 1000, "instance_id": 0},
                    "request": {"x": 50, "y": 60},
                }
            },
        }

        class Plantings:
            pending = tickets.copy()

            def __init__(self):
                self.cancelled = []

            def cancel(self, identity):
                self.cancelled.append(identity)

        plantings = Plantings()
        count = ecology_admin_runtime.cancel_plantings(
            plantings,
            {"scopes": [(1000, 0, None)]},
        )
        self.assertEqual(count, 1)
        self.assertEqual(plantings.cancelled, ["monster"])

    def test_explicitly_cancelled_actor_is_pruned_even_if_ticket_is_gone(self):
        class Plantings:
            pending = {}

            def __init__(self):
                self.cancelled = []

            def cancel(self, identity):
                self.cancelled.append(identity)

        plantings = Plantings()
        count = ecology_admin_runtime.cancel_plantings(
            plantings,
            {"scopes": [], "cancelled_characters": [77]},
        )
        self.assertEqual(count, 1)
        self.assertEqual(plantings.cancelled, [77])


class FloraAdminRuntimeTests(unittest.TestCase):
    def test_global_flora_reset_preserves_monsters_and_private_gardens(self):
        def ticket(monster, instance=0, map_id=1134):
            return {
                "prepared": {
                    "definition": {"monster_resource": monster},
                    "character": {"map_id": map_id, "instance_id": instance},
                    "request": {"x": 1, "y": 2},
                }
            }

        class Plantings:
            pending = {
                "flora": ticket(False),
                "monster": ticket(True),
                "private-flora": ticket(False, instance=17),
                "other-map": ticket(False, map_id=527),
            }

            def __init__(self):
                self.cancelled = []

            def cancel(self, identity):
                self.cancelled.append(identity)

        plantings = Plantings()
        count = ecology_admin_runtime.cancel_plantings(
            plantings, {"flora": True, "scopes": [(1134, 0, None)]}
        )
        self.assertEqual(count, 1)
        self.assertEqual(plantings.cancelled, ["flora"])
