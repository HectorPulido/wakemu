"""Seal original bulk resistance rows with equal before/after native source hashes."""
import argparse, hashlib, json
from pathlib import Path


def seal(original, before, after):
    data = json.loads(original.read_text())
    a = json.loads(before.read_text())
    b = json.loads(after.read_text())
    if a != b or not a or not any("wakfu-client.jar" in key for key in a):
        raise ValueError("Original native inputs changed or absent")
    if not any("bdata/" in key for key in a):
        raise ValueError("Original state bdata source hashes absent")
    if data.get("schema") != "native-class-state-resistance-v1":
        raise ValueError("Unexpected native state resistance source schema")
    data["provenance"] = dict(
        original_inputs_stable=True,
        original_input_hashes=a,
        original_export_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        before_manifest_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
        after_manifest_sha256=hashlib.sha256(after.read_bytes()).hexdigest(),
    )
    return data


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("original", "before", "after", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    args.output.write_text(
        json.dumps(seal(args.original, args.before, args.after), indent=2) + "\n"
    )
