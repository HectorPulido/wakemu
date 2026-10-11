"""Extract installed monster combat sources offline; never publish runtime catalogs.

The output is an evidence bundle, not an implementation/coverage certificate.
All monsters are exported. Names select the initial review cohort only.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path
import subprocess
import zipfile

from convert_spell_effect_trees import convert as convert_spells, read_effects
from convert_combat_states import convert as convert_states

ROOT = Path(__file__).resolve().parents[2]
EXPORTERS = (
    "ExportMonsterCombatData",
    "ExportMonsterEncyclopedia",
    "ExportActorCharacteristics",
    "ExportNativeSpellCasting",
    "ExportNativeSpellLimits",
    "ExportSpellEffectTrees",
    "ExportGrantedSpellEffectTrees",
    "ExportCombatStates",
    "ExportNativeCastingRoots",
    "ProbeNativeCastingCategories",
    "ExportEffectAreaTrees",
    "ExportNativeEffectAreas",
    "ExportNativeSpellLevelZero",
    "ExportEffectReferenceTrees",
)
LIMITATIONS = [
    "Extracted data does not certify executable casts or complete monster mechanics.",
    "Full effect parameter samples cover levels 1..200; separate native level-zero casting/effect evidence and raw curves are retained. Levels >200 require additional parameter sampling.",
    "State 304/321 and spell-grant 649 parameter links are conservative candidates across all sampled levels, not unconditional execution.",
    "Other dynamic references, summon/area creation, scripts and server-only mechanics require semantic reconstruction; raw definitions are retained.",
    "Native combat AI scripts and official decision policies are not reconstructed by this bundle.",
    "Runtime authority remains the pinned PostgreSQL release; these files are offline import/review artifacts only.",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_bytes())


def write(path, value):
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(raw, mtime=0))
    else:
        path.write_bytes(raw)


def translations():
    with zipfile.ZipFile(ROOT / "client/contents/i18n/i18n_es.jar") as archive:
        text = archive.read("texts_es.properties").decode("utf-8")
    return dict(
        line.partition("=")[::2]
        for line in text.splitlines()
        if "=" in line and not line.startswith("#")
    )


def unique(rows, field):
    result = {}
    for row in rows:
        key = str(row[field])
        if key in result:
            raise ValueError("Duplicate " + field + ": " + key)
        result[key] = row
    return result


def merge_effects(*tables):
    result = {}
    for table in tables:
        for key, value in table.items():
            if key in result and result[key] != value:
                raise ValueError("Conflicting native effect " + key)
            result[key] = value
    return result


def stable_effect(row):
    """OY.d is a process-local counter, not an original effect reference.

    OY's constructor assigns bbP=bbO++. Keep raw exports, but compare HMI
    definitions independently of that allocation order when supplementing.
    """
    value = dict(row)
    if "native_hmi_actions" in value:
        value["native_hmi_actions"] = {
            key: [
                dict(
                    action,
                    id="process-local",
                    native=re.sub(
                        r"HMIAction\{m_id=\d+",
                        "HMIAction{m_id=process-local",
                        action["native"],
                    ),
                )
                for action in actions
            ]
            for key, actions in value["native_hmi_actions"].items()
        }
    return value


def effect_fingerprint(row):
    return hashlib.sha256(
        json.dumps(stable_effect(row), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def dependency_index(table):
    """Release full level samples before loading another complete catalog.

    The original documents remain untouched. Fingerprints keep semantic
    overlap checks strict while the traversal retains only dependency data.
    """
    result = {}
    if "spells" in table:
        result["spells"] = {
            key: dict(
                levels=[
                    [0, 0, sorted({ref for level in row["levels"] for ref in level[2]})]
                ],
                level_zero_roots=row.get("level_zero_roots", []),
            )
            for key, row in table["spells"].items()
        }
    if "states" in table:
        result["states"] = {
            key: dict(
                effect_ids=sorted(
                    set(row.get("effect_ids", []))
                    | {
                        ref
                        for level in row.get("levels", [])
                        for ref in level["effects"]
                    }
                )
            )
            for key, row in table["states"].items()
        }
    result["effects"] = {
        key: dict(
            effect_class=row["effect_class"],
            children=row.get("children", []),
            source_fingerprint=effect_fingerprint(row),
            parameters_by_level=[
                list(values)
                for values in sorted(
                    {tuple(values) for values in row.get("parameters_by_level", [])}
                )
            ]
            if row["effect_class"] in (304, 321, 649)
            else [],
        )
        for key, row in table.get("effects", {}).items()
    }
    return result


def compress_source(path):
    """Compress a complete source file without decoding its large JSON graph."""
    with path.open("rb") as source, path.with_suffix(".json.gz").open("wb") as target:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=target, mtime=0
        ) as compressed:
            shutil.copyfileobj(source, compressed, length=1024 * 1024)
    path.unlink()


def supplement_effects(base, extra, known):
    result = dict(base)
    for key, row in extra.items():
        previous = base.get(key, known.get(key))
        if previous is not None:
            equivalent = (
                previous["source_fingerprint"] == effect_fingerprint(row)
                if "source_fingerprint" in previous
                else previous == row or stable_effect(previous) == stable_effect(row)
            )
            if not equivalent:
                raise ValueError("Conflicting supplemental native effect " + key)
        else:
            result[key] = row
    return result


def parameter_candidates(effect, index, extra=None):
    """Use native evaluated values, never reinterpret raw curve arithmetic."""
    samples = list(effect.get("parameters_by_level", []))
    if extra is not None:
        samples.append(extra["parameters"])
    return sorted(
        {
            values[index]
            for values in samples
            if len(values) > index and type(values[index]) is int
        }
    )


def dependency_closure(
    spell_ids, state_ids, spells, states, effects, zero_effects=None
):
    pending = [("spell", str(key)) for key in spell_ids]
    pending += [("state", str(key)) for key in state_ids]
    seen = {"spell": set(), "state": set(), "effect": set()}
    missing = set()
    links = set()
    while pending:
        kind, key = pending.pop()
        if key in seen[kind]:
            continue
        seen[kind].add(key)
        table = {"spell": spells, "state": states, "effect": effects}[kind]
        row = table.get(key)
        if row is None:
            missing.add(kind + ":" + key)
            continue
        if kind == "spell":
            roots = {ref for level in row.get("levels", []) for ref in level[2]}
            roots.update(row.get("level_zero_roots", []))
            pending += [("effect", str(ref)) for ref in roots]
        elif kind == "state":
            roots = set(row.get("effect_ids", []))
            roots.update(
                ref for level in row.get("levels", []) for ref in level["effects"]
            )
            pending += [("effect", str(ref)) for ref in roots]
        else:
            pending += [("effect", str(ref)) for ref in row.get("children", [])]
            family = row["effect_class"]
            target = (
                "state" if family in (304, 321) else "spell" if family == 649 else None
            )
            if target:
                for ref in parameter_candidates(
                    row, 2 if family == 649 else 0, (zero_effects or {}).get(key)
                ):
                    links.add((int(key), family, target, ref))
                    pending.append((target, str(ref)))
    return dict(
        spell_ids=sorted(map(int, seen["spell"])),
        state_ids=sorted(map(int, seen["state"])),
        effect_ids=sorted(map(int, seen["effect"])),
        effect_families=sorted(
            {effects[key]["effect_class"] for key in seen["effect"] if key in effects}
        ),
        missing_definitions=sorted(missing),
        candidate_links=[
            dict(effect_id=e, family=f, target_kind=k, reference=r)
            for e, f, k, r in sorted(links)
        ],
    )


def initial_states(monster):
    triples = monster["initial_state_triples"]
    if len(triples) % 3:
        raise ValueError("Malformed initial-state triples: " + str(monster["ref"]))
    return [
        dict(
            state_id=triples[i],
            level_parameter=triples[i + 1],
            native_flag=triples[i + 2],
        )
        for i in range(0, len(triples), 3)
    ]


def build_inventory(
    monsters, casting, limits, trees, states, roots, actors, names, zero=None
):
    unique(monsters, "ref")
    effects = merge_effects(trees["effects"], states["effects"])
    rows = []
    for monster in sorted(monsters, key=lambda row: row["ref"]):
        abilities = monster["native_abilities"]
        innate = initial_states(monster)
        closure = dependency_closure(
            [a["spell_id"] for a in abilities],
            [s["state_id"] for s in innate],
            trees["spells"],
            states["states"],
            effects,
            (zero or {}).get("effects"),
        )
        missing_casting = [
            a["spell_id"]
            for a in abilities
            if str(a["spell_id"]) not in casting["spells"]
        ]
        root_ids = sorted(
            {
                ref
                for a in abilities
                for level in casting["spells"]
                .get(str(a["spell_id"]), {})
                .get("levels", [])
                for ref in level[2]
            }
        )
        root_ids = sorted(
            set(root_ids)
            | {
                ref
                for a in abilities
                for ref in trees["spells"]
                .get(str(a["spell_id"]), {})
                .get("level_zero_roots", [])
            }
        )
        missing_roots = [ref for ref in root_ids if str(ref) not in roots["roots"]]
        rows.append(
            dict(
                ref=monster["ref"],
                name=names.get("content.7." + str(monster["ref"])),
                raw_native=monster.get("raw_native", {}),
                family_id=monster["family_id"],
                min_level=monster["min_level"],
                max_level=monster["max_level"],
                abilities=[
                    dict(
                        a,
                        name=names.get("content.3." + str(a["spell_id"])),
                        effective_level_range=[
                            monster["min_level"],
                            monster["max_level"],
                        ]
                        if a["level_parameter"] == -1
                        else [a["level_parameter"]] * 2,
                        casting_present=str(a["spell_id"]) in casting["spells"],
                        usage_limits_present=str(a["spell_id"]) in limits["spells"],
                    )
                    for a in abilities
                ],
                initial_states=innate,
                fight_properties=monster["fight_properties"],
                actor_profile_present=str(monster["ref"]) in actors["npc_profiles"],
                casting_root_ids=root_ids,
                missing_casting_tables=missing_casting,
                missing_casting_root_metadata=missing_roots,
                dependencies=closure,
                runtime_status="not_validated",
            )
        )
    families = Counter(
        f for row in rows for f in row["dependencies"]["effect_families"]
    )
    return dict(
        schema="monster-combat-inventory-v1",
        limitations=LIMITATIONS,
        summary=dict(
            monsters=len(rows),
            owned_spell_ids=len(
                {a["spell_id"] for row in rows for a in row["abilities"]}
            ),
            zero_level_ability_records=sum(
                a["level_parameter"] == 0 for row in rows for a in row["abilities"]
            ),
            ability_records_above_sampled_effect_levels=sum(
                a["effective_level_range"][1] > 200
                for row in rows
                for a in row["abilities"]
            ),
            monsters_with_abilities=sum(bool(row["abilities"]) for row in rows),
            monsters_with_initial_states=sum(
                bool(row["initial_states"]) for row in rows
            ),
            monsters_with_dependency_gaps=sum(
                bool(row["dependencies"]["missing_definitions"]) for row in rows
            ),
            monsters_missing_casting=sum(
                bool(row["missing_casting_tables"]) for row in rows
            ),
            monsters_missing_root_metadata=sum(
                bool(row["missing_casting_root_metadata"]) for row in rows
            ),
        ),
        effect_family_monster_counts=dict(sorted(families.items())),
        monsters=rows,
    )


def run_java(output, name, *args):
    subprocess.run(
        [
            "java",
            "-Xmx3g",
            "-cp",
            str(output / "classes") + ":client/lib/*",
            name,
            *map(str, args),
        ],
        cwd=ROOT,
        check=True,
    )


def export_level_zero(output):
    """Keep native level zero separate so positive-level indices never shift."""
    run_java(
        output,
        "ExportNativeSpellLevelZero",
        output / "spell-refs.txt",
        output / "level-zero.json",
    )
    zero = read(output / "level-zero.json")
    refs = sorted(map(int, zero["effects"]))
    (output / "zero-effect-refs.txt").write_text("\n".join(map(str, refs)) + "\n")
    run_java(
        output,
        "ExportEffectReferenceTrees",
        output / "zero-effect-refs.txt",
        output / "zero-effects.tsv",
    )
    states = dependency_index(read(output / "states.json.gz"))
    area_effects = dependency_index(read(output / "area-effects.json.gz"))["effects"]
    trees = read(output / "trees.json.gz")
    extra = read_effects(output / "zero-effects.tsv")
    write(output / "zero-effect-definitions.json.gz", dict(effects=extra))
    trees["effects"] = supplement_effects(
        trees["effects"], extra, merge_effects(states["effects"], area_effects)
    )
    for key, row in zero["spells"].items():
        trees["spells"][key]["level_zero_roots"] = row[2]
    write(output / "trees.json.gz", trees)
    trees = dependency_index(trees)
    monsters = read(output / "monsters.json.gz")["monsters"]
    casting = read(output / "casting.json.gz")
    combined = merge_effects(trees["effects"], states["effects"], area_effects)
    owned = {a["spell_id"] for monster in monsters for a in monster["native_abilities"]}
    closure = dependency_closure(
        owned,
        [s["state_id"] for m in monsters for s in initial_states(m)],
        trees["spells"],
        states["states"],
        combined,
        zero["effects"],
    )
    added = set(closure["spell_ids"]) & set(map(int, casting["spells"])) - set(
        map(int, trees["spells"])
    )
    if added:
        refs = set(map(int, trees["spells"])) | added
        (output / "spell-refs.txt").write_text("\n".join(map(str, sorted(refs))) + "\n")
        run_java(
            output,
            "ExportGrantedSpellEffectTrees",
            output / "spell-refs.txt",
            output / "spells",
        )
        write(
            output / "trees.json.gz",
            convert_spells(output / "spells", output / "trees.json"),
        )
        (output / "trees.json").unlink()
        export_level_zero(output)
        return
    write(output / "level-zero.json.gz", zero)
    (output / "level-zero.json").unlink()
    roots = set(map(int, read(output / "roots.json.gz")["roots"]))
    roots.update(ref for row in zero["spells"].values() for ref in row[2])
    (output / "root-refs.txt").write_text("\n".join(map(str, sorted(roots))) + "\n")
    run_java(
        output,
        "ExportNativeCastingRoots",
        output / "root-refs.txt",
        output / "roots.json",
    )
    write(output / "roots.json.gz", read(output / "roots.json"))
    (output / "roots.json").unlink()


def extract(output):
    output.mkdir(parents=True, exist_ok=False)
    (output / "classes").mkdir()
    sources = [ROOT / "sniffer/java" / (name + ".java") for name in EXPORTERS]
    provenance = dict(
        client_jar_sha256=digest(ROOT / "client/lib/wakfu-client.jar"),
        binary_archives={
            p.name: digest(p)
            for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        },
        localization_sha256=digest(ROOT / "client/contents/i18n/i18n_es.jar"),
        exporter_sources={p.name: digest(p) for p in sources},
    )
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            "client/lib/*",
            "-d",
            str(output / "classes"),
            *map(str, sources),
        ],
        cwd=ROOT,
        check=True,
    )
    for name, filename in (
        ("ExportMonsterCombatData", "monsters.json"),
        ("ExportActorCharacteristics", "actors.json"),
        ("ExportNativeSpellCasting", "casting.json"),
        ("ExportNativeSpellLimits", "limits.json"),
        ("ExportNativeEffectAreas", "areas.json"),
    ):
        run_java(output, name, output / filename)
    monsters = read(output / "monsters.json")["monsters"]
    casting = read(output / "casting.json")
    owned = {a["spell_id"] for m in monsters for a in m["native_abilities"]}
    missing = sorted(owned - set(map(int, casting["spells"])))
    if missing:
        raise ValueError(
            "Owned abilities without native casting definitions: " + str(missing)
        )
    run_java(output, "ExportCombatStates", output / "states")
    states = dependency_index(convert_states(output / "states", output / "states.json"))
    run_java(output, "ExportEffectAreaTrees", output / "area-effects.tsv")
    area_table = dict(effects=read_effects(output / "area-effects.tsv"))
    write(output / "area-effects.json", area_table)
    area_effects = dependency_index(area_table)["effects"]
    del area_table
    refs = set(owned)
    # Export owned spells, then native649 candidates from reachable states/trees.
    while True:
        (output / "spell-refs.txt").write_text("\n".join(map(str, sorted(refs))) + "\n")
        run_java(
            output,
            "ExportGrantedSpellEffectTrees",
            output / "spell-refs.txt",
            output / "spells",
        )
        trees = dependency_index(
            convert_spells(output / "spells", output / "trees.json")
        )
        combined = merge_effects(trees["effects"], states["effects"], area_effects)
        closure = dependency_closure(
            owned,
            [s["state_id"] for m in monsters for s in initial_states(m)],
            trees["spells"],
            states["states"],
            combined,
        )
        added = set(closure["spell_ids"]) & set(map(int, casting["spells"])) - refs
        if not added:
            break
        refs.update(added)
    root_ids = sorted(
        {
            root
            for ref in refs
            for level in casting["spells"][str(ref)]["levels"]
            for root in level[2]
        }
    )
    (output / "root-refs.txt").write_text("\n".join(map(str, root_ids)) + "\n")
    run_java(
        output,
        "ExportNativeCastingRoots",
        output / "root-refs.txt",
        output / "roots.json",
    )
    # Include area definitions/effects in the bundle even where semantic edges remain unknown.
    for filename in (
        "monsters",
        "actors",
        "casting",
        "limits",
        "states",
        "trees",
        "roots",
        "areas",
        "area-effects",
    ):
        path = output / (filename + ".json")
        compress_source(path)
    export_level_zero(output)
    write(output / "translations.json.gz", translations())
    provenance["bundle_documents"] = {
        p.name: digest(p) for p in sorted(output.glob("*.json.gz"))
    }
    provenance["python_sources"] = {
        p.name: digest(p)
        for p in [
            Path(__file__),
            ROOT / "server/tools/convert_spell_effect_trees.py",
            ROOT / "server/tools/convert_combat_states.py",
        ]
    }
    write(output / "provenance.json", provenance)


def report(output, inventory, focus_names):
    focus = [
        row
        for row in inventory["monsters"]
        if row["min_level"] <= 15
        and any(
            term.casefold() in (row["name"] or "").casefold() for term in focus_names
        )
    ]
    write(
        output / "focus.json",
        dict(summary=inventory["summary"], monsters=focus, limitations=LIMITATIONS),
    )
    casting = read(output / "casting.json.gz")["spells"]
    trees = read(output / "trees.json.gz")
    lines = [
        "# Monster combat extraction",
        "",
        "Offline installed-client evidence. No runtime catalogs were published.",
        "",
        "## Complete inventory",
        "",
        *[f"- {key}: {value}" for key, value in inventory["summary"].items()],
        "",
        "## Initial low-level review cohort",
        "",
        "| Monster | Ref | Levels | Owned spells | Initial states | Dependency gaps |",
        "|---|---:|---|---|---|---|",
    ]
    for row in focus:
        lines.append(
            f"| {row['name']} | {row['ref']} | {row['min_level']}–{row['max_level']} | "
            + ", ".join(
                f"{a['spell_id']} ({a['name'] or 'unnamed'})" for a in row["abilities"]
            )
            + f" | {row['initial_states']} | {row['dependencies']['missing_definitions']} |"
        )
    lines += [
        "",
        "## Owned ability samples at the minimum actor level",
        "",
        "Costs are native AP/MP/WP. A zero cost is retained. Parameters below are native family arguments, not inferred damage.",
        "",
    ]
    for row in focus:
        lines += [f"### {row['name']} ({row['ref']})", ""]
        for ability in row["abilities"]:
            key = str(ability["spell_id"])
            level = (
                row["min_level"]
                if ability["level_parameter"] == -1
                else ability["level_parameter"]
            )
            table = casting.get(key)
            if not table or not 1 <= level <= len(table["levels"]):
                lines += [f"- Spell {key}, level {level}: no positive-level sample."]
                continue
            selected = table["levels"][level - 1]
            lines += [
                f"- **{ability['name'] or key} ({key}), level {level}**: range {selected[:2]}, costs {table['costs'][level-1]}, "
                f"LOS={table['line_of_sight']}, linear={table['linear']}, roots={selected[2]}, conditional tables={len(table['conditional'])}."
            ]
            for root in selected[2]:
                effect = trees["effects"].get(str(root))
                if effect:
                    samples = effect.get("parameters_by_level", [])
                    params = (
                        samples[level - 1]
                        if 1 <= level <= len(samples)
                        else "not sampled"
                    )
                    lines += [
                        f"  - Root {root}: family {effect['effect_class']}, parameters {params}, "
                        f"children {effect['children']}, flags {effect.get('native_effect_flags')}, "
                        f"criteria `{effect['criteria'].replace(chr(10), ' ')}`."
                    ]
        lines += [""]
    lines += ["## Limits", "", *["- " + value for value in LIMITATIONS], ""]
    (output / "README.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Create a new offline bundle directly from installed client sources",
    )
    parser.add_argument(
        "--focus-name",
        action="append",
        help="Review name substring, repeated; never restricts full extraction",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.extract:
        if (ROOT / ".runtime").resolve() not in output.parents:
            parser.error("Fresh source exports must be beneath repository .runtime")
        extract(output)

    def bundle(name):
        return read(output / (name + ".json.gz"))

    provenance = read(output / "provenance.json")
    for name, checksum in provenance["bundle_documents"].items():
        if digest(output / name) != checksum:
            raise ValueError("Bundle checksum mismatch: " + name)
    states = dependency_index(bundle("states"))
    trees = dependency_index(bundle("trees"))
    trees["effects"] = merge_effects(
        trees["effects"], dependency_index(bundle("area-effects"))["effects"]
    )
    actors = dict(npc_profiles=dict.fromkeys(bundle("actors")["npc_profiles"]))
    if "translations.json.gz" not in provenance["bundle_documents"]:
        raise ValueError("Incomplete source bundle: missing pinned translations")
    inventory = build_inventory(
        bundle("monsters")["monsters"],
        bundle("casting"),
        bundle("limits"),
        trees,
        states,
        bundle("roots"),
        actors,
        bundle("translations"),
        bundle("level-zero"),
    )
    inventory["provenance"] = provenance
    inventory["inventory_builder_sha256"] = digest(Path(__file__))
    write(output / "inventory.json.gz", inventory)
    report(
        output, inventory, args.focus_name or ["miaumiau", "miamiau", "tofu", "jalat"]
    )
    print(json.dumps(dict(output=str(output), summary=inventory["summary"]), indent=2))


if __name__ == "__main__":
    main()
