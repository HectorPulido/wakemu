"""Source-bound local derivatives of ordered native static LOS columns.

Only trusted offline build outputs are accepted. Live actor blockers and the
native raster program remain authoritative at their existing call sites.
"""
import hashlib
import json
import marshal
import os
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from wakfu_server.prepared_geometry import (
    ArtifactUnavailable,
    _atomic_write,
    _inventory,
    _paths,
    _scope,
)


def build_artifact(directory, *, map_id, revision, source_raw):
    from wakfu_server.combat_native_los_ray import prepare_columns

    digest = hashlib.sha256(source_raw).hexdigest()
    scope = _scope(map_id, revision, digest, None)
    columns = prepare_columns(json.loads(source_raw), map_id)
    raw = marshal.dumps(("native-Sf-Vz-columns-v1", scope, columns), 4)
    binary, manifest = _paths(directory, scope)
    _atomic_write(binary, raw)
    _atomic_write(
        manifest,
        json.dumps(
            {
                "schema": "native-Sf-Vz-columns-v1",
                "scope": scope,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "columns": len(columns),
            },
            sort_keys=True,
        ).encode(),
    )
    del columns, raw
    return load_artifact(
        directory,
        map_id=map_id,
        revision=revision,
        source_sha256=digest,
    )


def load_artifact(directory, *, map_id, revision, source_sha256):
    scope = _scope(map_id, revision, source_sha256, None)
    binary, manifest = _paths(directory, scope)
    try:
        metadata = json.loads(manifest.read_bytes())
        raw = binary.read_bytes()
        if (
            metadata["schema"] != "native-Sf-Vz-columns-v1"
            or metadata["scope"] != list(scope)
            or metadata["bytes"] != len(raw)
            or metadata["sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise ValueError("Prepared LOS checksum or scope mismatch")
        payload = marshal.loads(raw)
        if (
            type(payload) is not tuple
            or len(payload) != 3
            or payload[:2] != ("native-Sf-Vz-columns-v1", scope)
            or type(payload[2]) is not dict
            or metadata["columns"] != len(payload[2])
        ):
            raise ValueError("Prepared LOS schema mismatch")
        return MappingProxyType(payload[2])
    except (OSError, ValueError, TypeError, KeyError, EOFError) as error:
        raise ArtifactUnavailable(str(error)) from error


@lru_cache(maxsize=4)
def _published(directory, revision, map_id, digest):
    try:
        return load_artifact(
            directory,
            map_id=map_id,
            revision=revision,
            source_sha256=digest,
        )
    except ArtifactUnavailable:
        return None


def published_columns(map_id):
    from wakfu_server import native_catalog

    directory = Path(
        os.environ.get(
            "WAKFU_PREPARED_LOS_DIR",
            str(Path(os.environ.get("WAKFU_RUNTIME", "/data")) / "prepared-los"),
        )
    )
    if not directory.is_dir():
        return None
    revision = native_catalog.release()
    digest = _inventory(revision).get(f"native-los-topology/{map_id}.json")
    if digest is None:
        return None
    return _published(str(directory), revision, map_id, digest)
