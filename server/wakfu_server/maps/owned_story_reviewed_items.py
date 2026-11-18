"""Explicit reconstructed server item producers after genuine owned encounters.

The item is native; its missing private-server award binding is reviewed data,
never represented as an original loot table. The controller's original frozen
victory verifier and durable step receipt provide production authority.
"""


def validate(selected, effect, native):
    if set(effect) != {"kind", "source_id"} or not isinstance(effect["source_id"], str):
        raise ValueError("Malformed reviewed story item source")
    source = native.get("reviewed_item_grants", {}).get(effect["source_id"])
    if (
        not isinstance(source, dict)
        or set(source)
        != {
            "reference",
            "quantity",
            "producer_step",
            "evidence",
            "native_item",
            "quest_id",
        }
        or not source["evidence"]
        or any(
            type(source[k]) is not int or source[k] <= 0
            for k in ("reference", "quantity", "quest_id")
        )
    ):
        raise ValueError("Reviewed item source lacks native identity and provenance")
    if source["native_item"].get("reference") != source["reference"] or not source[
        "native_item"
    ].get("name"):
        raise ValueError("Reviewed item source does not identify its original item")
    steps = [s for s in selected["steps"] if effect in s["effects"]]
    if len(steps) != 1 or steps[0]["id"] != source["producer_step"]:
        raise ValueError("Reviewed story item requires its genuine owned victory step")
    producer = steps[0]
    if producer["kind"] == "interactive":
        prerequisites = {step["id"]: step for step in selected["steps"]}
        prior = [prerequisites.get(identity) for identity in producer["requires"]]
        objects = [
            row
            for row in native.get("objects", [])
            if row.get("id") == producer["reference"]
        ]
        if (
            not any(
                step is not None and step["kind"] == "room_victory" for step in prior
            )
            or len(objects) != 1
            or objects[0].get("type") != "GenericActivableInteractiveElement"
        ):
            raise ValueError(
                "Reviewed chest requires its original source and prior owned victory"
            )
    elif producer["kind"] != "room_victory":
        raise ValueError(
            "Reviewed story item requires an owned victory or its source chest"
        )
    from wakfu_server.inventory_move import ACQUISITION_STACKS

    if source["reference"] not in ACQUISITION_STACKS:
        raise ValueError(
            "Reviewed story item is absent from the native inventory domain"
        )
    return source


def apply(db, store, character, selected, effect):
    from wakfu_server import owned_story_mechanics
    from wakfu_server.achievements import storage, service
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )

    source = validate(selected, effect, owned_story_mechanics.sources(selected))
    producer = next(
        step for step in selected["steps"] if step["id"] == source["producer_step"]
    )
    physical_chest = producer["kind"] == "interactive"
    if (
        not physical_chest
        and source["quest_id"]
        not in storage.load_locked(db, character["id"])["running"]
    ):
        return []
    if (
        complete_owned_item_quantity(character, (source["reference"],))
        >= source["quantity"]
    ):
        return []
    storage.enqueue_reward(
        db,
        character["id"],
        source["quest_id"],
        (
            f"reviewed-story-item:{character['instance_id']}:"
            if physical_chest
            else "reviewed-story-item:"
        )
        + effect["source_id"],
        "item",
        {
            "aeV": 5,
            "ckl": [source["reference"], source["quantity"]],
            "reviewed_story_source": effect["source_id"],
        },
    )
    # The existing delivery savepoint retains the entitlement when bags are
    # full. Inventory capacity must never abort a genuine terminal victory.
    return service.drain_rewards(db, store, character)
