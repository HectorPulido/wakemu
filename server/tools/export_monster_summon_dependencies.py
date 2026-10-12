"""Export append-only native307 profile books and their complete typed closure."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATHS = (
    "native-class-summon-abilities.json",
    "native-class-summon-initial-states.json",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_bundle(bundle, name):
    with gzip.open(Path(bundle) / (name + ".json.gz"), "rt") as stream:
        return json.load(stream)


def compact(document):
    """Retain original evaluated reference values while releasing large samples."""
    result = {}
    for kind in ("spells", "states", "areas"):
        result[kind] = {}
        for key, row in document.get(kind, {}).items():
            roots = set(row.get("effect_ids", [])) | set(
                row.get("level_zero_roots", [])
            )
            for level in row.get("levels", []):
                roots.update(level["effects"] if isinstance(level, dict) else level[2])
            result[kind][key] = sorted(roots)
    result["spell_level_roots"] = {}
    for key, row in document.get("spells", {}).items():
        samples = {
            str(level.get("level", index) if isinstance(level, dict) else index): list(
                level["effects"] if isinstance(level, dict) else level[2]
            )
            for index, level in enumerate(row.get("levels", []), 1)
        }
        if "level_zero_roots" in row:
            samples["0"] = list(row["level_zero_roots"])
        result["spell_level_roots"][key] = samples
    result["effects"] = {}
    for key, row in document.get("effects", {}).items():
        family = row["effect_class"]
        index = 2 if family == 649 else 0
        references = (
            sorted(
                {
                    values[index]
                    for values in row.get("parameters_by_level", [])
                    if len(values) > index and type(values[index]) is int
                }
            )
            if family in (304, 321, 307, 315, 426, 649)
            else []
        )
        result["effects"][key] = dict(
            family=family,
            children=row.get("children", []),
            references=references,
            native_effect_flags=row.get("native_effect_flags"),
        )
        if family == 994:
            # Installed eZq/eZn constructs faB; eHI.cmY is fixed2349.
            result["effects"][key]["references"] = [2349]
            result["effects"][key]["fixed_profile_source"] = "eZq.eZn.faB.eHI.cmY"
        if family == 307:
            result["effects"][key]["parameter_samples_by_level"] = {
                str(level): list(values)
                for level, values in enumerate(row.get("parameters_by_level", []), 1)
            }
            result["effects"][key]["parameter_samples"] = sorted(
                {tuple(values) for values in row.get("parameters_by_level", [])}
            )
    return result


def dependency_closure(tables, monsters, seed_spell_ids, seed_state_ids=()):
    """Follow cycles, nested summons, initial states, areas and granted spells."""
    seen = {
        kind: set() for kind in ("spells", "states", "areas", "effects", "profiles")
    }
    pending = [("spells", str(ref)) for ref in seed_spell_ids]
    pending += [("states", str(ref)) for ref in seed_state_ids]
    edges = set()
    missing = set()
    while pending:
        kind, key = pending.pop()
        if key in seen[kind]:
            continue
        seen[kind].add(key)
        row = (monsters if kind == "profiles" else tables[kind]).get(key)
        if row is None:
            missing.add(kind + ":" + key)
            continue
        if kind == "profiles":
            pending += [("spells", str(a["spell_id"])) for a in row["native_abilities"]]
            triples = row["initial_state_triples"]
            if len(triples) % 3:
                raise ValueError("Invalid original profile initial states")
            pending += [("states", str(ref)) for ref in triples[::3]]
        elif kind != "effects":
            pending += [("effects", str(ref)) for ref in row]
        else:
            pending += [("effects", str(ref)) for ref in row["children"]]
            target = {
                304: "states",
                321: "states",
                307: "profiles",
                994: "profiles",
                315: "areas",
                426: "spells",
                649: "spells",
            }.get(row["family"])
            if target:
                if not row["references"]:
                    missing.add("evaluated-references:" + key)
                for ref in row["references"]:
                    # eZl.C consumes a signed-short descriptor reference.
                    if row["family"] == 307:
                        ref = ((ref + 32768) % 65536) - 32768
                        edges.add((int(key), ref))
                    if row["family"] == 994:
                        if (
                            ref != 2349
                            or row.get("fixed_profile_source") != "eZq.eZn.faB.eHI.cmY"
                        ):
                            raise ValueError("Missing native994 fixed-profile source")
                        edges.add((int(key), ref))
                    if ref <= 0:
                        missing.add(target + ":" + str(ref))
                    else:
                        pending.append((target, str(ref)))
    return dict(
        **{
            "closure_" + kind[:-1] + "_ids": sorted(map(int, refs))
            for kind, refs in seen.items()
        },
        effect_profile_edges=[
            dict(
                effect_reference=e,
                profile_id=p,
                **(
                    dict(
                        family=994,
                        edge_type="native_fixed_profile",
                        producer="eZq.eZn.faB.eHI.cmY",
                    )
                    if tables["effects"][str(e)]["family"] == 994
                    else {}
                )
            )
            for e, p in sorted(edges)
        ],
        missing_definitions=sorted(missing)
    )


def assert_preserved(path, base, candidate):
    """Reject mutation or removal of any existing shared class profile or field."""
    if (
        path not in CATALOG_PATHS
        or not isinstance(base.get("profiles"), dict)
        or not isinstance(candidate.get("profiles"), dict)
    ):
        raise ValueError("Invalid native summon profile document")
    if any(
        candidate["profiles"].get(key) != value
        for key, value in base["profiles"].items()
    ):
        raise ValueError("NPC import changed an existing class summon profile")
    if any(
        candidate.get(key) != value
        for key, value in base.items()
        if key not in ("profiles", "npc_dependency_exports")
    ):
        raise ValueError("NPC import changed shared summon metadata")
    prior = base.get("npc_dependency_exports", [])
    receipts = candidate.get("npc_dependency_exports", [])
    if receipts[: len(prior)] != prior or any(
        row.get("original_inputs_stable") is not True for row in receipts[len(prior) :]
    ):
        raise ValueError("Missing sealed native summon provenance")
    if set(candidate["profiles"]) != set(base["profiles"]) and len(receipts) == len(
        prior
    ):
        raise ValueError("New summon profiles require native export evidence")


def merge_profiles(base_documents, exported, provenance):
    """Copy only consumer fields; keep existing class rows byte-equivalent."""
    documents = {}
    for path in CATALOG_PATHS:
        base = base_documents[path]
        result = deepcopy(base)
        added = []
        for key, row in exported["profiles"].items():
            fields = (
                ("abilities",)
                if path == CATALOG_PATHS[0]
                else ("initial_state_triples", "fight_properties")
            )
            addition = {field: deepcopy(row[field]) for field in fields}
            if key in base["profiles"]:
                if any(
                    base["profiles"][key].get(field) != addition[field]
                    for field in fields
                ):
                    raise ValueError(
                        "Native summon export conflicts with existing class profile "
                        + key
                    )
            else:
                result["profiles"][key] = addition
                added.append(int(key))
        if added:
            result.setdefault("npc_dependency_exports", []).append(
                dict(provenance, added_profile_ids=sorted(added))
            )
        assert_preserved(path, base, result)
        if result != base:
            documents[path] = result
    return documents


def resolved_container_domains(tables, monsters, spell, contexts):
    """Carry proven PL identity through eYk/eXR; other producers stay unknown.

    eVE.a forwards PL into Qe.bfq. eZR.fRR selects eVt.Oh or PL.cmZ;
    fresh eVt.Oh is -1. Flag16 (eVl.rwM) transmits parent fRR to children.
    This does not infer a spell container level from an actor level.
    """
    roots = tables.get("spell_level_roots", {}).get(str(spell), {})
    pending = []
    if contexts:
        for context in contexts:
            level = context.get("container_level")
            override = context.get("level_override", -1)
            if (
                type(level) is not int
                or not 0 <= level <= 32767
                or type(override) is not int
                or not -1 <= override <= 32767
                or str(level) not in roots
            ):
                raise ValueError("Unproven native spell container context")
            pending.extend(
                ("effects", str(root), level, override) for root in roots[str(level)]
            )
    else:
        pending.extend(
            ("effects", str(root), None, -1)
            for root in tables["spells"].get(str(spell), [])
        )
    seen, domains, unknown = set(), {}, set()
    while pending:
        kind, key, level, override = pending.pop()
        identity = (kind, key, level, override)
        if identity in seen:
            continue
        seen.add(identity)
        row = (monsters if kind == "profiles" else tables[kind]).get(key)
        if row is None:
            continue
        if kind == "effects":
            if level is None:
                unknown.add(int(key))
            else:
                domains.setdefault(int(key), set()).add(
                    level if override == -1 else override
                )
            flags = row.get("native_effect_flags")
            safe = (
                row["family"] in (349, 341)
                and isinstance(flags, list)
                and all(type(flag) is int for flag in flags)
            )
            child_level = level if safe else None
            child_override = (
                (level if override == -1 else override)
                if safe and level is not None and 16 in flags
                else -1
            )
            pending.extend(
                ("effects", str(child), child_level, child_override)
                for child in row["children"]
            )
            target = {
                304: "states",
                321: "states",
                307: "profiles",
                994: "profiles",
                315: "areas",
                426: "spells",
                649: "spells",
            }.get(row["family"])
            if target:
                for ref in row["references"]:
                    if row["family"] == 307:
                        ref = ((ref + 32768) % 65536) - 32768
                    if ref > 0:
                        pending.append((target, str(ref), None, -1))
        elif kind == "profiles":
            pending.extend(
                ("spells", str(a["spell_id"]), None, -1)
                for a in row["native_abilities"]
            )
            pending.extend(
                ("states", str(ref), None, -1)
                for ref in row["initial_state_triples"][::3]
            )
        else:
            # State application, granted spells and areas introduce contexts
            # whose resolved levels have not been proved by the wrapper audit.
            pending.extend(("effects", str(ref), None, -1) for ref in row)
    return domains, unknown


def summon_dependency_scopes(
    tables,
    monsters,
    seed_spell_ids,
    *,
    seed_actor_levels=None,
    seed_container_contexts=None
):
    """Report original descriptor levels; uncertain nested contexts stay blocked."""
    report = dict(spell_profile_dependencies={}, spell_summon_profiles={})
    for spell in sorted(set(seed_spell_ids)):
        closure = dependency_closure(tables, monsters, [spell])
        direct_effects = set(
            dependency_closure(tables, {}, [spell])["closure_effect_ids"]
        )
        report["spell_profile_dependencies"][str(spell)] = closure[
            "closure_profile_ids"
        ]
        scopes = {}
        container_contexts = (seed_container_contexts or {}).get(
            str(spell), (seed_container_contexts or {}).get(spell)
        )
        container_domains, unknown_containers = resolved_container_domains(
            tables, monsters, spell, container_contexts
        )
        parent_levels = (seed_actor_levels or {}).get(
            str(spell), (seed_actor_levels or {}).get(spell, range(246))
        )
        if any(
            type(level) is not int or not 0 <= level <= 32767 for level in parent_levels
        ):
            raise ValueError("Invalid source actor level domain")
        for effect_id in closure["closure_effect_ids"]:
            effect = tables["effects"].get(str(effect_id))
            if effect is not None and effect["family"] == 994:
                if (
                    effect.get("references") != [2349]
                    or effect.get("fixed_profile_source") != "eZq.eZn.faB.eHI.cmY"
                ):
                    raise ValueError("Missing native994 fixed-profile source")
                profile = monsters.get("2349")
                if profile is not None:
                    scope = scopes.setdefault(
                        "2349",
                        dict(
                            descriptor_levels=set(),
                            level_domain_exact=False,
                            level_modes=set(),
                            nonexecuting_samples=[],
                            spell_ids=sorted(
                                a["spell_id"] for a in profile["native_abilities"]
                            ),
                        ),
                    )
                    scope["level_domain_exact"] = False
                    scope.setdefault("contextual_target_levels", []).append(
                        dict(
                            family=994,
                            effect_id=effect_id,
                            producer="eZq.eZn.faB.eHI.cmZ.target_real_level",
                            target_domain="actual_owned_class_target",
                            finite_domain=None,
                            reason="target_level_population_not_supplied",
                        )
                    )
                    if not profile["native_abilities"]:
                        from monster_summon_book_source import empty_book_source

                        scope["native_empty_book_source"] = empty_book_source(
                            2349, profile
                        )
                continue
            if effect is None or effect["family"] != 307:
                continue
            for values in effect.get("parameter_samples", ()):
                if not values:
                    raise ValueError("Missing original summon reference")
                reference = ((values[0] + 32768) % 65536) - 32768
                profile = monsters.get(str(reference))
                if profile is None:
                    continue
                # eZl.C uses SQ.a(1, -1): omitted level mode means the actual
                # effect container level, exactly as summon_specification does.
                # Its level domain remains unproven below; this is no bypass.
                mode = values[1] if len(values) > 1 else -1
                current_scope = scopes.setdefault(
                    str(reference),
                    dict(
                        descriptor_levels=set(),
                        level_domain_exact=True,
                        level_modes=set(),
                        nonexecuting_samples=[],
                        spell_ids=sorted(
                            ability["spell_id"]
                            for ability in profile["native_abilities"]
                        ),
                    ),
                )
                current_scope["level_modes"].add(mode)
                if not profile["native_abilities"]:
                    from monster_summon_book_source import empty_book_source

                    current_scope["native_empty_book_source"] = empty_book_source(
                        reference, profile
                    )
                if mode <= 0 and mode not in (-3, -2, -1):
                    # eZl.C 227..249 logs and returns BEFORE eHD creation.
                    # Keep the sample/closure; it produces no descriptor level.
                    current_scope["nonexecuting_samples"].append(
                        dict(
                            effect_id=int(effect_id),
                            parameters=list(values),
                            level_mode=mode,
                            reason="native_invalid_level_mode_no_summon",
                            source="eZl.C.227_249",
                        )
                    )
                    continue
                # These are original evaluated eZl parameters. Preserve their
                # actual native descriptor mode instead of wild species bounds.
                known_container_levels = container_domains.get(effect_id, set())
                evaluated_samples = effect.get("parameter_samples_by_level", {})
                matched_container_levels = sorted(
                    level
                    for level in known_container_levels
                    if tuple(evaluated_samples.get(str(level), ())) == tuple(values)
                )
                levels = (
                    [profile["min_level"]]
                    if mode == -3
                    else parent_levels
                    if mode == -2
                    else matched_container_levels
                    if mode == -1
                    else [((mode + 32768) % 65536) - 32768]
                    if mode > 0
                    else []
                )
                if mode == -1 and not levels:
                    current_scope["level_domain_exact"] = False
                    current_scope.setdefault(
                        "unproven_container_effect_ids", []
                    ).append(effect_id)
                    continue
                if not levels or any(level < 0 for level in levels):
                    raise ValueError("Unsupported native summon descriptor level mode")
                current_scope["descriptor_levels"].update(levels)
                if mode == -1:
                    current_scope.setdefault("container_level_sources", []).append(
                        dict(
                            effect_id=effect_id,
                            descriptor_levels=list(levels),
                            producer="eVE.a.Qe.bfq.eZR.fRR.eZl.C",
                            wrappers="eYk/eXR.PL_reuse.eVt.rwM16",
                        )
                    )
                if (
                    mode == -1
                    and (
                        effect_id in unknown_containers
                        or any(
                            str(level) not in evaluated_samples
                            for level in known_container_levels
                        )
                    )
                    or mode == -2
                    and (not seed_actor_levels or effect_id not in direct_effects)
                ):
                    current_scope["level_domain_exact"] = False
        for scope in scopes.values():
            scope["descriptor_levels"] = sorted(scope["descriptor_levels"])
            scope["level_modes"] = sorted(scope["level_modes"])
            scope["min_level"] = min(scope["descriptor_levels"], default=None)
            scope["max_level"] = max(scope["descriptor_levels"], default=None)
            if not scope["descriptor_levels"]:
                # A native non-execution witness is not an activation proof.
                scope["level_domain_exact"] = False
        report["spell_summon_profiles"][str(spell)] = scopes
    return report


def build_documents(
    base_documents,
    bundle,
    seed_spell_ids,
    output,
    *,
    seed_state_ids=(),
    seed_actor_levels=None,
    seed_container_contexts=None,
    spell_supplement=None
):
    """Return changed shared documents and closure report; never write the DB."""
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        raise ValueError("Native summon exports must remain beneath .runtime")
    output.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((bundle / "provenance.json").read_text())
    inputs = {ROOT / "client/lib/wakfu-client.jar": provenance["client_jar_sha256"]}
    inputs.update(
        {
            ROOT / "client/contents/bdata" / name: value
            for name, value in provenance["binary_archives"].items()
        }
    )
    for name in (
        "trees",
        "states",
        "area-effects",
        "areas",
        "monsters",
        "level-zero",
        "zero-effect-definitions",
    ):
        path = bundle / (name + ".json.gz")
        inputs[path] = provenance["bundle_documents"][path.name]
    exporter = ROOT / "sniffer/java/ExportOwnedCapturedProfiles.java"
    before = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    if any(
        before[str(path.relative_to(ROOT))] != expected
        for path, expected in inputs.items()
    ):
        raise ValueError("Native summon inputs differ from sealed extraction")
    before[str(exporter.relative_to(ROOT))] = digest(exporter)
    tables = {
        kind: {}
        for kind in ("spells", "states", "areas", "effects", "spell_level_roots")
    }
    for name in ("trees", "states", "area-effects", "areas"):
        index = compact(read_bundle(bundle, name))
        for kind, records in index.items():
            for key, row in records.items():
                if key in tables[kind] and tables[kind][key] != row:
                    raise ValueError(
                        "Conflicting native dependency identity " + kind + ":" + key
                    )
                tables[kind][key] = row
    if spell_supplement is not None:
        from monster_spell_supplement import (
            verify_spell_supplement,
            merge_dependency_supplement,
        )

        tables = merge_dependency_supplement(
            tables, verify_spell_supplement(spell_supplement, bundle)
        )
    # Native level zero is a distinct sampled producer, not index one.
    extra = compact(read_bundle(bundle, "zero-effect-definitions"))["effects"]
    for key, row in extra.items():
        if key not in tables["effects"]:
            tables["effects"][key] = row
        elif (tables["effects"][key]["family"], tables["effects"][key]["children"]) != (
            row["family"],
            row["children"],
        ):
            raise ValueError("Conflicting zero-level effect identity " + key)
    zero = read_bundle(bundle, "level-zero")
    for key, row in zero["effects"].items():
        if key not in tables["effects"]:
            raise ValueError("Missing complete zero-level effect definition " + key)
        current = tables["effects"][key]
        if current["family"] != row["family"] or current["children"] != row["children"]:
            raise ValueError("Conflicting original zero-level effect " + key)
        if row["family"] in (304, 321, 307, 315, 426, 649):
            index = 2 if row["family"] == 649 else 0
            if len(row["parameters"]) <= index:
                raise ValueError("Missing original zero-level reference " + key)
            current["references"] = sorted(
                set(current["references"]) | {row["parameters"][index]}
            )
            if row["family"] == 307:
                current.setdefault("parameter_samples_by_level", {})["0"] = list(
                    row["parameters"]
                )
                current["parameter_samples"] = sorted(
                    set(map(tuple, current.get("parameter_samples", ())))
                    | {tuple(row["parameters"])}
                )
    monsters = {
        str(row["ref"]): row for row in read_bundle(bundle, "monsters")["monsters"]
    }
    report = dependency_closure(tables, monsters, seed_spell_ids, seed_state_ids)
    if spell_supplement is not None:
        report["spell_supplement"] = dict(
            receipt_sha256=digest(Path(spell_supplement) / "source-receipt.json"),
            document_sha256=digest(Path(spell_supplement) / "supplement.json"),
            ownership_changed=False,
            effect_parameters_above_200_qualified=False,
        )
    report.update(
        summon_dependency_scopes(
            tables,
            monsters,
            seed_spell_ids,
            seed_actor_levels=seed_actor_levels,
            seed_container_contexts=seed_container_contexts,
        )
    )
    if report["missing_definitions"]:
        raise ValueError(
            "Unclosed native summon dependencies: " + str(report["missing_definitions"])
        )
    profile_ids = report["closure_profile_ids"]
    if not profile_ids:
        return {}, report
    seeds = dict(
        schema="native-class-summon-dependency-seeds-v1",
        profile_ids=profile_ids,
        effect_profile_edges=report["effect_profile_edges"],
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
    native_path = output / "native-profiles.json"
    subprocess.run(
        [
            "java",
            "-Xmx1g",
            "-cp",
            str(classes) + ":" + str(ROOT / "client/lib/*"),
            "ExportOwnedCapturedProfiles",
            str(output / "seeds.json"),
            str(native_path),
        ],
        cwd=ROOT,
        check=True,
    )
    exported = json.loads(native_path.read_text())
    if set(exported["profiles"]) != set(map(str, profile_ids)):
        raise ValueError("Incomplete original summon profile export")
    after = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    after[str(exporter.relative_to(ROOT))] = digest(exporter)
    if after != before:
        raise ValueError("Native summon inputs changed during export")
    receipt = dict(
        original_inputs_stable=True,
        source_sha256=before,
        native_export_sha256=digest(native_path),
        native_book_checks=exported["native_book_checks"],
        effect_profile_edges=report["effect_profile_edges"],
    )
    documents = merge_profiles(base_documents, exported, receipt)
    report.update(receipt)
    report["changed_documents"] = sorted(documents)
    for path, document in documents.items():
        (output / path).write_text(json.dumps(document, separators=(",", ":")) + "\n")
    (output / "closure-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return documents, report
