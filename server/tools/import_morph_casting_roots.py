"""Publish only original fKX/aZF roots for the class11 profile5900 book."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source_path):
    source = json.loads(source_path.read_text())
    casting_path = Path("server/protocol/native-spell-casting.json")
    zero_path = Path("server/protocol/native-class-morph933-level-zero.json")
    casting = json.load(open(casting_path, "rt"))["spells"]
    zero = json.load(open(zero_path, "rt"))["casting"]
    roots = set()
    for reference in (8588, 8589, 8590):
        for row in casting[str(reference)]["levels"] + zero[str(reference)]["levels"]:
            roots.update(map(str, row[2]))
    if (
        source.get("schema") != "native-class-casting-roots-v1"
        or set(source["roots"]) != roots
    ):
        raise ValueError(
            "Original export does not match complete three-ability root domain"
        )
    source.update(
        class_dependency_domain="morph933",
        class_id=11,
        profile_id=5900,
        spell_references=[8588, 8589, 8590],
        provenance={
            "original_export_sha256": sha(source_path),
            "casting_source_sha256": sha(casting_path),
            "zero_source_sha256": sha(zero_path),
            "exporter_sha256": sha(Path("sniffer/java/ExportNativeCastingRoots.java")),
        },
    )
    destination = Path("server/protocol/native-class-morph933-casting-roots.json")
    destination.write_text(json.dumps(source, indent=2, allow_nan=False) + "\n")
    print(f"Published {len(roots)} original roots for three class morphology abilities")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_export", type=Path)
    run(parser.parse_args().original_export)
