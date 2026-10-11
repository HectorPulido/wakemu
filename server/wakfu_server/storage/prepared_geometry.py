"""Checksummed, revision-scoped derivatives of authoritative native catalogs.

Artifacts are trusted local build outputs, never client input. Marshal avoids
executable pickle reducers; source validation belongs to the offline builder.
Runtime still hydrates Python containers but skips JSON parsing and graph rebuilds.
"""
import hashlib
import json
import marshal
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import MappingProxyType

FORMAT_VERSION = 1


class ArtifactUnavailable(ValueError):
    """Missing, stale or damaged derived data; use authoritative catalogs."""


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    geometry: object
    forced_index: object
    scope: tuple


def _scope(map_id, revision, geometry_sha256, forced_sha256):
    if type(map_id) is not int or map_id <= 0 or not isinstance(revision, str):
        raise ValueError("Invalid prepared geometry identity")
    if geometry_sha256 is None:
        raise ValueError("Geometry source hash is required")
    for digest in (geometry_sha256, forced_sha256):
        if digest is not None and (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Invalid source hash")
    return FORMAT_VERSION, revision, map_id, geometry_sha256, forced_sha256


def _paths(directory, scope):
    key = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
    revision_key = hashlib.sha256(scope[1].encode()).hexdigest()
    base = Path(directory) / revision_key / f"{scope[2]}-{key}"
    return base.with_suffix(".marshal"), base.with_suffix(".json")


def _atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def build_artifact(directory, *, map_id, revision, geometry_raw, forced_raw=None):
    from wakfu_server.combat_geometry import prepare_geometry

    geometry_hash = hashlib.sha256(geometry_raw).hexdigest()
    forced_hash = None if forced_raw is None else hashlib.sha256(forced_raw).hexdigest()
    scope = _scope(map_id, revision, geometry_hash, forced_hash)
    geometry = prepare_geometry(json.loads(geometry_raw))
    if geometry.map_id != map_id:
        raise ValueError("Geometry source identity mismatch")
    forced = None
    if forced_raw is not None:
        from wakfu_server.combat_forced_terrain import prepare_compact_index

        forced = dict(prepare_compact_index(json.loads(forced_raw), map_id, 0, 4))
    payload = (
        scope,
        geometry.cells,
        geometry.edges,
        dict(geometry.outgoing),
        dict(geometry.incoming),
        forced,
    )
    raw = marshal.dumps(payload, 4)
    binary, manifest = _paths(directory, scope)
    _atomic_write(binary, raw)
    _atomic_write(
        manifest,
        json.dumps(
            {
                "scope": scope,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "cells": len(geometry.cells),
                "edges": len(geometry.edges),
                "forced_rows": 0 if forced is None else len(forced),
            },
            sort_keys=True,
        ).encode(),
    )
    return load_artifact(
        directory,
        map_id=map_id,
        revision=revision,
        geometry_sha256=geometry_hash,
        forced_sha256=forced_hash,
    )


def load_artifact(directory, *, map_id, revision, geometry_sha256, forced_sha256=None):
    from wakfu_server.combat_geometry import PreparedGeometry

    scope = _scope(map_id, revision, geometry_sha256, forced_sha256)
    binary, manifest = _paths(directory, scope)
    try:
        metadata = json.loads(manifest.read_bytes())
        raw = binary.read_bytes()
        if (
            metadata["scope"] != list(scope)
            or metadata["bytes"] != len(raw)
            or metadata["sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise ValueError("Prepared artifact checksum or scope mismatch")
        payload = marshal.loads(raw)
        if not isinstance(payload, tuple) or len(payload) != 6 or payload[0] != scope:
            raise ValueError("Prepared artifact schema mismatch")
        _, cells, edges, outgoing, incoming, forced = payload
        if (
            type(cells) is not frozenset
            or type(edges) is not frozenset
            or type(outgoing) is not dict
            or type(incoming) is not dict
            or (forced is not None and type(forced) is not dict)
            or (forced_sha256 is None) != (forced is None)
            or metadata["cells"] != len(cells)
            or metadata["edges"] != len(edges)
            or metadata["forced_rows"] != (0 if forced is None else len(forced))
        ):
            raise ValueError("Prepared artifact container mismatch")
        geometry = PreparedGeometry(
            map_id, cells, edges, MappingProxyType(outgoing), MappingProxyType(incoming)
        )
        return PreparedArtifact(
            geometry, None if forced is None else MappingProxyType(forced), scope
        )
    except (OSError, ValueError, TypeError, KeyError, EOFError) as exc:
        raise ArtifactUnavailable(str(exc)) from exc


@lru_cache(maxsize=1)
def _inventory(revision):
    from wakfu_server import native_catalog

    return native_catalog.document_hashes()


@lru_cache(maxsize=4)
def _published(directory, revision, map_id, geometry_hash, forced_hash):
    try:
        return load_artifact(
            directory,
            map_id=map_id,
            revision=revision,
            geometry_sha256=geometry_hash,
            forced_sha256=forced_hash,
        )
    except ArtifactUnavailable:
        return None


def published_artifact(map_id):
    from wakfu_server import native_catalog

    directory = Path(
        os.environ.get(
            "WAKFU_PREPARED_GEOMETRY_DIR",
            str(Path(os.environ.get("WAKFU_RUNTIME", "/data")) / "prepared-geometry"),
        )
    )
    if not directory.is_dir():
        return None
    revision = native_catalog.release()
    inventory = _inventory(revision)
    geometry_hash = inventory.get(f"combat-maps/{map_id}.json")
    if geometry_hash is None:
        return None
    forced_hash = inventory.get(f"forced-transitions/{map_id}.json")
    return _published(str(directory), revision, map_id, geometry_hash, forced_hash)
