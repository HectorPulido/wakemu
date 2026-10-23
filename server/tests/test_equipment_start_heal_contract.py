"""Complete original copied-equipment graphs and fail-closed mutations."""
import copy
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server import native_catalog
from wakfu_server.combat_copied_equipment_execution import equipment_effect_definitions
from wakfu_server.combat_equipment_start_heal_contract import start_heal_state_contract
from wakfu_server.combat_static_catalogs import characteristic_registry


@lru_cache(maxsize=None)
def original_graph(reference):
    definition = native_catalog.record(
        Path("server/protocol/native-copied-equipment-definitions.json"),
        "definitions",
        reference,
    )
    roots = [
        row
        for row in definition["ordered_effects"]
        if row["effect_class"] == 304 and row["variant"] == 0
    ]
    effects = equipment_effect_definitions({"roots": roots})
    states = {}
    for root in roots:
        state_id = int(root["parameters"][0])
        state = native_catalog.record(
            Path("server/protocol/combat-state-definitions.json"), "states", state_id
        )
        states[str(state_id)] = state
        pending = list(state["effect_ids"])
        while pending:
            effect_id = pending.pop()
            if str(effect_id) in effects:
                continue
            effect = native_catalog.record(
                Path("server/protocol/combat-state-definitions.json"),
                "effects",
                effect_id,
            )
            effects[str(effect_id)] = effect
            pending.extend(effect.get("children", ()))
    source = dict(
        attachment_field=None,
        unplanned_passive_effect_ids=(),
        roots=tuple(row["reference"] for row in roots),
        native_retained_container={"level": definition["fresh_container_level"]},
    )
    return source, SimpleNamespace(
        effects=effects, source_states={"states": states, "effects": effects}
    )


class EquipmentStartHealContractTests(unittest.TestCase):
    def test_all_five_complete_original_graphs_qualify(self):
        registry = characteristic_registry()
        for reference in (18090, 18458, 23211, 23212, 23230):
            with self.subTest(reference=reference):
                self.assertIsNone(
                    start_heal_state_contract(*original_graph(reference), registry)
                )

    def test_changed_live_predicate_clock_targets_or_siblings_reject(self):
        for change in (
            "criterion",
            "event",
            "selector",
            "healing_kind",
            "hmi",
            "stack",
            "missing_root",
            "omitted",
        ):
            with self.subTest(change=change):
                source, compiled = copy.deepcopy(original_graph(18090))
                heal = next(
                    row
                    for row in compiled.effects.values()
                    if row["effect_class"] == 25
                )
                carrier = next(
                    row
                    for row in compiled.effects.values()
                    if row["effect_class"] == 330
                )
                if change == "criterion":
                    heal["criteria"] = 'GetTotalHpInPercent("caster") <= 33'
                elif change == "event":
                    carrier["target_masks"][5] = [1002]
                elif change == "selector":
                    heal["native_target_selector"]["mask"] = 2
                elif change == "healing_kind":
                    heal["parameters"][2] = 3
                elif change == "hmi":
                    heal["native_hmi_actions"]["rzc"] = [{"type": "unknown"}]
                elif change == "stack":
                    next(iter(compiled.source_states["states"].values()))[
                        "additive"
                    ] = False
                elif change == "missing_root":
                    source["roots"] = source["roots"][:1]
                else:
                    source["unplanned_passive_effect_ids"] = (123,)
                self.assertIsNotNone(
                    start_heal_state_contract(
                        source, compiled, characteristic_registry()
                    )
                )


if __name__ == "__main__":
    unittest.main()
