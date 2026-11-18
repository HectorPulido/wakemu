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


def extension_scope(profile_id, profile_ids):
    """Require an explicit finite scope; native export receipts prove its data."""
    if profile_ids is not None:
        if (
            profile_id is not None
            or type(profile_ids) not in (list, tuple)
            or not 1 <= len(profile_ids) <= 16
            or any(
                type(value) is not int or not 0 < value < 2**31
                for value in profile_ids
            )
            or len(set(profile_ids)) != len(profile_ids)
        ):
            raise ValueError("Explicit unique native morphology additions required")
        values = sorted(profile_ids)
        return set(map(str, values)), "encounter-morphs-" + "-".join(map(str, values))
    tags = {
        4252: "brizlon-morph4252",
        2887: "abomination-morph2887",
        5852: "spirit-abomination-morphs",
        3907: "school-seed-morph3907-common5622",
    }
    if type(profile_id) is not int or profile_id not in tags:
        raise ValueError("Unreviewed legacy morphology extension scope")
    additions = {"2887", "5852"} if profile_id == 5852 else {str(profile_id)}
    if profile_id == 3907:
        additions |= {"2778", "5519", "5520", "5521", "5522", "5524"}
    return additions, tags[profile_id]


def fresh_summon_outputs(graph, base_documents, provenance):
    """Carry every actual307 dependency into both fresh constructor domains."""
    from tools.export_monster_summon_dependencies import merge_profiles

    references = {
        str(sample["reference"])
        for row in graph
        if row.get("kind") == "effect" and row.get("family") == 307
        for sample in row.get("classified_reference_samples", ())
        if sample.get("kind") == "profile"
        and 0 <= sample.get("sample_level", -1) <= 245
        and sample.get("reference", 0) > 0
    }
    if not references:
        return {}, []
    profiles = {
        str(row["reference"]): row["native_ability_profile"]
        for row in graph
        if row.get("kind") == "profile" and "native_ability_profile" in row
    }
    if not references <= profiles.keys() or any(
        profiles[key].get("profile_id") != int(key)
        or any(
            field not in profiles[key]
            for field in ("abilities", "initial_state_triples", "fight_properties")
        )
        for key in references
    ):
        raise ValueError("Original307 graph lacks complete fresh constructor metadata")
    outputs = merge_profiles(
        base_documents,
        {"profiles": {key: profiles[key] for key in sorted(references)}},
        provenance,
    )
    return outputs, sorted(map(int, references))


def build(
    pack_root,
    bundle,
    *,
    repository_root,
    profile_id=None,
    profile_ids=None,
    common_spell_documents=()
):
    if profile_id is None and profile_ids is None:
        profile_id = 4252
    expected_additions, tag = extension_scope(profile_id, profile_ids)
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
    if set(profile_document["profiles"]) - set(old_profiles) != expected_additions:
        raise ValueError(
            "Installation extension differs from its reviewed profile scope"
        )
    # Morph spell/state/area closures may create ordinary307 summons too.
    # Their books and initial triples are distinct mandatory source domains.
    owner = Path(proof["receipt"]).parent.parent
    graph_path = owner / "morph-typed-closure.jsonl.gz"
    graph = [json.loads(line) for line in gzip.open(graph_path, "rt")]
    from tools.export_monster_summon_dependencies import CATALOG_PATHS
    from tools.stage_rift_complete_metadata_catalog import read_document

    dependencies = any(
        row.get("kind") == "effect" and row.get("family") == 307 for row in graph
    )
    summon_ids = []
    if dependencies:
        base_documents = {
            name: read_document(source_path.parent, pack, indexed[name])
            for name in CATALOG_PATHS
        }
        additions, summon_ids = fresh_summon_outputs(
            graph,
            base_documents,
            dict(
                original_inputs_stable=True,
                source="Original307 typed profile constructor dependency",
                typed_graph_sha256=sha(graph_path.read_bytes()),
                dependency_receipt_sha256=sha(
                    (owner / "dependency-export-receipt.json").read_bytes()
                ),
            ),
        )
        outputs.update(
            {name: encode(value, compact=True) for name, value in additions.items()}
        )
    if common_spell_documents:
        documents = {Path(path).name: Path(path) for path in common_spell_documents}
        expected_common = {
            "native-common-spell-effect-trees.json",
            "native-common-spell-casting-roots.json",
        }
        if (
            profile_id != 3907
            or set(documents) != expected_common
            or len(common_spell_documents) != 2
        ):
            raise ValueError(
                "Common spell extension requires the reviewed complete two-document bundle"
            )
        for name, path in documents.items():
            raw = path.read_bytes()
            candidate = json.loads(raw)
            descriptor = indexed[name]
            original = b"".join(
                gzip.decompress((source_path.parent / part["path"]).read_bytes())
                for part in pack["blobs"][descriptor["sha256"]]["parts"]
            )
            if sha(original) != descriptor["sha256"]:
                raise ValueError("Common spell base chunk checksum changed")
            previous = json.loads(original)
            for field, value in previous.items():
                if isinstance(value, dict):
                    if not isinstance(candidate.get(field), dict) or any(
                        candidate[field].get(key) != row for key, row in value.items()
                    ):
                        raise ValueError(
                            "Existing common spell record changed: "
                            + name
                            + ":"
                            + field
                        )
                elif (
                    field not in ("source", "spell_references")
                    and candidate.get(field) != value
                ):
                    raise ValueError(
                        "Existing common spell metadata changed: " + name + ":" + field
                    )
            if set(candidate.get("spell_references", ())) != {5622, 5623}:
                raise ValueError(
                    "Common spell extension differs from reviewed native5622 scope"
                )
            outputs[name] = raw
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
    from tools.native_catalog_provenance import validated_retired_inventories

    # Compatibility seals can still name the exact parent after payload reuse
    # replaces its release. Carry its complete inventory for fresh installs.
    updated["retired_inventories"] = validated_retired_inventories(
        [*pack.get("retired_inventories", ()), parent],
        payload_revisions=[row["revision"] for row in updated["releases"]],
    )
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
        fresh_summon_profile_ids=summon_ids,
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
    parser.add_argument("--pack", type=Path, default=Path("database/data/installation"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--profile-id", type=int, choices=(4252, 2887, 5852, 3907))
    scope.add_argument("--profile-ids", type=int, nargs="+")
    parser.add_argument("--select-public", action="store_true")
    parser.add_argument(
        "--common-spell-document", action="append", type=Path, default=[]
    )
    args = parser.parse_args()
    receipt = build(
        args.pack,
        args.bundle,
        repository_root=args.repository_root,
        profile_id=(None if args.profile_ids is not None else args.profile_id or 4252),
        profile_ids=args.profile_ids,
        common_spell_documents=args.common_spell_document,
    )
    if args.select_public:
        receipt.update(select_public(args.pack, receipt))
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
