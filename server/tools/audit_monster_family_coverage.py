"""Cheap offline family coverage estimate, not an execution certification."""
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMBAT = ROOT / "server/wakfu_server/combat"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_assignment(path, name):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing literal assignment: {name}")


def supported_families(registry, setters):
    """Read actual handler registrations without importing DB-backed modules."""
    constants = {
        "DAMAGE_FAMILIES": literal_assignment(
            COMBAT / "combat_damage_healing.py", "DAMAGE_FAMILIES"
        ),
        "HEAL_ELEMENTS": literal_assignment(
            COMBAT / "combat_damage_healing.py", "HEAL_ELEMENTS"
        ),
        "FAMILIES": literal_assignment(COMBAT / "combat_displacement.py", "FAMILIES"),
        "SET_CURRENT_FAMILIES": list(map(int, setters["effects"])),
    }
    families = set(map(int, registry["effects"]))
    assert {row["runner"] for row in registry["effects"].values()} <= {
        "eWQ",
        "eWR",
        "eXE",
        "eYO",
    }
    tree = ast.parse((COMBAT / "combat_effect_runtime.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "handlers" for t in node.targets
        ):
            if isinstance(node.value, ast.DictComp):
                families.update(constants[node.value.generators[0].iter.id])
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.value, ast.Name) and node.value.id == "handlers":
                if (
                    isinstance(node.slice, ast.Constant)
                    and type(node.slice.value) is int
                ):
                    families.add(node.slice.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "handlers"
                and node.func.attr == "update"
            ):
                arg = node.args[0]
                if isinstance(arg, ast.Dict):
                    families.update(ast.literal_eval(key) for key in arg.keys)
                elif isinstance(arg, ast.DictComp):
                    iterable = arg.generators[0].iter
                    families.update(
                        constants[iterable.id]
                        if isinstance(iterable, ast.Name)
                        else ast.literal_eval(iterable)
                    )
                else:
                    raise ValueError("Unrecognized handler registration")
    # Branches executed directly by EffectDispatcher, before handler lookup.
    families.update(
        (
            865,
            1076,
            1080,
            349,
            345,
            949,
            330,
            341,
            352,
            844,
            910,
            912,
            913,
            999,
            1020,
            1047,
            1103,
        )
    )
    return families


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--setters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-level",
        type=int,
        default=24,
        help="Inclusive maximum level (default: 24)",
    )
    parser.add_argument(
        "--all", action="store_true", help="Include every native monster reference"
    )
    parser.add_argument(
        "--reuse",
        type=Path,
        help="Reuse previously classified references with identical inputs",
    )
    args = parser.parse_args()
    if args.max_level < 1:
        parser.error("--max-level must be positive")
    with gzip.open(args.inventory, "rt") as stream:
        inventory = json.load(stream)
    registry = json.loads(args.registry.read_text())
    assert registry["client_jar_sha256"] == inventory["provenance"]["client_jar_sha256"]
    supported = supported_families(registry, json.loads(args.setters.read_text()))
    sources = {
        str(path.relative_to(ROOT))
        if path.is_relative_to(ROOT)
        else str(path): digest(path)
        for path in [
            args.inventory.resolve(),
            args.registry.resolve(),
            args.setters.resolve(),
            COMBAT / "combat_effect_runtime.py",
            COMBAT / "combat_effect_dispatch.py",
        ]
    }
    cached = {}
    if args.reuse:
        previous = json.loads(args.reuse.read_text())
        if previous["sources"] != sources or previous["supported_families"] != sorted(
            supported
        ):
            raise ValueError(
                "Cannot reuse classifications: source evidence or supported families changed"
            )
        cached = {row["ref"]: row for row in previous["monsters"]}
        if len(cached) != len(previous["monsters"]):
            raise ValueError("Duplicate cached monster references")
    rows = []
    reused = 0
    for mob in inventory["monsters"]:
        if not args.all and not 1 <= mob["min_level"] <= args.max_level:
            continue
        if mob["ref"] in cached:
            rows.append(cached[mob["ref"]])
            reused += 1
            continue
        missing = sorted(set(mob["dependencies"]["effect_families"]) - supported)
        data_gaps = bool(
            mob["dependencies"]["missing_definitions"]
            or mob["missing_casting_tables"]
            or mob["missing_casting_root_metadata"]
            or not mob["actor_profile_present"]
        )
        status = (
            "no_owned_spells"
            if not mob["abilities"]
            else "data_gap"
            if data_gaps
            else "covered"
            if not missing
            else "almost_one_family"
            if len(missing) == 1
            else "multiple_missing_families"
        )
        rows.append(
            dict(
                ref=mob["ref"],
                name=mob["name"],
                min_level=mob["min_level"],
                max_level=mob["max_level"],
                status=status,
                missing_families=missing,
                data_gaps=data_gaps,
                spell_ids=[a["spell_id"] for a in mob["abilities"]],
            )
        )

    def summarize(cohort):
        counts = Counter(row["status"] for row in cohort)
        return dict(
            total=len(cohort),
            counts=dict(counts),
            percentages={
                key: round(value * 100 / len(cohort), 2) if cohort else 0
                for key, value in counts.items()
            },
        )

    result = dict(
        method="Static all-reachable-level family coverage; available handlers, not executed NPCs",
        limitations=[
            "Not a runtime, AI, condition, targeting or native-parameter validation",
            "Includes event, pet, summon and NPC references; no encounter-only filter",
            "Empty spellbooks are not counted as functional",
            "Closure includes native dependencies outside the selected low-level range",
            "Conditional handlers are counted as available; NPC context wiring is untested",
            "Extracted sources have not been published to runtime catalogs",
        ],
        sources=sources,
        reuse=dict(
            report=str(args.reuse) if args.reuse else None,
            reused_references=reused,
            newly_classified_references=len(rows) - reused,
        ),
        supported_families=sorted(supported),
        maximum_level_inclusive=None if args.all else args.max_level,
        intersects_level_range=summarize(rows),
        entirely_in_level_range=summarize(
            [r for r in rows if args.all or r["max_level"] <= args.max_level]
        ),
        entirely_in_level_range_with_owned_spells=summarize(
            [
                r
                for r in rows
                if (args.all or r["max_level"] <= args.max_level) and r["spell_ids"]
            ]
        ),
        with_owned_spells=summarize([r for r in rows if r["spell_ids"]]),
        missing_family_monster_counts=dict(
            Counter(
                f for r in rows if r["spell_ids"] for f in r["missing_families"]
            ).most_common()
        ),
        monsters=rows,
    )
    # Preserve the original report keys for existing default-level consumers.
    if args.max_level == 24 and not args.all:
        result.update(
            intersects_under_25=result["intersects_level_range"],
            entirely_under_25=result["entirely_in_level_range"],
            entirely_under_25_with_owned_spells=result[
                "entirely_in_level_range_with_owned_spells"
            ],
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "intersects_level_range",
                    "entirely_in_level_range",
                    "entirely_in_level_range_with_owned_spells",
                    "with_owned_spells",
                    "missing_family_monster_counts",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
