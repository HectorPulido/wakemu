"""Offline spell/effect dependency work index; static fanout is not qualification."""
import argparse, ast, collections, gzip, hashlib, json
from pathlib import Path
from audit_monster_family_coverage import supported_families
from wakfu_server.combat_local_criteria import parse_local_criterion


class Reader:
    def __init__(self, stream):
        self.stream, self.buffer, self.decoder = stream, "", json.JSONDecoder()

    def peek(self):
        while not self.buffer.strip():
            chunk = self.stream.read(65536)
            if not chunk:
                raise ValueError("Truncated native source JSON")
            self.buffer += chunk
        self.buffer = self.buffer.lstrip()
        return self.buffer[0]

    def char(self, value):
        if self.peek() != value:
            raise ValueError("Unexpected source JSON token")
        self.buffer = self.buffer[1:]

    def value(self):
        while True:
            self.buffer = self.buffer.lstrip()
            try:
                value, end = self.decoder.raw_decode(self.buffer)
                self.buffer = self.buffer[end:]
                return value
            except json.JSONDecodeError:
                chunk = self.stream.read(65536)
                if not chunk:
                    raise ValueError("Truncated native source JSON")
                self.buffer += chunk


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def load(path):
    with gzip.open(path, "rt") if path.suffix == ".gz" else path.open() as f:
        return json.load(f)


def records(path, sections):
    with gzip.open(path, "rt") if path.suffix == ".gz" else path.open() as f:
        r = Reader(f)
        r.char("{")
        while r.peek() != "}":
            section = r.value()
            r.char(":")
            if section in sections:
                r.char("{")
                while r.peek() != "}":
                    key = r.value()
                    r.char(":")
                    yield section, key, r.value()
                    if r.peek() == ",":
                        r.char(",")
                r.char("}")
            else:
                r.value()
            if r.peek() == ",":
                r.char(",")
        r.char("}")


def roots(row):
    result = set(row.get("effect_ids", [])) | set(row.get("level_zero_roots", []))
    for level in row.get("levels", []):
        result.update(level.get("effects", []) if isinstance(level, dict) else level[2])
    return set(map(str, result))


def predicate_signatures(raw):
    if not raw:
        return []
    try:
        tree = parse_local_criterion(raw)
    except (ValueError, SyntaxError):
        return [("unparsed_native_criterion", raw)]
    return [
        (node.func.id, ast.dump(node, include_attributes=False))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]


def dependency_namespace(family):
    return {304: "state", 321: "state", 315: "area", 426: "spell", 649: "spell"}.get(
        family
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--effective-minigame-policy", action="store_true")
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--trees", type=Path, action="append", required=True)
    p.add_argument("--areas", type=Path, required=True)
    p.add_argument("--area-effects", type=Path, required=True)
    p.add_argument("--states", type=Path, required=True)
    p.add_argument("--casting", type=Path, required=True)
    p.add_argument("--pending-reference-queue", type=Path, required=True)
    p.add_argument("--published-policy", type=Path)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--setters", type=Path, required=True)
    p.add_argument("--block-index", type=Path, action="append", default=[])
    p.add_argument("--receipt", type=Path, action="append", default=[])
    p.add_argument("--initial-lifecycle-output", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists()
    native = {m["ref"]: m for m in load(a.inventory)["monsters"]}
    queue = load(a.pending_reference_queue)
    requested = {
        r.get("ref", r.get("reference")): r
        for r in queue.get("jobs", queue.get("monsters", []))
    }
    policy = {}
    if a.published_policy:
        # Stream unrelated spell/effect records rather than loading the catalog.
        with a.published_policy.open() as f:
            reader = Reader(f)
            reader.char("{")
            while reader.peek() != "}":
                key = reader.value()
                reader.char(":")
                if key in ("spells", "effects", "baseline_effects"):
                    reader.char("{")
                    while reader.peek() != "}":
                        reader.value()
                        reader.char(":")
                        reader.value()
                        if reader.peek() == ",":
                            reader.char(",")
                    reader.char("}")
                    value = None
                else:
                    value = reader.value()
                if key == "activation_policy":
                    policy = value["enabled_monsters"]
                    break
                if reader.peek() == ",":
                    reader.char(",")
    owners = collections.defaultdict(set)
    contexts = collections.defaultdict(list)
    effective_minigames = set()
    if a.effective_minigame_policy:
        from wakfu_server.maps.monster_minigame_policy import (
            effective_minigame_references,
        )

        effective_minigames = set(effective_minigame_references())
    for ref, job in requested.items():
        if ref not in native or ref in effective_minigames:
            continue
        m = native[ref]
        published = policy.get(str(ref))
        intervals = job.get("uncovered_ranges") or [[m["min_level"], m["max_level"]]]
        intervals = [[max(1, lo), hi] for lo, hi in intervals if hi >= max(1, lo)]
        if published:
            intervals = [
                [max(lo, published["max_level"] + 1), hi]
                for lo, hi in intervals
                if hi > published["max_level"]
            ]
        if not intervals or job.get("group") in (
            "blocked_native_minigame",
            "verified_implemented_class_only_ordinary_wild_excluded",
        ):
            continue
        for ability in m["abilities"]:
            spell = str(ability["spell_id"])
            owners[spell].add(ref)
            contexts[spell].append(
                {
                    "ref": ref,
                    "native_actor_ranges": intervals,
                    "native_level_parameter": ability["level_parameter"],
                    "native_effective_spell_level_range": ability[
                        "effective_level_range"
                    ],
                    "actor_levels_not_deduplicated_or_clamped": True,
                }
            )
    effects = {}
    spells = {}
    states = {}
    areas = {}
    for path in [a.states, *a.trees, a.area_effects, a.areas]:
        for section, key, row in records(
            path, {"spells", "states", "effects", "baseline_effects", "areas"}
        ):
            if section in ("effects", "baseline_effects"):
                family = row["effect_class"]
                position = 2 if family == 649 else 0
                refs = (
                    {
                        str(values[position])
                        for values in row.get("parameters_by_level", [])
                        if len(values) > position
                        and type(values[position]) is int
                        and values[position] > 0
                    }
                    if family in (304, 321, 315, 426, 649)
                    else set()
                )
                effects[key] = {
                    "family": family,
                    "children": set(map(str, row.get("children", []))),
                    "references": refs,
                    "criteria": row.get("criteria", ""),
                }
            elif section == "spells":
                spells[key] = roots(row)
            elif section == "states":
                states[key] = roots(row)
            else:
                areas[key] = roots(row)
    casting = {}
    for _, key, row in records(a.casting, {"spells"}):
        if key in owners:
            casting[key] = {
                "criterion": row.get("cast_criterion_raw", ""),
                "costs": sorted(
                    {tuple(v) for v in row.get("costs", []) if isinstance(v, list)}
                ),
                "ranges": sorted(
                    {tuple(v[:2]) for v in row.get("levels", []) if isinstance(v, list)}
                ),
                "flags": {
                    k: row.get(k)
                    for k in (
                        "allow_self",
                        "free_cell",
                        "linear",
                        "diagonal",
                        "line_of_sight",
                    )
                },
                "maximum_level": row.get("maximum_level"),
            }
    blocks = {}
    spell_index = {}
    supported = supported_families(load(a.registry), load(a.setters))
    missing_nodes = []

    def add(key, kind, spell, dependency):
        block = blocks.setdefault(
            key,
            {
                "block_id": key,
                "kind": kind,
                "spell_ids": set(),
                "refs": set(),
                "effect_ids": set(),
                "effect_families": set(),
                "predicate_signature": None,
                "static_dependency_not_observed_failure": True,
                "actual_pending_case_keys": set(),
                "actual_validated_case_keys": set(),
                "native_source_witness_case_keys": set(),
            },
        )
        block["spell_ids"].add(int(spell))
        block["refs"].update(owners.get(spell, ()))
        block["effect_ids"].update(dependency.get("effects", []))
        block["effect_families"].update(dependency.get("families", []))
        block["predicate_signature"] = dependency.get(
            "predicate", block["predicate_signature"]
        )
        return block

    for spell in sorted(owners, key=int):
        todo = [("effect", key) for key in spells.get(spell, set())]
        seen = set()
        effect_ids = set()
        families = set()
        while todo:
            kind, key = todo.pop()
            if (kind, key) in seen:
                continue
            seen.add((kind, key))
            if kind == "effect":
                row = effects.get(key)
                if row is None:
                    missing_nodes.append(
                        {"spell_id": int(spell), "missing_effect": key}
                    )
                    continue
                effect_ids.add(int(key))
                families.add(row["family"])
                todo.extend(("effect", v) for v in row["children"])
                namespace = dependency_namespace(row["family"])
                if namespace:
                    todo.extend((namespace, v) for v in row["references"])
            else:
                source = {"state": states, "spell": spells, "area": areas}[kind]
                if key not in source:
                    missing_nodes.append(
                        {
                            "spell_id": int(spell),
                            "missing_kind": kind,
                            "missing_id": key,
                        }
                    )
                todo.extend(("effect", v) for v in source.get(key, set()))
        spell_index[spell] = {
            "spell_id": int(spell),
            "refs": sorted(owners[spell]),
            "effect_ids": sorted(effect_ids),
            "effect_families": sorted(families),
            "resolved_native_level_contexts": contexts[spell],
            "casting": casting.get(spell),
            "runtime_registered_families": sorted(families & supported),
            "runtime_missing_families": sorted(families - supported),
            "registration_not_execution_proof": True,
        }
        for family in families:
            add(
                f"family:{family}",
                "source_consumer_gap"
                if family == 803
                else "handler_missing"
                if family not in supported
                else "effect_family_dependency",
                spell,
                {"effects": effect_ids, "families": [family]},
            )
        for effect_id in effect_ids:
            for name, signature in predicate_signatures(
                effects[str(effect_id)]["criteria"]
            ):
                add(
                    "predicate:" + signature,
                    "condition_witness_dependency",
                    spell,
                    {
                        "predicate": signature,
                        "effects": [effect_id],
                        "families": [effects[str(effect_id)]["family"]],
                    },
                )
        table = casting.get(spell, {})
        for name, signature in predicate_signatures(table.get("criterion", "")):
            add(
                "predicate:" + signature,
                "condition_witness_dependency",
                spell,
                {"predicate": signature, "effects": effect_ids, "families": families},
            )
        if any(lo == hi == 0 for lo, hi in table.get("ranges", [])):
            add(
                "selector:zero_range_native",
                "selector_context_dependency",
                spell,
                {"effects": effect_ids, "families": families},
            )
        for cost in table.get("costs", []):
            if len(cost) == 3 and cost[2] > 0:
                add(
                    "resource:native_wp_cost:" + str(cost[2]),
                    "resource_producer_or_expected_guard_dependency",
                    spell,
                    {"effects": effect_ids, "families": families},
                )
    cache = []
    receipt_contexts = {}
    for receipt_path in a.receipt:
        receipt = load(receipt_path)
        digest = sha(receipt_path)
        context = {
            "receipt": str(receipt_path.resolve()),
            "sha256": digest,
            "schema": receipt.get("schema"),
            "source_root": receipt.get("source_root"),
            "candidate_manifest_sha256": receipt.get("candidate_manifest_sha256"),
            "source_sha256": receipt.get("source_sha256"),
            "sources_stable": receipt.get("sources_stable"),
            "wrappers_stable": receipt.get("wrappers_stable"),
            "qualification_scope": receipt.get("qualification_scope"),
            "exhaustive_all_levels_execution": receipt.get(
                "exhaustive_all_levels_execution", False
            ),
        }
        context["original_source_and_catalog_bindings"] = {
            k: v
            for k, v in receipt.items()
            if ("sha256" in k or k.endswith("_stable")) and k not in context
        }
        receipt_contexts[digest] = context
        receipt_rows = receipt.get("rows", receipt.get("monsters", []))
        if receipt.get("schema") == "monster-effect-work-qualification-v1":
            receipt_rows = [
                {"reference": item["context"]["reference"], "cases": [item]}
                for item in receipt["cases"]
            ]
        if receipt.get("schema") == "historical-native-context-source-reuse-audit-v1":
            receipt_rows = []
            originals = {}
            for result in receipt["results"]:
                if result.get("source_equivalence_verified") is not True:
                    continue
                authority = result["original_receipt"]
                path = Path(authority["receipt"])
                if sha(path) != authority["sha256"]:
                    raise ValueError("Original historical receipt hash mismatch")
                original = originals.setdefault(str(path), load(path))
                value = original
                for component in authority["json_pointer"].strip("/").split("/"):
                    value = (
                        value[int(component)]
                        if isinstance(value, list)
                        else value[component]
                    )
                raw = value.get("raw_case", value)
                receipt_rows.append(
                    {
                        "reference": result["context"]["reference"],
                        "cases": [{"raw_case": raw, "original_authority": authority}],
                    }
                )
        for ri, row in enumerate(receipt_rows):
            ref = row.get("reference", row.get("ref"))
            for ci, wrapped in enumerate(row.get("cases", [])):
                case = wrapped.get("raw_case", wrapped)
                spell = str(case["spell_id"])
                key = hashlib.sha256(
                    json.dumps(
                        [
                            digest,
                            ref,
                            case.get("level"),
                            case["spell_id"],
                            case.get("spell_level"),
                        ]
                    ).encode()
                ).hexdigest()
                entry = {
                    "proof_key": key,
                    "context_ref": digest,
                    "reference": ref,
                    "actor_level": case.get("level"),
                    "spell_id": case["spell_id"],
                    "spell_level": case.get("spell_level"),
                    "status": case.get("status"),
                    "availability": wrapped.get("availability"),
                    "native_initialization_receipts": case.get(
                        "initialization_receipts", []
                    ),
                    "errors": case.get("errors", {}),
                    "original_json_pointer": (
                        f"/results/{ri}"
                        if receipt.get("schema")
                        == "historical-native-context-source-reuse-audit-v1"
                        else f"/cases/{ri}"
                        if receipt.get("schema")
                        == "monster-effect-work-qualification-v1"
                        else f"/{'rows'if 'rows'in receipt else'monsters'}/{ri}/cases/{ci}"
                    ),
                    "original_authority": wrapped.get("original_authority"),
                    "no_source_or_level_rebinding": True,
                }
                cache.append(entry)
                dependency = spell_index.get(spell, {})
                for block in blocks.values():
                    if int(spell) in block["spell_ids"]:
                        block[
                            "actual_validated_case_keys"
                            if case.get("status") == "validated"
                            else "native_source_witness_case_keys"
                            if case.get("status")
                            in (
                                "passive_initialization_only",
                                "native_zero_amount_unavailable",
                            )
                            else "actual_pending_case_keys"
                        ].add(key)
                if case.get("status") not in (
                    "validated",
                    "passive_initialization_only",
                    "native_zero_amount_unavailable",
                ):
                    for error in case.get("errors", {}) or [
                        "no_effectful_native_execution"
                    ]:
                        block = add(
                            "observed:" + error,
                            "observed_diagnostic",
                            spell,
                            {
                                "effects": dependency.get("effect_ids", []),
                                "families": dependency.get("effect_families", []),
                            },
                        )
                        block["static_dependency_not_observed_failure"] = False
                        block["actual_pending_case_keys"].add(key)
    unique = {entry["proof_key"]: entry for entry in cache}
    cache = list(unique.values())
    for index_path in a.block_index:
        external = load(index_path)
        for item in external.get("work_blocks", []):
            selected = set(item["spell_ids"]) & set(map(int, owners))
            for spell_id in selected:
                block = add(
                    "verified:" + item["block_id"], item["kind"], str(spell_id), {}
                )
                block["static_dependency_not_observed_failure"] = False
                block["evidence"] = {
                    "path": str(index_path.resolve()),
                    "sha256": sha(index_path),
                    "status": item["status"],
                    "source_evidence": item.get("source_evidence"),
                }
                block["actual_blocked_spell_count"] = len(selected)
    for block in blocks.values():
        for field in (
            "spell_ids",
            "refs",
            "effect_ids",
            "effect_families",
            "actual_pending_case_keys",
            "actual_validated_case_keys",
            "native_source_witness_case_keys",
        ):
            block[field] = sorted(block[field])
        block["unique_spell_count"] = len(block["spell_ids"])
        block["reference_count"] = len(block["refs"])
        block["actual_pending_case_count"] = len(block["actual_pending_case_keys"])
        block.setdefault(
            "actual_blocked_spell_count",
            len(
                {
                    entry["spell_id"]
                    for entry in cache
                    if entry["proof_key"] in block["actual_pending_case_keys"]
                }
            ),
        )
        block["unlock_count_is_projection_not_qualification"] = True
        block["single_fix_unlock_count"] = None
    diagnostics = [b for b in blocks.values() if b["kind"] == "observed_diagnostic"]
    diagnostics.sort(key=lambda b: (-b["actual_blocked_spell_count"], b["block_id"]))
    priority = [
        b
        for b in blocks.values()
        if b["kind"]
        in (
            "source_consumer_gap",
            "handler_missing",
            "verified_runtime_gap",
            "qualification_pending",
            "observed_summon_block",
        )
    ]
    priority.sort(
        key=lambda b: (
            -b.get(
                "actual_blocked_spell_count",
                len(
                    {
                        e["spell_id"]
                        for e in cache
                        if e["proof_key"] in b["actual_pending_case_keys"]
                    }
                ),
            ),
            -b["unique_spell_count"],
            b["block_id"],
        )
    )
    if a.initial_lifecycle_output:
        from monster_initial_lifecycle_index import build_initial_lifecycle_index

        if a.initial_lifecycle_output.exists():
            raise ValueError("Lifecycle output must be new")
        lifecycle = build_initial_lifecycle_index(
            [native[ref] for ref in requested if ref in native],
            effects,
            states,
            spells,
            areas,
            supported,
        )
        lifecycle["input_sha256"] = {
            str(path.resolve()): sha(path)
            for path in [
                a.inventory,
                a.states,
                a.areas,
                a.area_effects,
                *a.trees,
                Path(__file__),
                Path(__file__).with_name("monster_initial_lifecycle_index.py"),
            ]
        }
        a.initial_lifecycle_output.write_text(
            json.dumps(lifecycle, separators=(",", ":")) + "\n"
        )
    a.output.mkdir()
    inputs = [
        a.inventory,
        a.areas,
        a.area_effects,
        a.states,
        a.casting,
        a.pending_reference_queue,
        a.registry,
        a.setters,
        *a.trees,
        *a.receipt,
        *a.block_index,
        Path(__file__),
    ]
    inputs += [a.published_policy] if a.published_policy else []
    result = {
        "schema": "monster-effect-spell-work-index-v1",
        "unique_spell_count": len(spell_index),
        "reference_count": len({ref for refs in owners.values() for ref in refs}),
        "blocks": list(blocks.values()),
        "spell_index": spell_index,
        "actual_case_cache": cache,
        "receipt_contexts": receipt_contexts,
        "deduplicated_actual_case_count": len(cache),
        "missing_source_nodes": missing_nodes,
        "runtime_registered_family_count": len(supported),
        "effective_minigame_references": sorted(effective_minigames),
        "source_gap803_separate": True,
        "top10": priority[:10],
        "diagnostic_triage": diagnostics,
        "diagnostic_codes_not_causal_unlock_groups": True,
        "input_sha256": {str(path.resolve()): sha(path) for path in inputs},
        "static_fanout_not_execution_qualification": True,
        "engines_executed": False,
        "database_reads_or_exports": False,
    }
    (a.output / "index.json").write_text(
        json.dumps(result, separators=(",", ":")) + "\n"
    )
    (a.output / "top10.json").write_text(json.dumps(result["top10"], indent=2) + "\n")
    print(
        json.dumps(
            {
                "unique_spells": len(spell_index),
                "refs": result["reference_count"],
                "actual_cases": len(cache),
                "blocks": len(blocks),
                "top10": [
                    (b["block_id"], b["unique_spell_count"], b["reference_count"])
                    for b in priority[:10]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
