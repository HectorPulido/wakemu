"""Verify the repository's public data pack and materialize installer inputs.

No database access, SQL execution, activation or player data is involved.
The public manifest describes data artifacts only; it cannot supply commands.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile


FORMAT = "wakemu-public-installation-v1"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_ARTIFACT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\Z")


def _sha(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid public data checksum")
    return value


def _file(root, value):
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "\0" in value
        or PurePosixPath(value).is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("Unsafe public data artifact path")
    path = root.joinpath(*PurePosixPath(value).parts)
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Missing or foreign public data artifact")
    return path


def _hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify(pack):
    root = Path(pack)
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != FORMAT
        or manifest.get("contains_private_capture") is not False
        or manifest.get("player_tables_exported") != []
    ):
        raise ValueError("Installation requires a player-free public data pack")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("Missing public data artifacts")
    for key, row in artifacts.items():
        if (
            not isinstance(key, str)
            or _ARTIFACT.fullmatch(key) is None
            or not isinstance(row, dict)
            or type(row.get("size")) is not int
            or row["size"] < 0
            or row.get("compression", "none") not in ("none", "gzip")
        ):
            raise ValueError("Invalid public data artifact declaration")
        artifact = _file(root, row.get("path"))
        if artifact.stat().st_size != row["size"] or _hash(artifact) != _sha(
            row.get("sha256")
        ):
            raise ValueError("Public data artifact checksum mismatch")
    counts = manifest.get("expected_counts")
    if not isinstance(counts, dict) or any(
        not isinstance(key, str)
        or _NAME.fullmatch(key) is None
        or type(value) is not int
        or value < 0
        for key, value in counts.items()
    ):
        raise ValueError("Invalid installation table-count declaration")
    if not isinstance(manifest.get("expected_semantics", {}), dict):
        raise ValueError("Invalid installation semantic-count declaration")
    seeds = manifest.get("sql_seeds", [])
    if (
        not isinstance(seeds, list)
        or any(not isinstance(ref, str) or ref not in artifacts for ref in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("Invalid installation SQL artifact references")
    for section in ("catalogs", "bootstrap", "reviewed_dungeons"):
        node = manifest.get(section)
        ref = (
            node.get("manifest" if section == "catalogs" else "artifact")
            if isinstance(node, dict)
            else None
        )
        if ref not in artifacts:
            raise ValueError("Missing required installation data component")
    return manifest


def _materialize_artifact(root, manifest, reference, destination):
    row = manifest["artifacts"][reference]
    source = _file(root, row["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if row.get("compression", "none") == "gzip" else open
    with opener(source, "rb") as stream, destination.open("wb") as output:
        shutil.copyfileobj(stream, output, 1024 * 1024)
    return dict(
        path=destination.name,
        sha256=_hash(destination),
        source_bytes=destination.stat().st_size,
    )


def materialize(pack, output):
    """Return the legacy input manifest after all immutable artifacts verify."""
    root, output = Path(pack), Path(output)
    manifest = verify(root)
    if output.exists():
        raise ValueError("Installation data output must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.unpack_native_catalog_pack import unpack

    with tempfile.TemporaryDirectory(
        prefix=".wakemu-data-", dir=output.parent
    ) as temporary:
        stage = Path(temporary) / "inputs"
        stage.mkdir()
        catalog_artifact = manifest["artifacts"][manifest["catalogs"]["manifest"]]
        if catalog_artifact.get("compression", "none") != "none":
            raise ValueError("Catalog submanifest must be plain verified JSON")
        native_directory = Path(temporary) / "native"
        result = unpack(_file(root, catalog_artifact["path"]), native_directory)
        if result["active_revision"] != manifest["catalogs"]["active_revision"]:
            raise ValueError("Public native active revision differs from catalog pack")
        declared = manifest["catalogs"]
        revisions = {row["revision"] for row in result["releases"]}
        roles = {
            declared.get(key)
            for key in ("active_revision", "mining_revision", "fishing_revision")
        }
        if (
            None in roles
            or revisions != roles
            or {row["revision"] for row in declared.get("releases", [])} != revisions
        ):
            raise ValueError(
                "Public native release set differs from pinned catalog roles"
            )
        shutil.move(native_directory / "catalogs", stage / "catalogs")
        node = manifest["bootstrap"]
        bootstrap = _materialize_artifact(
            root, manifest, node["artifact"], stage / "bootstrap.synthetic.jsonl"
        )
        if bootstrap["sha256"] != _sha(node["sha256"]):
            raise ValueError("Synthetic bootstrap identity differs from manifest")
        # The public frames carry their own explicit synthetic authority and
        # contain no transport/session/capture metadata.
        records = [
            json.loads(line)
            for line in (stage / bootstrap["path"]).read_text().splitlines()
        ]
        if (
            not records
            or any(
                set(row) - {"direction", "opcode", "body_base64", "synthetic_template"}
                for row in records
            )
            or records[0].get("synthetic_template", {}).get("policy")
            != "wakemu-synthetic-bootstrap-v1"
        ):
            raise ValueError("Bootstrap is not the declared synthetic public template")
        reviewed = _materialize_artifact(
            root,
            manifest,
            manifest["reviewed_dungeons"]["artifact"],
            stage / "reviewed-dungeons.sql",
        )
        if reviewed["sha256"] != _sha(manifest["reviewed_dungeons"]["sha256"]):
            raise ValueError("Reviewed public dungeon seed differs from manifest")
        additional = []
        for reference in manifest.get("sql_seeds", []):
            sql = _materialize_artifact(
                root, manifest, reference, stage / "sql" / (reference + ".sql")
            )
            sql["path"] = "sql/" + sql["path"]
            additional.append(sql)
        result.update(
            contains_private_capture=False,
            player_tables_exported=[],
            bootstrap_exported=True,
            bootstrap=dict(
                capture_key=node["capture_key"],
                source_sha256=bootstrap["sha256"],
                frame_count=len(records),
            ),
            bootstrap_export=dict(
                **bootstrap,
                import_expected_sha256=bootstrap["sha256"],
                serialization="wakemu-synthetic-template-v1"
            ),
            reviewed_dungeons=reviewed,
            additional_seeds=additional,
            expected_counts=manifest["expected_counts"],
            expected_semantics=manifest.get("expected_semantics", {}),
        )
        encoded = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
        (stage / "manifest.json").write_bytes(encoded)
        (stage / "manifest.sha256").write_text(
            hashlib.sha256(encoded).hexdigest() + "  manifest.json\n"
        )
        stage.rename(output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "installation",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        manifest = verify(args.pack)
        print(
            json.dumps(
                dict(
                    format=manifest["format"],
                    verified=True,
                    artifact_count=len(manifest["artifacts"]),
                ),
                sort_keys=True,
            )
        )
    else:
        if args.output is None:
            parser.error("--output is required unless --verify-only")
        result = materialize(args.pack, args.output)
        print(
            json.dumps(
                dict(
                    format=result["format"],
                    output=str(args.output),
                    active_revision=result["active_revision"],
                    release_count=len(result["releases"]),
                    bootstrap_frames=result["bootstrap"]["frame_count"],
                    manifest_sha256=_hash(args.output / "manifest.json"),
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
