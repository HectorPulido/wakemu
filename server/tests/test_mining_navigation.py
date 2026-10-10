import copy
import unittest
from unittest.mock import patch

from wakfu_server import mining_navigation as navigation


class MiningNavigationTests(unittest.TestCase):
    def setUp(self):
        navigation._map_index.cache_clear()
        self.document = {
            "map_id": 2419,
            "profile": navigation.PROFILE,
            "provenance": {
                "source": "installed-client",
                "client_sha256": "a" * 64,
                "topology_sha256": "b" * 64,
                "approach_authority": "cWn.gu:VF.a:profession73",
            },
            "cells": [[10000, -20000, 6]],
            "resource_approaches": [
                {
                    "position": [10001, -20000, 2],
                    "ground_id": 75,
                    "eligible_refs": [433],
                    "approaches": [[10000, -20000, 6]],
                }
            ],
        }

    def test_nonwalkable_resource_uses_published_native_neighbor(self):
        with patch.object(
            navigation.native_catalog, "release", return_value="r1"
        ), patch.object(
            navigation.native_catalog, "exists", return_value=True
        ), patch.object(
            navigation.native_catalog, "load", return_value=self.document
        ):
            self.assertEqual(
                frozenset({(10000, -20000, 6)}),
                navigation.approaches(2419, (10001, -20000, 2)),
            )
            player = dict(map_id=2419, instance_id=0, x=10000, y=-20000, z=6)
            mineral = dict(map_id=2419, instance_id=0, x=10001, y=-20000, z=2)
            self.assertTrue(navigation.reachable(player, mineral))
            ground = navigation.surface(2419, 10001, -20000, 2)
            self.assertEqual(75, ground["ground_id"])
            self.assertEqual(frozenset({433}), ground["eligible_refs"])
            self.assertFalse(navigation.reachable(mineral, player))
            self.assertFalse(navigation.reachable(player, dict(mineral, instance_id=1)))
            with self.assertRaisesRegex(ValueError, "no native world"):
                navigation.validate_placement(2419, (10000, -20000, 6))

    def test_unpublished_world_catalog_fails_closed(self):
        with patch.object(
            navigation.native_catalog, "release", return_value="r1"
        ), patch.object(navigation.native_catalog, "exists", return_value=False):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                navigation.approaches(2419, (10001, -20000, 2))

    def test_invalid_profile_provenance_and_edges_fail_closed(self):
        for edit in (
            {"map_id": 2980},
            {"profile": "combat"},
            {"provenance": {}},
            {
                "resource_approaches": [
                    {"position": [10001, -20000, 2], "approaches": [[0, 0, 0]]}
                ]
            },
            {
                "resource_approaches": [
                    {"position": [10000, -20000, 6], "approaches": [[10000, -20000, 6]]}
                ]
            },
        ):
            with self.subTest(edit=edit):
                document = copy.deepcopy(self.document)
                document.update(edit)
                with self.assertRaises(ValueError):
                    navigation._incoming(document, 2419)

    def test_publication_revision_reloads_geometry(self):
        with patch.object(
            navigation.native_catalog, "release", side_effect=["r1", "r1", "r2"]
        ), patch.object(
            navigation.native_catalog, "exists", return_value=True
        ), patch.object(
            navigation.native_catalog, "load", return_value=self.document
        ) as load:
            for _ in range(3):
                navigation.approaches(2419, (10001, -20000, 2))
            self.assertEqual(2, load.call_count)
