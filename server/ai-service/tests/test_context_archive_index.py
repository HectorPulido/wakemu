"""Warm catalogue verification visits every archive without rescanning blobs."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from wakfu_ai.context.context_store import ContextStore


class ArchiveIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ContextStore(self.tmp.name)
        self.addCleanup(self.store.close)

    def put(self, body):
        digest = hashlib.sha256(body).hexdigest()
        self.store.put(digest, len(body), 0, body)
        return digest

    def seal(self, bodies):
        entries = []
        for index, body in enumerate(bodies):
            digest = self.put(body)
            entries.append(dict(path=str(index), sha256=digest, size=len(body)))
        manifest = self.put(
            json.dumps(
                dict(format="wakfu-complete-context-1", entries=entries)
            ).encode()
        )
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])
        return manifest

    def test_11000_blob_refs_are_indexed_once_and_warm_check_visits_three_archives(
        self,
    ):
        refs = {
            str(index): dict(
                path="archive-%s" % (index % 3), identity=(1, index % 3, 5, 6, 7)
            )
            for index in range(11000)
        }
        archives = self.store._snapshot_archive_index(refs)
        self.assertEqual(len(archives), 3)

        class NoWarmTraversal(dict):
            def values(self):
                raise AssertionError("Warm archive checks must not traverse blobs")

        snapshot = dict(blobs=NoWarmTraversal(refs), archives=archives)
        with patch.object(self.store, "_check_frozen_ref") as verify:
            self.store._check_snapshot_archives(snapshot)
        self.assertEqual(verify.call_count, 3)
        self.assertEqual(
            {
                (call.args[0]["path"], call.args[0]["identity"])
                for call in verify.call_args_list
            },
            set(archives),
        )

    def test_reused_and_new_archives_both_reject_tampering_on_warm_seal(self):
        for archive_index in (0, 1):
            with self.subTest(archive=archive_index):
                with tempfile.TemporaryDirectory() as folder:
                    store = ContextStore(folder)
                    try:
                        original = self.store
                        self.store = store
                        self.seal([b"shared"])
                        manifest = self.seal([b"shared", b"new"])
                        snapshot = store._sealed[manifest]["snapshot"]
                        self.assertEqual(len(snapshot["archives"]), 2)
                        path = Path(snapshot["archives"][archive_index][0])
                        os.chmod(path, 0o600)
                        with path.open("ab") as stream:
                            stream.write(b"tampered")
                        with self.assertRaisesRegex(ValueError, "snapshot changed"):
                            store.seal_manifest(manifest)
                    finally:
                        self.store = original
                        store.close()
