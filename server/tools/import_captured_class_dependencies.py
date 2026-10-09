"""Publish original scoped captured-class effects; preserve existing native identities."""
import gzip
import argparse
import hashlib
import json
from pathlib import Path
from import_class_summon_dependencies import select

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "server/protocol"
PRIVATE = ROOT / ".runtime/combat-review-20261007/captured-roster"
IDENTITY = (
    "effect_class",
    "parameters",
    "children",
    "variant",
    "minimum_level",
    "maximum_level",
    "criteria",
    "target_masks",
    "native_target_selector",
    "native_effect_flags",
    "native_localization_enabled",
)


def native_effect(row):
    samples = row["samples"]
    parameters = [samples[str(level)]["parameters"] for level in range(1, 246)]
    effect = dict(
        effect_class=row["family"],
        variant=row["native_definition"]["native_fields"]["Qa.bev"],
        minimum_level=row["minimum_level"],
        maximum_level=row["maximum_level"],
        criteria=row["criterion_raw"],
        parameters=row["raw_parameters"],
        children=row["children_ordered"],
        parameter_count=len(row["raw_parameters"]) // 2,
        probabilities=[samples[str(level)]["probability"] for level in range(1, 246)],
        parameter0_by_level=[values[0] if values else None for values in parameters],
        parameters_by_level=parameters,
    )
    effect.update(row["native_metadata"])
    if "native_active_effect" not in effect:
        definition = row["native_definition"]
        fields = definition["native_fields"]
        if definition["native_class"] not in ("eVy", "eVH") or any(
            type(fields.get(key)) is not bool for key in ("eVE.rzi", "eVE.rzj")
        ):
            raise ValueError("Missing original native fKP contract")
        # Installed eVE.fKP returns rzi||rzj; eVy/eVH do not override it.
        effect["native_active_effect"] = fields["eVE.rzi"] or fields["eVE.rzj"]
        effect[
            "native_active_effect_source"
        ] = "original eVE.fKP:rzi||rzj, eVy/eVH inherited; raw native fields"
    effect["native_timing_checks"] = {
        level: samples[level]["timing"] for level in ("0", "1", "200", "32767")
    }
    return effect


def main(publish=False, *, graph_path=None, zero_path=None, domain="captured"):
    if domain not in ("captured", "triggered426", "morph933"):
        raise ValueError("Unapproved native class dependency domain")
    graph = (
        PRIVATE / "captured-typed-closure.jsonl.gz"
        if graph_path is None
        else Path(graph_path)
    )
    prefix = {
        "captured": "native-class-captured",
        "triggered426": "native-class-triggered426",
        "morph933": "native-class-morph933",
    }[domain]
    zero_path = (
        PRIVATE / "captured-level-zero.json"
        if zero_path is None and domain == "captured"
        else zero_path
    )
    before = hashlib.sha256(graph.read_bytes()).hexdigest()
    effects = {}
    spells = {}
    references = {"state": set(), "area": set()}
    state_rows = {}
    with gzip.open(graph, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("native_missing"):
                raise ValueError("Native captured dependency is missing")
            key = str(row["reference"])
            if row["kind"] == "effect":
                effects[key] = native_effect(row)
            elif row["kind"] == "spell":
                spells[key] = row
            elif row["kind"] in references:
                references[row["kind"]].add(key)
                if row["kind"] == "state":
                    state_rows[key] = row
    paths = [
        "spell-effect-trees.json",
        "granted-spell-effect-trees.json",
        "combat-state-definitions.json",
        "native-area-effect-trees.json",
    ]
    existing = {}
    disagreements = []
    for name in paths:
        for key, local in select(DATA / name, "effects", set(effects)).items():
            native = effects[key]
            fields = [
                field for field in IDENTITY if local.get(field) != native.get(field)
            ]
            if fields:
                disagreements.append({"effect": key, "source": name, "fields": fields})
            if (
                "native_active_effect" in local
                and local["native_active_effect"] != native["native_active_effect"]
            ):
                raise ValueError(f"Captured native active-effect mismatch {key}")
            existing.setdefault(
                key, {**local, "native_active_effect": native["native_active_effect"]}
            )
    if disagreements:
        (PRIVATE / "captured-import-conflicts.json").write_text(
            json.dumps(disagreements, indent=2)
        )
        raise ValueError(
            f"Native captured identity conflicts: {len(disagreements)}; see captured-import-conflicts.json"
        )
    for kind, name, section in [
        ("state", "combat-state-definitions.json", "states"),
        ("area", "native-effect-areas.json", "areas"),
    ]:
        found = select(DATA / name, section, references[kind])
        if set(found) != references[kind]:
            raise ValueError(f"Missing captured {kind} definitions")
        if kind == "state":
            import sys

            sys.path.insert(0, str(ROOT / "server"))
            from wakfu_server.combat_definitions import state_profile

            source_catalog = {"states": found, "effects": effects}
            for key, native in state_rows.items():
                for level, sample in native["level_samples"].items():
                    if int(level) < 0:
                        continue
                    actual = state_profile(source_catalog, int(key), int(level))
                    if any(
                        actual[field] != sample[native_field]
                        for field, native_field in (
                            ("level", "selected_level"),
                            ("effects", "roots"),
                            ("duration", "duration"),
                            ("realtime_duration", "realtime_duration"),
                            ("skip_turn_timer", "skip_turn_timer"),
                        )
                    ):
                        raise ValueError(
                            f"Original captured state profile mismatch {key}/{level}"
                        )
    casting = select(DATA / "native-spell-casting.json", "spells", set(spells))
    if set(casting) != set(spells):
        raise ValueError("Missing original captured casting table")
    zero = json.loads(Path(zero_path).read_text()) if zero_path is not None else None
    if zero is not None and set(zero["spells"]) != set(spells):
        raise ValueError("Incomplete original captured level-zero roots")
    for key, row in spells.items():
        for level in range(1, len(casting[key]["levels"]) + 1):
            if casting[key]["levels"][level - 1][2] != row["root_samples"][str(level)]:
                raise ValueError(f"Captured casting root mismatch {key}/{level}")
        if zero is not None and zero["spells"][key][2] != row["root_samples"]["0"]:
            raise ValueError(f"Captured zero root mismatch {key}")
    if before != hashlib.sha256(graph.read_bytes()).hexdigest():
        raise ValueError("Captured graph changed during import")
    output = dict(
        schema=prefix + "-effect-closure-v1",
        class_id={"captured": 2, "triggered426": None, "morph933": 11}[domain],
        class_dependency_domain=domain,
        original_zero_casting_verified=zero is not None,
        source_graph_sha256=before,
        effects={key: existing.get(key, value) for key, value in effects.items()},
        added_effect_ids=sorted(int(key) for key in effects if key not in existing),
        effect_reference_closure=sorted(map(int, effects)),
        spell_reference_closure=sorted(map(int, spells)),
        state_reference_closure=sorted(map(int, references["state"])),
        area_reference_closure=sorted(map(int, references["area"])),
    )
    if publish:
        (DATA / (prefix + "-effect-closure.json")).write_bytes(
            json.dumps(output, separators=(",", ":")).encode()
        )
        if zero is not None:
            (DATA / (prefix + "-level-zero.json")).write_bytes(
                json.dumps(zero, separators=(",", ":")).encode()
            )
    print(
        json.dumps(
            {
                "effects": len(effects),
                "added_effects": len(output["added_effect_ids"]),
                "spells": len(spells),
                "states": len(references["state"]),
                "areas": len(references["area"]),
                "publish": publish,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--zero", type=Path)
    parser.add_argument(
        "--domain", choices=("captured", "triggered426", "morph933"), default="captured"
    )
    args = parser.parse_args()
    main(args.publish, graph_path=args.graph, zero_path=args.zero, domain=args.domain)
