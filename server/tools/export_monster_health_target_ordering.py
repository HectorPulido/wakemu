"""Reproducible offline flag8 identity export and append-only package validation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CATALOG_PATH = "native-health-target-ordering.json"
CONTRACT = "faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1"
EXPORTER = "sniffer/java/ExportNativeHealthTargetOrdering.java"
JAR = "client/lib/wakfu-client.jar"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_rows(rows):
    if not isinstance(rows, dict) or not rows:
        raise ValueError("Missing native health ordering identities")
    for reference, row in rows.items():
        if (
            not isinstance(reference, str)
            or not reference.isdecimal()
            or int(reference) <= 0
        ):
            raise ValueError("Invalid native health ordering reference")
        if (
            not isinstance(row, dict)
            or type(row.get("effect_class")) is not int
            or row["effect_class"] <= 0
        ):
            raise ValueError("Missing native health ordering definition class")
        flags = row.get("native_effect_flags")
        if (
            not isinstance(flags, list)
            or any(type(v) is not int or not 0 <= v < 128 for v in flags)
            or len(flags) != len(set(flags))
            or 8 not in flags
        ):
            raise ValueError("Missing exact native health ordering flags")
        maximum = row.get("maximum_targets")
        if type(maximum) is not int or not -128 <= maximum <= 127:
            raise ValueError("Missing native signed target cap")
        if row.get("ordering_contract") != CONTRACT:
            raise ValueError("Missing native faI ordering contract")
    return rows


def package_document(path, manifest, *, root):
    """Validate installed-source receipt; append only or keep identical shared data."""
    path, root = Path(path), Path(root)
    receipt = json.loads(path.with_suffix(".receipt.json").read_text())
    rows = validate_rows(json.loads(path.read_text()))
    if (
        receipt.get("schema") != "native-health-target-ordering-export-v1"
        or receipt.get("document_sha256") != sha(path)
        or receipt.get("definition_count") != len(rows)
        or receipt.get("sources")
        != {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}
    ):
        raise ValueError(
            "Native health ordering export differs from installed source proof"
        )
    if CATALOG_PATH in manifest:
        if manifest[CATALOG_PATH] != sha(path):
            raise ValueError(
                "Existing shared health ordering catalog must not be replaced"
            )
        return {}
    return {CATALOG_PATH: path.read_bytes()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if (root / ".runtime").resolve() not in output.parents:
        parser.error("Native private exports must be beneath .runtime")
    output.parent.mkdir(parents=True, exist_ok=True)
    classes = output.parent / "health-ordering-export-classes"
    classes.mkdir(exist_ok=True)
    source_hashes = {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            str(root / "client/lib/*"),
            "-d",
            str(classes),
            str(root / EXPORTER),
        ],
        check=True,
        cwd=root,
    )
    subprocess.run(
        [
            "java",
            "-cp",
            str(classes) + ":" + str(root / "client/lib/*"),
            "ExportNativeHealthTargetOrdering",
            str(output),
        ],
        check=True,
        cwd=root,
    )
    rows = validate_rows(json.loads(output.read_text()))
    if source_hashes != {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}:
        raise ValueError(
            "Installed native sources changed during health ordering export"
        )
    receipt = dict(
        schema="native-health-target-ordering-export-v1",
        sources=source_hashes,
        document_sha256=sha(output),
        definition_count=len(rows),
        published=False,
    )
    output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    package_document(output, {}, root=root)


if __name__ == "__main__":
    main()
