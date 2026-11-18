"""Native inventory gates and payments declared by immutable story sources."""


def validate(selected, effect, native):
    fields = {"reference", "quantity", "consume"}
    if (
        set(effect) != fields | {"kind"}
        or any(
            type(effect.get(key)) is not int or effect[key] <= 0
            for key in ("reference", "quantity")
        )
        or type(effect.get("consume")) is not bool
    ):
        raise ValueError("Malformed native story item gate")
    choices = [
        row
        for row in selected.get("item_gates", ())
        if all(row.get(key) == effect[key] for key in fields)
    ]
    if len(choices) != 1 or not choices[0].get("evidence"):
        raise ValueError(
            "Story item gate lacks its explicit reviewed native declaration"
        )
    declaration = choices[0]
    table = native.get("loot_tables", {}).get(str(declaration.get("table_id")))
    native_output = table is not None and any(
        row.get("aAi") == effect["reference"]
        and row.get("cqy", 0) >= effect["quantity"]
        for row in table.get("gBN", ())
    )
    reviewed_output = any(
        row.get("reference") == effect["reference"]
        and row.get("quantity", 0) >= effect["quantity"]
        for row in native.get("reviewed_item_grants", {}).values()
    )
    native_action_output = False
    if declaration.get("item_action_id") is not None:
        from wakfu_server.simple_item_actions import native_use_contexts

        context = native_use_contexts().get(declaration["item_action_id"], {})
        native_action_output = (
            context.get("native_class") == "bHS"
            and context.get("item_ref") == declaration.get("source_reference")
            and context.get("action_parameters", [])[1:] == [str(effect["reference"])]
            and effect["quantity"] == 1
        )
    if not native_output and not reviewed_output and not native_action_output:
        raise ValueError("Story item gate names no frozen original native loot output")
    return declaration


def failure_packets(store, character, selected, effects):
    """Repeat native missing-key feedback without consuming the gate step."""
    from wakfu_server import owned_story_mechanics
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )

    for effect in effects:
        if effect["kind"] != "native_item_gate":
            continue
        native = owned_story_mechanics.sources(selected)
        declaration = validate(selected, effect, native)
        if (
            complete_owned_item_quantity(character, (effect["reference"],))
            >= effect["quantity"]
        ):
            continue
        if "failure_event" not in declaration:
            return None
        return [
            owned_story_mechanics.scenario_packet(
                selected, declaration["failure_event"]
            )
        ]
    return None


def apply(db, store, character, selected, effect):
    from wakfu_server import owned_story_mechanics
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )
    from wakfu_server.native_generic_rewards import _payment

    validate(selected, effect, owned_story_mechanics.sources(selected))
    if (
        complete_owned_item_quantity(character, (effect["reference"],))
        < effect["quantity"]
    ):
        raise ValueError("This passage requires its actual native equipment or item")
    if not effect["consume"]:
        return []
    _, packets, _ = _payment(
        db,
        store,
        character,
        dict(group_cod=effect["reference"], group_coe=effect["quantity"]),
    )
    return packets
