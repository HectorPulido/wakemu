"""Pure eGj.PJ definition-order planning; no cosmetic or inventory synthesis."""
from copy import deepcopy

SOURCE = "eGj.PJ.foA.Wc.fnR.k.iterator"


def copied_equipment_plan(reference, catalog):
    """Keep fnR's real item PL and order for a subsequent explicit-self apply.

    A complete native table is required even for Wc's missing-item return.
    This helper does not claim that every exported runner is implemented.
    """
    if type(reference) is not int or not -(1 << 31) <= reference < (1 << 31):
        raise ValueError("Invalid actual PJ definition operand")
    if reference == 0:
        return dict(producer=SOURCE, reference=0, status="zero_return", roots=[])
    if (
        not isinstance(catalog, dict)
        or catalog.get("producer") != SOURCE
        or catalog.get("complete") is not True
        or not isinstance(catalog.get("definitions"), dict)
        or type(catalog.get("definition_count")) is not int
        or catalog["definition_count"] <= 0
        or catalog["definition_count"] != len(catalog["definitions"])
    ):
        raise ValueError("Missing complete native copied equipment definitions")
    definition = catalog["definitions"].get(str(reference))
    if definition is None:
        return dict(
            producer=SOURCE,
            reference=reference,
            status="missing_definition_return",
            roots=[],
        )
    if (
        not isinstance(definition, dict)
        or definition.get("reference") != reference
        or definition.get("container_type") != 12
        or type(definition.get("fresh_container_level")) is not int
        or not 0 <= definition["fresh_container_level"] <= 32767
        or not isinstance(definition.get("ordered_effects"), list)
    ):
        raise ValueError("Invalid native fresh fnR definition")
    roots = definition["ordered_effects"]
    for index, root in enumerate(roots):
        if (
            not isinstance(root, dict)
            or root.get("ordinal") != index
            or type(root.get("reference")) is not int
            or type(root.get("effect_class")) is not int
            or not isinstance(root.get("metadata"), dict)
            or not isinstance(root.get("parameters"), list)
        ):
            raise ValueError("Invalid native fnR ordered effect")
    return dict(
        producer=SOURCE,
        reference=reference,
        status="explicit_self_effects",
        roots=deepcopy(roots),
        native_retained_container=dict(
            present=True,
            type=12,
            id=reference,
            level=definition["fresh_container_level"],
            is_spell=False,
            native_kind="item",
        ),
    )
