"""Publish original casting roots for the actual class2 captured ability books."""
import argparse
import hashlib
import json
from pathlib import Path


def run(source_path):
    root = Path("server/protocol")
    profiles_path = root / "native-class-captured-profiles.json"
    casting_path = root / "native-spell-casting.json"
    zero_path = root / "native-class-captured-level-zero.json"
    profiles = json.loads(profiles_path.read_text())["profiles"]
    references = sorted(
        {
            row["reference"]
            for profile in profiles.values()
            for row in profile["abilities"]
        }
    )
    casting = json.load(open(casting_path, "rt"))["spells"]
    zero = json.load(open(zero_path, "rt"))["casting"]
    roots = {
        str(reference)
        for spell in references
        for level in casting[str(spell)]["levels"] + zero[str(spell)]["levels"]
        for reference in level[2]
    }
    source = json.loads(source_path.read_text())
    if (
        source.get("schema") != "native-class-casting-roots-v1"
        or set(source["roots"]) != roots
    ):
        raise ValueError(
            "Native export does not match complete captured ability root domain"
        )
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source.update(
        class_dependency_domain="captured_class2",
        class_id=2,
        profile_ids=sorted(map(int, profiles)),
        spell_references=references,
        provenance={
            "original_export_sha256": sha(source_path),
            "profiles_source_sha256": sha(profiles_path),
            "casting_source_sha256": sha(casting_path),
            "zero_source_sha256": sha(zero_path),
            "exporter_sha256": sha(Path("sniffer/java/ExportNativeCastingRoots.java")),
        },
    )
    destination = root / "native-class-captured-casting-roots.json"
    destination.write_text(json.dumps(source, indent=2, allow_nan=False) + "\n")
    print(
        f"Published {len(roots)} original roots for {len(references)} captured class abilities"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_export", type=Path)
    run(parser.parse_args().original_export)
