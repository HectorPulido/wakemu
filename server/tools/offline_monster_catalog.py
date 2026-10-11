"""Explicit offline candidate-base snapshot; never a published DB release.

Only bytes matching the declared pinned manifest can satisfy catalog reads.
The receipt separates declared seals from raw documents actually verified.
"""
from contextlib import contextmanager, ExitStack
import gzip
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch


class OfflineMonsterCatalog:
    def __init__(self, candidate, roots=()):
        self.candidate = Path(candidate).resolve()
        self.manifest = json.loads((self.candidate / "manifest.json").read_text())
        if self.manifest.get("schema") != "native-npc-activation-candidate-v1":
            raise ValueError("Missing native offline candidate manifest")
        self.revision = self.manifest["base_revision"]
        self.hashes = dict(self.manifest["unchanged_documents"])
        for key, value in self.manifest["base_document_hashes"].items():
            if key in self.hashes and self.hashes[key] != value:
                raise ValueError("Conflicting offline base seal: " + key)
            self.hashes[key] = value
        for key, digest in self.hashes.items():
            if (
                Path(key).is_absolute()
                or ".." in Path(key).parts
                or not isinstance(digest, str)
                or len(digest) != 64
            ):
                raise ValueError("Invalid offline base manifest seal")
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.verified = {}
        self.failures = []

    def read_bytes(self, path):
        from wakfu_server import native_catalog

        try:
            key = (
                Path(path)
                .resolve()
                .relative_to(native_catalog.DATA_ROOT.resolve())
                .as_posix()
            )
        except ValueError:
            # Noncatalog files remain actual local input, outside this receipt.
            return Path(path).read_bytes()
        expected = self.hashes.get(key)
        if expected is None:
            raise FileNotFoundError("Undeclared offline catalog document: " + key)
        paths = [self.candidate / ("base-" + key)]
        paths += [root / key for root in self.roots]
        rejected = []
        for source in paths:
            for actual, compressed in (
                (source, False),
                (Path(str(source) + ".gz"), True),
            ):
                if not actual.is_file():
                    continue
                raw = (
                    gzip.decompress(actual.read_bytes())
                    if compressed
                    else actual.read_bytes()
                )
                actual_hash = hashlib.sha256(raw).hexdigest()
                if actual_hash != expected:
                    rejected.append(dict(path=str(actual), sha256=actual_hash))
                    continue
                self.verified[key] = dict(
                    sha256=actual_hash, source=str(actual), gzip=compressed
                )
                return raw
        self.failures.append(
            dict(document=key, expected_sha256=expected, rejected=rejected)
        )
        raise FileNotFoundError(
            "Missing SHA-qualified offline catalog document: " + key
        )

    def read_text(self, path, encoding="utf8"):
        return self.read_bytes(path).decode(encoding)

    def load(self, path):
        return json.loads(self.read_bytes(path))

    def exists(self, path):
        from wakfu_server import native_catalog

        try:
            key = (
                Path(path)
                .resolve()
                .relative_to(native_catalog.DATA_ROOT.resolve())
                .as_posix()
            )
        except ValueError:
            return Path(path).is_file()
        if key not in self.hashes:
            return False
        self.read_bytes(path)  # A declared seal is not actual raw availability.
        return True

    def open(self, path, mode="rt", encoding=None):
        if mode not in ("r", "rt", "rb"):
            raise ValueError("Offline native catalogs are read-only")
        raw = self.read_bytes(path)
        return (
            io.BytesIO(raw)
            if mode == "rb"
            else io.StringIO(raw.decode(encoding or "utf8"))
        )

    def receipt(self):
        return dict(
            schema="offline-monster-catalog-consumption-v1",
            authority="declared_offline_candidate_base_not_active_database",
            base_revision=self.revision,
            candidate=str(self.candidate),
            manifest_sha256=hashlib.sha256(
                (self.candidate / "manifest.json").read_bytes()
            ).hexdigest(),
            declared_document_count=len(self.hashes),
            verified_documents=dict(self.verified),
            failed_reads=list(self.failures),
            qualification="only_accessed_hash_verified_documents; deployment_requires_live_rebase",
        )

    @contextmanager
    def install(self):
        from wakfu_server import native_catalog
        from wakfu_server.storage import native_catalog as storage_catalog

        def record(path, collection, record_key):
            # Resolve through the current loader so a validated candidate overlay
            # can replace a document after install_overlay audits its base.
            rows = native_catalog.load(path)[collection]
            if not isinstance(rows, dict):
                raise ValueError("Offline indexed record collection must be a mapping")
            return rows.get(str(record_key))

        with ExitStack() as stack:
            for module in dict.fromkeys((native_catalog, storage_catalog)):
                for name, callback in (
                    ("release", lambda: self.revision),
                    ("document_hashes", lambda: dict(self.hashes)),
                    ("read_bytes", self.read_bytes),
                    ("read_text", self.read_text),
                    ("load", self.load),
                    ("record", record),
                    ("exists", self.exists),
                    ("open", self.open),
                ):
                    stack.enter_context(patch.object(module, name, callback))
            yield self
