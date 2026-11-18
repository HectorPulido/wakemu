"""Reviewed server birth publisher for the original conveyor area programs.

The installed 767/787 prototypes subscribe to 10000, not movement entry10001.
Publishing 10000 after a real registered307 birth is an explicit reconstruction
of the unavailable server producer. Native area targeting and303 orientation
remain responsible for the result; no actor direction is assigned here.
"""

POLICY = {
    "schema": "reviewed-native-order-birth-area-v1",
    "authority": "wakemu_reconstructed_registered_birth_publisher",
    "event_id": 10000,
    "normal_area": 767,
    "hard_area": 787,
    "original_server_publisher": "unrecovered",
}


def activate(handler, actor):
    fight = handler.fight
    if getattr(fight, "native_order_trial", None) is None:
        return ()
    if getattr(fight, "native_order_birth_policy", None) != POLICY:
        raise ValueError("Order birth lost its frozen reviewed publisher")
    from .native_order_trial_events import _owned_summon, _proof
    from .combat_effect_area_events import NativeAreaEventRuntime
    from .combat_effect_area_geometry import contains_area_cell
    from .combat_environment_glyphs import verify_environment_glyph

    proof, _, _ = _proof(fight)
    _owned_summon(fight, actor, proof.owner_id)
    callbacks = getattr(handler, "native_order_birth_areas", None)
    if (
        type(callbacks) is not NativeAreaEventRuntime
        or callbacks.fight is not fight
        or fight.actors.get(actor.id) is not actor
    ):
        raise ValueError("Order birth requires its actual registered area runtime")
    reference = POLICY[proof.mode + "_area"]
    receipts = dict(getattr(fight, "native_order_birth_area_receipts", {}))
    previous = receipts.get(actor.id)
    if previous is not None:
        row = getattr(fight, "native_effect_areas", {}).get(previous.get("area_uid"))
        if (
            row is None
            or row.get("reference") != reference
            or previous
            != dict(
                policy=dict(POLICY),
                actor_id=actor.id,
                area_uid=row["uid"],
                area_reference=reference,
            )
        ):
            raise ValueError("Order birth area receipt changed")
        verify_environment_glyph(fight, row)
        return ()
    matches = [
        row
        for row in getattr(fight, "native_effect_areas", {}).values()
        if row.get("reference") == reference and contains_area_cell(row, actor.position)
    ]
    if len(matches) != 1:
        raise ValueError("Order birth requires its matching registered conveyor")
    row = matches[0]
    verify_environment_glyph(fight, row)
    receipt = dict(
        policy=dict(POLICY),
        actor_id=actor.id,
        area_uid=row["uid"],
        area_reference=reference,
    )
    result = callbacks.event(POLICY["event_id"], actor.id, area_uid=row["uid"])
    receipts[actor.id] = receipt
    fight.native_order_birth_area_receipts = receipts
    return result
