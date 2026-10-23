import unittest
from types import SimpleNamespace

from wakfu_server.combat_equipment_operation_capability import (
    validate_effect,
    validate_graph,
)
from wakfu_server.combat_operation_registry import RuntimeOperationBinding
from wakfu_server.combat_effect_runtime import (
    NativeEffectRuntimeFactory,
    NativeRuntimeContexts,
)
from wakfu_server.combat_stat_handler import NativeStatHandler


def _effect(family, parameters, *, parameter_count=None, criteria=""):
    values = tuple(parameters)
    return dict(
        effect_class=family,
        parameters=values,
        parameter_count=len(values) // 2
        if parameter_count is None
        else parameter_count,
        variant=0,
        native_execution_mode=0,
        native_definition_class="eVE",
        native_target_selector={"class": "fcE", "mask": 0},
        area_native="empty",
        area_class="anA",
        target_masks=(None,) * 7,
        native_effect_flags=(),
        native_timing_definition={"clock_on_caster": False, "clock_on_target": True},
        native_hmi_actions={
            "rzc": (),
            "rzd": (),
            "rze": (),
            "rzf": (),
            "rzg": (),
            "rzh": (),
        },
        application_flag="NONE",
        removal_flag="NONE",
        probability_base=100,
        probability_per_level=0,
        minimum_level=0,
        maximum_level=32767,
        children=(),
        criteria=criteria,
    )


def _provider(**_):
    return True


_NULL400_ROW = {
    "additional_fields": {},
    "dynamic_stat": False,
    "effect_class": 400,
    "fixed_stat_id": None,
    "operation": "none",
    "parameter_contract": {
        "current_stat_change": False,
        "evaluation_level": 0,
        "parameterless_status": -1,
        "parameterless_status_policy": "preserve_existing_status",
        "signed_byte_cast": True,
        "status_parameter_index": 0,
    },
    "runner": "eXE",
}


def _runtime_binding(family):
    return RuntimeOperationBinding(family, None, lambda *_args, **_kwargs: None)


class CombatEquipmentOperationCapabilityTests(unittest.TestCase):
    def _factory_capability(self):
        callback = lambda *_args, **_kwargs: None
        contexts = NativeRuntimeContexts(*([callback] * 13))
        factory = NativeEffectRuntimeFactory(
            effects={},
            state_catalog={"effects": {}},
            characteristic_registry={"effects": {}},
            action_id=1,
            contexts=contexts,
        )
        return factory, factory.equipment_operation_capability()

    def test_assessment_conditional_is_not_executable_without_runtime_or_provider(self):
        effect = _effect(31, (2, 0, 1, 0, 0, 0))
        missing = validate_effect(
            effect, 1, {}, runtime_bindings={}, criteria_capability=_provider
        )
        self.assertEqual("unknown", missing.status)
        self.assertEqual("resource.maximum", missing.operation_id)
        self.assertEqual(
            dict(stat_id=2, amount=2, apply_current=True, remove_current=False),
            missing.parameters[0],
        )
        self.assertIn("RuntimeOperationBinding", missing.reasons[0])
        self.assertEqual(
            "unknown",
            validate_effect(
                effect,
                1,
                {},
                runtime_bindings={31: _runtime_binding(31)},
                criteria_capability=None,
            ).status,
        )
        self.assertEqual(
            "unknown",
            validate_effect(
                effect,
                1,
                {},
                runtime_bindings={31: object()},
                criteria_capability=_provider,
            ).status,
        )

    def test_factory_manifest_records_inline_group_route_separately(self):
        factory, (routes, provider) = self._factory_capability()
        self.assertIs(routes.factory, factory)
        self.assertIn(31, routes.routes)
        self.assertIn(56, routes.routes)
        self.assertIn(304, routes.routes)
        self.assertIn(330, routes.routes)
        self.assertIn(25, routes.routes)
        self.assertIn(321, routes.routes)
        self.assertIn(421, routes.routes)
        self.assertTrue(routes.routes[330].inline)
        self.assertTrue(
            provider(
                kind="context",
                effect=_effect(31, (2, 0, 1, 0, 0, 0)),
                level=1,
                operation_id="resource.maximum",
                requires_context=("native_target_selection",),
                detail="native_target_selection",
            )
        )
        event_effect = _effect(31, (2, 0, 1, 0, 0, 0))
        event_effect["target_masks"] = (None, None, None, (2,), None, None, None)
        self.assertTrue(
            provider(
                kind="context",
                effect=event_effect,
                level=1,
                operation_id="resource.maximum",
                requires_context=("native_event_scope",),
                detail="native_event_scope",
            )
        )
        turn_effect = _effect(304, (77, 0, 1, 0, -1, 0))
        turn_effect["target_masks"] = (None, None, None, None, None, (1001,), None)
        self.assertTrue(
            provider(
                kind="context",
                effect=turn_effect,
                level=1,
                operation_id="state.apply",
                requires_context=("native_event_scope",),
                detail="native_event_scope",
            )
        )
        unknown_event = dict(
            turn_effect, target_masks=(None, None, None, None, None, (11001,), None)
        )
        self.assertIsNone(
            provider(
                kind="context",
                effect=unknown_event,
                level=1,
                operation_id="state.apply",
                requires_context=("native_event_scope",),
                detail="native_event_scope",
            )
        )
        mixed_output = dict(
            turn_effect,
            target_masks=(None, None, None, None, None, (1001,), (2500,)),
        )
        self.assertIsNone(
            provider(
                kind="context",
                effect=mixed_output,
                level=1,
                operation_id="state.apply",
                requires_context=("native_event_scope",),
                detail="native_event_scope",
            )
        )

    def test_registry_bound_null400_uses_real_stat_route_and_levelzero_parser(self):
        callback = lambda *_args, **_kwargs: None
        contexts = NativeRuntimeContexts(*([callback] * 13))
        factory = NativeEffectRuntimeFactory(
            effects={},
            state_catalog={"effects": {}},
            characteristic_registry={"effects": {"400": dict(_NULL400_ROW)}},
            action_id=1,
            contexts=contexts,
        )
        routes, capability = factory.equipment_operation_capability()
        self.assertIs(routes.routes[400].handler_type, NativeStatHandler)
        effect = _effect(400, (130, 2))
        result = validate_effect(
            effect,
            7,
            factory.characteristic_registry,
            runtime_bindings=routes,
            criteria_capability=_provider,
        )
        self.assertEqual("supported", result.status, result.reasons)
        self.assertEqual("resource.current", result.operation_id)
        self.assertEqual(
            {"runner": "eXE", "execution_status": -126}, result.parameters[0]
        )

        parameterless = validate_effect(
            _effect(400, ()),
            7,
            factory.characteristic_registry,
            runtime_bindings=routes,
            criteria_capability=_provider,
        )
        self.assertEqual("supported", parameterless.status, parameterless.reasons)
        self.assertEqual(-1, parameterless.parameters[0]["execution_status"])
        self.assertTrue(
            capability(
                kind="context",
                effect=effect,
                level=7,
                operation_id="resource.current",
                requires_context=("native_null_execution_context",),
                detail="native_null_execution_context",
            )
        )

    def test_non_null400_registry_shape_does_not_gain_noop_support(self):
        wrong = dict(_NULL400_ROW, operation="world-property")
        callback = lambda *_args, **_kwargs: None
        contexts = NativeRuntimeContexts(*([callback] * 13))
        factory = NativeEffectRuntimeFactory(
            effects={},
            state_catalog={"effects": {}},
            characteristic_registry={"effects": {"400": wrong}},
            action_id=1,
            contexts=contexts,
        )
        routes, capability = factory.equipment_operation_capability()
        result = validate_effect(
            _effect(400, (1, 0)),
            1,
            factory.characteristic_registry,
            runtime_bindings=routes,
            criteria_capability=capability,
        )
        self.assertEqual("unsupported", result.status)
        self.assertIn("eXE", result.reasons[0])

    def test_missing_retained_container_defers_but_malformed_present_one_rejects(self):
        _factory, (_routes, provider) = self._factory_capability()
        effect = _effect(25, (100, 0))
        common = dict(
            kind="context",
            effect=effect,
            level=1,
            operation_id="healing.apply",
            requires_context=("native_runner_lifecycle",),
        )
        self.assertIsNone(provider(**common, detail={"retained_container": None}))
        self.assertFalse(
            provider(
                **common,
                detail={
                    "retained_container": {"present": False},
                }
            )
        )

    def test_owned_removal_and_healing_parsers_do_not_grant_missing_lifecycle(self):
        _factory, (routes, provider) = self._factory_capability()
        cases = (
            (25, (100, 0), "healing.apply"),
            (321, (77, 0), "state.decurse"),
            (421, (1, 0), "effect.dispel"),
        )
        for family, parameters, operation_id in cases:
            with self.subTest(family=family):
                result = validate_effect(
                    _effect(family, parameters),
                    1,
                    {},
                    runtime_bindings=routes,
                    criteria_capability=provider,
                )
                self.assertEqual("unknown", result.status, result.reasons)
                self.assertEqual(operation_id, result.operation_id)
                self.assertTrue(
                    result.parameters,
                    "shared native parser must run before context deferral",
                )
                self.assertTrue(
                    any(
                        requirement in result.requires_context
                        for requirement in (
                            "native_runner_lifecycle",
                            "owned_state_removal_and_reapplication",
                            "native_dispel_retention",
                            "native_healing_execution",
                        )
                    )
                )

    def test_unknown_factory_context_stays_deferred_and_native_healing_flag2_is_supported(
        self,
    ):
        _factory, (routes, provider) = self._factory_capability()
        effect = _effect(25, (100, 0))
        effect["native_effect_flags"] = (2,)
        accepted = provider(
            kind="context",
            effect=effect,
            level=1,
            operation_id="healing.apply",
            requires_context=("native_healing_execution",),
            detail="native_healing_execution",
        )
        self.assertTrue(
            accepted, "native flag 2 is accepted by the real healing adapter"
        )

        # This factory has routes but intentionally incomplete callbacks. A
        # context miss must remain deferrable, not become a known rejection.
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
        )
        self.assertEqual("unknown", result.status, result.reasons)

    def test_factory_criterion_validation_does_not_evaluate_truth(self):
        _factory, (routes, provider) = self._factory_capability()
        effect = _effect(31, (2, 0, 1, 0, 0, 0), criteria="1 == 2")
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
        )
        self.assertEqual("supported", result.status, result.reasons)
        unsupported = provider(
            kind="criterion",
            effect=effect,
            level=1,
            operation_id="resource.maximum",
            requires_context=(),
            detail={"expression": "UnknownNativePredicate()", "parsed": None},
        )
        self.assertFalse(unsupported)

    def test_unparsed_family_is_unknown_for_legacy_fallback(self):
        result = validate_effect(
            _effect(449, (1, 0)),
            1,
            {},
            runtime_bindings={},
            criteria_capability=_provider,
        )
        self.assertEqual("unknown", result.status)

    def test_eWN_and_eWO_parsers_preserve_live_parameter_dependencies(self):
        ewn = _effect(31, (2, 0, 1, 0, 0, 0))
        parsed = validate_effect(
            ewn,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", parsed.status)
        self.assertEqual(
            dict(stat_id=2, amount=2, apply_current=True, remove_current=False),
            parsed.parameters[0],
        )

        for family, stat in ((20, 1), (41, 3), (191, 4), (991, 14)):
            with self.subTest(family=family):
                parsed = validate_effect(
                    _effect(family, (2, 0, 1, 0, 0, 0)),
                    1,
                    {},
                    runtime_bindings={family: _runtime_binding(family)},
                    criteria_capability=_provider,
                )
                self.assertEqual("supported", parsed.status, parsed.reasons)
                self.assertEqual(stat, parsed.parameters[0]["stat_id"])

        for family, stat in ((57, 3), (192, 4)):
            with self.subTest(family=family):
                parsed = validate_effect(
                    _effect(family, (2, 0)),
                    1,
                    {},
                    runtime_bindings={family: _runtime_binding(family)},
                    criteria_capability=_provider,
                )
                self.assertEqual("supported", parsed.status, parsed.reasons)
                self.assertEqual(stat, parsed.parameters[0]["stat_id"])

        ewo = _effect(56, (2, 0, 50, 0, 1, 0, 0, 0))
        parsed = validate_effect(
            ewo,
            1,
            {},
            runtime_bindings={56: _runtime_binding(56)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", parsed.status)
        self.assertIn("native_eWO_probability_rng", parsed.requires_context)
        blocked = validate_effect(
            ewo,
            1,
            {},
            runtime_bindings={56: _runtime_binding(56)},
            criteria_capability=lambda **kw: kw.get("detail")
            != "native_eWO_probability_rng",
        )
        self.assertEqual("unsupported", blocked.status)

    def test_common_probability_timing_and_native_target_parser_are_required(self):
        effect = _effect(31, (2, 0, 1, 0, 0, 0))
        effect["probability_base"] = 101
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("unknown", result.status)
        self.assertIn("probability", result.reasons[0])

        effect = _effect(31, (2, 0, 1, 0, 0, 0))
        effect["native_timing_definition"]["duration"] = float("nan")
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("unknown", result.status)
        self.assertIn("timing", result.reasons[0])

        effect = _effect(31, (2, 0, 1, 0, 0, 0))
        effect["native_target_selector"]["mask"] = 4
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", result.status, result.reasons)

        # The same selector and geometry parsers used by the live resolver
        # accept self-only/area selection and known shaped areas without an
        # object-specific topology allowlist.
        for mask, area in ((2, "empty"), (3, "point"), (1, "circle-2")):
            with self.subTest(mask=mask, area=area):
                effect = _effect(31, (2, 0, 1, 0, 0, 0))
                effect["native_target_selector"] = {"class": "fcE", "mask": mask}
                effect["area_native"] = area
                effect["area_class"] = (
                    "anu" if area == "circle-2" else "anA" if area == "empty" else "anD"
                )
                parsed = validate_effect(
                    effect,
                    1,
                    {},
                    runtime_bindings={31: _runtime_binding(31)},
                    criteria_capability=_provider,
                )
                self.assertEqual("supported", parsed.status, parsed.reasons)

        unknown_selector = _effect(31, (2, 0, 1, 0, 0, 0))
        unknown_selector["native_target_selector"]["mask"] = 1 << 60
        parsed = validate_effect(
            unknown_selector,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("unknown", parsed.status)
        self.assertIn("target/area adapter", parsed.reasons[0])

        unknown_area = _effect(31, (2, 0, 1, 0, 0, 0))
        unknown_area["native_target_selector"]["mask"] = 1
        unknown_area["area_native"] = "not-a-native-area"
        parsed = validate_effect(
            unknown_area,
            1,
            {},
            runtime_bindings={31: _runtime_binding(31)},
            criteria_capability=_provider,
        )
        self.assertEqual("unknown", parsed.status)
        self.assertIn("target/area adapter", parsed.reasons[0])

    def test_mask2_is_supported_by_shared_selector_with_root_self_context(self):
        _factory, (routes, provider) = self._factory_capability()
        effect = _effect(304, (77, 0, 1, 0, -1, 0))
        effect["native_target_selector"] = {"class": "fcE", "mask": 2}
        root = validate_effect(
            effect,
            1,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
            explicit_self_state_root=True,
        )
        self.assertEqual("supported", root.status, root.reasons)
        self.assertIn("native_explicit_self_state_root", root.requires_context)

        effect["native_target_selector"] = {"class": "fcE", "mask": 3}
        effect["area_native"] = "point"
        effect["area_class"] = "anD"
        root_point = validate_effect(
            effect,
            1,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
            explicit_self_state_root=True,
        )
        self.assertEqual("supported", root_point.status, root_point.reasons)
        descendant = validate_effect(
            effect,
            1,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
        )
        self.assertEqual("supported", descendant.status, descendant.reasons)
        self.assertNotIn("native_explicit_self_state_root", descendant.requires_context)

    def test_eWQ_registry_parser_accepts_single_and_two_value_shapes(self):
        registry = {
            "effects": {
                "701": dict(
                    runner="eWQ",
                    fixed_stat_id=9,
                    percent_default=False,
                    limit_policy="NORMAL",
                    zero_initial_amount_rejected=False,
                    parameter_contract={"supported_counts": (1, 2, 3)},
                )
            }
        }
        for raw in ((5, 0), (5, 0, 1, 0)):
            with self.subTest(raw=raw):
                effect = _effect(701, raw)
                result = validate_effect(
                    effect,
                    2,
                    registry,
                    runtime_bindings={701: _runtime_binding(701)},
                    criteria_capability=_provider,
                )
                self.assertEqual("supported", result.status)
                self.assertEqual(9, result.parameters[0]["stat_id"])
        dice = _effect(701, (5, 0, 1, 2, 9, 0))
        result = validate_effect(
            dice,
            2,
            registry,
            runtime_bindings={701: _runtime_binding(701)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", result.status)
        self.assertEqual(9, result.parameters[0]["stat_id"])

        unsupported_dice = _effect(701, (5, 0) * 4)
        result = validate_effect(
            unsupported_dice,
            2,
            registry,
            runtime_bindings={701: _runtime_binding(701)},
            criteria_capability=_provider,
        )
        self.assertEqual("unsupported", result.status)

    def test_group_decoder_reports_context_instead_of_assuming_mode(self):
        # Relative group mode plus cell targeting are decoded by the native
        # dispatcher parser; acceptance still requires a provider for both.
        effect = _effect(330, (1, 0, 0, 0, 0, 0, 1, 0))
        result = validate_effect(
            effect,
            1,
            {},
            runtime_bindings={330: _runtime_binding(330)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", result.status)
        self.assertIn("relative_group_candidates", result.requires_context)

    def test_graph_requires_complete_source_and_state_context_capabilities(self):
        root = _effect(304, (77, 0, 1, 0, -1, 0))
        state = dict(
            maximum_level=0,
            duration_base=-1,
            duration_per_level=0,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="target",
            tick_at_turn_end=False,
            additive=False,
            replace=False,
            refresh=False,
            protected=False,
            skip_turn_timer=False,
            effect_ids=(),
        )
        compiled = SimpleNamespace(
            effects={"77": root},
            source_states={"states": {"77": state}, "effects": {}},
        )
        source = dict(
            roots=(77,),
            unplanned_passive_effect_ids=(),
            attachment_field=None,
            native_retained_container={"level": 1},
        )
        result = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings={304: _runtime_binding(304)},
            criteria_capability=_provider,
        )
        self.assertEqual("supported", result.status)
        self.assertIn("native_state_stack_policy", result.requires_context)
        reject_state = lambda **kw: kw.get("kind") != "context" or kw.get(
            "requires_context"
        ) != ("native_state_stack_policy",)
        result = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings={304: _runtime_binding(304)},
            criteria_capability=reject_state,
        )
        self.assertEqual("unsupported", result.status)

    def test_attachment_graphs_require_the_same_complete_roots_and_native_contexts(
        self,
    ):
        root = _effect(304, (77, 0, 1, 0, -1, 0))
        state = dict(
            maximum_level=0,
            duration_base=-1,
            duration_per_level=0,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="target",
            tick_at_turn_end=False,
            additive=False,
            replace=False,
            refresh=False,
            protected=False,
            skip_turn_timer=False,
            effect_ids=(),
        )
        compiled = SimpleNamespace(
            effects={"77": root}, source_states={"states": {"77": state}, "effects": {}}
        )
        for tag in (None, 24, 32):
            with self.subTest(tag=tag):
                source = dict(
                    roots=(77,),
                    unplanned_passive_effect_ids=(),
                    attachment_field=tag,
                    native_retained_container={"level": 80},
                )
                accepted = validate_graph(
                    source,
                    compiled,
                    {},
                    runtime_bindings={304: _runtime_binding(304)},
                    criteria_capability=_provider,
                )
                self.assertEqual(accepted.status, "supported", accepted.reasons)
                missing = validate_graph(
                    dict(source, unplanned_passive_effect_ids=(88,)),
                    compiled,
                    {},
                    runtime_bindings={304: _runtime_binding(304)},
                    criteria_capability=_provider,
                )
                self.assertEqual(missing.status, "unsupported")
                unknown = validate_graph(
                    source,
                    compiled,
                    {},
                    runtime_bindings={},
                    criteria_capability=_provider,
                )
                self.assertEqual(unknown.status, "unknown")

    def test_native_factory_context_reads_state_profile_separately(self):
        factory, (routes, provider) = self._factory_capability()
        root = _effect(304, (77, 0, 1, 0, -1, 0))
        state = dict(
            maximum_level=0,
            duration_base=-1,
            duration_per_level=0,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="target",
            tick_at_turn_end=False,
            additive=False,
            replace=False,
            refresh=False,
            protected=False,
            skip_turn_timer=False,
            effect_ids=(),
        )
        compiled = SimpleNamespace(
            effects={"77": root},
            source_states={"states": {"77": state}, "effects": {}},
        )
        source = dict(
            roots=(77,),
            unplanned_passive_effect_ids=(),
            attachment_field=None,
            native_retained_container={"level": 1},
        )
        result = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings=routes,
            criteria_capability=provider,
        )
        self.assertEqual("supported", result.status, result.reasons)


if __name__ == "__main__":
    unittest.main()
