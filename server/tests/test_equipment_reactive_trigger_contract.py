"""Pure graph admission over the installed original43-node equipment closure."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_equipment_reactive_trigger_contract import (
    reactive_trigger_state_contract,
)


class EquipmentReactiveTriggerContractTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures/native_equipment_reactive_trigger.json"
            ).read_text()
        )
        self.effects, self.states = fixture["effects"], fixture["states"]
        self.source = dict(
            roots=fixture["roots"],
            attachment_field=None,
            native_retained_container=dict(level=0),
            unplanned_passive_effect_ids=[],
        )
        # Only null400 needs a characteristic operation descriptor; all other
        # reviewed nodes have existing generic operation contracts. This is
        # the original eXE binding, not a synthetic scalar PC or430 allowance.
        self.registry = {"effects": {"400": {"runner": "eXE"}}}

    def qualify(self):
        compiled = SimpleNamespace(
            effects=self.effects,
            source_states=dict(states=self.states, effects=self.effects),
        )
        return reactive_trigger_state_contract(self.source, compiled, self.registry)

    def by_family(self, family):
        return next(e for e in self.effects.values() if e["effect_class"] == family)

    def assertRejected(self):
        reason = self.qualify()
        self.assertIsInstance(reason, str)
        self.assertTrue(reason.startswith("reactive_trigger_"), reason)

    def test_original_complete_native_graph_qualifies_with_scoped430_guards(self):
        from wakfu_server.combat_operation_registry import assess_operation

        self.assertEqual(
            assess_operation(
                self.by_family(430), characteristic_registry=self.registry
            ).status,
            "conditional",
        )
        self.assertIsNone(self.qualify())

    def test_bijective_graph_identity_renaming_uses_edges_not_allowlisted_ids(self):
        mapping = {int(key): int(key) + 1000000 for key in self.effects}
        renamed = {}
        for key, effect in self.effects.items():
            effect["children"] = [mapping[ref] for ref in effect["children"]]
            if effect["effect_class"] == 421:
                effect["parameters"][0] = mapping[int(effect["parameters"][0])]
            for old, new in mapping.items():
                effect["criteria"] = effect["criteria"].replace(str(old), str(new))
            renamed[str(mapping[int(key)])] = effect
        self.effects = renamed
        self.source["roots"] = [mapping[ref] for ref in self.source["roots"]]
        for state in self.states.values():
            state["effect_ids"] = [mapping[ref] for ref in state["effect_ids"]]
        state_id, state = next(iter(self.states.items()))
        replacement_state_id = int(state_id) + 1000000
        self.states = {str(replacement_state_id): state}
        self.effects[str(self.source["roots"][0])]["parameters"][
            0
        ] = replacement_state_id
        self.assertIsNone(self.qualify())

    def test_missing_duplicate_extra_or_crosslinked_graph_nodes_reject(self):
        original = deepcopy(self.effects)
        movement = next(
            e
            for e in self.effects.values()
            if e["effect_class"] == 330 and e["target_masks"][5] == [1005]
        )
        movement_id = next(
            key for key, value in self.effects.items() if value is movement
        )
        for mutation in ("missing", "duplicate", "extra", "crosslink"):
            with self.subTest(mutation=mutation):
                self.effects = deepcopy(original)
                movement = self.effects[movement_id]
                if mutation == "missing":
                    del self.effects[str(movement["children"][0])]
                elif mutation == "duplicate":
                    movement["children"][1] = movement["children"][0]
                elif mutation == "extra":
                    movement["children"].append(movement["children"][0])
                else:
                    remove = self.by_family(421)
                    remove["parameters"][0] += 1
                self.assertRejected()

    def test_trigger_mode_replace_dynamic_and_asymmetric_amounts_reject(self):
        original = deepcopy(self.effects)
        identity = next(
            key for key, value in self.effects.items() if value["effect_class"] == 430
        )
        for parameter, value in ((0, 0), (4, 1), (3, 1), (2, 799)):
            with self.subTest(parameter=parameter, value=value):
                self.effects = deepcopy(original)
                self.effects[identity]["parameters"][parameter] = value
                self.assertRejected()

    def test_unsupported_event_selector_flags_clock_and_criteria_reject(self):
        original = deepcopy(self.effects)
        identity = next(
            key
            for key, value in self.effects.items()
            if value["effect_class"] == 330 and value["target_masks"][5] == [1005]
        )
        for field, value in (
            ("target_masks", [None, None, None, None, None, [1005, 1003], None]),
            ("native_target_selector", {"class": "fcE", "mask": 2}),
            ("native_effect_flags", [17, 99]),
            ("criteria", "HasState(1)"),
            (
                "native_timing_definition",
                dict(original[identity]["native_timing_definition"], ryE=1),
            ),
        ):
            with self.subTest(field=field):
                self.effects = deepcopy(original)
                self.effects[identity][field] = value
                self.assertRejected()

    def test_unplanned_roots_state_stack_and_clock_changes_reject(self):
        self.source["unplanned_passive_effect_ids"] = [1]
        self.assertRejected()
        self.source["unplanned_passive_effect_ids"] = []
        state = next(iter(self.states.values()))
        original = deepcopy(state)
        for field, value in (
            ("additive", True),
            ("replace", True),
            ("refresh", True),
            ("duration_base", 1),
            ("realtime_duration_base", 1000),
            ("clock_actor", "caster"),
            ("maximum_level", 2),
        ):
            with self.subTest(field=field):
                state.clear()
                state.update(deepcopy(original))
                state[field] = value
                self.assertRejected()
