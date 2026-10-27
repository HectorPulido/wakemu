"""Append exact native NPC eYk metadata while preserving all class definitions."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from tools.export_monster_state_resistance import ROOT, digest

CATALOG_PATH = "native-class-cell-group-metadata.json"


def required_effect_ids(active_effect_ids, prepared_graph):
    """Include newly imported native children absent from active DB records."""
    effects = prepared_graph.get("effects")
    if not isinstance(effects, dict):
        raise ValueError("Missing prepared native effect graph")
    result = set(active_effect_ids)
    for key, effect in effects.items():
        if not isinstance(effect, dict):
            raise ValueError("Invalid prepared native effect definition")
        if effect.get("effect_class") == 349:
            if str(int(key)) != key or int(key) <= 0:
                raise ValueError("Invalid prepared native cell-group reference")
            result.add(int(key))
    return sorted(result)


def validate(document):
    if document.get("schema") != "native-eYk-class-cell-group-v1" or not isinstance(
        document.get("effects"), dict
    ):
        raise ValueError("Missing original native cell-group schema")
    for key, row in document["effects"].items():
        if (
            str(int(key)) != key
            or int(key) <= 0
            or not isinstance(row, dict)
            or type(row.get("criterion_present")) is not bool
            or not isinstance(row.get("area_class"), str)
            or not isinstance(row.get("raw_parameters"), list)
            or any(type(value) not in (int, float) for value in row["raw_parameters"])
        ):
            raise ValueError("Invalid original native cell-group definition")


def assert_preserved(base, candidate):
    for document in (base, candidate):
        validate(document)
    if (
        any(
            candidate.get(key) != value
            for key, value in base.items()
            if key not in {"effects", "npc_dependency_exports"}
        )
        or any(
            candidate["effects"].get(key) != value
            for key, value in base["effects"].items()
        )
        or candidate.get("npc_dependency_exports", [])[
            : len(base.get("npc_dependency_exports", []))
        ]
        != base.get("npc_dependency_exports", [])
    ):
        raise ValueError("NPC import changed original class cell-group metadata")
    additions = candidate.get("npc_dependency_exports", [])[
        len(base.get("npc_dependency_exports", [])) :
    ]
    if not additions or any(
        row.get("original_inputs_stable") is not True for row in additions
    ):
        raise ValueError("Missing original NPC cell-group provenance")
    new_ids = set(candidate["effects"]) - set(base["effects"])
    if new_ids != {str(ref) for row in additions for ref in row["effect_ids"]}:
        raise ValueError("Incomplete original NPC cell-group dependency domain")


def export(base, effect_ids, bundle, output):
    validate(base)
    ids = sorted(set(effect_ids) - set(map(int, base["effects"])))
    if not ids:
        return None
    output, bundle = Path(output).resolve(), Path(bundle).resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        raise ValueError("Native cell-group work must remain beneath .runtime")
    output.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((bundle / "provenance.json").read_text())
    expected = {ROOT / "client/lib/wakfu-client.jar": provenance["client_jar_sha256"]}
    expected.update(
        {
            ROOT / "client/contents/bdata" / name: value
            for name, value in provenance["binary_archives"].items()
        }
    )
    before = {str(path.relative_to(ROOT)): digest(path) for path in expected}
    if any(
        before[str(path.relative_to(ROOT))] != value for path, value in expected.items()
    ):
        raise ValueError("Original NPC extraction inputs changed")
    source = ROOT / "sniffer/java/ExportMonsterCellGroupMetadata.java"
    before[str(source.relative_to(ROOT))] = digest(source)
    (output / "effect-ids.txt").write_text("\n".join(map(str, ids)) + "\n")
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
            str(source),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "java",
            "-Xmx1g",
            "-cp",
            str(classes) + ":" + str(ROOT / "client/lib/*"),
            "ExportMonsterCellGroupMetadata",
            str(output / "effect-ids.txt"),
            str(output / "original.json"),
        ],
        cwd=ROOT,
        check=True,
    )
    after = {str(path.relative_to(ROOT)): digest(path) for path in expected}
    after[str(source.relative_to(ROOT))] = digest(source)
    if before != after:
        raise ValueError("Original cell-group export inputs changed during execution")
    rows = json.loads((output / "original.json").read_text())
    if set(map(int, rows)) != set(ids):
        raise ValueError("Incomplete original cell-group export")
    result = deepcopy(base)
    result["effects"].update(rows)
    result.setdefault("npc_dependency_exports", []).append(
        dict(
            original_inputs_stable=True,
            original_input_hashes=before,
            original_export_sha256=digest(output / "original.json"),
            effect_ids=ids,
        )
    )
    assert_preserved(base, result)
    (output / CATALOG_PATH).write_text(json.dumps(result, separators=(",", ":")) + "\n")
    return result
