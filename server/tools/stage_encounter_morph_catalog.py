"""Add an attested morphology bundle to the installation pack, never the live DB."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path

from tools.export_monster_morph_profiles import NAMES, package_document
from tools.import_native_catalogs import catalog_records, release_identity
from tools.stage_rift_complete_metadata_catalog import encode


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(pack_root, bundle, *, repository_root, profile_id=4252):
    if type(profile_id) is not int or profile_id not in (4252, 2887, 5852):
        raise ValueError("Unreviewed encounter morphology extension scope")
    root = Path(pack_root)
    top_path = root / "manifest.json"
    top = json.loads(top_path.read_bytes())
    source_path = root / top["artifacts"]["native-catalogs"]["path"]
    original_raw = source_path.read_bytes()
    if sha(original_raw) != top["artifacts"]["native-catalogs"]["sha256"]:
        raise ValueError("Installation source manifest checksum changed")
    pack = json.loads(original_raw)
    parent_revision = pack["active_revision"]
    parent = next(row for row in pack["releases"] if row["revision"] == parent_revision)
    indexed = {row["path"]: row for row in parent["documents"]}
    if not set(NAMES) <= indexed.keys():
        raise ValueError("Installation base lacks the complete morphology bundle")
    base_hashes = {name: indexed[name]["sha256"] for name in NAMES}
    outputs = package_document(bundle, base_hashes, root=repository_root)
    profile_document = json.loads(outputs[NAMES[0]])
    proof = profile_document["native_source_package"]
    receipt = json.loads(Path(proof["receipt"]).read_bytes())
    old_profiles = json.loads((Path(receipt["base"]) / NAMES[0]).read_bytes())[
        "profiles"
    ]
    expected_additions = {"2887", "5852"} if profile_id == 5852 else {str(profile_id)}
    if set(profile_document["profiles"]) - set(old_profiles) != expected_additions:
        raise ValueError(
            "Installation extension differs from its reviewed profile scope"
        )
    updated = deepcopy(pack)
    changed = {}
    catalogs = root / "catalogs"
    for name, raw in outputs.items():
        checksum = sha(raw)
        buffer = io.BytesIO()
        with gzip.GzipFile(
            filename="", fileobj=buffer, mode="wb", mtime=0, compresslevel=9
        ) as target:
            target.write(raw)
        compressed = buffer.getvalue()
        relative = "parts/" + checksum + ".json.gz"
        destination = catalogs / relative
        if destination.exists() and destination.read_bytes() != compressed:
            raise ValueError("Immutable morphology chunk collision")
        destination.write_bytes(compressed)
        updated["blobs"][checksum] = dict(
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
        changed[name] = dict(
            path=name,
            sha256=checksum,
            source_bytes=len(raw),
            record_count=sum(1 for _ in catalog_records(name, json.loads(raw))),
        )
    release = next(
        row for row in updated["releases"] if row["revision"] == parent_revision
    )
    release["documents"] = [
        changed.get(row["path"], row) for row in release["documents"]
    ]
    inventory = [
        (row["path"], row["sha256"], row["source_bytes"])
        for row in release["documents"]
    ]
    release.update(release_identity(inventory))
    release.update(
        document_count=len(inventory), source_bytes=sum(row[2] for row in inventory)
    )
    revision = release["revision"]
    updated["active_revision"] = revision
    tag = {
        4252: "brizlon-morph4252",
        2887: "abomination-morph2887",
        5852: "spirit-abomination-morphs",
    }[profile_id]
    name = "manifest-" + tag + "-v1.json"
    raw = encode(updated)
    target = catalogs / name
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Immutable morphology manifest already owns other bytes")
    target.write_bytes(raw)
    receipt = dict(
        schema="wakemu-encounter-morph-catalog-release-v1",
        parent_revision=parent_revision,
        candidate_revision=revision,
        parent_manifest_sha256=sha(original_raw),
        candidate_manifest="catalogs/" + name,
        candidate_manifest_sha256=sha(raw),
        changed_documents=list(changed.values()),
        unchanged_documents=len(inventory) - len(changed),
        preserved_old_chunk_files=True,
        reused_unchanged_chunks=True,
        added_profile_ids=sorted(map(int, expected_additions)),
        database_staged=False,
        activated=False,
        public_selector_changed=False,
    )
    (catalogs / (tag + "-v1-receipt.json")).write_bytes(encode(receipt))
    return receipt


def select_public(pack_root, receipt):
    """Select an immutable installation source; active database remains untouched."""
    root = Path(pack_root)
    path = root / "manifest.json"
    top = json.loads(path.read_bytes())
    parent, revision = receipt["parent_revision"], receipt["candidate_revision"]
    if top["catalogs"]["active_revision"] not in (parent, revision):
        raise ValueError("Installation selector left the qualified lineage")
    raw = (root / receipt["candidate_manifest"]).read_bytes()
    if sha(raw) != receipt["candidate_manifest_sha256"]:
        raise ValueError("Candidate morphology manifest checksum changed")
    pack = json.loads(raw)
    release = next(row for row in pack["releases"] if row["revision"] == revision)
    top["artifacts"]["native-catalogs"].update(
        path=receipt["candidate_manifest"], sha256=sha(raw), size=len(raw)
    )
    top["catalogs"]["active_revision"] = revision
    for row in top["catalogs"]["releases"]:
        if row["revision"] == parent:
            row.update(
                revision=revision,
                document_count=release["document_count"],
                source_bytes=release["source_bytes"],
            )
    output = encode(top)
    path.write_bytes(output)
    (root / "manifest.sha256").write_text(sha(output) + "  manifest.json\n")
    return dict(
        public_selector_changed=True,
        candidate_revision=revision,
        installation_manifest_sha256=sha(output),
        activated=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path("server/data/installation"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--profile-id", type=int, choices=(4252, 2887, 5852), default=4252
    )
    parser.add_argument("--select-public", action="store_true")
    args = parser.parse_args()
    receipt = build(
        args.pack,
        args.bundle,
        repository_root=args.repository_root,
        profile_id=args.profile_id,
    )
    if args.select_public:
        receipt.update(select_public(args.pack, receipt))
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
