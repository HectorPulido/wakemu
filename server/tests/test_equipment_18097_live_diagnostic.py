"""Read-only live-factory diagnosis of the 18097 native source graph."""
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class Equipment18097LiveDiagnosticTests(PostgresCase):
    def test_18097_reports_live_registry_routes_and_first_graph_blocker(self):
        import wakfu_server.combat_owned_equipment_pin as equipment_pin
        import wakfu_server.combat_equipment_operation_capability as capability
        import wakfu_server.combat_equipment_initialization as initialization
        from wakfu_server.combat_definitions import effect_profile, state_profile
        from wakfu_server.combat_state_parameters import interpret_state_parameters
        from wakfu_server.combat_owned_equipment_pin import compiled_with_sources
        from wakfu_server.combat_fight_property import property_registry

        context = {}
        validation_calls = []
        original_prepare = equipment_pin.prepare
        original_validate_effect = capability.validate_effect
        original_plan = initialization.plan
        original_validate_graph = capability.validate_graph

        def plain(value):
            if hasattr(value, "items"):
                return {str(key): plain(child) for key, child in value.items()}
            if isinstance(value, (tuple, list)):
                return [plain(child) for child in value]
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            return repr(value)

        def observe_prepare(*args, **kwargs):
            context.update(
                character=args[0],
                compiled=args[2],
                registry=args[3],
                runtime_capability=kwargs.get("runtime_capability"),
            )
            result = original_prepare(*args, **kwargs)
            context["prepared"] = {
                "sources": tuple(result["sources"]),
                "deferred": tuple(result["deferred"]),
            }
            return result

        def observe_plan(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            context["planned_sources"] = tuple(result)
            return result

        def observe_validate_effect(effect, level, registry, **kwargs):
            result = original_validate_effect(effect, level, registry, **kwargs)
            reference = kwargs.get("effect_reference")
            family = effect.get("effect_class")
            rows = registry.get("effects", registry) if hasattr(registry, "get") else {}
            row = (
                rows.get(str(family), rows.get(family))
                if hasattr(rows, "get")
                else None
            )
            routes = context.get("runtime_capability", (None,))[0]
            route_map = getattr(routes, "routes", {})
            route = route_map.get(family) if hasattr(route_map, "get") else None
            validation_calls.append(
                {
                    "reference": reference,
                    "family": family,
                    "level": level,
                    "registry_row": plain(row),
                    "route_declared": route is not None,
                    "route_handler": getattr(
                        getattr(route, "handler_type", None), "__name__", None
                    ),
                    "status": result.status,
                    "operation_id": result.operation_id,
                    "requires_context": list(result.requires_context),
                    "reasons": list(result.reasons),
                }
            )
            return result

        def observe_validate_graph(*args, **kwargs):
            result = original_validate_graph(*args, **kwargs)
            context["graph_result"] = {
                "status": result.status,
                "operation_id": result.operation_id,
                "requires_context": list(result.requires_context),
                "reasons": list(result.reasons),
            }
            return result

        # This fixture persists actual IsAdmin authority, equips the real
        # source in a supported slot, and reaches ordinary SaveBuild/Ready.
        with patch.object(
            equipment_pin, "prepare", side_effect=observe_prepare
        ), patch.object(initialization, "plan", side_effect=observe_plan), patch.object(
            capability, "validate_graph", side_effect=observe_validate_graph
        ), patch.object(
            capability, "validate_effect", side_effect=observe_validate_effect
        ):
            char, _monster, _deck, _rng, runtime, _stats = __import__(
                "test_equipment_null_carrier_pipeline"
            ).EquipmentNullCarrierPipelineTests._fixture(
                self,
                reference=18097,
                slot=7,
                level=200,
                administrator=True,
            )

        routes, _provider = context["runtime_capability"]
        routes, provider = context["runtime_capability"]
        prepared = context["prepared"]
        source = next(
            (
                item
                for item in context.get("planned_sources", ())
                if item.get("source_reference") == 18097
            ),
            None,
        )

        compiled = (
            context["compiled"]
            if source is None
            else compiled_with_sources(context["compiled"], (source,))
        )
        definitions = getattr(compiled, "effects", {})
        registry_effects = context["registry"].get("effects", context["registry"])
        node_rows = []
        if source is not None:
            root_level = source.get("native_retained_container", {}).get("level", 0)
            queue = [
                (reference, root_level, True) for reference in source.get("roots", ())
            ]
            visited = set()
            while queue:
                reference, level, is_root = queue.pop(0)
                if (reference, level) in visited:
                    continue
                visited.add((reference, level))
                effect = definitions.get(str(reference))
                if not hasattr(effect, "get"):
                    continue
                family = effect.get("effect_class")
                registry_row = registry_effects.get(
                    str(family), registry_effects.get(family)
                )
                route = getattr(routes, "routes", {}).get(family)
                try:
                    node_profile = effect_profile(effect, level)
                    node_validation = original_validate_effect(
                        effect,
                        level,
                        context["registry"],
                        runtime_bindings=routes,
                        criteria_capability=provider,
                        explicit_self_state_root=is_root and family == 304,
                        retained_container=source.get("native_retained_container"),
                        effect_reference=reference,
                    )
                    validation_status = node_validation.status
                    validation_reasons = list(node_validation.reasons)
                    if family == 304:
                        applied_state = interpret_state_parameters(
                            node_profile["parameters"]
                        )
                        state = state_profile(
                            compiled.source_states,
                            applied_state["reference"],
                            applied_state["level"],
                        )
                        for child in state["effects"]:
                            queue.append((child, state["level"], False))
                except (KeyError, TypeError, ValueError) as error:
                    node_profile = None
                    validation_status = "unknown"
                    validation_reasons = ["diagnostic traversal: " + str(error)]
                if family == 330:
                    queue.extend(
                        (child, level, False) for child in effect.get("children", ())
                    )
                node_rows.append(
                    {
                        "reference": int(reference),
                        "family": family,
                        "level": level,
                        "evaluated_parameters": None
                        if node_profile is None
                        else node_profile["parameters"],
                        "registry_row": plain(registry_row),
                        "route_declared": route is not None,
                        "route_handler": getattr(
                            getattr(route, "handler_type", None), "__name__", None
                        ),
                        "children": list(effect.get("children", ())),
                        "independent_validation_status": validation_status,
                        "independent_validation_reasons": validation_reasons,
                    }
                )

        authority = getattr(
            getattr(routes, "factory", None), "displacement_authority", None
        )
        family447 = next((row for row in node_rows if row["family"] == 447), None)
        property_probe = None
        if family447 is not None:
            effect = definitions.get(str(family447["reference"]))
            property_id = family447["evaluated_parameters"][0]
            property_row = property_registry().get(property_id)
            requirement = ("native_fight_property_context",)
            property_probe = {
                "effect_reference": family447["reference"],
                "level": family447["level"],
                "evaluated_parameters": family447["evaluated_parameters"],
                "property_id": property_id,
                "property_registry_row": plain(property_row),
                "authority_class": None
                if authority is None
                else type(authority).__name__,
                "route_handler": family447["route_handler"],
                "provider_context_decision": provider(
                    kind="context",
                    effect=effect,
                    level=family447["level"],
                    operation_id="fight.property",
                    requires_context=requirement,
                    detail={
                        "requirement": requirement[0],
                        "retained_container": source.get("native_retained_container"),
                    },
                ),
            }

        outcome = {
            "item_reference": 18097,
            "character_id": char["id"],
            "runtime_phase": runtime.fight.phase,
            "source_roots": [] if source is None else list(source.get("roots", ())),
            "prepared_sources": [
                {
                    "reference": row.get("source_reference"),
                    "generic_admission": row.get("_generic_operation_admission")
                    is True,
                }
                for row in prepared["sources"]
            ],
            "deferred": plain(prepared["deferred"]),
            "graph_nodes": node_rows,
            "validation_trace": validation_calls,
            "first_blocker": next(
                (row for row in validation_calls if row["status"] != "supported"), None
            ),
            "validate_graph_result": context.get("graph_result"),
            "fight_property_probe": property_probe,
            "registry_effect_families": sorted(
                (str(key) for key in registry_effects.keys())
            )
            if hasattr(registry_effects, "keys")
            else [],
            "live_route_families": sorted(
                (int(key) for key in getattr(routes, "routes", {}).keys())
            ),
        }
        output = Path(
            ".runtime/equipment-capability-census-20261021/18097-live-node-diagnostic.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
        self.assertEqual(runtime.fight.phase, "active")
        self.assertIsNotNone(source, f"Real 18097 source missing; see {output}")
        self.assertTrue(node_rows, f"No native graph nodes captured; see {output}")
        self.assertTrue(
            validation_calls, f"No live validation trace captured; see {output}"
        )
