import copy
import hashlib
import json
import os
import unittest
from unittest.mock import patch

from wakfu_server import mining_navigation as navigation


class MiningNavigationTests(unittest.TestCase):
    def setUp(self):
        navigation._map_index.cache_clear()
        self.previous_revision = os.environ.pop("WAKFU_MINING_CATALOG_REVISION", None)
        self.addCleanup(self._restore_revision)
        self.addCleanup(navigation._map_index.cache_clear)
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

    def _restore_revision(self):
        os.environ.pop("WAKFU_MINING_CATALOG_REVISION", None)
        if self.previous_revision is not None:
            os.environ["WAKFU_MINING_CATALOG_REVISION"] = self.previous_revision

    def _published_document_row(self, *, sha256=None):
        raw = json.dumps(self.document, separators=(",", ":")).encode("utf-8")
        return {"raw": raw, "sha256": sha256 or hashlib.sha256(raw).hexdigest()}

    def _database(self, row, calls, *, release_complete=True):
        class FakeDatabase:
            def connection(self):
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def execute(self, query, params):
                calls.append((query, params))
                return self

            def fetchone(self):
                return row if release_complete else None

        return FakeDatabase

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

    def test_mining_revision_pin_does_not_read_or_change_active_catalog(self):
        revision = "d" * 64
        os.environ["WAKFU_MINING_CATALOG_REVISION"] = revision
        calls = []
        with patch.object(
            navigation.native_catalog,
            "release",
            return_value="c" * 64,
        ) as release, patch.object(
            navigation.native_catalog,
            "_database",
            return_value=self._database(self._published_document_row(), calls)(),
        ):
            self.assertEqual(revision, navigation._revision())
            self.assertEqual(
                frozenset({(10000, -20000, 6)}),
                navigation.approaches(2419, (10001, -20000, 2)),
            )
        release.assert_not_called()
        self.assertEqual(1, len(calls))
        query, params = calls[0]
        self.assertIn("JOIN native_catalog_releases r USING(revision)", query)
        self.assertIn("AND r.complete", query)
        self.assertEqual((revision, "world-navigation/2419.json"), params)

    def test_pinned_navigation_rejects_missing_or_incomplete_document(self):
        os.environ["WAKFU_MINING_CATALOG_REVISION"] = "d" * 64
        cases = (
            ("missing document", None, True),
            ("incomplete release", self._published_document_row(), False),
        )
        for label, row, release_complete in cases:
            with self.subTest(case=label):
                navigation._map_index.cache_clear()
                calls = []
                with patch.object(
                    navigation.native_catalog,
                    "_database",
                    return_value=self._database(
                        row, calls, release_complete=release_complete
                    )(),
                ):
                    with self.assertRaisesRegex(ValueError, "unavailable"):
                        navigation.approaches(2419, (10001, -20000, 2))
                self.assertIn("AND r.complete", calls[0][0])

    def test_pinned_navigation_rejects_incomplete_geometry_document(self):
        os.environ["WAKFU_MINING_CATALOG_REVISION"] = "d" * 64
        incomplete = dict(self.document)
        incomplete.pop("cells")
        raw = json.dumps(incomplete, separators=(",", ":")).encode("utf-8")
        row = {"raw": raw, "sha256": hashlib.sha256(raw).hexdigest()}
        with patch.object(
            navigation.native_catalog,
            "_database",
            return_value=self._database(row, [])(),
        ):
            with self.assertRaisesRegex(ValueError, "geometry"):
                navigation.approaches(2419, (10001, -20000, 2))

    def test_pinned_navigation_rejects_checksum_tampering(self):
        os.environ["WAKFU_MINING_CATALOG_REVISION"] = "d" * 64
        row = self._published_document_row(sha256="0" * 64)
        with patch.object(
            navigation.native_catalog,
            "_database",
            return_value=self._database(row, [])(),
        ):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                navigation.approaches(2419, (10001, -20000, 2))

    def test_pinned_navigation_reads_valid_geometry_from_database(self):
        revision = "e" * 64
        os.environ["WAKFU_MINING_CATALOG_REVISION"] = revision
        calls = []
        row = self._published_document_row()
        with patch.object(
            navigation.native_catalog,
            "_database",
            return_value=self._database(row, calls)(),
        ), patch.object(
            navigation.native_catalog, "exists", side_effect=AssertionError
        ), patch.object(
            navigation.native_catalog, "load", side_effect=AssertionError
        ):
            self.assertEqual(
                frozenset({(10000, -20000, 6)}),
                navigation.approaches(2419, (10001, -20000, 2)),
            )
            self.assertEqual(
                {
                    "ground_id": 75,
                    "eligible_refs": frozenset({433}),
                    "approaches": frozenset({(10000, -20000, 6)}),
                },
                navigation.surface(2419, 10001, -20000, 2),
            )
        self.assertEqual(1, len(calls))
        self.assertEqual((revision, "world-navigation/2419.json"), calls[0][1])
