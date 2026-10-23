"""Assemble pinned, player-free installation artifacts into a repository data pack."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def assemble(
    *, catalog_manifest, bootstrap, reviewed_dungeons, output, metadata, seeds
):
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "catalogs"
    if destination.exists() and digest(destination / catalog_manifest.name) != digest(
        catalog_manifest
    ):
        raise ValueError("Public catalog destination owns a different manifest")
    native = json.loads(catalog_manifest.read_text())
    # Copy only the pinned submanifest and its declared compressed parts.
    # Private audit/scanner output beside an exported pack is never published.
    destination.mkdir(exist_ok=True)
    if catalog_manifest.resolve() != (destination / catalog_manifest.name).resolve():
        shutil.copyfile(catalog_manifest, destination / catalog_manifest.name)
    copied = set()
    for blob in native["blobs"].values():
        for part in blob["parts"]:
            relative = Path(part["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe native catalog artifact path")
            if relative.as_posix() in copied:
                continue
            copied.add(relative.as_posix())
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if (catalog_manifest.parent / relative).resolve() != target.resolve():
                shutil.copyfile(catalog_manifest.parent / relative, target)
    artifacts = {}

    def artifact(key, source, *, compression="none"):
        path = output / "artifacts" / source.name
        path.parent.mkdir(exist_ok=True)
        if source.resolve() != path.resolve():
            shutil.copyfile(source, path)
        artifacts[key] = dict(
            path=path.relative_to(output).as_posix(),
            sha256=digest(path),
            size=path.stat().st_size,
            compression=compression,
        )
        return key

    artifacts["native-catalogs"] = dict(
        path="catalogs/" + catalog_manifest.name,
        sha256=digest(destination / catalog_manifest.name),
        size=(destination / catalog_manifest.name).stat().st_size,
        compression="none",
    )
    bootstrap_ref = artifact("synthetic-bootstrap", bootstrap, compression="gzip")
    reviewed_ref = artifact("reviewed-dungeons", reviewed_dungeons, compression="gzip")
    references = [artifact(key, source) for key, source in seeds]
    releases = [
        {
            key: row[key]
            for key in ("revision", "directory", "document_count", "source_bytes")
            if key in row
        }
        for row in native["releases"]
    ]
    manifest = dict(
        format="wakemu-public-installation-v1",
        contains_private_capture=False,
        contains_capture_origin_templates=True,
        static_protocol_templates=True,
        player_tables_exported=[],
        catalogs=dict(
            manifest="native-catalogs",
            active_revision=native["active_revision"],
            mining_revision=metadata["mining_revision"],
            fishing_revision=metadata["fishing_revision"],
            releases=releases,
        ),
        bootstrap=dict(
            artifact=bootstrap_ref,
            capture_key="native-bootstrap-v1",
            sha256=hashlib.sha256(gzip.decompress(bootstrap.read_bytes())).hexdigest(),
        ),
        reviewed_dungeons=dict(
            artifact=reviewed_ref,
            sha256=hashlib.sha256(
                gzip.decompress(reviewed_dungeons.read_bytes())
            ).hexdigest(),
        ),
        artifacts=artifacts,
        sql_seeds=references,
        expected_counts=metadata["expected_counts"],
        expected_semantics=metadata["expected_semantics"],
    )
    encoded = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    (output / "manifest.json").write_bytes(encoded)
    (output / "manifest.sha256").write_text(
        hashlib.sha256(encoded).hexdigest() + "  manifest.json\n"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "catalog-manifest",
        "bootstrap",
        "reviewed-dungeons",
        "output",
        "metadata",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--seed", action="append", default=[], help="artifact-key=path")
    args = parser.parse_args()
    seeds = [
        (key, Path(path)) for key, path in (value.split("=", 1) for value in args.seed)
    ]
    manifest = assemble(
        catalog_manifest=args.catalog_manifest,
        bootstrap=args.bootstrap,
        reviewed_dungeons=args.reviewed_dungeons,
        output=args.output,
        metadata=json.loads(args.metadata.read_text()),
        seeds=seeds,
    )
    print(
        json.dumps(
            dict(
                format=manifest["format"],
                artifacts=len(manifest["artifacts"]),
                manifest_sha256=digest(args.output / "manifest.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
