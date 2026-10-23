"""Original complete opposed-damage equipment graph and negative boundaries."""
from copy import deepcopy
from collections.abc import Mapping
from types import SimpleNamespace
import unittest


def fixture():
    from wakfu_server.combat_character_copy_equipment import (
        native_copied_equipment_catalog,
    )
    from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
    from wakfu_server.combat_copied_equipment_execution import (
        equipment_effect_definitions,
    )
    from wakfu_server.combat_server_spell import compiled_runtime_catalog
    from wakfu_server.combat_static_catalogs import characteristic_registry

    plan = copied_equipment_plan(33395, native_copied_equipment_catalog())
    roots = [r for r in plan["roots"] if r["effect_class"] == 304]
    source = dict(
        reference=33395,
        source_reference=33395,
        uid=90001,
        attachment_field=None,
        roots=tuple(r["reference"] for r in roots),
        unplanned_passive_effect_ids=(),
        native_retained_container=plan["native_retained_container"],
    )
    catalog = compiled_runtime_catalog()
    compiled = SimpleNamespace(
        effects=dict(catalog.effects, **equipment_effect_definitions({"roots": roots})),
        source_states=catalog.source_states,
    )
    return source, compiled, characteristic_registry()


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(row) for key, row in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(row) for row in value]
    return value


class EquipmentOpposedDamageContractTests(unittest.TestCase):
    def test_actual_complete_graph_and_snapshot_siblings_at_adjusted_levels(self):
        from wakfu_server.combat_equipment_opposed_damage_contract import (
            opposed_damage_state_contract,
        )
        from wakfu_server.equipment_level_groups import (
            qualified_source,
            project,
            snapshot_root,
        )

        source, compiled, registry = fixture()
        self.assertIsNone(opposed_damage_state_contract(source, compiled, registry))
        self.assertIsNotNone(qualified_source(33395))
        for level in (1, 50, 170, 245):
            rows = project(
                33395, actor_level=level, container_level=170, criterion_context={}
            )
            self.assertEqual([r["generic"] for r in rows], [304, 31, 150, 120])
            self.assertEqual(
                [r["values"] for r in rows], [[9364, 1, -1], [1, 1, 0], [3], [level]]
            )
        self.assertFalse(snapshot_root(33395, source["roots"][0]))
        self.assertTrue(snapshot_root(33395, 417992))

    def test_unreviewed_channels_predicates_clocks_scalar_and_siblings_reject(self):
        from wakfu_server.combat_equipment_opposed_damage_contract import (
            opposed_damage_state_contract,
        )

        source, original, registry = fixture()
        mutations = {
            "damage-channel": lambda e, s: e["417988"]["target_masks"].__setitem__(
                3, [3]
            ),
            "indirect": lambda e, s: e["417988"].__setitem__("criteria", "True"),
            "identity": lambda e, s: e["417988"].__setitem__(
                "criteria", e["417988"]["criteria"].replace("417989", "417990")
            ),
            "start": lambda e, s: e["417989"]["target_masks"].__setitem__(5, [1002]),
            "wait-clock": lambda e, s: e["417989"][
                "native_timing_definition"
            ].__setitem__("ryE", 2),
            "extra-child": lambda e, s: e["417989"]["children"].append(417987),
            "state-clock": lambda e, s: s["states"]["9365"].__setitem__(
                "duration_base", 2
            ),
            "state-replace": lambda e, s: s["states"]["9365"].__setitem__(
                "replace", True
            ),
            "scalar-growth": lambda e, s: e["417987"]["parameters"].__setitem__(1, 1),
            "scalar-resource": lambda e, s: e["417987"].__setitem__("effect_class", 21),
            "flags": lambda e, s: e["417988"]["native_effect_flags"].append(17),
            "selector": lambda e, s: e["417990"]["native_target_selector"].__setitem__(
                "mask", 2
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                # Copy only this small native closure, not the full shared catalog.
                ids = ("417985", "417987", "417988", "417989", "417990")
                effects = {key: thaw(original.effects[key]) for key in ids}
                states = dict(
                    states={
                        key: thaw(original.source_states["states"][key])
                        for key in ("9364", "9365")
                    },
                    effects=effects,
                )
                self.assertIsNone(
                    opposed_damage_state_contract(
                        source,
                        SimpleNamespace(effects=effects, source_states=states),
                        registry,
                    )
                )
                mutate(effects, states)
                self.assertIsNotNone(
                    opposed_damage_state_contract(
                        source,
                        SimpleNamespace(effects=effects, source_states=states),
                        registry,
                    )
                )
        self.assertIsNotNone(
            opposed_damage_state_contract(
                dict(source, unplanned_passive_effect_ids=(1,)), original, registry
            )
        )


if __name__ == "__main__":
    unittest.main()
