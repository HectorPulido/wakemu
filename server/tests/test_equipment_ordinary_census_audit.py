"""Read-only finite ordinary-template census, never an equipability assertion."""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import unittest


class OrdinaryEquipmentCensusAudit(unittest.TestCase):
    def test_collect_all_ordinary_equipment_static_sources(self):
        from wakfu_server import (
            native_catalog,
            equipment_stats,
            inventory_elements,
            equipment_conditions,
        )
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_characteristics import native_rows
        from wakfu_server.combat_local_criteria import parse_local_criterion
        from wakfu_server.empty_equipment_effects import template as empty_template

        with native_catalog._database().connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            pets = {
                r["reference"]: dict(r)
                for r in db.execute("SELECT * FROM native_pet_models")
            }
            mounts = {
                r["reference"]: dict(r)
                for r in db.execute("SELECT * FROM mount_models")
            }
        conditions, native_pc = equipment_conditions.catalog(), native_rows()
        counters, families, unsupported_refs, errors = (
            Counter(),
            defaultdict(set),
            set(),
            [],
        )
        unsupported_patterns, condition_patterns, condition_functions = (
            Counter(),
            Counter(),
            defaultdict(set),
        )
        summaries = []
        for reference, rule in sorted(RULES.items()):
            counters["ordinary_rule_templates"] += 1
            counters["missing_equipment_condition_catalog_rows"] += (
                str(reference) not in conditions
            )
            if not rule["slots"]:
                errors.append(
                    dict(reference=reference, phase="slots", error="No native slot")
                )
                continue
            template = equipment_stats.CATALOG.get(reference)
            if template is None:
                template = empty_template(reference)
                counters[
                    "recovered_empty_templates"
                    if template is not None
                    else "missing_templates"
                ] += 1
            passive = (
                []
                if template is None
                else [
                    e
                    for e in template["effects"]
                    if e.get("native_variant") == 0
                    and e.get("native_active_effect") is False
                ]
            )
            counters["unknown_passive_identity_roots"] += (
                0
                if template is None
                else sum(
                    type(e.get("native_variant")) is not int
                    or type(e.get("native_active_effect")) is not bool
                    for e in template["effects"]
                )
            )
            counters["passive_root_occurrences"] += len(passive)
            counters["active_root_occurrences"] += (
                0 if template is None else len(template["effects"]) - len(passive)
            )
            counters["templates_with_passive_roots"] += bool(passive)
            item = dict(uid=101, character_id=7, reference=reference, quantity=1)
            selection = None
            try:
                selection = inventory_elements.create(reference)
                if selection is not None:
                    for effect in template["effects"]:
                        if effect["generic"] in inventory_elements.FIELDS:
                            count = int(effect["params"][2])
                            selection[
                                inventory_elements.FIELDS[effect["generic"]]
                            ] = sum(1 << e for e in range(1, count + 1))
                    inventory_elements.masks(selection)
                    item.update(selection)
                    counters["templates_with_native_element_choices"] += 1
            except ValueError as exc:
                errors.append(
                    dict(reference=reference, phase="element-options", error=str(exc))
                )
                continue
            variants = [(None, dict(item))]
            if reference in pets:
                model = pets[reference]
                variants = []
                for rank in sorted({0, model["maximum_level"]}):
                    typed = dict(
                        item,
                        pet=dict(
                            model_id=model["model_id"],
                            xp=rank * model["xp_per_level"],
                            xp_per_level=model["xp_per_level"],
                            maximum_level=model["maximum_level"],
                            health=model["maximum_health"],
                            sleep_item_ref=0,
                            sleep_date=0,
                        ),
                    )
                    variants.append((rank, typed))
                counters["native_pet_templates"] += 1
            elif reference in mounts:
                model = mounts[reference]
                variants = [
                    (
                        rank,
                        dict(
                            item,
                            mount=dict(
                                model_id=model["model_id"],
                                xp=rank * model["xp_per_level"],
                            ),
                        ),
                    )
                    for rank in sorted({0, model["maximum_level"]})
                ]
                counters["native_mount_templates"] += 1
            by_level, all_bad = [], {}
            for rank, typed in variants:
                character = dict(
                    id=7,
                    account_id=9,
                    breed=8,
                    level=245,
                    active_build_index=0,
                    builds={},
                    inventory_items=[typed],
                )
                entries = [dict(uid=101, slot=rule["slots"][0])]
                try:
                    result = equipment_stats.bonuses(
                        character, _selected_entries=entries
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(
                        dict(
                            reference=reference,
                            phase="static-bonuses",
                            native_pet_level=rank,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
                    continue
                counters["typed_static_cases"] += 1
                for row in result["unsupported"]:
                    effect = next(
                        (e for e in passive if e["id"] == row.get("effect_id")), {}
                    )
                    detail = dict(
                        row,
                        runner=effect.get("runner"),
                        parameters=effect.get("params"),
                        values=effect.get("values"),
                        effect_criteria=effect.get("effect_criteria"),
                        has_triggers=effect.get("has_triggers"),
                        target_mask=effect.get("target_mask"),
                    )
                    all_bad[(row.get("effect_id"), row["reason"])] = detail
                by_level.append(
                    dict(
                        native_pet_level=rank,
                        unsupported_count=len(result["unsupported"]),
                    )
                )
            if all_bad:
                unsupported_refs.add(reference)
                for row in all_bad.values():
                    key = (row.get("generic"), row.get("runner"), row["reason"])
                    unsupported_patterns[key] += 1
                    families[key].add(reference)
            criterion = conditions.get(str(reference), {}).get("EQUIP")
            condition_error = None
            if criterion:
                condition_patterns[criterion] += 1
                try:
                    tree = parse_local_criterion(criterion)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(
                            node.func, ast.Name
                        ):
                            condition_functions[node.func.id].add(reference)
                    equipment_conditions.evaluate(
                        criterion,
                        item=item,
                        selected=[dict(uid=101, slot=rule["slots"][0])],
                        owned={101: item},
                        current_characteristics={
                            pc: r["current"] for pc, r in native_pc.items() if pc > 0
                        },
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    condition_error = f"{type(exc).__name__}: {exc}"
                    counters["condition_context_or_grammar_rejected_templates"] += 1
            if all_bad or condition_error:
                summaries.append(
                    dict(
                        reference=reference,
                        name=None if template is None else template.get("name"),
                        native_slots=rule["slots"],
                        native_minimum_level=rule["minimum_level"],
                        native_pet=reference in pets,
                        native_mount=reference in mounts,
                        native_element_selection=selection,
                        cases=by_level,
                        passive_roots=[
                            dict(id=e["id"], generic=e["generic"], runner=e["runner"])
                            for e in passive
                        ],
                        unsupported=list(all_bad.values()),
                        equip_criterion=criterion,
                        condition_error=condition_error,
                    )
                )
        counters["static_templates_with_unsupported"] = len(unsupported_refs)
        counters["native_equipment_condition_templates"] = sum(
            condition_patterns.values()
        )
        summary = dict(
            counts=dict(counters),
            native_release=native_catalog.release(),
            source_hashes={
                module.__name__: hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest()
                for module in (
                    equipment_stats,
                    equipment_conditions,
                    inventory_elements,
                )
            },
            unsupported_families=[
                dict(
                    generic=k[0],
                    runner=k[1],
                    reason=k[2],
                    root_occurrences=n,
                    item_references=len(families[k]),
                    examples=sorted(families[k])[:10],
                )
                for k, n in unsupported_patterns.most_common()
            ],
            equip_condition_functions=[
                dict(name=name, item_references=len(refs), examples=sorted(refs)[:10])
                for name, refs in sorted(condition_functions.items())
            ],
            condition_expression_counts=dict(condition_patterns),
            fixture_errors=errors,
        )
        directory = Path(".runtime/equipment-ordinary-census-20261020")
        directory.mkdir(exist_ok=True)
        (directory / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        )
        (directory / "unsupported-items.json").write_text(
            json.dumps(summaries, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            "ORDINARY_EQUIPMENT_CENSUS",
            json.dumps(dict(counters)),
            "fixture_errors",
            len(errors),
        )

    def test_classify_existing_ready_roles_for_census(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.combat_equipment_snapshot_roles import native_relic_aura
        from wakfu_server.combat_owned_equipment import (
            compiled_with_sources,
            ordinary_turn_state_contract,
        )
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.equipment_stats import CATALOG

        directory = Path(".runtime/equipment-ordinary-census-20261020")
        census = json.loads((directory / "unsupported-items.json").read_text())
        native, compiled, registry = (
            native_copied_equipment_catalog(),
            compiled_runtime_catalog(),
            characteristic_registry(),
        )
        roots, reasons, states, aura = [], Counter(), defaultdict(set), []
        for row in census:
            reference = row["reference"]
            failures = row["unsupported"]
            for failure in failures:
                if failure.get("generic") == 400 and native_relic_aura(
                    reference, failure["effect_id"]
                ):
                    aura.append(
                        dict(reference=reference, effect_id=failure["effect_id"])
                    )
            if not any(f.get("generic") == 304 for f in failures):
                continue
            plan = copied_equipment_plan(reference, native)
            selected = [
                e
                for e in plan["roots"]
                if e["effect_class"] == 304
                and e["variant"] == 0
                and e["metadata"]["native_active_effect"] is False
            ]
            source = dict(
                uid=101,
                reference=reference,
                source_reference=reference,
                attachment_field=None,
                roots=tuple(e["reference"] for e in selected),
                effects=equipment_effect_definitions(dict(roots=selected)),
                native_retained_container=plan["native_retained_container"],
            )
            source["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                reference, plan, source["roots"], templates=CATALOG
            )
            try:
                extended = compiled_with_sources(compiled, [source])
                reason = ordinary_turn_state_contract(source, extended, registry)
                graph_reason = ordinary_turn_state_contract(
                    dict(source, unplanned_passive_effect_ids=[]), extended, registry
                )
                applications = []
                for identity in source["roots"]:
                    effect = extended.effects[str(identity)]
                    values = effect_profile(
                        effect, plan["native_retained_container"]["level"]
                    )["parameters"]
                    if values:
                        states[values[0]].add(reference)
                        definition = extended.source_states["states"].get(
                            str(values[0]), {}
                        )
                        applications.append(
                            dict(
                                root=identity,
                                parameters=values,
                                state_name=definition.get("name"),
                                state_roots=definition.get("effect_ids", ()),
                            )
                        )
            except (ValueError, KeyError, TypeError) as exc:
                reason = graph_reason = f"{type(exc).__name__}: {exc}"
                applications = []
            reasons[reason or "qualified-existing-ready-role"] += 1
            roots.append(
                dict(
                    reference=reference,
                    unplanned_passive_effect_ids=source["unplanned_passive_effect_ids"],
                    existing_ready_contract_reason=reason,
                    isolated_graph_contract_reason=graph_reason,
                    applications=applications,
                )
            )
        output = dict(
            state_template_count=len(roots),
            existing_ready_qualified=sum(
                r["existing_ready_contract_reason"] is None for r in roots
            ),
            isolated_state_graph_qualified=sum(
                r["isolated_graph_contract_reason"] is None for r in roots
            ),
            known_relic_aura_roots=len(aura),
            known_relic_aura_items=len({r["reference"] for r in aura}),
            reason_counts=dict(reasons),
            known_relic_auras=aura,
            common_state_applications=[
                dict(state_id=identity, items=len(refs), examples=sorted(refs)[:10])
                for identity, refs in sorted(states.items(), key=lambda v: -len(v[1]))
            ],
            items=roots,
        )
        (directory / "existing-ready-role-summary.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            "EXISTING_READY_ROLE_CENSUS",
            {
                k: v
                for k, v in output.items()
                if k
                not in (
                    "items",
                    "reason_counts",
                    "common_state_applications",
                    "known_relic_auras",
                )
            },
        )

    def test_group_remaining_state_and_visual_contract_shapes(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_definitions import effect_profile

        directory = Path(".runtime/equipment-ordinary-census-20261020")
        remaining = json.loads(
            (directory / "remaining-after-known-roles.json").read_text()
        )["items"]
        native, compiled = native_copied_equipment_catalog(), compiled_runtime_catalog()
        states, visuals = [], []

        def describe(identity, definition, rank):
            hmi = definition.get("native_hmi_actions", {})
            return dict(
                reference=identity,
                family=definition["effect_class"],
                level=rank,
                parameters=definition["parameters"],
                values=effect_profile(definition, rank)["parameters"],
                criterion=definition.get("criteria"),
                children=definition.get("children", ()),
                selector=definition.get("native_target_selector"),
                area=definition.get("area_native"),
                definition_class=definition.get("native_definition_class"),
                flags=definition.get("native_effect_flags"),
                timing=definition.get("native_timing_definition"),
                application=definition.get("application_flag"),
                removal=definition.get("removal_flag"),
                masks=definition.get("target_masks"),
                hmi=hmi,
                hmi_types=sorted(
                    {action["type"] for rows in hmi.values() for action in rows}
                ),
            )

        for row in remaining:
            ref = row["reference"]
            relevant = [
                u
                for u in row["remaining_unsupported"]
                if u.get("generic") in (304, 400)
            ]
            if not relevant:
                continue
            plan = copied_equipment_plan(ref, native)
            definitions = equipment_effect_definitions(plan)
            source = dict(effects=definitions)
            extended = compiled_with_sources(compiled, [source])
            nominal_level = plan["native_retained_container"]["level"]
            for unsupported in relevant:
                if unsupported["generic"] == 400:
                    visuals.append(
                        dict(
                            item_reference=ref,
                            name=row["name"],
                            effect=describe(
                                unsupported["effect_id"],
                                definitions[str(unsupported["effect_id"])],
                                nominal_level,
                            ),
                        )
                    )
            if not any(u["generic"] == 304 for u in relevant):
                continue
            pending = [
                (u["effect_id"], nominal_level) for u in relevant if u["generic"] == 304
            ]
            seen, seen_states, nodes, definitions_by_state = set(), set(), [], {}
            failures = []
            while pending:
                identity, rank = pending.pop()
                if (identity, rank) in seen:
                    continue
                seen.add((identity, rank))
                try:
                    effect = extended.effects[str(identity)]
                    detail = describe(identity, effect, rank)
                    nodes.append(detail)
                    pending.extend(
                        (child, rank) for child in effect.get("children", ())
                    )
                    if effect["effect_class"] == 304:
                        params = detail["values"]
                        if len(params) < 2:
                            continue
                        state_id, state_rank = params[:2]
                        if (state_id, state_rank) in seen_states:
                            continue
                        seen_states.add((state_id, state_rank))
                        state = extended.source_states["states"][str(state_id)]
                        definitions_by_state[str(state_id)] = {
                            k: v
                            for k, v in state.items()
                            if k
                            in (
                                "name",
                                "maximum_level",
                                "clock_actor",
                                "tick_at_turn_end",
                                "additive",
                                "replace",
                                "refresh",
                                "protected",
                                "duration_base",
                                "duration_per_level",
                                "realtime_duration_base",
                                "realtime_duration_per_level",
                                "skip_turn_timer",
                                "effect_ids",
                            )
                        }
                        pending.extend(
                            (child, state_rank) for child in state["effect_ids"]
                        )
                except (ValueError, KeyError, TypeError) as exc:
                    failures.append(
                        dict(reference=identity, level=rank, error=str(exc))
                    )
            states.append(
                dict(
                    item_reference=ref,
                    name=row["name"],
                    equip_criterion=row["equip_criterion"],
                    families=dict(Counter(n["family"] for n in nodes)),
                    hmi_types=sorted({kind for n in nodes for kind in n["hmi_types"]}),
                    criteria=sorted({n["criterion"] for n in nodes if n["criterion"]}),
                    nodes=nodes,
                    states=definitions_by_state,
                    traversal_failures=failures,
                )
            )
        result = dict(
            note="Nominal native source/state-level traversal; dynamic child-group level domains are not execution qualification",
            state_items=states,
            visual_items=visuals,
            state_family_patterns=[
                dict(families=list(key), items=count)
                for key, count in Counter(
                    tuple(sorted(r["families"])) for r in states
                ).most_common()
            ],
            state_hmi_patterns=[
                dict(types=list(key), items=count)
                for key, count in Counter(
                    tuple(r["hmi_types"]) for r in states
                ).most_common()
            ],
            visual_hmi_patterns=[
                dict(types=list(key), items=count)
                for key, count in Counter(
                    tuple(r["effect"]["hmi_types"]) for r in visuals
                ).most_common()
            ],
        )
        (directory / "remaining-state-visual-shapes.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            "REMAINING_STATE_VISUAL_SHAPES",
            len(states),
            len(visuals),
            result["state_hmi_patterns"],
            result["visual_hmi_patterns"],
        )

    def test_measure_cosmetic_flag_only_contract_difference(self):
        from collections import ChainMap
        from types import SimpleNamespace
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_equipment_null_carrier_contract import (
            permanent_null_carrier_contract,
        )
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry

        directory = Path(".runtime/equipment-ordinary-census-20261020")
        data = json.loads(
            (directory / "remaining-state-visual-shapes.json").read_text()
        )
        candidates = [
            r
            for r in data["state_items"]
            if set(r["families"]) == {"304", "400"}
            and set(r["hmi_types"]) <= {"COSTUME", "SKIN_PART_VISIBILITY"}
        ]
        native, compiled, registry = (
            native_copied_equipment_catalog(),
            compiled_runtime_catalog(),
            characteristic_registry(),
        )
        result = []
        for candidate in candidates:
            ref = candidate["item_reference"]
            plan = copied_equipment_plan(ref, native)
            selected = [
                r
                for r in plan["roots"]
                if r["effect_class"] == 304
                and r["variant"] == 0
                and r["metadata"]["native_active_effect"] is False
            ]
            source = dict(
                reference=ref,
                attachment_field=None,
                roots=tuple(r["reference"] for r in selected),
                effects=equipment_effect_definitions(dict(roots=selected)),
                native_retained_container=plan["native_retained_container"],
            )
            extended = compiled_with_sources(compiled, [source])
            overrides = {}
            for node in candidate["nodes"]:
                if node["family"] == 400 and node["flags"] == [17]:
                    effect = extended.effects[str(node["reference"])]
                    overrides[str(node["reference"])] = dict(
                        effect, native_effect_flags=[15]
                    )
            shadow = SimpleNamespace(
                effects=ChainMap(overrides, extended.effects),
                source_states=extended.source_states,
            )
            result.append(
                dict(
                    reference=ref,
                    original_reason=permanent_null_carrier_contract(
                        source, extended, registry
                    ),
                    hypothetical_flags15_only_reason=permanent_null_carrier_contract(
                        source, shadow, registry
                    ),
                    changed_child_effect_ids=[int(key) for key in overrides],
                )
            )
        (directory / "cosmetic-flag-only-difference.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(
            "COSMETIC_FLAG_ONLY_DIFFERENCE",
            len(result),
            "qualified_after_only_hypothetical_flag_change",
            sum(r["hypothetical_flags15_only_reason"] is None for r in result),
        )
