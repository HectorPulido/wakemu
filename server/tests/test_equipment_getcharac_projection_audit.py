"""Read-only finite projection audit; generated failures are coverage, not grants."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest


class EquipmentGetCharacProjectionAudit(unittest.TestCase):
    def test_collect_all_native_getcharac_projections_with_valid_typed_options(self):
        from wakfu_server import (
            equipment_conditions,
            equipment_stats,
            inventory_elements,
        )
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_eligibility import _projection
        from wakfu_server import native_catalog

        with native_catalog._database().connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            pets = {
                row["reference"]: dict(row)
                for row in db.execute("SELECT * FROM native_pet_models")
            }
            mounts = {
                row["reference"]: dict(row)
                for row in db.execute("SELECT * FROM mount_models")
            }
        cohort = [
            (int(ref), row["EQUIP"])
            for ref, row in equipment_conditions.catalog().items()
            if "GetCharac(" in row.get("EQUIP", "")
        ]
        self.assertEqual(len(cohort), 133)
        findings = []
        for reference, criterion in cohort:
            template = equipment_stats.CATALOG[reference]
            item = dict(uid=101, character_id=7, reference=reference, quantity=1)
            selection = inventory_elements.create(reference)
            if selection is not None:
                for effect in template["effects"]:
                    if effect["generic"] not in inventory_elements.FIELDS:
                        continue
                    count = int(effect["params"][2])
                    self.assertTrue(0 <= count <= 4)
                    selection[inventory_elements.FIELDS[effect["generic"]]] = sum(
                        1 << e for e in range(1, count + 1)
                    )
                inventory_elements.masks(selection)
                item.update(selection)
            if reference in pets:
                model = pets[reference]
                item["pet"] = dict(
                    model_id=model["model_id"],
                    xp=0,
                    xp_per_level=model["xp_per_level"],
                    maximum_level=model["maximum_level"],
                    health=model["maximum_health"],
                    sleep_item_ref=0,
                    sleep_date=0,
                )
            elif reference in mounts:
                model = mounts[reference]
                item["mount"] = dict(model_id=model["model_id"], xp=0)
            character = dict(
                id=7,
                account_id=9,
                breed=8,
                level=230,
                active_build_index=0,
                builds={},
                inventory_items=[item],
            )
            entries = [dict(uid=101, slot=RULES[reference]["slots"][0])]
            result = equipment_stats.bonuses(character, _selected_entries=entries)
            unsupported = []
            for row in result["unsupported"]:
                effect = next(
                    (e for e in template["effects"] if e["id"] == row.get("effect_id")),
                    {},
                )
                unsupported.append(
                    dict(
                        row,
                        runner=effect.get("runner"),
                        params=effect.get("params"),
                        values=effect.get("values"),
                        effect_criteria=effect.get("effect_criteria"),
                    )
                )
            error = None
            try:
                _projection(character, entries)
            except ValueError as exc:
                error = str(exc)
            findings.append(
                dict(
                    reference=reference,
                    name=template.get("name"),
                    criterion=criterion,
                    selected_slot=entries[0]["slot"],
                    selected_masks=selection,
                    pet=reference in pets,
                    mount=reference in mounts,
                    stat_operations=result["stat_operations"],
                    unsupported=unsupported,
                    projection_error=error,
                )
            )
        counts = Counter(
            (row["runner"], row.get("generic"))
            for item in findings
            for row in item["unsupported"]
        )
        summary = dict(
            cohort=len(findings),
            projection_ok=sum(r["projection_error"] is None for r in findings),
            unsupported_items=sum(bool(r["unsupported"]) for r in findings),
            pets=sum(r["pet"] for r in findings),
            mounts=sum(r["mount"] for r in findings),
            families=[
                dict(runner=key[0], generic=key[1], occurrences=count)
                for key, count in sorted(counts.items(), key=str)
            ],
        )
        files = [Path(equipment_conditions.__file__), Path(equipment_stats.__file__)]
        output = Path(".runtime/equipment-getcharac-20261020/projection-audit.json")
        output.write_text(
            json.dumps(
                dict(
                    summary=summary,
                    fixtures="owned-style; no live character grants or writes",
                    native_release=native_catalog.release(),
                    source_hashes={
                        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in files
                    },
                    items=findings,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        print("READONLY_PROJECTION_AUDIT", json.dumps(summary), output)

    def test_collect_published_literal_false_equipment_roots(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server import equipment_stats

        catalog = native_copied_equipment_catalog()
        self.assertIs(catalog["complete"], True)
        literal = []
        for key, definition in catalog["definitions"].items():
            for root in definition["ordered_effects"]:
                if root.get("criterion_raw") == "False":
                    literal.append(dict(item_reference=int(key), effect=root))
        output = Path(
            ".runtime/equipment-getcharac-20261020/published-literal-false-roots.json"
        )
        output.write_text(
            json.dumps(
                dict(
                    producer=catalog["producer"],
                    complete=catalog["complete"],
                    definitions=len(catalog["definitions"]),
                    root_occurrences=len(literal),
                    item_references=len({r["item_reference"] for r in literal}),
                    equipment_occurrences=sum(
                        r["item_reference"] in equipment_stats.CATALOG for r in literal
                    ),
                    items=literal,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        print("PUBLISHED_LITERAL_FALSE", len(literal), output)
        print("SAMPLE", json.dumps(literal[0], ensure_ascii=False))

    def test_existing_relic_aura_classifier_matches_actual_three_roots(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_equipment_snapshot_roles import _relic_aura

        catalog = native_copied_equipment_catalog()
        findings = []
        for item_ref, effect_id in ((24095, 240698), (24114, 240822), (24361, 252647)):
            roots = catalog["definitions"][str(item_ref)]["ordered_effects"]
            root = next(r for r in roots if r["reference"] == effect_id)
            self.assertTrue(_relic_aura(root))
            self.assertIsInstance(root["criterion_raw"], str)
            self.assertNotEqual(root["criterion_raw"], "False")
            findings.append(
                dict(item_reference=item_ref, root=root, existing_classifier=True)
            )
        output = Path(
            ".runtime/equipment-getcharac-20261020/relic-aura-classifier-proof.json"
        )
        output.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
        print("EXISTING_RELIC_AURA_CLASSIFIER", len(findings), output)

    def test_collect_remaining_reactive_state_qualification(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_owned_equipment import (
            compiled_with_sources,
            ordinary_turn_state_contract,
        )
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_definitions import effect_profile, state_profile
        from wakfu_server.combat_operation_registry import assess_operation

        catalog = native_copied_equipment_catalog()
        matching = []
        for ref, definition in catalog["definitions"].items():
            for root in definition["ordered_effects"]:
                values = root.get("native_values_at_fresh_item_level", [])
                if root["effect_class"] == 304 and values and values[0] in (2636, 5886):
                    matching.append(
                        dict(
                            item_reference=int(ref),
                            root=root["reference"],
                            values=values,
                        )
                    )
        compiled = compiled_runtime_catalog()
        registry = characteristic_registry()
        rows = []
        for item_ref in sorted({r["item_reference"] for r in matching}):
            native_plan = copied_equipment_plan(item_ref, catalog)
            roots = [
                r
                for r in native_plan["roots"]
                if r["effect_class"] == 304
                and r["variant"] == 0
                and r["metadata"]["native_active_effect"] is False
            ]
            source = dict(
                uid=101,
                reference=item_ref,
                source_reference=item_ref,
                attachment_field=None,
                roots=tuple(r["reference"] for r in roots),
                effects=equipment_effect_definitions(dict(roots=roots)),
                native_retained_container=native_plan["native_retained_container"],
            )
            from wakfu_server.equipment_stats import CATALOG

            source["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                item_ref, native_plan, source["roots"], templates=CATALOG
            )
            extended = compiled_with_sources(compiled, [source])
            reason = ordinary_turn_state_contract(source, extended, registry)
            pending = [
                (r, native_plan["native_retained_container"]["level"])
                for r in source["roots"]
            ]
            state_definitions = {}
            visited, seen_states, graph = set(), set(), []
            while pending:
                ref, level = pending.pop()
                if (ref, level) in visited:
                    continue
                visited.add((ref, level))
                effect = extended.effects[str(ref)]
                profile = effect_profile(effect, level)
                support = assess_operation(effect, characteristic_registry=registry)
                graph.append(
                    dict(
                        reference=ref,
                        level=level,
                        effect_class=effect["effect_class"],
                        values=profile["parameters"],
                        criteria=effect.get("criteria"),
                        target_masks=effect.get("target_masks"),
                        native_target_selector=effect.get("native_target_selector"),
                        operation_status=support.status,
                        operation_repr=repr(support),
                        native_definition=effect,
                        children=effect.get("children", []),
                    )
                )
                pending.extend((r, level) for r in effect.get("children", []))
                if effect["effect_class"] == 304:
                    state_id, state_level = profile["parameters"][:2]
                    if (state_id, state_level) not in seen_states:
                        seen_states.add((state_id, state_level))
                        state = state_profile(
                            extended.source_states, state_id, state_level
                        )
                        state_definitions[str(state_id)] = dict(
                            definition=extended.source_states["states"][str(state_id)],
                            profile=state,
                        )
                        pending.extend((r, state_level) for r in state["effects"])
            rows.append(
                dict(
                    item_reference=item_ref,
                    source_roots=source["roots"],
                    unplanned_passive_effect_ids=source["unplanned_passive_effect_ids"],
                    qualification_reason=reason,
                    states=state_definitions,
                    graph=graph,
                )
            )
        output = Path(
            ".runtime/equipment-getcharac-20261020/reactive-state-qualification.json"
        )
        output.write_text(
            json.dumps(dict(matches=matching, items=rows), ensure_ascii=False, indent=2)
            + "\n"
        )
        print(
            "REACTIVE_STATE_QUALIFICATION",
            len(matching),
            [(r["item_reference"], r["qualification_reason"]) for r in rows],
            output,
        )
