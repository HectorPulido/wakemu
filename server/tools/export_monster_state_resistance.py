"""Append original NPC fyW.elk metadata without changing existing class rows."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = "native-class-state-resistance.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(document):
    seeds = document.get("seed_identity", {})
    ids = seeds.get("state_ids", [])
    states = document.get("states", {})
    missing = document.get("missing_state_ids", [])
    enums = document.get("enum_ordinals", {})
    if (
        document.get("schema") != "native-class-state-resistance-v1"
        or seeds.get("schema") != "native-class-state-resistance-seeds-v1"
        or not isinstance(ids, list)
        or not ids
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(ids) != len(set(ids))
        or not isinstance(states, dict)
        or not isinstance(missing, list)
        or any(type(value) is not int or value <= 0 for value in missing)
        or len(missing) != len(set(missing))
        or set(map(int, states)) | set(missing) != set(ids)
        or set(map(int, states)) & set(missing)
        or set(enums) != {"NEGATIF", "NEUTRAL", "POSITIF"}
        or any(type(value) is not int for value in enums.values())
        or set(enums.values()) != {0, 1, 2}
        or document.get("native_level_checks") != 6 * len(states)
    ):
        raise ValueError("Incomplete original resistance domain")
    for row in states.values():
        mode = row.get("native_resistance_mode", {})
        if (
            row.get("native_getter") != "fyW.elk"
            or mode.get("enum_class") != "fza"
            or mode.get("name") not in enums
            or type(mode.get("ordinal")) is not int
            or mode["ordinal"] != enums[mode["name"]]
        ):
            raise ValueError("Invalid original resistance enum")


def merge(base, addition):
    """Extend the proven domain; reject changes to values or attested absences."""
    for document in (base, addition):
        validate(document)
        if document.get("provenance", {}).get("original_inputs_stable") is not True:
            raise ValueError("Unsealed original resistance inputs")
    if base["enum_ordinals"] != addition["enum_ordinals"]:
        raise ValueError("Conflicting native resistance enum")
    for key, row in addition["states"].items():
        if (key in base["states"] and base["states"][key] != row) or int(key) in base[
            "missing_state_ids"
        ]:
            raise ValueError("Existing resistance definition or absence changed")
    if set(addition["missing_state_ids"]) & set(map(int, base["states"])):
        raise ValueError("Existing native state became absent")
    result = deepcopy(base)
    result["states"].update(deepcopy(addition["states"]))
    result["missing_state_ids"] = sorted(
        set(base["missing_state_ids"]) | set(addition["missing_state_ids"])
    )
    result["seed_identity"]["state_ids"] = sorted(
        set(base["seed_identity"]["state_ids"])
        | set(addition["seed_identity"]["state_ids"])
    )
    result["native_level_checks"] = 6 * len(result["states"])
    result.setdefault("npc_dependency_exports", []).append(
        dict(
            seed_identity=deepcopy(addition["seed_identity"]),
            provenance=deepcopy(addition["provenance"]),
        )
    )
    validate(result)
    return result


def assert_preserved(base, candidate):
    """Publication guard for this shared, append-only metadata document."""
    validate(base)
    validate(candidate)
    if (
        candidate["enum_ordinals"] != base["enum_ordinals"]
        or not set(base["seed_identity"]["state_ids"])
        <= set(candidate["seed_identity"]["state_ids"])
        or not set(base["missing_state_ids"]) <= set(candidate["missing_state_ids"])
        or any(
            candidate["states"].get(key) != value
            for key, value in base["states"].items()
        )
        or any(
            candidate.get(key) != value
            for key, value in base.items()
            if key
            not in {
                "states",
                "seed_identity",
                "missing_state_ids",
                "native_level_checks",
                "npc_dependency_exports",
            }
        )
        or any(
            candidate["seed_identity"].get(key) != value
            for key, value in base["seed_identity"].items()
            if key != "state_ids"
        )
        or candidate.get("npc_dependency_exports", [])[
            : len(base.get("npc_dependency_exports", []))
        ]
        != base.get("npc_dependency_exports", [])
    ):
        raise ValueError("NPC metadata changed existing class resistance data")
    additions = candidate.get("npc_dependency_exports", [])[
        len(base.get("npc_dependency_exports", [])) :
    ]
    if not additions or any(
        row.get("provenance", {}).get("original_inputs_stable") is not True
        for row in additions
    ):
        raise ValueError("Missing sealed NPC resistance dependency export")


def export(base, state_ids, bundle, output):
    """Reuse the class exporter against exact native NPC dependency IDs."""
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        raise ValueError("Native resistance work must remain beneath .runtime")
    validate(base)
    ids = sorted(set(state_ids) - set(base["seed_identity"]["state_ids"]))
    if not ids:
        return None
    output.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((bundle / "provenance.json").read_text())
    inputs = {ROOT / "client/lib/wakfu-client.jar": provenance["client_jar_sha256"]}
    inputs.update(
        {
            ROOT / "client/contents/bdata" / name: value
            for name, value in provenance["binary_archives"].items()
        }
    )
    exporter = ROOT / "sniffer/java/ExportNativeClassStateResistance.java"
    before = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    if any(
        before[str(path.relative_to(ROOT))] != expected
        for path, expected in inputs.items()
    ):
        raise ValueError("Installed native inputs differ from monster extraction")
    before[str(exporter.relative_to(ROOT))] = digest(exporter)
    (output / "before.json").write_text(json.dumps(before, sort_keys=True))
    seeds = dict(
        schema="native-class-state-resistance-seeds-v1",
        state_ids=ids,
        scope="Native monster typed state dependency closure",
        source_hashes={
            str((bundle / "inventory.json.gz").relative_to(ROOT)): digest(
                bundle / "inventory.json.gz"
            )
        },
    )
    (output / "seeds.json").write_text(json.dumps(seeds))
    classes = output / "classes"
    classes.mkdir()
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            str(classes),
            str(exporter),
        ],
        cwd=ROOT,
        check=True,
    )
    original = output / "original.json"
    subprocess.run(
        [
            "java",
            "-Xmx1g",
            "-cp",
            str(classes) + ":" + str(ROOT / "client/lib/*"),
            "ExportNativeClassStateResistance",
            str(output / "seeds.json"),
            str(original),
        ],
        cwd=ROOT,
        check=True,
    )
    after = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    after[str(exporter.relative_to(ROOT))] = digest(exporter)
    (output / "after.json").write_text(json.dumps(after, sort_keys=True))
    from import_class_state_resistance import seal

    addition = seal(original, output / "before.json", output / "after.json")
    result = merge(base, addition)
    assert_preserved(base, result)
    (output / CATALOG_PATH).write_text(json.dumps(result, separators=(",", ":")) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "bundle", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    with gzip.open(args.bundle / "inventory.json.gz", "rt") as stream:
        inventory = json.load(stream)
    ids = {
        state
        for mob in inventory["monsters"]
        for state in mob["dependencies"]["state_ids"]
    }
    result = export(json.loads(args.base.read_text()), ids, args.bundle, args.output)
    print(
        json.dumps(
            dict(
                changed=result is not None,
                states=len(result["states"]) if result else None,
            )
        )
    )


if __name__ == "__main__":
    main()
