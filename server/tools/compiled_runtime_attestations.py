"""Generation-bound proofs for reviewed mixed runtime/compiler modules.

An attestation is recorded only while the exact source bytes and a complete,
immutable publication's manifest match. Missing or stale proofs never grant
reuse; the caller must fall back to normal compilation.
"""
import hashlib
from pathlib import Path
import sys

from tools import compiled_runtime_projection as projection


def policy_digest():
    """Invalidate proofs whenever projection code or its reviewed list changes."""
    raw = Path(projection.__file__).read_bytes()
    # AST shape and semantics can change between interpreter versions even
    # when the projection source is identical.
    version = f"python={sys.implementation.name}:{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n".encode()
    return hashlib.sha256(version + raw).hexdigest()


def _source(path, expected_sha256, source_root):
    if path not in projection.RUNTIME_FUNCTIONS or not isinstance(expected_sha256, str):
        return None
    try:
        raw = (Path(source_root) / path).read_bytes()
    except (FileNotFoundError, OSError):
        return None
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        return None
    return projection.masked_fingerprint(path, raw)


def record_exact_publication(db, generation, identity, source_root, canonical_bytes):
    """Record reviewed projections after an exact, sealed publication exists."""
    row = db.execute(
        "SELECT generation,manifest_raw,manifest,complete FROM native_compiled_catalog_releases WHERE generation=%s",
        (generation,),
    ).fetchone()
    if not row or not row["complete"]:
        return 0
    raw = bytes(row["manifest_raw"])
    manifest = row["manifest"]
    if (
        hashlib.sha256(raw).hexdigest() != generation
        or canonical_bytes(manifest) != raw
        or any(
            manifest.get(k) != identity.get(k)
            for k in (
                "policy",
                "source_revision",
                "source_inventory_sha256",
                "compiler_contract_sha256",
                "config_sha256",
                "compiler_sources",
            )
        )
    ):
        return 0
    sources = manifest.get("compiler_sources")
    if not isinstance(sources, dict):
        return 0
    policy = policy_digest()
    count = 0
    for path in sorted(projection.RUNTIME_FUNCTIONS):
        expected = sources.get(path)
        fingerprint = _source(path, expected, source_root)
        if fingerprint is None:
            continue
        db.execute(
            "INSERT INTO native_compiled_runtime_projections "
            "(generation,source_path,source_sha256,policy_sha256,projection_sha256) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (generation, path, expected, policy, fingerprint),
        )
        count += 1
    return count


def verified_unchanged_paths(db, generation, previous, current, source_root):
    """Prove a subset of changed paths equivalent, or return no proof for them."""
    old, new = previous.get("compiler_sources"), current.get("compiler_sources")
    if not isinstance(old, dict) or not isinstance(new, dict):
        return set()
    paths = [
        p
        for p in projection.RUNTIME_FUNCTIONS
        if p in old and p in new and old[p] != new[p]
    ]
    if not paths:
        return set()
    policy = policy_digest()
    rows = db.execute(
        "SELECT source_path,source_sha256,projection_sha256 FROM native_compiled_runtime_projections "
        "WHERE generation=%s AND policy_sha256=%s AND source_path=ANY(%s)",
        (generation, policy, paths),
    ).fetchall()
    proved = set()
    for row in rows:
        path = row["source_path"]
        if path not in paths or row["source_sha256"] != old[path]:
            continue
        current_projection = _source(path, new[path], source_root)
        if (
            current_projection is not None
            and current_projection == row["projection_sha256"]
        ):
            proved.add(path)
    return proved
