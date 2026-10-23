"""Fail-closed guards over actual native start-characteristic equipment sources."""
from collections import ChainMap
from collections.abc import Mapping
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def _mutable(value):
    if isinstance(value, Mapping):
        return {key: _mutable(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_mutable(child) for child in value]
    return value


class EquipmentStartCharacteristicContractGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.equipment_stats import CATALOG
        from wakfu_server.equipment_characteristics import native_rows
        from wakfu_server.combat_definitions import effect_profile

        native, compiled = native_copied_equipment_catalog(), compiled_runtime_catalog()
        cls.registry, cls.rows = characteristic_registry(), native_rows()
        cls.fixtures = {}
        for reference in (18091, 23215, 27297, 27298):
            plan = copied_equipment_plan(reference, native)
            roots = [
                row
                for row in plan["roots"]
                if row["effect_class"] == 304
                and row["variant"] == 0
                and row["metadata"]["native_active_effect"] is False
            ]
            source = dict(
                uid=1000 + reference,
                reference=reference,
                source_reference=reference,
                attachment_field=None,
                roots=tuple(row["reference"] for row in roots),
                effects=equipment_effect_definitions(dict(roots=roots)),
                native_retained_container=plan["native_retained_container"],
            )
            source["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                reference, plan, source["roots"], templates=CATALOG
            )
            extended = compiled_with_sources(compiled, [source])
            root = extended.effects[str(source["roots"][0])]
            state_id = effect_profile(
                root, source["native_retained_container"]["level"]
            )["parameters"][0]
            state = extended.source_states["states"][str(state_id)]
            listener = next(
                extended.effects[str(ref)]
                for ref in state["effect_ids"]
                if extended.effects[str(ref)]["effect_class"] == 330
            )
            cls.fixtures[reference] = source, extended, state_id, listener

    def qualify(
        self,
        *,
        effect_changes=None,
        state_changes=None,
        source_changes=None,
        registry=None
    ):
        from wakfu_server.combat_equipment_start_characteristic_contract import (
            start_characteristic_state_contract,
        )

        source, compiled, state_id, listener = self.fixtures[18091]
        effects = ChainMap(effect_changes or {}, compiled.effects)
        states = ChainMap(state_changes or {}, compiled.source_states["states"])
        view = SimpleNamespace(
            effects=effects, source_states=dict(states=states, effects=effects)
        )
        candidate = dict(source, **(source_changes or {}))
        return start_characteristic_state_contract(
            candidate, view, self.registry if registry is None else registry
        )

    def assertRejected(self, reason):
        self.assertIsInstance(reason, str)
        self.assertTrue(reason.startswith("start_characteristic_"), reason)

    def test_four_actual_native_sources_are_the_positive_controls(self):
        from wakfu_server.combat_equipment_start_characteristic_contract import (
            start_characteristic_state_contract,
        )

        for reference, (source, compiled, _, _) in self.fixtures.items():
            with self.subTest(reference=reference):
                self.assertIsNone(
                    start_characteristic_state_contract(source, compiled, self.registry)
                )

    def test_unknown_resource_and_frozen_selected_pa_are_rejected(self):
        _, compiled, _, listener = self.fixtures[18091]
        identity = listener["children"][0]
        original = compiled.effects[str(identity)]
        unknown = next(value for value in range(1, 256) if value not in self.rows)
        for stat in (unknown, 1):
            with self.subTest(selected_pc=stat):
                group = _mutable(original)
                group["parameters"][12] = stat
                self.assertRejected(self.qualify(effect_changes={str(identity): group}))
        selected = int(original["parameters"][12])
        altered = dict(self.rows[selected], frozen=True)
        with patch(
            "wakfu_server.equipment_characteristics.native_rows",
            return_value=ChainMap({selected: altered}, self.rows),
        ):
            self.assertRejected(self.qualify())

    def test_resource_or_frozen_scalar_binding_is_rejected(self):
        _, compiled, _, listener = self.fixtures[18091]
        group = compiled.effects[str(listener["children"][0])]
        leaf = compiled.effects[str(group["children"][0])]
        family = str(leaf["effect_class"])
        for stat in (
            1,
            next(value for value in range(1, 256) if value not in self.rows),
        ):
            with self.subTest(output_pc=stat):
                binding = dict(self.registry["effects"][family], fixed_stat_id=stat)
                registry = dict(
                    self.registry,
                    effects=ChainMap({family: binding}, self.registry["effects"]),
                )
                self.assertRejected(self.qualify(registry=registry))
        stat = self.registry["effects"][family]["fixed_stat_id"]
        with patch(
            "wakfu_server.equipment_characteristics.native_rows",
            return_value=ChainMap(
                {stat: dict(self.rows[stat], frozen=True)}, self.rows
            ),
        ):
            self.assertRejected(self.qualify())

    def test_extra_event_wrong_flags_and_changed_timing_are_rejected(self):
        _, compiled, _, listener = self.fixtures[18091]
        listener_id = next(
            ref
            for ref in compiled.source_states["states"][str(self.fixtures[18091][2])][
                "effect_ids"
            ]
            if compiled.effects[str(ref)]["effect_class"] == 330
        )
        group_id = listener["children"][1]
        for label, identity, field, value in (
            (
                "extra-event",
                listener_id,
                "target_masks",
                [None, None, None, None, None, [1003, 1005], None],
            ),
            ("wrong-second-group-flag", group_id, "native_effect_flags", []),
            ("unknown-group-flag", group_id, "native_effect_flags", [17, 99]),
            (
                "retimed-group",
                group_id,
                "native_timing_definition",
                dict(
                    compiled.effects[str(group_id)]["native_timing_definition"], ryE=1
                ),
            ),
        ):
            with self.subTest(mutation=label):
                effect = _mutable(compiled.effects[str(identity)])
                effect[field] = value
                self.assertRejected(
                    self.qualify(effect_changes={str(identity): effect})
                )

    def test_altered_coefficients_state_clock_and_unplanned_roots_are_rejected(self):
        _, compiled, state_id, listener = self.fixtures[18091]
        identity = listener["children"][0]
        group = _mutable(compiled.effects[str(identity)])
        group["parameters"][19] = 0.02
        self.assertRejected(self.qualify(effect_changes={str(identity): group}))
        for key, value in (
            ("duration_base", 1),
            ("additive", True),
            ("replace", True),
            ("clock_actor", "caster"),
        ):
            with self.subTest(state_field=key):
                state = _mutable(compiled.source_states["states"][str(state_id)])
                state[key] = value
                self.assertRejected(self.qualify(state_changes={str(state_id): state}))
        self.assertRejected(
            self.qualify(source_changes={"unplanned_passive_effect_ids": [999999]})
        )
        self.assertRejected(
            self.qualify(
                source_changes={"roots": (*self.fixtures[18091][0]["roots"], 999999)}
            )
        )
