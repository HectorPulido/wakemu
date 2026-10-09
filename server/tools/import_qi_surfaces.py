"""Publish a verified native surface batch offline, preserving failed maps."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import os

from wakfu_server.combat_qi_surfaces import NativeQISurfaces


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(source, destination, topology, manifest_sha256):
    manifest_path = source / "manifest.json"
    if digest(manifest_path) != manifest_sha256:
        raise ValueError("Native surface batch manifest changed")
    manifest = json.loads(manifest_path.read_text())
    if destination.exists():
        raise ValueError(
            "Surface destination already exists; preserve it before replacing"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".native-qi-import-", dir=destination.parent)
    )
    counts = dict(imported=0, failed_native=0, columns=0, surfaces=0)
    try:
        seen = set()
        for row in manifest["maps"]:
            if row.get("status") != "exported":
                counts["failed_native"] += 1
                continue
            identity = row["map_id"]
            if type(identity) is not int or identity <= 0 or identity in seen:
                raise ValueError("Invalid or duplicate native surface map identity")
            seen.add(identity)
            path = source / f"{identity}.json"
            archive = topology / f"{identity}.jar"
            if (
                digest(path) != row["output_sha256"]
                or digest(archive) != row["source_sha256"]
            ):
                raise ValueError(
                    f"Native map {identity} surface/topology checksum mismatch"
                )
            data = json.loads(path.read_bytes())
            parsed = NativeQISurfaces(
                data, map_id=identity, source_sha256=row["source_sha256"]
            )
            column_count = sum(len(columns) for _, columns in parsed.chunks)
            surface_count = sum(
                len(values)
                for _, columns in parsed.chunks
                for values in columns.values()
            )
            if (
                len(parsed.chunks) != row["chunks"]
                or column_count != row["columns"]
                or surface_count != row["surfaces"]
            ):
                raise ValueError(f"Native map {identity} surface count mismatch")
            shutil.copyfile(path, temporary / path.name)
            if digest(temporary / path.name) != row["output_sha256"]:
                raise ValueError("Published native surface checksum mismatch")
            counts["imported"] += 1
            counts["columns"] += column_count
            counts["surfaces"] += surface_count
        if digest(manifest_path) != manifest_sha256:
            raise ValueError("Native surface manifest changed during publication")
        shutil.copyfile(manifest_path, temporary / "manifest.json")
        (temporary / "publication.json").write_text(
            json.dumps(
                dict(
                    schema="native-QI-surface-publication-v1",
                    manifest_sha256=manifest_sha256,
                    counts=counts,
                    importer_sha256=digest(Path(__file__)),
                ),
                indent=2,
            )
            + "\n"
        )
        os.replace(temporary, destination)
        return counts
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            publish(args.source, args.destination, args.topology, args.manifest_sha256)
        )
    )
