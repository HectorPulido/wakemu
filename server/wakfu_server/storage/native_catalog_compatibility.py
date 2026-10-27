"""Validate frozen source revisions by the documents a consumer actually uses.

A metadata-only publication must not relabel sealed gameplay source records.
Historical inventories are either complete PostgreSQL releases or original
inventories carried by a current immutable published document. Neither path
accepts a revision alias, an incomplete inventory, or a changed dependency.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import PurePosixPath
import re

from wakfu_server import native_catalog

MANIFEST_DOCUMENT = "native-source-revision-manifests.json"
MANIFEST_POLICY = "wakemu.native-catalog-source-manifests.v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _digest(value):
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError("Invalid native source revision/checksum")
    return value


def _path(value):
    if (
        type(value) is not str
        or not value.endswith(".json")
        or "\\" in value
        or "\0" in value
        or PurePosixPath(value).is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("Invalid native source dependency path")
    return value


def _inventory(release, revision):
    """Prove the complete original inventory using its published algorithm."""
    if (
        type(release) is not dict
        or release.get("revision") != revision
        or release.get("complete") is not True
    ):
        raise ValueError("Missing complete original native source release")
    documents = release.get("documents")
    if type(documents) is not list or not documents:
        raise ValueError("Missing original native source inventory")
    rows, seen = [], set()
    for row in documents:
        if type(row) is not dict:
            raise ValueError("Invalid original native source document")
        path, checksum, size = (
            _path(row.get("path")),
            _digest(row.get("sha256")),
            row.get("source_bytes"),
        )
        if path in seen or type(size) is not int or not 0 <= size < 2**63:
            raise ValueError("Invalid/duplicate original native source document")
        seen.add(path)
        rows.append((path, checksum, size))
    if (
        type(release.get("document_count")) is not int
        or release["document_count"] != len(rows)
        or type(release.get("source_bytes")) is not int
        or release["source_bytes"] != sum(row[2] for row in rows)
    ):
        raise ValueError("Original native source inventory/header mismatch")
    rows.sort()

    def lines(ordered):
        return hashlib.sha256(
            b"".join(
                path.encode("utf8") + b"\0" + checksum.encode("ascii") + b"\n"
                for path, checksum, _ in ordered
            )
        ).hexdigest()

    canonical = lines(rows)
    identities = {
        "posix-path-sha256-v1": canonical,
        "legacy-path-sha256-v1": lines(
            sorted(rows, key=lambda row: PurePosixPath(row[0]).parts)
        ),
    }
    if all(row[0].startswith("fishing-navigation/") for row in rows):
        identities["fishing-json-manifest-v1"] = hashlib.sha256(
            json.dumps(rows, separators=(",", ":")).encode()
        ).hexdigest()
    scheme = release.get("identity_scheme")
    if scheme is None:
        valid = revision in identities.values()
    else:
        valid = identities.get(scheme) == revision
    if not valid or release.get("manifest_sha256", canonical) != canonical:
        raise ValueError("Original native source revision does not match its inventory")
    return tuple((path, checksum) for path, checksum, _ in rows)


@lru_cache(maxsize=32)
def _historical_documents(revision, current):
    # Query only headers/hashes, never decode the multi-gigabyte native catalog.
    with native_catalog._database().connection() as db:
        row = db.execute(
            "SELECT revision,document_count,source_bytes,complete FROM native_catalog_releases "
            "WHERE revision=%s",
            (revision,),
        ).fetchone()
        if row is not None:
            documents = db.execute(
                "SELECT path,sha256,source_bytes FROM native_catalog_documents "
                'WHERE revision=%s ORDER BY path COLLATE "C"',
                (revision,),
            ).fetchall()
            return _inventory(
                dict(row, documents=[dict(document) for document in documents]),
                revision,
            )
    # Fresh installations may carry only the newest release. Its authoritative
    # published metadata includes the unchanged original public inventories.
    document = json.loads(native_catalog.read_published_bytes(MANIFEST_DOCUMENT))
    if (
        type(document) is not dict
        or document.get("policy") != MANIFEST_POLICY
        or type(document.get("releases")) is not list
    ):
        raise ValueError("Invalid published original native source inventories")
    releases = document["releases"]
    if any(type(row) is not dict for row in releases):
        raise ValueError("Invalid original native source release")
    identities = [row.get("revision") for row in releases]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate original native source releases")
    selected = [row for row in releases if row.get("revision") == revision]
    if len(selected) != 1 or native_catalog.release() != current:
        raise ValueError("Original native source revision is unavailable")
    return _inventory(selected[0], revision)


@lru_cache(maxsize=4)
def _current_documents(revision):
    rows = native_catalog.document_hashes()
    if native_catalog.release() != revision:
        raise ValueError("Native catalog publication changed during source validation")
    return tuple((_path(path), _digest(checksum)) for path, checksum in rows.items())


def require_source_revision(pinned, required_paths):
    """Require unchanged original SHA256 for every real consumer dependency.

    Exact current revisions retain the prior fast path. A different revision is
    compatible only after its complete original identity is verified; absent,
    changed, or malformed source documents fail closed. Callers retain their
    original frozen revision and all record-level provenance checks.
    """
    _digest(pinned)
    if (
        not isinstance(required_paths, (tuple, list, set, frozenset))
        or not required_paths
    ):
        raise ValueError("Explicit nonempty native source dependencies required")
    required = tuple(_path(path) for path in required_paths)
    if len(set(required)) != len(required):
        raise ValueError("Duplicate native source dependency")
    current = _digest(native_catalog.release())
    if pinned == current:
        return
    original = dict(_historical_documents(pinned, current))
    published = dict(_current_documents(current))
    for path in required:
        if (
            path not in original
            or path not in published
            or original[path] != published[path]
        ):
            raise ValueError("Frozen native source dependency changed: " + path)
