"""Build one immutable public Rift metadata release without staging or activation.

Reuses all unchanged content-addressed chunks. Adds original casting getters and
an original source-revision inventory to the already additive eYk candidate.
No client, database, private capture, player data or whole-catalog decode is used.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path

from tools.import_native_catalogs import catalog_records, release_identity

CASTING = "native-class-casting-roots.json"
SOURCE_MANIFESTS = "native-source-revision-manifests.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value, *, compact=False):
    options = dict(sort_keys=True, ensure_ascii=False)
    options.update(dict(separators=(",", ":")) if compact else dict(indent=2))
    return (json.dumps(value, **options) + "\n").encode()


def read_document(root, pack, row):
    if row["source_bytes"] > 2 * 1024 * 1024:
        raise ValueError("Metadata document exceeds the bounded source domain")
    output = bytearray()
    for part in pack["blobs"][row["sha256"]]["parts"]:
        compressed = (root / part["path"]).read_bytes()
        if (
            len(compressed) != part["compressed_bytes"]
            or sha(compressed) != part["compressed_sha256"]
        ):
            raise ValueError("Original metadata compressed checksum differs")
        raw = gzip.decompress(compressed)
        if len(raw) != part["source_bytes"] or sha(raw) != part["sha256"]:
            raise ValueError("Original metadata chunk checksum differs")
        output.extend(raw)
    if len(output) != row["source_bytes"] or sha(output) != row["sha256"]:
        raise ValueError("Original metadata document checksum differs")
    return json.loads(output)


def store_document(root, pack, name, value):
    raw = encode(value, compact=True)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Published metadata exceeds bounded reader size")
    checksum = sha(raw)
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
    ) as target:
        target.write(raw)
    compressed = buffer.getvalue()
    relative = "parts/" + checksum + ".json.gz"
    destination = root / relative
    if destination.exists() and destination.read_bytes() != compressed:
        raise ValueError("Content-addressed metadata collision")
    destination.write_bytes(compressed)
    pack["blobs"][checksum] = dict(
        source_bytes=len(raw),
        parts=[
            dict(
                path=relative,
                sha256=checksum,
                source_bytes=len(raw),
                compressed_bytes=len(compressed),
                compressed_sha256=sha(compressed),
            )
        ],
    )
    return dict(
        path=name,
        sha256=checksum,
        source_bytes=len(raw),
        record_count=sum(1 for _ in catalog_records(name, value)),
    )


def build(pack_root, casting_proof_path):
    root = Path(pack_root)
    catalogs = root / "catalogs"
    top_path = root / "manifest.json"
    top = json.loads(top_path.read_bytes())
    original_raw = (catalogs / "manifest.json").read_bytes()
    original = json.loads(original_raw)
    base_revision = original["active_revision"]
    old_release = next(
        row for row in original["releases"] if row["revision"] == base_revision
    )
    old_inventory = [
        (row["path"], row["sha256"], row["source_bytes"])
        for row in old_release["documents"]
    ]
    release_identity(
        old_inventory,
        expected_revision=base_revision,
        identity_scheme=old_release["identity_scheme"],
    )
    cell_receipt = json.loads(
        (catalogs / "rift-cell-groups-v1-receipt.json").read_bytes()
    )
    cell_raw = (root / cell_receipt["candidate_manifest"]).read_bytes()
    if sha(cell_raw) != cell_receipt["candidate_manifest_sha256"]:
        raise ValueError("Additive eYk source package differs")
    pack = json.loads(cell_raw)
    parent_revision = pack["active_revision"]
    parent = next(row for row in pack["releases"] if row["revision"] == parent_revision)
    proof_raw = Path(casting_proof_path).read_bytes()
    proof = json.loads(proof_raw)
    if (
        proof.get("schema") != "wakemu-original-casting-root-additions-v1"
        or proof.get("original_inputs_stable") is not True
        or proof.get("base_revision") != base_revision
    ):
        raise ValueError("Unverified original casting-root additions")
    casting_row = next(row for row in parent["documents"] if row["path"] == CASTING)
    if proof["base_document_sha256"] != casting_row["sha256"]:
        raise ValueError("Original casting source checksum differs")
    before = read_document(catalogs, pack, casting_row)
    exported = proof["original_export"]
    for key in ("schema", "fight_properties", "normal_casting_overrides"):
        if before[key] != exported[key]:
            raise ValueError("Original casting globals differ: " + key)
    if set(before["roots"]) & set(exported["roots"]):
        raise ValueError("Casting additions overlap existing native definitions")
    candidate = deepcopy(before)
    candidate["roots"].update(exported["roots"])
    if any(candidate["roots"][key] != value for key, value in before["roots"].items()):
        raise ValueError("Existing native casting metadata changed")
    candidate.setdefault("native_dependency_exports", []).append(
        dict(
            original_inputs_stable=True,
            original_input_hashes=proof["original_input_hashes"],
            original_export_sha256=proof["original_export_sha256"],
            source_proof_sha256=sha(proof_raw),
            root_ids=sorted(map(int, exported["roots"])),
            scope=proof["scope"],
            source="Original eVn.fKX/aZF, independent aZP",
        )
    )
    sources = dict(
        policy="wakemu.native-catalog-source-manifests.v1",
        releases=[deepcopy(old_release)],
    )
    updated = deepcopy(pack)
    changed = [
        store_document(catalogs, updated, CASTING, candidate),
        store_document(catalogs, updated, SOURCE_MANIFESTS, sources),
    ]
    active = next(
        row for row in updated["releases"] if row["revision"] == parent_revision
    )
    documents = {row["path"]: row for row in active["documents"]}
    documents.update({row["path"]: row for row in changed})
    active["documents"] = [documents[key] for key in sorted(documents)]
    inventory = [
        (row["path"], row["sha256"], row["source_bytes"]) for row in active["documents"]
    ]
    active.update(release_identity(inventory))
    active.update(
        document_count=len(inventory), source_bytes=sum(row[2] for row in inventory)
    )
    revision = active["revision"]
    if top["catalogs"]["active_revision"] not in (
        base_revision,
        parent_revision,
        revision,
    ):
        raise ValueError(
            "Public selector changed outside this immutable release lineage"
        )
    updated["active_revision"] = revision
    referenced = {
        row["sha256"] for release in updated["releases"] for row in release["documents"]
    }
    updated["blobs"] = {
        key: value for key, value in updated["blobs"].items() if key in referenced
    }
    name = "manifest-rift-complete-metadata-v1.json"
    manifest_raw = encode(updated)
    target = catalogs / name
    if target.exists() and target.read_bytes() != manifest_raw:
        raise ValueError("Immutable combined catalog name already owns other content")
    target.write_bytes(manifest_raw)
    new_top = deepcopy(top)
    new_top["artifacts"]["native-catalogs"].update(
        path="catalogs/" + name, sha256=sha(manifest_raw), size=len(manifest_raw)
    )
    new_top["catalogs"]["active_revision"] = revision
    for row in new_top["catalogs"]["releases"]:
        if row["revision"] in (base_revision, parent_revision, revision):
            row.update(
                revision=revision,
                document_count=active["document_count"],
                source_bytes=active["source_bytes"],
            )
    top_raw = encode(new_top)
    top_path.write_bytes(top_raw)
    (root / "manifest.sha256").write_text(sha(top_raw) + "  manifest.json\n")
    receipt = dict(
        schema="wakemu-rift-complete-metadata-release-v1",
        activated=False,
        original_revision=base_revision,
        parent_349_revision=parent_revision,
        candidate_revision=revision,
        document_count=active["document_count"],
        changed_documents=changed,
        source_manifest_sha256=sha(original_raw),
        candidate_manifest="catalogs/" + name,
        candidate_manifest_sha256=sha(manifest_raw),
        installation_manifest_sha256=sha(top_raw),
        casting_proof_sha256=sha(proof_raw),
        original_casting_roots=len(before["roots"]),
        added_casting_roots=len(exported["roots"]),
        existing_casting_rows_preserved=True,
        original_source_manifest_reproduces_revision=True,
        original_source_manifest_documents=len(old_inventory),
        actual_new_chunk_bytes=sum(
            updated["blobs"][row["sha256"]]["parts"][0]["compressed_bytes"]
            for row in changed
        ),
        database_staged=False,
        live_environment_changed=False,
    )
    (catalogs / "rift-complete-metadata-v1-receipt.json").write_bytes(encode(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path("server/data/installation"))
    parser.add_argument(
        "--casting-proof",
        type=Path,
        default=Path("server/data/native-rift-casting-root-additions-v1.json"),
    )
    args = parser.parse_args()
    print(json.dumps(build(args.pack, args.casting_proof), sort_keys=True))


if __name__ == "__main__":
    main()
