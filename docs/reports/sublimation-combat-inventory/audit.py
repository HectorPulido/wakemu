"""Read-only inventory from pinned native catalog snapshots; no game mutation."""
import ast
from collections import Counter, defaultdict
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
PRIVATE = ROOT / ".runtime/local/sublimation-combat-inventory"
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    catalogs = json.loads((PRIVATE / "catalogs.json").read_text())
    patterns = json.loads((PRIVATE / "patterns.json").read_text())
    state_catalog = catalogs["combat-state-definitions.json"]
    native = catalogs["native-copied-equipment-definitions.json"]["definitions"]
    summaries = {
        row["reference"]: row
        for row in catalogs["item-equipment-effects.json"]["items"]
    }
    retained = catalogs["native-retained-effect-metadata.json"]["effects"]
    runtime = set(
        json.loads((PRIVATE / "runtime-effects.json").read_text())["effect_ids"]
    )
    DAMAGE_FAMILIES = (1, 2, 3, 4, 5, 917, 1083)
    HEAL_ELEMENTS = (24, 25, 251, 253, 258, 259, 1084)
    SET_CURRENT = json.loads((PRIVATE / "set-current.json").read_text())
    DISPLACEMENT = (300, 301, 302, 340, 331, 305, 422)
    source_path = ROOT / "server/wakfu_server/combat/combat_effect_runtime.py"
    source = source_path.read_text()
    handlers = {int(x) for x in re.findall(r"handlers\[(\d+)\]", source)}
    handlers.update(DAMAGE_FAMILIES)
    handlers.update(HEAL_ELEMENTS)
    handlers.update(SET_CURRENT)
    handlers.update(DISPLACEMENT)
    handlers.update(
        map(int, catalogs["effect-characteristic-registry.json"]["effects"])
    )
    handlers.update((48, 55, 20, 31, 41, 191, 56, 57, 192, 1201, 1202))
    groups = {
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
        345,
        349,
        949,
        865,
        1076,
    }
    supported = handlers | groups
    with zipfile.ZipFile(ROOT / "client/contents/i18n/i18n_es.jar") as jar:
        texts = dict(
            line.split("=", 1)
            for line in jar.read("texts_es.properties").decode().splitlines()
            if "=" in line
        )
    condition_path = ROOT / "server/wakfu_server/combat/combat_conditions.py"
    conditions_source = condition_path.read_text()
    # Vocabulary presence is deliberately weaker than successful evaluation.
    from wakfu_server.combat import combat_conditions as condition_module

    syntax_tree = ast.parse(inspect.getsource(condition_module.evaluate_condition))
    syntax_tree.body[0].body[-1] = ast.Return(value=ast.Constant(True))
    namespace = dict(vars(condition_module))
    aliases = json.loads((PRIVATE / "condition-aliases.json").read_text())
    namespace["canonical_aliases"] = lambda: {k: v["name"] for k, v in aliases.items()}
    exec(
        compile(ast.fix_missing_locations(syntax_tree), str(condition_path), "exec"),
        namespace,
    )
    validate_condition = namespace["evaluate_condition"]
    condition_vocabulary = {
        n.value
        for n in ast.walk(ast.parse(conditions_source))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    effects = {}
    state_rows = {}
    items = []

    def compact(reference, row):
        metadata = row.get("metadata", row)
        criterion = row.get("criterion_raw", row.get("criteria", ""))
        try:
            validate_condition(
                criterion or "", condition_module.ConditionContext(actors={})
            )
            condition_validation = (
                "syntax_and_signature_supported_context_still_required"
            )
        except (ValueError, SyntaxError) as error:
            condition_validation = str(error)
        return dict(
            condition_validation=condition_validation,
            reference=reference,
            effect_class=row["effect_class"],
            variant=row.get("variant"),
            parameters=row.get("parameters"),
            parameter_count=row.get("parameter_count"),
            minimum_level=row.get("minimum_level"),
            maximum_level=row.get("maximum_level"),
            children=row.get("children", []),
            criterion=criterion,
            condition_functions=sorted(
                set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", criterion or ""))
                - {"and", "or", "not"}
            ),
            metadata={
                k: v
                for k, v in metadata.items()
                if k.startswith("native_")
                or k.startswith("area_")
                or k
                in (
                    "target_masks",
                    "probability_base",
                    "probability_per_level",
                    "application_flag",
                    "removal_flag",
                )
            },
            retained_metadata=retained.get(str(reference)),
            in_compiled_runtime=reference in runtime,
            primitive_status="handler_or_group_present_requires_contract_validation"
            if row["effect_class"] in supported
            else "missing_dispatch_primitive",
        )

    for pattern in patterns["items"]:
        reference = pattern["reference"]
        definition = native.get(str(reference))
        record = dict(
            pattern,
            name=texts.get(f"content.15.{reference}"),
            owned_source_wired=False,
            definition_present=definition is not None,
            roots=[],
            passive_roots=[],
            effect_refs=[],
            state_refs=[],
            gaps=[],
        )
        if definition is None:
            record["gaps"].append("missing_native_item_definition")
            items.append(record)
            continue
        seen = set()
        states = set()
        missing = []
        dynamic = []
        implicit_states = set()

        def visit(ref, row=None):
            if ref in seen:
                return
            seen.add(ref)
            row = row or state_catalog["effects"].get(str(ref))
            if row is None:
                missing.append(ref)
                return
            effects.setdefault(str(ref), compact(ref, row))
            nested = {
                child["reference"]: child for child in row.get("child_definitions", [])
            }
            for child in row.get("children", []):
                visit(child, nested.get(child))
            if row["effect_class"] == 304:
                params = row.get("parameters", [])
                if len(params) < 2 or params[1] != 0:
                    dynamic.append(ref)
                    return
                state_id = int(params[0])
                state_id = (state_id + 32768) % 65536 - 32768
                visit_state(state_id)
            if row["effect_class"] in (48, 55):
                implicit_states.add(5227)
                visit_state(5227)

        def visit_state(state_id):
            if state_id in states:
                return
            states.add(state_id)
            state = state_catalog["states"].get(str(state_id))
            if state is None:
                missing.append(f"state:{state_id}")
                return
            children = set(state.get("effect_ids", []))
            for level in state.get("levels", []):
                children.update(level.get("effects", []))
            state_rows.setdefault(
                str(state_id),
                dict(
                    reference=state_id,
                    name=state.get("name"),
                    maximum_level=state.get("maximum_level"),
                    effect_refs=sorted(children),
                ),
            )
            for child in children:
                visit(child)

        for root in definition["ordered_effects"]:
            record["roots"].append(root["reference"])
            if (
                root.get("variant") == 0
                and root.get("metadata", {}).get("native_active_effect") is False
            ):
                record["passive_roots"].append(root["reference"])
            visit(root["reference"], root)
        record["effect_refs"] = sorted(seen)
        record["state_refs"] = sorted(states)
        record["implicit_runtime_state_refs"] = sorted(implicit_states)
        record["missing_definitions"] = missing
        record["dynamic_state_reference_effects"] = dynamic
        record["missing_primitive_classes"] = sorted(
            {
                effects[str(ref)]["effect_class"]
                for ref in seen
                if str(ref) in effects
                and effects[str(ref)]["primitive_status"]
                == "missing_dispatch_primitive"
            }
        )
        record["uncompiled_effect_refs"] = sorted(seen - runtime)
        record["condition_functions"] = sorted(
            {
                f
                for ref in seen
                if str(ref) in effects
                for f in effects[str(ref)]["condition_functions"]
            }
        )
        record["missing_condition_function_vocabulary"] = sorted(
            set(record["condition_functions"]) - condition_vocabulary
        )
        summary = summaries.get(reference)
        summary_effects = (
            {}
            if summary is None
            else {row["id"]: row for row in summary.get("effects", [])}
        )
        record["missing_filter_authority_roots"] = [
            ref
            for ref in record["roots"]
            if ref not in summary_effects
            or type(summary_effects[ref].get("native_variant")) is not int
            or type(summary_effects[ref].get("native_active_effect")) is not bool
        ]
        record["gaps"] = ["owned_equipment_lifecycle_unwired"]
        if record["missing_filter_authority_roots"]:
            record["gaps"].append("missing_native_item_filter_authority")
        if missing:
            record["gaps"].append("missing_effect_or_state_definition")
        if dynamic:
            record["gaps"].append("dynamic_state_reference_needs_native_resolution")
        if record["missing_primitive_classes"]:
            record["gaps"].append("missing_dispatch_primitive")
        if record["uncompiled_effect_refs"]:
            record["gaps"].append("equipment_effect_closure_not_in_compiled_runtime")
        record["unsupported_criterion_effects"] = sorted(
            ref
            for ref in seen
            if str(ref) in effects
            and effects[str(ref)]["condition_validation"]
            != "syntax_and_signature_supported_context_still_required"
        )
        if record["missing_condition_function_vocabulary"]:
            record["gaps"].append("missing_condition_function")
        if record["unsupported_criterion_effects"]:
            record["gaps"].append("unsupported_criterion_signature_or_function")
        items.append(record)
    classes = defaultdict(
        lambda: dict(effect_refs=[], scroll_refs=[], primitive_status=None)
    )
    for ref, row in effects.items():
        entry = classes[row["effect_class"]]
        entry["effect_refs"].append(int(ref))
        entry["primitive_status"] = row["primitive_status"]
    for row in items:
        for cls in {
            effects[str(ref)]["effect_class"]
            for ref in row["effect_refs"]
            if str(ref) in effects
        }:
            classes[cls]["scroll_refs"].append(row["reference"])
    counts = dict(
        scrolls=len(items),
        categories=dict(Counter(x["type"] for x in items)),
        unique_effects=len(effects),
        unique_states=len(state_rows),
        effect_classes=len(classes),
        missing_primitive_classes=sorted(c for c in classes if c not in supported),
        scrolls_by_gap=dict(Counter(g for x in items for g in x["gaps"])),
    )
    result = dict(
        schema=1,
        scope="Every installed-native scroll; union of native item/group/all-state-level closures plus mandatory resource-loss state5227; not execution acceptance",
        catalog_revision=json.loads((PRIVATE / "catalog-index.json").read_text())[
            "revision"
        ],
        counts=counts,
        items=items,
        effects=effects,
        states=state_rows,
        classes=dict(sorted(classes.items())),
        source_sha256={
            str(p.relative_to(ROOT)): digest(p)
            for p in (source_path, condition_path, ROOT / "client/lib/wakfu-client.jar")
        },
    )
    if (
        digest(ROOT / "client/lib/wakfu-client.jar")
        != patterns["source"]["client_jar_sha256"]
    ):
        raise ValueError("Native pattern export differs from installed client JAR")
    from enrich import enrich

    enrich(result, catalogs, ROOT, PRIVATE)
    (OUT / "inventory.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
