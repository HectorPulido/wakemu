"""Native fishing range and immutable navigation authority regressions."""
import unittest
from unittest.mock import patch
from wakfu_server import fishing_navigation as fishing


class FishingNavigationTests(unittest.TestCase):
    def document(self):
        return dict(
            map_id=527,
            profile=fishing.PROFILE,
            provenance=dict(
                source="installed-client",
                client_sha256="a" * 64,
                topology_sha256="b" * 64,
                approach_authority="cWn.gu:VF.a:profession75",
            ),
            cells=[[3, 0, 100]],
            resource_approaches=[
                dict(
                    position=[0, 0, -100],
                    approaches=[[3, 0, 100]],
                    ground_id=187,
                    eligible_refs=[369],
                )
            ],
        )

    def test_native_range_three_accepts_arbitrary_height(self):
        self.assertEqual(
            fishing._incoming(self.document(), 527)[(0, 0, -100)]["approaches"],
            frozenset({(3, 0, 100)}),
        )

    def test_range_four_is_rejected(self):
        d = self.document()
        d["cells"] = [[4, 0, 100]]
        d["resource_approaches"][0]["approaches"] = [[4, 0, 100]]
        with self.assertRaises(ValueError):
            fishing._incoming(d, 527)

    def test_mining_provenance_is_rejected(self):
        d = self.document()
        d["provenance"]["approach_authority"] = "cWn.gu:VF.a:profession73"
        with self.assertRaises(ValueError):
            fishing._incoming(d, 527)

    def test_missing_or_invalid_revision_fails_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                fishing._revision()
        with patch.dict(
            "os.environ", {"WAKFU_FISHING_CATALOG_REVISION": "broken"}, clear=True
        ):
            with self.assertRaises(ValueError):
                fishing._map_index("broken", 527)

    def test_checksum_mismatch_is_rejected(self):
        fishing._map_index.cache_clear()
        with patch.dict(
            "os.environ", {"WAKFU_FISHING_CATALOG_REVISION": "a" * 64}
        ), patch.object(fishing.native_catalog, "_database") as database:
            database.return_value.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
                "raw": b"{}",
                "sha256": "b" * 64,
            }
            with self.assertRaisesRegex(ValueError, "checksum"):
                fishing._map_index("a" * 64, 527)


if __name__ == "__main__":
    unittest.main()
