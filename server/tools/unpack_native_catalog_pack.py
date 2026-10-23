"""Verify and materialize immutable catalog documents without a client or database."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

FORMAT = "wakemu-native-catalog-pack-v1"
PART_BYTES = 16 * 1024 * 1024


def safe_path(value):
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "\0" in value
        or PurePosixPath(value).is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("Unsafe catalog pack path")
    return PurePosixPath(value)


def digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid catalog pack checksum")
    return value


def unpack(manifest_path, output_directory):
    """Return a legacy seed manifest; never activate or import its releases."""
    from tools.import_native_catalogs import validate_release_inventory

    manifest_path = Path(manifest_path)
    pack = json.loads(manifest_path.read_text())
    if (
        pack.get("format") != FORMAT
        or not isinstance(pack.get("blobs"), dict)
        or not isinstance(pack.get("releases"), list)
        or not pack["releases"]
    ):
        raise ValueError("Invalid native catalog pack")
    active = digest(pack.get("active_revision"))
    revisions = set()
    required = {}
    for release in pack["releases"]:
        revision = digest(release.get("revision"))
        if revision in revisions:
            raise ValueError("Duplicate catalog release")
        revisions.add(revision)
        documents = release.get("documents", [])
        validate_release_inventory(
            [(row["path"], row["sha256"], row["source_bytes"]) for row in documents],
            release,
        )
        for row in documents:
            previous = required.setdefault(row["sha256"], row["source_bytes"])
            if previous != row["source_bytes"]:
                raise ValueError("Conflicting document sizes")
    if active not in revisions or set(pack["blobs"]) != set(required):
        raise ValueError("Catalog pack contains missing or unreferenced content")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    (output_directory / "INCOMPLETE").write_text("Catalog materialization incomplete\n")
    objects = output_directory / ".catalog-objects"
    objects.mkdir()
    for checksum, size in required.items():
        digest(checksum)
        blob = pack["blobs"][checksum]
        if (
            type(size) is not int
            or size < 0
            or blob.get("source_bytes") != size
            or not isinstance(blob.get("parts"), list)
            or not blob["parts"]
        ):
            raise ValueError("Invalid catalog document content")
        total = 0
        document_hash = hashlib.sha256()
        with (objects / checksum).open("xb") as target:
            for part in blob["parts"]:
                count = part.get("source_bytes")
                compressed_count = part.get("compressed_bytes")
                if (
                    type(count) is not int
                    or not 0 <= count <= PART_BYTES
                    or type(compressed_count) is not int
                    or not 0 < compressed_count <= PART_BYTES + 65536
                ):
                    raise ValueError("Invalid catalog part size")
                relative = safe_path(part.get("path"))
                path = manifest_path.parent.joinpath(*relative.parts)
                if path.is_symlink() or not path.resolve().is_relative_to(
                    manifest_path.parent.resolve()
                ):
                    raise ValueError("Catalog part escapes its pack")
                if path.stat().st_size != compressed_count:
                    raise ValueError("Catalog compressed size mismatch")
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest(
                    part.get("compressed_sha256")
                ):
                    raise ValueError("Catalog compressed checksum mismatch")
                # Bound decompression even for malformed or adversarial bundles.
                with gzip.open(path, "rb") as source:
                    decoded = source.read(count + 1)
                    if len(decoded) != count or source.read(1):
                        raise ValueError("Catalog decoded size mismatch")
                if hashlib.sha256(decoded).hexdigest() != digest(part.get("sha256")):
                    raise ValueError("Catalog part checksum mismatch")
                target.write(decoded)
                document_hash.update(decoded)
                total += count
        if total != size or document_hash.hexdigest() != checksum:
            raise ValueError("Native document checksum mismatch")
    # Independent copies: editing one extracted release cannot modify another.
    import shutil

    for release in pack["releases"]:
        root = output_directory / "catalogs" / release["revision"]
        for row in release["documents"]:
            relative = safe_path(row["path"])
            path = root.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with (objects / row["sha256"]).open("rb") as source, path.open(
                "xb"
            ) as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    shutil.rmtree(objects)
    result = {
        "format": "wakemu-installation-seed-v1",
        "active_revision": active,
        "releases": pack["releases"],
        "player_tables_exported": [],
    }
    (output_directory / "catalog-manifest.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n"
    )
    (output_directory / "INCOMPLETE").unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(unpack(args.manifest, args.directory), sort_keys=True))


if __name__ == "__main__":
    main()
