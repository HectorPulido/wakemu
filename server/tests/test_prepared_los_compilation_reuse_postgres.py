"""Map compilation reuse links real SQL contents without copying map records."""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import publish_compiled_combat_catalog as publisher
from wakfu_server import native_catalog, native_compiled_catalog as storage
from wakfu_server import prepared_los_compiled as prepared


class MapCompilationReusePostgresTests(PostgresCase):
    def test_second_generation_reuses_map_content_and_changed_map_rebuilds(self):
        source_raw = json.dumps(
            dict(
                map_id=7,
                schema="native-Sf-Vz-columns-v1",
                columns=[[2, 3, [[0, 2, True]]]],
            )
        ).encode()
        checksum = hashlib.sha256(source_raw).hexdigest()
        identity = dict(
            policy=storage.PUBLICATION_POLICY,
            source_revision="a" * 64,
            source_inventory_sha256="b" * 64,
            compiler_contract_sha256="c" * 64,
            config_sha256="d" * 64,
            source_documents={"native-los-topology/7.json": checksum},
            compiler_sources={name: "e" * 64 for name in prepared._COMPILER_INPUTS},
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,1,%s,true)",
                (identity["source_revision"], len(source_raw)),
            )
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(
            native_catalog, "release", return_value=identity["source_revision"]
        ):
            first = publisher.PublicationSpool(str(Path(temporary) / "first.sqlite"))
            self.addCleanup(first.db.close)
            with patch.object(
                native_catalog, "read_published_bytes", return_value=source_raw
            ):
                prepared_entry, reused = prepared.publish_map_collection(
                    first, identity
                )
            self.assertFalse(reused)
            manifest = dict(
                identity,
                collections=first.collections,
                prepared_los=prepared_entry,
                variants={},
                documents={},
            )
            with self.store.connection() as db:
                original = publisher.publish(
                    db, first, manifest, storage.canonical_bytes
                )

            second = publisher.PublicationSpool(str(Path(temporary) / "second.sqlite"))
            self.addCleanup(second.db.close)
            # An unrelated compiler change creates a new publication without
            # invalidating the map compiler's narrower input inventory.
            changed_identity = dict(
                identity,
                compiler_contract_sha256="f" * 64,
                compiler_sources=dict(identity["compiler_sources"], unrelated="f" * 64),
            )
            with patch.object(
                prepared,
                "CompilerRecords",
                side_effect=AssertionError("must reuse maps"),
            ), patch.object(
                native_catalog,
                "read_published_bytes",
                side_effect=AssertionError("must not read maps"),
            ):
                entry, reused = prepared.publish_map_collection(
                    second, changed_identity
                )
            self.assertTrue(reused)
            self.assertEqual(
                second.db.execute("SELECT count(*) FROM records").fetchone()[0], 0
            )
            self.assertEqual(entry, prepared_entry)
            second_manifest = dict(
                changed_identity,
                collections=second.collections,
                prepared_los=entry,
                variants={},
                documents={},
            )
            with patch.object(publisher, "log") as logs, self.store.connection() as db:
                new = publisher.publish(
                    db, second, second_manifest, storage.canonical_bytes
                )
            copied = [
                call.kwargs
                for call in logs.call_args_list
                if call.args[0] == "compiled_publication_copied"
            ]
            self.assertEqual(copied[0]["copied_records"], 0)
            self.assertNotEqual(original, new)
            with self.store.connection() as db:
                counts = db.execute(
                    "SELECT (SELECT count(*) FROM native_compiled_collection_contents) AS contents,"
                    "(SELECT count(*) FROM native_compiled_content_records) AS physical,"
                    "(SELECT count(*) FROM native_compiled_catalog_records) AS logical"
                ).fetchone()
                self.assertEqual(counts, dict(contents=1, physical=1, logical=2))

            changed_raw = json.dumps(
                dict(
                    map_id=7,
                    schema="native-Sf-Vz-columns-v1",
                    columns=[[2, 3, [[0, 3, False]]]],
                )
            ).encode()
            changed_map = dict(
                identity,
                source_documents={
                    "native-los-topology/7.json": hashlib.sha256(
                        changed_raw
                    ).hexdigest()
                },
            )
            third = publisher.PublicationSpool(str(Path(temporary) / "third.sqlite"))
            self.addCleanup(third.db.close)
            with patch.object(
                native_catalog, "read_published_bytes", return_value=changed_raw
            ) as reads:
                changed_entry, reused = prepared.publish_map_collection(
                    third, changed_map
                )
            self.assertFalse(reused)
            reads.assert_called_once_with("native-los-topology/7.json")
            self.assertNotEqual(
                changed_entry["inputs_sha256"], prepared_entry["inputs_sha256"]
            )
