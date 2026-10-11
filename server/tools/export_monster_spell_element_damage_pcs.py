"""Offline native element-PC export with source-bound append-only packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CATALOG_PATH = "native-spell-element-damage-pcs.json"
CONTRACT = "eYW.fQG.fyG.gtZ.fyF.gtQ.eVg.fa.fLC.aKg.v1"
EXPORTER = "sniffer/java/ExportNativeSpellElementDamagePCs.java"
JAR = "client/lib/wakfu-client.jar"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_document(document):
    if (
        not isinstance(document, dict)
        or document.get("source") != CONTRACT
        or document.get("null_pc_present") is not False
    ):
        raise ValueError("Missing native element PC and null-presence contract")
    rows = document.get("elements")
    if not isinstance(rows, dict) or len(rows) != 8:
        raise ValueError("Missing complete native eVg element domain")
    names, stats = set(), set()
    for key, row in rows.items():
        try:
            identity = int(key)
        except (ValueError, TypeError):
            raise ValueError("Invalid native eVg element identity") from None
        if (
            not isinstance(key, str)
            or str(identity) != key
            or not -128 <= identity <= 127
            or not isinstance(row, dict)
            or type(row.get("native_element")) is not int
            or row["native_element"] != identity
        ):
            raise ValueError("Invalid native eVg element identity")
        name = row.get("element_name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Invalid native eVg element name")
        names.add(name)
        if "damage_stat" not in row:
            raise ValueError("Missing native eVg.fLC PC identity")
        stat = row["damage_stat"]
        if stat is not None:
            if type(stat) is not int or not -128 <= stat <= 127 or stat in stats:
                raise ValueError("Invalid native eVg.fLC PC identity")
            stats.add(stat)
    return document


def package_document(path, manifest, *, root):
    path, root = Path(path), Path(root)
    document = validate_document(json.loads(path.read_text()))
    receipt = json.loads(path.with_suffix(".receipt.json").read_text())
    if (
        receipt.get("schema") != "native-spell-element-damage-pcs-export-v1"
        or receipt.get("document_sha256") != sha(path)
        or receipt.get("element_count") != len(document["elements"])
        or receipt.get("sources")
        != {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}
    ):
        raise ValueError("Native element PC export differs from installed source proof")
    if CATALOG_PATH in manifest:
        if manifest[CATALOG_PATH] != sha(path):
            raise ValueError(
                "Existing shared spell element PC catalog must not be replaced"
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
    classes = output.parent / "element-pc-export-classes"
    classes.mkdir(exist_ok=True)
    sources = {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}
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
            "-Xmx64m",
            "-cp",
            str(classes) + ":" + str(root / "client/lib/*"),
            "ExportNativeSpellElementDamagePCs",
            str(output),
        ],
        check=True,
        cwd=root,
    )
    document = validate_document(json.loads(output.read_text()))
    if sources != {JAR: sha(root / JAR), EXPORTER: sha(root / EXPORTER)}:
        raise ValueError("Installed native sources changed during element PC export")
    receipt = dict(
        schema="native-spell-element-damage-pcs-export-v1",
        sources=sources,
        document_sha256=sha(output),
        element_count=len(document["elements"]),
        published=False,
    )
    output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    package_document(output, {}, root=root)


if __name__ == "__main__":
    main()
