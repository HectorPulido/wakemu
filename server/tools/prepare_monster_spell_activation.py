"""Prepare a scoped NPC catalog candidate from native data; never publish it."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from audit_monster_family_coverage import supported_families
from convert_spell_effect_trees import convert
from extract_monster_combat_inventory import stable_effect

ROOT = Path(__file__).resolve().parents[2]
NPC_PATH = "native-npc-spell-effect-trees.json"
ROOT_PATH = "native-class-casting-roots.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_records(existing, additions, *, effects=False):
    """Keep every existing definition; reject conflicting shared fields."""
    merged = dict(existing)
    for key, row in additions.items():
        if key in existing:
            old, new = (
                (stable_effect(existing[key]), stable_effect(row))
                if effects
                else (existing[key], row)
            )

            def conflicts(field):
                if (
                    field == "levels"
                    and isinstance(old[field], list)
                    and isinstance(new[field], list)
                ):
                    return (
                        old[field][: min(len(old[field]), len(new[field]))]
                        != new[field][: min(len(old[field]), len(new[field]))]
                    )
                return old[field] != new[field]

            if any(conflicts(field) for field in old.keys() & new.keys()):
                raise ValueError("Conflicting existing native definition: " + key)
        else:
            merged[key] = row
    return merged


def supplement_zero_level_dependencies(exported, required, shared_ids, definitions):
    """Append original full zero-level-only rows missing from shared catalogs.

    Keep bounds and all sampled arrays intact: index zero in positive-level
    samples still means native level one, never the zero-level sample.
    """
    missing = set(required) - set(exported["effects"]) - set(shared_ids)
    additions = {}
    for key in sorted(missing):
        row = definitions.get(key)
        if row is None:
            continue
        if (
            type(row.get("minimum_level")) is not int
            or type(row.get("maximum_level")) is not int
            or row["minimum_level"] != 0
            or row["maximum_level"] != 0
        ):
            continue
        if (
            type(row.get("effect_class")) is not int
            or not isinstance(row.get("parameters"), list)
            or type(row.get("parameter_count")) is not int
            or len(row["parameters"]) != 2 * row["parameter_count"]
            or not isinstance(row.get("children"), list)
            or not isinstance(row.get("native_timing_definition"), dict)
            or not isinstance(row.get("native_target_selector"), dict)
            or type(row.get("native_execution_mode")) is not int
            or not isinstance(row.get("native_definition_class"), str)
        ):
            raise ValueError("Incomplete original zero-level effect definition: " + key)
        additions[key] = deepcopy(row)
    result = dict(exported)
    result["effects"] = merge_records(exported["effects"], additions, effects=True)
    return result


def select_candidates(coverage, maximum=9):
    if type(maximum) is not int or maximum < 1:
        raise ValueError("Maximum native level must be a positive integer")
    from monster_activation_exceptions import exception_reason

    return [
        row
        for row in coverage["monsters"]
        if exception_reason(row["ref"]) is None
        and row["status"] == "covered"
        and row["spell_ids"]
        and not row["data_gaps"]
        and not row["missing_families"]
        and 1 <= row["min_level"] <= row["max_level"] <= maximum
    ]


def inventory_activation_status(reference, selected, previously_enabled):
    """Keep earlier activations visible when validating a disjoint cohort."""
    from monster_activation_exceptions import exclusion_status

    excluded = exclusion_status(reference)
    if excluded is not None:
        return excluded
    if reference in selected:
        return "candidate_pending_execution_validation"
    if str(reference) in previously_enabled:
        return "activated"
    return "inventory_only"


def merge_npc(existing, exported, candidates):
    result = dict(existing)
    result["baseline_effects"] = deepcopy(
        existing.get("baseline_effects", existing["effects"])
    )
    for collection in ("spells", "effects"):
        result[collection] = merge_records(
            existing[collection], exported[collection], effects=collection == "effects"
        )
    old_policy = existing.get("activation_policy")
    legacy = (
        sorted(map(int, existing["spells"]))
        if old_policy is None
        else old_policy["legacy_spell_ids"]
    )
    enabled = {} if old_policy is None else deepcopy(old_policy["enabled_monsters"])
    for mob in candidates:
        record = deepcopy(enabled.get(str(mob["ref"]), {}))
        record.update(
            {key: mob[key] for key in ("min_level", "max_level", "spell_ids")}
        )
        if "initial_state_triples" in mob:
            triples = mob["initial_state_triples"]
            if (
                not isinstance(triples, list)
                or len(triples) % 3
                or any(
                    type(value) is not int or not -32768 <= value <= 32767
                    for value in triples
                )
            ):
                raise ValueError("Malformed native monster initial-state triples")
            record["initial_state_triples"] = list(triples)
        enabled[str(mob["ref"])] = record
    result["activation_policy"] = dict(
        schema="native-npc-activation-v1",
        legacy_spell_ids=legacy,
        enabled_monsters=enabled,
    )
    return result


def attach_summon_dependencies(npc, candidates, closure, maximum):
    """Scope imported books to their enabled ordinary parent and native levels."""
    by_spell = closure.get("spell_summon_profiles", {})
    for mob in candidates:
        scopes = {}
        for spell in mob["spell_ids"]:
            for reference, source in by_spell.get(str(spell), {}).items():
                if source.get("level_domain_exact") is not True:
                    continue
                levels = sorted(
                    {
                        level
                        for level in source["descriptor_levels"]
                        if 0 <= level <= maximum
                    }
                )
                if not levels:
                    continue
                book = source.get("spell_ids")
                from monster_summon_book_source import qualified_empty_book

                if (
                    not isinstance(reference, str)
                    or not reference.isdecimal()
                    or int(reference) <= 0
                    or not isinstance(book, list)
                    or not book
                    and not qualified_empty_book(
                        int(reference), source.get("native_empty_book_source")
                    )
                    or any(type(value) is not int or value <= 0 for value in book)
                    or len(set(book)) != len(book)
                ):
                    raise ValueError("Invalid original registered summon book scope")
                scope = scopes.setdefault(
                    reference, dict(descriptor_levels=[], spell_ids=sorted(book))
                )
                if not book:
                    receipt = source["native_empty_book_source"]
                    if scope.get("native_empty_book_source", receipt) != receipt:
                        raise ValueError(
                            "Conflicting original empty summon book source"
                        )
                    scope["native_empty_book_source"] = deepcopy(receipt)
                if scope["spell_ids"] != sorted(book):
                    raise ValueError("Conflicting parent summon action book")
                scope["descriptor_levels"] = sorted(
                    set(scope["descriptor_levels"]) | set(levels)
                )
        for scope in scopes.values():
            scope.update(
                min_level=min(scope["descriptor_levels"]),
                max_level=max(scope["descriptor_levels"]),
            )
        if scopes:
            npc["activation_policy"]["enabled_monsters"][str(mob["ref"])][
                "registered_summon_profiles"
            ] = scopes


def write(path, document):
    path.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    )


def read_bundle(bundle, name):
    with gzip.open(bundle / (name + ".json.gz"), "rt") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-level",
        type=int,
        default=9,
        help="Inclusive maximum of the entire native reference level range",
    )
    parser.add_argument(
        "--only-ref",
        type=int,
        action="append",
        help="Restrict the covered cohort without bypassing eligibility",
    )
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument(
        "--spell-supplement",
        type=Path,
        help="Verified append-only native source supplement directory",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--setters", type=Path, required=True)
    parser.add_argument(
        "--resource-costs",
        type=Path,
        help="Required complete native cost export when absent from the active release",
    )
    parser.add_argument(
        "--health-target-ordering",
        type=Path,
        help="Source-qualified native flag8 identities to append when absent; never replace shared data",
    )
    parser.add_argument(
        "--spell-element-damage-pcs",
        type=Path,
        help="Source-qualified eYW spell element PCs to append when absent; never replace shared data",
    )
    parser.add_argument(
        "--morph-supplement",
        type=Path,
        help="Source-bound append-only native morphology bundle preserving existing class definitions",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        parser.error("Candidate packages must be beneath .runtime")
    output.mkdir(parents=True, exist_ok=False)
    coverage = json.loads(args.coverage.read_text())
    registry = json.loads(args.registry.read_text())
    supported = supported_families(registry, json.loads(args.setters.read_text()))
    if sorted(supported) != coverage["supported_families"]:
        raise ValueError("Effect-family coverage is stale")
    inventory = read_bundle(args.bundle, "inventory")
    inventory_path = (args.bundle / "inventory.json.gz").resolve()
    inventory_key = str(inventory_path.relative_to(ROOT))
    if coverage["sources"].get(inventory_key) != sha(inventory_path):
        raise ValueError("Coverage inventory differs from native activation evidence")
    provenance = json.loads((args.bundle / "provenance.json").read_text())
    if registry["client_jar_sha256"] != provenance["client_jar_sha256"]:
        raise ValueError("Native characteristic registry source differs")
    for name in ("client/lib/wakfu-client.jar",):
        if sha(ROOT / name) != provenance["client_jar_sha256"]:
            raise ValueError("Installed client differs from extracted sources")
    for name, expected in provenance["exporter_sources"].items():
        if sha(ROOT / "sniffer/java" / name) != expected:
            raise ValueError("Native exporter changed: " + name)
    candidates = select_candidates(coverage, args.max_level)
    if args.only_ref:
        requested = set(args.only_ref)
        candidates = [row for row in candidates if row["ref"] in requested]
        if {row["ref"] for row in candidates} != requested:
            raise ValueError(
                "Requested references must all belong to the fully covered native level cohort"
            )
    if not candidates:
        raise ValueError("No fully covered native monster candidates")
    inventory_by_ref = {row["ref"]: row for row in inventory["monsters"]}
    if len(inventory_by_ref) != len(inventory["monsters"]):
        raise ValueError("Duplicate native monster references")
    for candidate in candidates:
        native = inventory_by_ref[candidate["ref"]]
        if (
            candidate["min_level"] != native["min_level"]
            or candidate["max_level"] != native["max_level"]
            or candidate["spell_ids"]
            != [ability["spell_id"] for ability in native["abilities"]]
            or set(native["dependencies"]["effect_families"]) - supported
            or native["dependencies"]["missing_definitions"]
            or native["missing_casting_tables"]
            or native["missing_casting_root_metadata"]
        ):
            raise ValueError(
                "Covered candidate differs from native dependency evidence"
            )
    spells = sorted(
        {
            spell
            for mob in candidates
            for spell in inventory_by_ref[mob["ref"]]["dependencies"]["spell_ids"]
        }
    )
    (output / "spell-refs.txt").write_text("\n".join(map(str, spells)) + "\n")
    # Reuse the same native exporter and converter used for class spell trees.
    sources = [
        ROOT / "sniffer/java" / name
        for name in (
            "ExportGrantedSpellEffectTrees.java",
            "ExportSpellEffectTrees.java",
            "ExportCombatStates.java",
        )
    ]
    (output / "classes").mkdir()
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            str(output / "classes"),
            *map(str, sources),
        ],
        check=True,
    )
    subprocess.run(
        [
            "java",
            "-Xmx1g",
            "-cp",
            str(output / "classes") + ":" + str(ROOT / "client/lib/*"),
            "ExportGrantedSpellEffectTrees",
            str(output / "spell-refs.txt"),
            str(output / "spells"),
        ],
        check=True,
    )
    exported = convert(output / "spells", output / "exported-spells.json")
    from psycopg import connect

    with connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        revision = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
        ).fetchone()[0]
        manifest = {
            p: h
            for p, h in connection.execute(
                "SELECT path,sha256 FROM native_catalog_documents WHERE revision=%s ORDER BY path",
                (revision,),
            )
        }
        additional_documents = {}
        cost_path = "native-spell-resource-costs.json"
        if cost_path not in manifest:
            if args.resource_costs is None:
                raise ValueError(
                    "Current runtime requires complete native resource-cost catalog"
                )
            from stage_spell_resource_cost_catalog import documents as validate_costs

            validated = validate_costs(args.resource_costs.parent)
            if (
                len(validated) != 1
                or validated[0]["source"].resolve() != args.resource_costs.resolve()
            ):
                raise ValueError("Unexpected native resource-cost source")
            additional_documents[cost_path] = args.resource_costs.read_bytes()
        elif args.resource_costs and manifest[cost_path] != sha(args.resource_costs):
            raise ValueError(
                "Existing shared resource-cost catalog must not be replaced"
            )
        if args.health_target_ordering is not None:
            from export_monster_health_target_ordering import package_document

            additional_documents.update(
                package_document(args.health_target_ordering, manifest, root=ROOT)
            )
        if args.spell_element_damage_pcs is not None:
            from export_monster_spell_element_damage_pcs import (
                package_document as package_element_pcs,
            )

            additional_documents.update(
                package_element_pcs(args.spell_element_damage_pcs, manifest, root=ROOT)
            )
        if args.morph_supplement is not None:
            from export_monster_morph_profiles import package_document as package_morph

            additional_documents.update(
                package_morph(args.morph_supplement, manifest, root=ROOT)
            )
        active_monsters = {
            int(key): row
            for key, row in connection.execute(
                "SELECT record_key,payload FROM native_catalog_records WHERE revision=%s AND path='monsters.json' AND collection='monsters' AND record_key=ANY(%s)",
                (revision, [str(mob["ref"]) for mob in candidates]),
            )
        }
        for mob in candidates:
            active = active_monsters.get(mob["ref"])
            source = inventory_by_ref[mob["ref"]]
            expected = [
                (ability["spell_id"], ability["level_parameter"])
                for ability in source["abilities"]
            ]
            if (
                active is None
                or active["min_level"] != mob["min_level"]
                or active["max_level"] != mob["max_level"]
                or [
                    (ability["spell_id"], ability["level_parameter"])
                    for ability in active["native_abilities"]
                ]
                != expected
            ):
                raise ValueError(
                    "Active native ownership differs from selected source evidence"
                )
        base = {}
        for path in (NPC_PATH, ROOT_PATH):
            raw = bytes(
                connection.execute(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (revision, path),
                ).fetchone()[0]
            )
            if hashlib.sha256(raw).hexdigest() != manifest[path]:
                raise ValueError("Active catalog checksum mismatch")
            base[path] = json.loads(raw)
            (output / ("base-" + path)).write_bytes(raw)
        from export_monster_summon_dependencies import (
            CATALOG_PATHS as SUMMON_PATHS,
            build_documents,
        )

        summon_bases, summon_raw = {}, {}
        for path in SUMMON_PATHS:
            raw = bytes(
                connection.execute(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (revision, path),
                ).fetchone()[0]
            )
            if hashlib.sha256(raw).hexdigest() != manifest[path]:
                raise ValueError("Active summon catalog checksum mismatch")
            summon_bases[path], summon_raw[path] = json.loads(raw), raw
        seed_states = {
            s
            for mob in candidates
            for s in inventory_by_ref[mob["ref"]]["dependencies"]["state_ids"]
        }
        from monster_pending_scenarios import scenario_recipes

        native_encounters = {
            row["ref"]: row for row in read_bundle(args.bundle, "monsters")["monsters"]
        }
        encounter_dependencies = []
        for mob in candidates:
            for spell in mob["spell_ids"]:
                for recipe in scenario_recipes(mob["ref"], spell):
                    if "opponent" not in recipe:
                        continue
                    descriptor = recipe["opponent"]
                    native = native_encounters[descriptor["reference"]]
                    if (
                        not native["min_level"]
                        <= descriptor["level"]
                        <= native["max_level"]
                    ):
                        raise ValueError(
                            "Encounter dependency level differs from original native descriptor"
                        )
                    seed_states.update(native["initial_state_triples"][::3])
                    dependency = dict(
                        descriptor,
                        initial_state_triples=native["initial_state_triples"],
                    )
                    if dependency not in encounter_dependencies:
                        encounter_dependencies.append(dependency)
        del native_encounters
        source_levels = {}
        for mob in candidates:
            for spell in mob["spell_ids"]:
                source_levels.setdefault(str(spell), set()).update(
                    range(mob["min_level"], mob["max_level"] + 1)
                )
        summon_documents, closure = build_documents(
            summon_bases,
            args.bundle,
            spells,
            output / "summon-export",
            seed_state_ids=seed_states,
            seed_actor_levels=source_levels,
            **(
                {"spell_supplement": args.spell_supplement}
                if args.spell_supplement is not None
                else {}
            ),
        )
        for path, document in summon_documents.items():
            base[path] = summon_bases[path]
            (output / ("base-" + path)).write_bytes(summon_raw[path])
            additional_documents[path] = (output / "summon-export" / path).read_bytes()
        expanded_spells = sorted(set(spells) | set(closure["closure_spell_ids"]))
        if expanded_spells != spells:
            spells = expanded_spells
            (output / "spell-refs.txt").write_text("\n".join(map(str, spells)) + "\n")
            subprocess.run(
                [
                    "java",
                    "-Xmx1g",
                    "-cp",
                    str(output / "classes") + ":" + str(ROOT / "client/lib/*"),
                    "ExportGrantedSpellEffectTrees",
                    str(output / "spell-refs.txt"),
                    str(output / "summon-spells"),
                ],
                check=True,
            )
            exported = convert(
                output / "summon-spells", output / "exported-spells.json"
            )
        state_ids = sorted(map(str, seed_states | set(closure["closure_state_ids"])))
        # The class-scoped fyW.elk seed set does not cover ordinary NPC states.
        # Extend it from original native getters, retaining every class row.
        from export_monster_state_resistance import (
            CATALOG_PATH,
            export as export_resistance,
        )

        resistance_raw = bytes(
            connection.execute(
                "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, CATALOG_PATH),
            ).fetchone()[0]
        )
        if hashlib.sha256(resistance_raw).hexdigest() != manifest[CATALOG_PATH]:
            raise ValueError("Active resistance catalog checksum mismatch")
        resistance = export_resistance(
            json.loads(resistance_raw),
            map(int, state_ids),
            args.bundle,
            output / "resistance-export",
        )
        if resistance is not None:
            base[CATALOG_PATH] = json.loads(resistance_raw)
            (output / ("base-" + CATALOG_PATH)).write_bytes(resistance_raw)
            additional_documents[CATALOG_PATH] = (
                output / "resistance-export" / CATALOG_PATH
            ).read_bytes()
        from export_monster_cell_groups import (
            CATALOG_PATH as CELL_PATH,
            export as export_cells,
            required_effect_ids,
        )

        effect_ids = sorted(
            {
                str(e)
                for mob in candidates
                for e in inventory_by_ref[mob["ref"]]["dependencies"]["effect_ids"]
            }
            | set(map(str, closure["closure_effect_ids"]))
        )
        cell_ids = [
            int(key)
            for key, in connection.execute(
                "SELECT DISTINCT record_key FROM native_catalog_records WHERE revision=%s AND collection='effects' AND record_key=ANY(%s) AND (payload->>'effect_class')::integer=349",
                (revision, effect_ids),
            )
        ]
        cell_ids = required_effect_ids(cell_ids, exported)
        cell_raw = bytes(
            connection.execute(
                "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, CELL_PATH),
            ).fetchone()[0]
        )
        if hashlib.sha256(cell_raw).hexdigest() != manifest[CELL_PATH]:
            raise ValueError("Active cell-group catalog checksum mismatch")
        cells = export_cells(
            json.loads(cell_raw), cell_ids, args.bundle, output / "cell-group-export"
        )
        if cells is not None:
            base[CELL_PATH] = json.loads(cell_raw)
            (output / ("base-" + CELL_PATH)).write_bytes(cell_raw)
            additional_documents[CELL_PATH] = (
                output / "cell-group-export" / CELL_PATH
            ).read_bytes()
        got = {
            key
            for key, in connection.execute(
                "SELECT record_key FROM native_catalog_records WHERE revision=%s AND path='combat-state-definitions.json' AND collection='states' AND record_key=ANY(%s)",
                (revision, state_ids),
            )
        }
        if got != set(state_ids):
            raise ValueError("Candidate NPC states missing in active shared catalog")
        # Verify all dependencies resolve in the proposed NPC tree or unchanged shared catalogs.
        needed = set(effect_ids)
        missing = needed - exported["effects"].keys()
        got = {
            key
            for key, in connection.execute(
                "SELECT DISTINCT record_key FROM native_catalog_records WHERE revision=%s AND path=ANY(%s) AND collection='effects' AND record_key=ANY(%s)",
                (
                    revision,
                    [
                        "combat-state-definitions.json",
                        "spell-effect-trees.json",
                        "granted-spell-effect-trees.json",
                        "native-area-effect-trees.json",
                    ],
                    sorted(missing),
                ),
            )
        }
        exported = supplement_zero_level_dependencies(
            exported,
            needed,
            got,
            read_bundle(args.bundle, "zero-effect-definitions")["effects"],
        )
        # Persist the complete candidate source, retaining original zero bounds.
        (output / "exported-spells.json").write_text(
            json.dumps(exported, separators=(",", ":"))
        )
        unresolved = needed - exported["effects"].keys() - got
        if unresolved:
            raise ValueError(
                "Missing candidate effect dependencies: " + str(sorted(unresolved))
            )
    # Constructor states share the same fenced NPC document as spell imports.
    # Keep raw cle order, levels (including -1), and flags from native evidence.
    candidates = [
        dict(
            mob,
            initial_state_triples=[
                value
                for state in inventory_by_ref[mob["ref"]]["initial_states"]
                for value in (
                    state["state_id"],
                    state["level_parameter"],
                    state["native_flag"],
                )
            ],
        )
        for mob in candidates
    ]
    npc = merge_npc(base[NPC_PATH], exported, candidates)
    attach_summon_dependencies(npc, candidates, closure, args.max_level)
    native_roots = read_bundle(args.bundle, "roots")
    casting = read_bundle(args.bundle, "casting")["spells"]
    roots = {
        str(root)
        for spell in spells
        for level in casting[str(spell)]["levels"]
        for root in level[2]
    }
    root_document = dict(base[ROOT_PATH])
    for field in ("fight_properties", "normal_casting_overrides"):
        if root_document[field] != native_roots[field]:
            raise ValueError("Native casting global metadata conflict")
    root_document["roots"] = merge_records(
        root_document["roots"], {root: native_roots["roots"][root] for root in roots}
    )
    write(output / NPC_PATH, npc)
    write(output / ROOT_PATH, root_document)
    for name, raw in additional_documents.items():
        (output / name).write_bytes(raw)
    changed = {NPC_PATH, ROOT_PATH} | additional_documents.keys()
    write(
        output / "manifest.json",
        dict(
            schema="native-npc-activation-candidate-v1",
            base_revision=revision,
            activated=False,
            selected_references=[m["ref"] for m in candidates],
            changed_documents={name: sha(output / name) for name in sorted(changed)},
            base_document_hashes={name: manifest[name] for name in base},
            added_dependencies=sorted(additional_documents),
            encounter_dependencies=encounter_dependencies,
            unchanged_documents={p: h for p, h in manifest.items() if p not in changed},
            coverage_sha256=sha(args.coverage),
            native_source_provenance=provenance,
            maximum_native_level=args.max_level,
            candidate_spell_count=len(spells),
            candidate_state_count=len(state_ids),
            candidate_effect_count=len(exported["effects"]),
        ),
    )
    from monster_activation_exceptions import exception_reason

    rows = []
    selected = {row["ref"] for row in candidates}
    previously_enabled = (
        base[NPC_PATH].get("activation_policy", {}).get("enabled_monsters", {})
    )
    for row in coverage["monsters"]:
        properties = inventory_by_ref[row["ref"]]["raw_native"].get("csc", [])
        roles = [
            name
            for code, name in (
                (49, "ultimate_boss"),
                (99, "raid_boss"),
                (43, "boss"),
                (45, "archmonster"),
                (115, "dominant"),
            )
            if code in properties
        ]
        rows.append(
            dict(
                row,
                native_roles=roles or ["ordinary_or_other"],
                activation_status=inventory_activation_status(
                    row["ref"], selected, previously_enabled
                ),
                activation_exception=exception_reason(row["ref"]),
                runtime_status="candidate_release_not_activated",
                execution_validation=None,
                all_owned_spells_in_baseline_npc_catalog=bool(row["spell_ids"])
                and all(
                    str(spell) in base[NPC_PATH]["spells"] for spell in row["spell_ids"]
                ),
            )
        )
    write(
        output / "monster-status.json",
        dict(
            schema="monster-spell-activation-inventory-v1",
            base_revision=revision,
            activated=False,
            scope=f"Entire native level range from 1 through {args.max_level} and all effect families covered",
            summary=dict(Counter(row["activation_status"] for row in rows)),
            monsters=rows,
        ),
    )
    print(
        json.dumps(
            dict(
                base_revision=revision,
                selected=len(candidates),
                spells=len(spells),
                states=len(state_ids),
                effects=len(exported["effects"]),
                activated=False,
            )
        )
    )


if __name__ == "__main__":
    main()
