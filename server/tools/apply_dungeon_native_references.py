"""Apply independently verified exact-name reference resolutions to evidence files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dungeon_reference_names import NAME_NORMALIZATION_POLICY, normalized_name


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence path escapes repository")
    return path


def prepare(root, report):
    root = root.resolve()
    documents = {}
    seen = set()
    applied = 0
    for record in report["records"]:
        if record["status"] != "resolved":
            continue
        path = local_path(root, record["composition"])
        if path not in documents:
            documents[path] = json.loads(path.read_text())
        rooms = [
            r for r in documents[path]["rooms"] if r["order"] == record["room_order"]
        ]
        if len(rooms) != 1:
            raise ValueError("Room order is missing or ambiguous")
        index = record["monster_index"]
        if type(index) is not int or not 0 <= index < len(rooms[0]["monsters"]):
            raise ValueError("Monster index must be a bounded nonnegative integer")
        key = (path, record["room_order"], index)
        if key in seen:
            raise ValueError("Duplicate resolution target")
        seen.add(key)
        monster = rooms[0]["monsters"][record["monster_index"]]
        if monster["name"] != record["guide_name"]:
            raise ValueError("Composition name changed since resolution")
        native_path = local_path(root, record["native_name_catalog"])
        native = json.loads(native_path.read_text())
        archive = local_path(root, native["source"]["archive"])
        if sha256(archive) != native["source"]["archive_sha256"]:
            raise ValueError("Native archive hash mismatch")
        candidates = [
            r["ref"] for r in native["monsters"] if r["name_fr"] == monster["name"]
        ]
        if sorted(candidates) != sorted(record["exact_name_candidates"]):
            raise ValueError("Native name candidates changed")
        policy = record.get("name_normalization_policy")
        if policy is not None:
            if policy != NAME_NORMALIZATION_POLICY:
                raise ValueError("Unknown native name normalization policy")
            if record.get("normalized_guide_name") != normalized_name(monster["name"]):
                raise ValueError("Normalized guide name changed")
            candidates = sorted(
                set(
                    r["ref"]
                    for r in native["monsters"]
                    if isinstance(r["name_fr"], str)
                    and normalized_name(r["name_fr"])
                    == normalized_name(monster["name"])
                )
            )
            if candidates != record.get("normalized_name_candidates"):
                raise ValueError("Normalized native name candidates changed")
        context = record.get("context")
        evidence_path = native_path
        if context:
            context_path = local_path(root, context["catalog"])
            if sha256(context_path) != context["catalog_sha256"]:
                raise ValueError("Context catalog hash mismatch")
            definitions = json.loads(context_path.read_text())
            matches = [d for d in definitions if d["id"] == context["definition_id"]]
            if (
                len(matches) != 1
                or matches[0][context["species_field"]] != context["species_refs"]
            ):
                raise ValueError("Context species evidence mismatch")
            candidates = [
                ref for ref in candidates if ref in matches[0][context["species_field"]]
            ]
            evidence_path = context_path
        ref = record["resolved_ref"]
        if candidates != [ref] or record["remaining_candidates"] != [ref]:
            raise ValueError("Reference resolution is not unique")
        if monster["ref_id"] not in (None, ref):
            raise ValueError("Conflicting existing reference")
        monster["ref_id"] = ref
        monster["unknown_fields"] = [
            f for f in monster["unknown_fields"] if f != "ref_id"
        ]
        evidence = {
            "source_url": f"urn:wakfu:client:content.7.{ref}",
            "archive_path": str(native_path.relative_to(root)),
            "kind": "client_catalog",
            "locator": f'content.7.{ref}; name_fr={monster["name"]}; native_catalog_sha256={sha256(native_path)}; context={evidence_path.relative_to(root)}; context_sha256={sha256(evidence_path)}',
            "excerpt": monster["name"],
        }
        if evidence not in monster["evidence"]:
            monster["evidence"].append(evidence)
        applied += 1
    return documents, applied


def apply(root, report, backup_directory):
    documents, count = prepare(root, report)
    originals = {path: path.read_bytes() for path in documents}
    backups = {path: backup_directory / path.name for path in documents}
    if len(set(backups.values())) != len(backups):
        raise ValueError("Backup destinations collide")
    if any(destination.exists() for destination in backups.values()):
        raise ValueError("Backup already exists")
    for path in documents:
        if path.read_bytes() != originals[path]:
            raise ValueError("Composition changed during preparation")
    backup_directory.mkdir(parents=True, exist_ok=True)
    staged = {}
    rollback = {}
    replaced = []
    temporary_paths = []
    created_backups = []
    try:
        for path, document in documents.items():
            for target, payload in (
                (
                    staged,
                    (
                        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
                    ).encode(),
                ),
                (rollback, originals[path]),
            ):
                with tempfile.NamedTemporaryFile(
                    "wb", dir=path.parent, delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    temporary_paths.append(temporary)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                    target[path] = temporary
        for path, destination in backups.items():
            with destination.open("xb") as stream:
                created_backups.append(destination)
                stream.write(originals[path])
        for path in documents:
            if path.read_bytes() != originals[path]:
                raise ValueError("Composition changed during staging")
        for path in documents:
            os.replace(staged[path], path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            os.replace(rollback[path], path)
        for destination in created_backups:
            destination.unlink(missing_ok=True)
        raise
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-directory", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "applied": apply(
                    args.root.resolve(),
                    json.loads(args.report.read_text()),
                    args.backup_directory,
                )
            }
        )
    )
