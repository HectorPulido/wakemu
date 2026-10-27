"""Real SQL supplements retain original source identity in fresh publications."""
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class NativeSupplementCompatibilityTests(PostgresCase):
    def test_nine_flags_two_owned_roots_fresh_sources_and_changed_dependencies(self):
        from wakfu_server import native_catalog as catalog
        from wakfu_server import native_catalog_compatibility as compatibility
        from wakfu_server import combat_health_ordering_authority as health
        from wakfu_server import native_casting_roots as casting

        directory = Path(__file__).resolve().parents[1] / "data/installation/catalogs"
        manifest = json.loads(
            (directory / "manifest-rift-complete-metadata-v1.json").read_bytes()
        )
        current = manifest["active_revision"]
        release = next(
            row for row in manifest["releases"] if row["revision"] == current
        )
        hashes = {row["path"]: row["sha256"] for row in release["documents"]}
        proof_sha = hashes[compatibility.MANIFEST_DOCUMENT]
        proof = gzip.decompress(
            (directory / "parts" / (proof_sha + ".json.gz")).read_bytes()
        )
        self.assertEqual(hashlib.sha256(proof).hexdigest(), proof_sha)
        authority = json.loads(
            (
                Path(__file__).with_name("fixtures")
                / "native_descending_health_ordering_authority.json"
            ).read_bytes()
        )
        with self.store.connection() as db:
            # An installation need not retain ANY old published catalog rows.
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_releases"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_health_ordering_authority_rows"
                ).fetchone()["n"],
                9,
            )
            originals = db.execute(
                "SELECT catalog_revision,root_id,source_spell_references FROM native_casting_root_supplements ORDER BY root_id"
            ).fetchall()
            self.assertEqual([row["root_id"] for row in originals], [401997, 402030])
            self.assertTrue(
                all(row["source_spell_references"] == [8460] for row in originals)
            )
            self.assertTrue(
                all(
                    row["catalog_revision"] == authority["catalog_revision"]
                    for row in originals
                )
            )

        def reset():
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()
            health._for_revision.cache_clear()
            casting._supplemental_root.cache_clear()

        reset()
        self.addCleanup(reset)
        active = {"revision": current}
        with patch.object(catalog, "_database", return_value=self.store), patch.object(
            catalog, "release", side_effect=lambda: active["revision"]
        ), patch.object(catalog, "document_hashes", return_value=hashes), patch.object(
            catalog, "read_published_bytes", return_value=proof
        ) as read_proof:
            actual = health.descending_health_target_ordering()
            self.assertEqual(len(actual), 9)
            for reference, row in actual.items():
                self.assertEqual(
                    dict(row, native_effect_flags=list(row["native_effect_flags"])),
                    authority["rows"][reference],
                )
            for root, mask in ((401997, 1266637395197957), (402030, 140737488363540)):
                metadata = casting.supplemental_root(root, spell_reference=8460)
                self.assertIsNone(metadata["native_casting_collision_area"])
                self.assertIs(metadata["native_selector_present"], True)
                self.assertEqual(
                    metadata["native_target_selector"], {"class": "fcE", "mask": mask}
                )
                self.assertIsNone(casting.supplemental_root(root, spell_reference=4778))
            self.assertIsNone(casting.supplemental_root(1, spell_reference=8460))
            read_proof.assert_called_once_with(compatibility.MANIFEST_DOCUMENT)
            # Unavailable/changed source documents reject instead of silently
            # dropping all flag25 identities or both owned casting supplements.
            for operation, paths in (
                (health.descending_health_target_ordering, health.SOURCE_DOCUMENTS),
                (
                    lambda: casting.supplemental_root(401997, spell_reference=8460),
                    casting.SOURCE_DOCUMENTS,
                ),
            ):
                for path in paths:
                    reset()
                    changed = dict(hashes, **{path: "b" * 64})
                    with patch.object(catalog, "document_hashes", return_value=changed):
                        with self.assertRaisesRegex(
                            ValueError, "source dependencies changed"
                        ):
                            operation()
            # A publication change during the compatibility proof cannot be
            # cached or returned under the request's former publication key.
            real_require = compatibility.require_source_revision

            def change_after_proof(*args):
                real_require(*args)
                active["revision"] = "f" * 64

            for operation in (
                health.descending_health_target_ordering,
                lambda: casting.supplemental_root(401997, spell_reference=8460),
            ):
                active["revision"] = current
                reset()
                with patch.object(
                    compatibility,
                    "require_source_revision",
                    side_effect=change_after_proof,
                ):
                    with self.assertRaisesRegex(
                        ValueError, "publication changed during lookup"
                    ):
                        operation()
            active["revision"] = current
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT DISTINCT catalog_revision FROM native_casting_root_supplements"
                ).fetchone()["catalog_revision"],
                authority["catalog_revision"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT catalog_revision FROM native_health_ordering_authority_versions"
                ).fetchone()["catalog_revision"],
                authority["catalog_revision"],
            )
