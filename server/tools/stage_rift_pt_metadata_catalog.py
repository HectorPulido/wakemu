"""Publish original PT collision getters additively; never stage or activate DB data."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from tools.import_native_catalogs import release_identity
from tools.stage_rift_complete_metadata_catalog import (
    encode,
    read_document,
    sha,
    store_document,
)

CASTING = "native-class-casting-roots.json"


def build(pack_root, proof_path):
    root = Path(pack_root)
    catalogs = root / "catalogs"
    parent_path = catalogs / "manifest-rift-complete-metadata-v1.json"
    parent_raw = parent_path.read_bytes()
    pack = json.loads(parent_raw)
    parent_revision = pack["active_revision"]
    parent = next(row for row in pack["releases"] if row["revision"] == parent_revision)
    proof_raw = Path(proof_path).read_bytes()
    proof = json.loads(proof_raw)
    if (
        proof.get("schema") != "wakemu-original-rift-pt-casting-additions-v1"
        or proof.get("original_inputs_stable") is not True
        or proof.get("parent_revision") != parent_revision
    ):
        raise ValueError("Invalid original PT source authority")
    old = next(row for row in parent["documents"] if row["path"] == CASTING)
    document = read_document(catalogs, pack, old)
    exported = proof["original_export"]
    for field in ("schema", "fight_properties", "normal_casting_overrides"):
        if document[field] != exported[field]:
            raise ValueError("Original casting globals differ: " + field)
    for key in set(exported["roots"]) & set(document["roots"]):
        if exported["roots"][key] != document["roots"][key]:
            raise ValueError("Original overlapping PT metadata differs: " + key)
    additions = {
        key: row
        for key, row in exported["roots"].items()
        if key not in document["roots"]
    }
    if not additions:
        raise ValueError("No new original PT descriptors")
    candidate = deepcopy(document)
    candidate["roots"].update(additions)
    candidate.setdefault("native_dependency_exports", []).append(
        dict(
            original_inputs_stable=True,
            original_input_hashes=proof["input_hashes"],
            original_export_sha256=proof["export_sha256"],
            source_proof_sha256=sha(proof_raw),
            root_ids=sorted(map(int, additions)),
            scope=proof["scope"],
            source="Original eVn.fKX/aZF for non-null PT collision descriptors",
        )
    )
    updated = deepcopy(pack)
    changed = store_document(catalogs, updated, CASTING, candidate)
    active = next(
        row for row in updated["releases"] if row["revision"] == parent_revision
    )
    active["documents"] = [
        changed if row["path"] == CASTING else row for row in active["documents"]
    ]
    inventory = [
        (row["path"], row["sha256"], row["source_bytes"]) for row in active["documents"]
    ]
    active.update(release_identity(inventory))
    active.update(
        document_count=len(inventory), source_bytes=sum(row[2] for row in inventory)
    )
    revision = active["revision"]
    updated["active_revision"] = revision
    referenced = {
        row["sha256"] for release in updated["releases"] for row in release["documents"]
    }
    updated["blobs"] = {
        key: value for key, value in updated["blobs"].items() if key in referenced
    }
    name = "manifest-rift-pt-metadata-v1.json"
    raw = encode(updated)
    target = catalogs / name
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Immutable PT catalog already owns other content")
    target.write_bytes(raw)
    receipt = dict(
        schema="wakemu-rift-pt-metadata-release-v1",
        parent_revision=parent_revision,
        candidate_revision=revision,
        parent_manifest_sha256=sha(parent_raw),
        candidate_manifest="catalogs/" + name,
        candidate_manifest_sha256=sha(raw),
        old_casting_roots=len(document["roots"]),
        added_casting_roots=len(additions),
        old_rows_preserved=True,
        changed_documents=[changed],
        source_proof_sha256=sha(proof_raw),
        database_staged=False,
        activated=False,
        public_selector_changed=False,
        actual_new_chunk_bytes=updated["blobs"][changed["sha256"]]["parts"][0][
            "compressed_bytes"
        ],
    )
    (catalogs / "rift-pt-metadata-v1-receipt.json").write_bytes(encode(receipt))
    return receipt


def select_public(pack_root, receipt):
    """Select the qualified immutable package for future fresh installations only."""
    root = Path(pack_root)
    path = root / "manifest.json"
    top = json.loads(path.read_bytes())
    parent = receipt["parent_revision"]
    revision = receipt["candidate_revision"]
    if top["catalogs"]["active_revision"] not in (parent, revision):
        raise ValueError("Public catalog selector left the qualified lineage")
    raw = (root / receipt["candidate_manifest"]).read_bytes()
    if sha(raw) != receipt["candidate_manifest_sha256"]:
        raise ValueError("Candidate public catalog checksum differs")
    pack = json.loads(raw)
    release = next(row for row in pack["releases"] if row["revision"] == revision)
    top["artifacts"]["native-catalogs"].update(
        path=receipt["candidate_manifest"], sha256=sha(raw), size=len(raw)
    )
    top["catalogs"]["active_revision"] = revision
    for row in top["catalogs"]["releases"]:
        if row["revision"] in (parent, revision):
            row.update(
                revision=revision,
                document_count=release["document_count"],
                source_bytes=release["source_bytes"],
            )
    output = encode(top)
    path.write_bytes(output)
    (root / "manifest.sha256").write_text(sha(output) + "  manifest.json\n")
    return dict(
        installation_manifest_sha256=sha(output),
        candidate_revision=revision,
        public_selector_changed=True,
        database_staged=False,
        activated=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path("server/data/installation"))
    parser.add_argument(
        "--proof",
        type=Path,
        default=Path("server/data/native-rift-pt-casting-additions-v1.json"),
    )
    parser.add_argument(
        "--select-public",
        action="store_true",
        help="Select for future fresh installation; never changes the active database",
    )
    args = parser.parse_args()
    receipt = build(args.pack, args.proof)
    if args.select_public:
        receipt = {**receipt, **select_public(args.pack, receipt)}
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
