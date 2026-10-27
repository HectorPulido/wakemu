"""Read bounded original metadata from the versioned catalog publication.

Qualification tools may use this byte backend instead of reconstructing an
import dependency list. Large documents still require explicit projections.
This module never loads game catalogs, opens a database or starts a runtime.
"""

import gzip
import hashlib
import io
import json
from pathlib import Path

from tools.import_native_catalogs import validate_release_inventory
from tools.unpack_native_catalog_pack import FORMAT, digest, safe_path


MAX_METADATA_BYTES = 2 * 1024 * 1024


class PublishedMetadataPack:
    def __init__(self, manifest_path, *, revision, manifest_sha256):
        self.path = Path(manifest_path).resolve()
        raw = self.path.read_bytes()
        self.manifest_sha256 = digest(manifest_sha256)
        if hashlib.sha256(raw).hexdigest() != self.manifest_sha256:
            raise ValueError("Published metadata manifest checksum mismatch")
        pack = json.loads(raw)
        self.revision = digest(revision)
        if pack.get("format") != FORMAT:
            raise ValueError("Unknown published metadata pack format")
        releases = [row for row in pack["releases"] if row["revision"] == self.revision]
        if len(releases) != 1 or releases[0].get("complete") is not True:
            raise ValueError("Missing complete published metadata release")
        release = releases[0]
        validate_release_inventory(
            [
                (row["path"], row["sha256"], row["source_bytes"])
                for row in release["documents"]
            ],
            release,
        )
        self.documents = {row["path"]: row for row in release["documents"]}
        self.blobs = pack["blobs"]
        self.read_documents = {}

    def read(self, name):
        """Return original bytes, or reject before reading an oversized blob."""
        safe_path(name)
        document = self.documents.get(name)
        if document is None:
            raise ValueError("Unpublished metadata document: " + name)
        size = document["source_bytes"]
        if type(size) is not int or not 0 <= size <= MAX_METADATA_BYTES:
            raise ValueError(
                "Metadata requires an explicit bounded projection: " + name
            )
        checksum = digest(document["sha256"])
        blob = self.blobs[checksum]
        parts = blob["parts"]
        if blob["source_bytes"] != size or not parts:
            raise ValueError("Invalid published metadata blob")
        result = bytearray()
        for part in parts:
            count = part["source_bytes"]
            compressed_count = part["compressed_bytes"]
            if (
                type(count) is not int
                or not 0 <= count <= size - len(result)
                or type(compressed_count) is not int
                or not 0 < compressed_count <= MAX_METADATA_BYTES + 65536
            ):
                raise ValueError("Invalid bounded metadata part size")
            relative = safe_path(part["path"])
            path = self.path.parent.joinpath(*relative.parts)
            if path.is_symlink() or not path.resolve().is_relative_to(self.path.parent):
                raise ValueError("Published metadata part escapes its pack")
            if path.stat().st_size != compressed_count:
                raise ValueError("Published metadata compressed size mismatch")
            compressed = path.read_bytes()
            if hashlib.sha256(compressed).hexdigest() != digest(
                part["compressed_sha256"]
            ):
                raise ValueError("Published metadata compressed checksum mismatch")
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
                decoded = source.read(count + 1)
            if len(decoded) != count or hashlib.sha256(decoded).hexdigest() != digest(
                part["sha256"]
            ):
                raise ValueError("Published metadata part checksum or size mismatch")
            result.extend(decoded)
        if len(result) != size or hashlib.sha256(result).hexdigest() != checksum:
            raise ValueError("Published metadata document checksum or size mismatch")
        self.read_documents[name] = dict(
            revision=self.revision,
            sha256=checksum,
            source_bytes=size,
            pack_manifest_sha256=self.manifest_sha256,
        )
        return bytes(result)
