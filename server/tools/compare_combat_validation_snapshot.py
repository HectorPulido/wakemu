"""Report which offline snapshot evidence still matches the current source."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(manifest_path, source_root=None):
    manifest = json.loads(manifest_path.read_text())
    root = Path(source_root or manifest["source_root"]).resolve()
    snapshot = manifest_path.parent.resolve()
    changed, missing, invalid_snapshot = [], [], []
    for relative, expected in manifest["files"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid snapshot relative path")
        captured = snapshot / path
        if (
            not captured.is_file()
            or hashlib.sha256(captured.read_bytes()).hexdigest() != expected
        ):
            invalid_snapshot.append(relative)
        current = root / path
        if not current.is_file():
            missing.append(relative)
        elif hashlib.sha256(current.read_bytes()).hexdigest() != expected:
            changed.append(relative)
    from snapshot_combat_validation import files

    added = sorted(
        str(path) for path in files(root) if str(path) not in manifest["files"]
    )
    return dict(
        scope="Byte identity only; this does not certify spell behavior",
        manifest=str(manifest_path.resolve()),
        source_root=str(root),
        captured_files=len(manifest["files"]),
        invalid_snapshot=invalid_snapshot,
        changed=changed,
        missing=missing,
        added=added,
        snapshot_intact=not invalid_snapshot,
        source_matches_snapshot=not (changed or missing or added),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.manifest, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in ("changed", "missing", "added", "invalid_snapshot")
            }
            | {
                key: len(result[key])
                for key in ("changed", "missing", "added", "invalid_snapshot")
            }
        )
    )
