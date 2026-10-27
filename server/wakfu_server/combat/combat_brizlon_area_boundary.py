"""Scoped Slek egg glyph end boundary, reconstructed by Wakemu.

Native QA.bhV=10016 and area1173 retain the original consumer. The original
server producer is unavailable. The owned player-end timing is reconstructed
from the authored Queen Slek mechanic: end on the white glyph, then transform
on the following turn (https://wakfulabs.com/dungeons/caverne-des-slekymoses/).
No creation/movement callback or fabricated Qe mask6 event is introduced.
"""

POLICY = "wakemu.brizlon-owned-glyph-player-end-v1"
_CREATORS = {4251: frozenset((189472, 189489)), 4280: frozenset((197885, 197887))}


def deliver_brizlon_area_turn_end(dispatcher, *, actor_id):
    """Activate only an actual owned1173 after the once-only native end event."""
    fight = dispatcher.native_retention.fight
    callbacks = getattr(dispatcher, "native_area_events", None)
    actor = fight.current
    if (
        callbacks is None
        or fight.phase != "active"
        or actor is None
        or actor.id != actor_id
        or getattr(actor, "controlled", False) is not True
        or actor.hp <= 0
    ):
        return ()
    areas = getattr(fight, "native_effect_areas", {})
    candidates = tuple(
        row
        for row in areas.values()
        if isinstance(row, dict) and row.get("reference") == 1173
    )
    if not candidates:
        return ()
    end = getattr(fight, "native_turn_event_deliveries", {}).get(
        f"{fight.turn_id}:{actor_id}:end"
    )
    if (
        not isinstance(end, dict)
        or end.get("actor_id") != actor_id
        or end.get("turn_id") != fight.turn_id
        or end.get("event_id") != 1002
        or end.get("phase") != "end"
    ):
        raise ValueError("Brizlon glyph requires the actual owned player end boundary")
    if end.get("suppressed") is not False:
        return ()
    from .combat_area_authority import area_guards
    from .combat_effect_area_geometry import contains_area_actor

    outcomes = []
    for row in candidates:
        if fight.phase != "active" or fight.current is not actor or actor.hp <= 0:
            break
        identity, owner_id = row.get("uid"), row.get("owner_id")
        if (
            type(identity) is not int
            or areas.get(identity) is not row
            or row.get("native_area_contract") != "faY"
            or row.get("effect_class") != 315
            or row.get("executing") is not False
            or row.get("remaining_activations", 0) == 0
        ):
            continue
        owner = fight.actors.get(owner_id)
        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(owner_id)
        if (
            owner is None
            or owner.hp <= 0
            or not isinstance(receipt, dict)
            or receipt.get("initialized") is not True
            or row.get("effect_reference") not in _CREATORS.get(receipt.get("ref"), ())
        ):
            continue
        runner_id = row.get("effect_uid")
        runner = getattr(fight, "native_owned_area_effects", {}).get(runner_id)
        if (
            not isinstance(runner, dict)
            or runner.get("uid") != runner_id
            or runner.get("area_uid") != identity
            or runner.get("effect_class") != 315
            or runner.get("caster_id") != owner_id
            or runner.get("executed") is not True
        ):
            continue
        if area_guards(fight, identity) != dict(baG=False, baK=False, baF=True):
            continue
        if not contains_area_actor(row, actor.position, actor.physical_radius):
            continue
        definition = callbacks._definition(row)
        if (
            definition.get("type") != "GLYPH"
            or tuple(definition.get("entry_masks", ())) != (10016,)
            or tuple(definition.get("effect_ids", ())) != (189484, 189460)
        ):
            raise ValueError("Brizlon glyph differs from the original native consumer")
        # Keep native activation charges, affiliations, criteria, Qq lifecycle,
        # original roots and their real retained area container unchanged.
        outcomes.extend(callbacks._deliver_event(row, definition, actor, 10016))
    return tuple(outcomes)
