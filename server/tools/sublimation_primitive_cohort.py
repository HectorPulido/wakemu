"""Bounded qualification of every actual native sublimation primitive shape.

The caller supplies the same typed factory and compiled closure used by its
bulk census. This helper never creates a catalog heap, actor, provider, sampled
runtime value or execution authority. Results describe parsing and factory
admission, not gameplay execution of each sublimation.
"""

from collections import Counter
from collections.abc import Mapping
from types import SimpleNamespace


def qualify_primitive_cohort(
    factory,
    compiled,
    registry,
    closure,
    *,
    retained_container,
    owner_level_facts=None,
):
    """Inspect all matching native effects at their admitted domain endpoints.

    Level one is also retained when it lies in the original interval, since
    native additive parameters distinguish constructor level zero from an
    actual positive stack. No endpoint stands in for a future dynamic operand;
    the ordinary capability provider must separately accept every context.
    """
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_equipment_native_primitive_capability import (
        FAMILIES,
        context_capability,
        parse,
    )
    from wakfu_server.combat_equipment_operation_capability import validate_effect

    if not isinstance(closure, Mapping) or not isinstance(
        closure.get("effects"), Mapping
    ):
        raise ValueError("Missing bounded native sublimation closure")
    definitions = getattr(compiled, "effects", None)
    if not isinstance(definitions, Mapping):
        raise ValueError("Missing actual compiled native definitions")
    routes, provider = factory.equipment_operation_capability()
    rows, references, families = [], set(), Counter()
    for key, original in sorted(
        closure["effects"].items(), key=lambda pair: int(pair[0])
    ):
        family = original.get("effect_class")
        if family not in FAMILIES:
            continue
        definition = definitions.get(str(key))
        if (
            not isinstance(definition, Mapping)
            or any(
                definition.get(field) != original.get(field)
                for field in ("effect_class", "parameter_count")
            )
            or any(
                tuple(definition.get(field, ())) != tuple(original.get(field, ()))
                for field in ("parameters", "native_effect_flags", "children")
            )
        ):
            raise ValueError("Compiled primitive differs from its native closure")
        low, high = definition.get("minimum_level"), definition.get("maximum_level")
        if type(low) is not int or type(high) is not int or low > high:
            raise ValueError("Invalid native primitive level domain")
        low, high = max(-32768, low), min(32767, high)
        if low > high:
            raise ValueError("Primitive has no admitted native signed-short level")
        levels = sorted({low, high} | ({1} if low <= 1 <= high else set()))
        references.add(int(key))
        families[family] += 1
        for level in levels:
            profile = effect_profile(definition, level)
            parsed, contexts, dependencies, error = parse(definition, profile)
            if error is not None or parsed is None or dependencies:
                raise ValueError("Current native primitive parameter parse failed")
            assessment = validate_effect(
                definition,
                level,
                registry,
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container=retained_container,
                owner_level_facts=owner_level_facts,
                state_catalog=getattr(compiled, "source_states", None),
                effect_reference=int(key),
            )
            route = routes.routes.get(family)
            # A handler of the wrong native class must never gain authority by
            # preserving a valid family's numeric identifier or its callbacks.
            wrong_routes = SimpleNamespace(
                routes={family: SimpleNamespace(handler_type=object)}
            )
            if (
                context_capability(
                    factory,
                    wrong_routes,
                    definition,
                    {"retained_container": retained_container},
                )
                is not False
            ):
                raise ValueError("Primitive accepted an unrelated handler route")
            rows.append(
                dict(
                    reference=int(key),
                    family=family,
                    level=level,
                    native_parameter_count=definition["parameter_count"],
                    parsed=parsed,
                    required_primitive_context=list(contexts),
                    actual_handler=None
                    if route is None
                    else route.handler_type.__name__,
                    admission=assessment.status,
                    reasons=list(assessment.reasons),
                    wrong_handler_rejected=True,
                )
            )
    if not references:
        raise ValueError("Native closure contains no primitive qualification cohort")
    return dict(
        scope="all actual matching primitive effects in the bounded native closure",
        semantic_execution_claimed=False,
        effect_count=len(references),
        family_counts=dict(sorted(families.items())),
        witness_count=len(rows),
        admission_counts=dict(Counter(row["admission"] for row in rows)),
        rows=rows,
    )
