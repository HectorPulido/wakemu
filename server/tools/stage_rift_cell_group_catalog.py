"""Build an additive immutable Rift eYk catalog and public installation selector.

Only one small original document is decoded. Existing compressed catalog chunks
are referenced in place; neither a client nor a database is needed to rebuild.
This command never activates a database catalog or changes a running service.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path

from tools.export_monster_cell_groups import assert_preserved
from tools.import_native_catalogs import catalog_records, release_identity

DOCUMENT = "native-class-cell-group-metadata.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def build(pack_root, proof_path):
    root, proof_path = Path(pack_root), Path(proof_path)
    top_path = root / "manifest.json"
    top = json.loads(top_path.read_bytes())
    baseline_path = root / top["artifacts"]["native-catalogs"]["path"]
    baseline_raw = baseline_path.read_bytes()
    if sha(baseline_raw) != top["artifacts"]["native-catalogs"]["sha256"]:
        raise ValueError("Public catalog manifest checksum mismatch")
    pack = json.loads(baseline_raw)
    proof_raw = proof_path.read_bytes()
    proof = json.loads(proof_raw)
    proof_sha = sha(proof_raw)
    base_revision = pack["active_revision"]
    active = next(row for row in pack["releases"] if row["revision"] == base_revision)
    document = next(row for row in active["documents"] if row["path"] == DOCUMENT)
    if proof.get("original_inputs_stable") is not True:
        raise ValueError("Original native getter inputs were not stable")
    # An exact rerun does not rebase or duplicate the additive release.
    if document["sha256"] != proof["source_document_sha256"]:
        receipt = root / "catalogs" / "rift-cell-groups-v1-receipt.json"
        if receipt.exists():
            prior = json.loads(receipt.read_bytes())
            if (
                prior["proof_sha256"] == proof_sha
                and prior["candidate_revision"] == base_revision
            ):
                return prior
        raise ValueError("Native eYk base document differs from reviewed source")
    if document["source_bytes"] > 2 * 1024 * 1024:
        raise ValueError("Native eYk source exceeds bounded metadata size")
    raw = bytearray()
    for part in pack["blobs"][document["sha256"]]["parts"]:
        source = baseline_path.parent / part["path"]
        compressed = source.read_bytes()
        if (
            len(compressed) != part["compressed_bytes"]
            or sha(compressed) != part["compressed_sha256"]
        ):
            raise ValueError("Original eYk compressed chunk differs")
        value = gzip.decompress(compressed)
        if len(value) != part["source_bytes"] or sha(value) != part["sha256"]:
            raise ValueError("Original eYk decoded chunk differs")
        raw.extend(value)
    if len(raw) != document["source_bytes"] or sha(raw) != document["sha256"]:
        raise ValueError("Original eYk document checksum mismatch")
    base = json.loads(raw)
    candidate = deepcopy(base)
    rows = proof["exported_rows"]
    if (
        set(rows) & set(base["effects"])
        or sorted(map(int, rows)) != proof["exported_references"]
    ):
        raise ValueError("Native getter addition overlaps or changes identity")
    candidate["effects"].update(rows)
    candidate.setdefault("npc_dependency_exports", []).append(
        dict(
            original_inputs_stable=True,
            original_input_hashes=proof["original_input_hashes"],
            original_export_sha256=proof["original_export_sha256"],
            effect_ids=proof["exported_references"],
            source_proof_sha256=proof_sha,
            native_getter=proof["getter"],
        )
    )
    assert_preserved(base, candidate)
    candidate_raw = encoded(candidate)
    checksum = sha(candidate_raw)
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
    ) as target:
        target.write(candidate_raw)
    compressed = buffer.getvalue()
    relative = "parts/" + checksum + ".json.gz"
    target = baseline_path.parent / relative
    if target.exists() and target.read_bytes() != compressed:
        raise ValueError("Content-addressed eYk chunk collision")
    target.write_bytes(compressed)
    replacement = dict(
        document,
        sha256=checksum,
        source_bytes=len(candidate_raw),
        record_count=sum(1 for _ in catalog_records(DOCUMENT, candidate)),
    )
    updated = deepcopy(pack)
    new_active = next(
        row for row in updated["releases"] if row["revision"] == base_revision
    )
    new_active["documents"] = [
        replacement if row["path"] == DOCUMENT else row
        for row in new_active["documents"]
    ]
    inventory = [
        (row["path"], row["sha256"], row["source_bytes"])
        for row in new_active["documents"]
    ]
    new_active.update(release_identity(inventory))
    revision = new_active["revision"]
    new_active["source_bytes"] = sum(row[2] for row in inventory)
    updated["active_revision"] = revision
    updated["blobs"][checksum] = dict(
        source_bytes=len(candidate_raw),
        parts=[
            dict(
                path=relative,
                sha256=checksum,
                source_bytes=len(candidate_raw),
                compressed_bytes=len(compressed),
                compressed_sha256=sha(compressed),
            )
        ],
    )
    referenced = {
        row["sha256"] for release in updated["releases"] for row in release["documents"]
    }
    updated["blobs"] = {
        key: value for key, value in updated["blobs"].items() if key in referenced
    }
    manifest_name = "manifest-rift-cell-groups-v1.json"
    manifest_raw = encoded(updated)
    new_path = baseline_path.parent / manifest_name
    if new_path.exists() and new_path.read_bytes() != manifest_raw:
        raise ValueError("Versioned eYk manifest already owns different content")
    new_path.write_bytes(manifest_raw)
    new_top = deepcopy(top)
    new_top["artifacts"]["native-catalogs"].update(
        path="catalogs/" + manifest_name,
        sha256=sha(manifest_raw),
        size=len(manifest_raw),
    )
    new_top["catalogs"]["active_revision"] = revision
    for row in new_top["catalogs"]["releases"]:
        if row["revision"] == base_revision:
            row.update(revision=revision, source_bytes=new_active["source_bytes"])
    # Fresh installs select the candidate; the old immutable manifest and all
    # old compressed bytes remain unchanged. Live environment is not touched.
    top_raw = encoded(new_top)
    top_path.write_bytes(top_raw)
    (root / "manifest.sha256").write_text(sha(top_raw) + "  manifest.json\n")
    receipt = dict(
        schema="wakemu-rift-cell-groups-release-v1",
        base_revision=base_revision,
        candidate_revision=revision,
        activated=False,
        source_document=DOCUMENT,
        original_document_sha256=document["sha256"],
        candidate_document_sha256=checksum,
        original_rows=len(base["effects"]),
        candidate_rows=len(candidate["effects"]),
        added_references=proof["exported_references"],
        proof_sha256=proof_sha,
        candidate_manifest="catalogs/" + manifest_name,
        candidate_manifest_sha256=sha(manifest_raw),
        installation_manifest_sha256=sha(top_raw),
        new_chunk_compressed_bytes=len(compressed),
        reused_content_addressed_chunks=True,
    )
    (root / "catalogs" / "rift-cell-groups-v1-receipt.json").write_bytes(
        encoded(receipt)
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path("server/data/installation"))
    parser.add_argument(
        "--proof",
        type=Path,
        default=Path("server/data/native-rift-cell-groups-v1.json"),
    )
    args = parser.parse_args()
    print(json.dumps(build(args.pack, args.proof), sort_keys=True))


if __name__ == "__main__":
    main()
