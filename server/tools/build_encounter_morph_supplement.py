"""Build an additive original morphology bundle without database publication."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from export_monster_morph_profiles import NAMES
from import_captured_class_dependencies import native_effect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def append_records(base, additions, label):
    result = copy.deepcopy(base)
    for key, value in additions.items():
        if key in result and result[key] != value:
            raise ValueError("Conflicting existing " + label + ": " + str(key))
        result[key] = value
    return result


def build(base_directory, native_directory, output_directory):
    """Preserve every base record and bind additions to original export receipts."""
    base_directory = Path(base_directory).resolve()
    native_directory = Path(native_directory).resolve()
    output_directory = Path(output_directory).resolve()
    if output_directory.parent != native_directory:
        raise ValueError("Supplement must retain its original adjacent evidence")
    base = {name: read(base_directory / name) for name in NAMES}
    result = copy.deepcopy(base)
    profiles = read(native_directory / "native-profiles.json")
    seeds = profiles.get("seed_identity", {})
    if (
        profiles.get("schema") != "native-class-morph-profiles-v1"
        or seeds.get("schema") != "native-class-morph-profile-seeds-v1"
        or set(profiles["profiles"]) != {str(n) for n in seeds["profile_ids"]}
        or not profiles.get("native_book_checks", 0)
    ):
        raise ValueError("Missing original morphology profile constructors")
    profile_doc = result[NAMES[0]]
    profile_doc.pop("native_source_package", None)
    profile_doc["profiles"] = append_records(
        profile_doc["profiles"], profiles["profiles"], "morph profile"
    )
    seed_doc = profile_doc["seed_identity"]
    seed_doc["profile_ids"] = sorted(map(int, profile_doc["profiles"]))
    edge_map = {
        (row["effect_reference"], row["profile_id"]): row
        for row in seed_doc["effect_profile_edges"] + seeds["effect_profile_edges"]
    }
    seed_doc["effect_profile_edges"] = [edge_map[key] for key in sorted(edge_map)]
    profile_doc["native_book_checks"] += profiles["native_book_checks"]
    graph_path = native_directory / "morph-typed-closure.jsonl.gz"
    graph = [json.loads(line) for line in gzip.open(graph_path, "rt")]
    if any(row.get("native_missing") for row in graph):
        raise ValueError("Original morphology graph contains a missing dependency")
    effects = {
        str(row["reference"]): native_effect(row)
        for row in graph
        if row["kind"] == "effect"
    }
    closure = result[NAMES[1]]
    closure["effects"] = append_records(closure["effects"], effects, "morph effect")
    closure["effect_reference_closure"] = sorted(map(int, closure["effects"]))
    closure["added_effect_ids"] = sorted(
        set(closure["added_effect_ids"]) | {int(n) for n in effects}
    )
    for kind, field in (
        ("spell", "spell_reference_closure"),
        ("state", "state_reference_closure"),
        ("area", "area_reference_closure"),
    ):
        closure[field] = sorted(
            set(closure[field])
            | {row["reference"] for row in graph if row["kind"] == kind}
        )
    zero = read(native_directory / "morph-level-zero.json")
    for field in ("spells", "casting", "effects"):
        result[NAMES[2]][field] = append_records(
            result[NAMES[2]][field], zero[field], "zero-level " + field
        )
    roots = read(native_directory / "morph-casting-roots.json")
    root_doc = result[NAMES[3]]
    for field in ("fight_properties", "normal_casting_overrides"):
        if root_doc[field] != roots[field]:
            raise ValueError("Original casting global metadata changed: " + field)
    root_doc["roots"] = append_records(
        root_doc["roots"], roots["roots"], "casting root"
    )
    abilities = sorted(
        {
            action["reference"]
            for profile in profile_doc["profiles"].values()
            for action in profile["abilities"]
        }
    )
    root_doc["spell_references"] = abilities
    if closure["spell_reference_closure"] != abilities:
        raise ValueError("Original morphology ability closure is incomplete")
    new_abilities = {
        action["reference"]
        for profile in profiles["profiles"].values()
        for action in profile["abilities"]
    }
    if set(map(int, zero["spells"])) != new_abilities:
        raise ValueError("Missing exact morphology level-zero compatibility roots")
    positive = {str(row["reference"]): row for row in graph if row["kind"] == "spell"}
    for profile in profiles["profiles"].values():
        for action in profile["abilities"]:
            level = min(profile["minimum_level"], action["maximum_level"])
            row = positive[str(action["reference"])]
            if str(level) not in row["root_samples"]:
                raise ValueError("Missing native positive-level casting root evidence")
            if any(str(e) not in effects for e in row["root_samples"][str(level)]):
                raise ValueError("Incomplete native positive-level effect closure")
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, document in result.items():
        (output_directory / name).write_text(
            json.dumps(document, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
    receipt = dict(
        schema="native-npc-morph-preserved-supplement-v1",
        base=str(base_directory),
        base_sha256={name: sha(base_directory / name) for name in NAMES},
        outputs={name: sha(output_directory / name) for name in NAMES},
        added_profile_ids=sorted(map(int, profiles["profiles"])),
        added_ability_ids=sorted(new_abilities),
        original_positive_book_levels={
            key: row["minimum_level"] for key, row in profiles["profiles"].items()
        },
        native_typed_graph_sha256=sha(graph_path),
        publication=False,
    )
    (output_directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = build(args.base, args.native, args.output)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
