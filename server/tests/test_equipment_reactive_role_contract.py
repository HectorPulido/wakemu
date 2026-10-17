"""Source-only role admission; paid execution receipts remain separate."""
from collections import ChainMap
from types import SimpleNamespace
import unittest

from wakfu_server.wire import proto_field
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_owned_equipment import (
    compiled_with_sources,
    ordinary_turn_state_contract,
)
from wakfu_server.combat_reactive_equipment_contract import (
    reactive_damage_state_contract,
)
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry


class ReactiveRoleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owner = dict(
            id=7,
            breed=8,
            level=245,
            active_build_index=0,
            inventory_items=[
                dict(uid=1000, reference=32351, character_id=7, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=proto_field(24, 245).hex(),
                    equipment=proto_field(
                        10, proto_field(8, 1000) + proto_field(16, 17)
                    ).hex(),
                )
            },
        )
        (cls.source,) = plan(owner, ordinary_only=True)
        cls.compiled = compiled_with_sources(compiled_runtime_catalog(), (cls.source,))
        cls.registry = characteristic_registry()

    def test_actual_native_graph_and_composed_guard_accept_complete_source(self):
        self.assertEqual(self.source["unplanned_passive_effect_ids"], ())
        self.assertIsNone(
            reactive_damage_state_contract(self.source, self.compiled, self.registry)
        )
        self.assertIsNone(
            ordinary_turn_state_contract(self.source, self.compiled, self.registry)
        )

    def test_role_clock_merge_and_skip_variants_defer(self):
        for reference in (8784, 8785, 8786, 8787, 8788):
            original = self.compiled.source_states["states"][str(reference)]
            for field, value in (
                (
                    "clock_actor",
                    "caster" if original["clock_actor"] == "target" else "target",
                ),
                ("tick_at_turn_end", not original["tick_at_turn_end"]),
                ("replace", True),
                ("refresh", True),
                ("additive", True),
                ("protected", True),
                ("skip_turn_timer", True),
                ("realtime_duration_base", -1),
            ):
                with self.subTest(reference=reference, field=field):
                    states = ChainMap(
                        {str(reference): dict(original, **{field: value})},
                        self.compiled.source_states["states"],
                    )
                    source_states = dict(self.compiled.source_states, states=states)
                    altered = SimpleNamespace(
                        effects=self.compiled.effects, source_states=source_states
                    )
                    self.assertIsNotNone(
                        reactive_damage_state_contract(
                            self.source, altered, self.registry
                        )
                    )

    def test_recipient_application_timing_and_flag_variants_defer(self):
        changes = (
            (392261, "native_target_selector", {"class": "fcE", "mask": 1}),
            (392263, "application_flag", "NONE"),
            (392264, "application_flag", "EFFECT_CARRIER"),
            (392266, "native_target_selector", {"class": "fcE", "mask": 2}),
            (392272, "native_effect_flags", []),
            (392277, "native_effect_flags", []),
            (392273, "native_execution_mode", 0),
            (392274, "variant", 1),
        )
        for reference, field, value in changes:
            with self.subTest(reference=reference, field=field):
                original = self.compiled.effects[str(reference)]
                effects = ChainMap(
                    {str(reference): dict(original, **{field: value})},
                    self.compiled.effects,
                )
                altered = SimpleNamespace(
                    effects=effects, source_states=self.compiled.source_states
                )
                self.assertIsNotNone(
                    reactive_damage_state_contract(self.source, altered, self.registry)
                )
        original = self.compiled.effects["392264"]
        timing = dict(original["native_timing_definition"], ryE=2)
        effects = ChainMap(
            {"392264": dict(original, native_timing_definition=timing)},
            self.compiled.effects,
        )
        altered = SimpleNamespace(
            effects=effects, source_states=self.compiled.source_states
        )
        self.assertIsNotNone(
            reactive_damage_state_contract(self.source, altered, self.registry)
        )
