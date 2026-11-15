"""Transactional batching for the reconstructed four-target area lesson.

Only the authenticated spell preview supplies impacts; an incomplete cast
never damages any of its lesson sacks.  The owning spell transaction owns
publication and rolls back the preview on any failure.
"""

from .lesson_area import AREA_EFFECTS, REQUIRED_HITS, formation


def begin(fight, *, source_id, action_id, spell_id):
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return False
    if not isinstance(contract, dict) or spell_id not in (7969, 7970, 7971):
        return False
    if contract.get("initialized") is not True or contract.get("owner") != source_id:
        return False
    if getattr(fight, "_rii_area_pending", None) is not None:
        raise ValueError("Area lesson cast is already pending")
    fight._rii_area_pending = {
        "action_id": action_id,
        "source_id": source_id,
        "hits": [],
    }
    return True


def defer(
    fight,
    *,
    action_id,
    source_id,
    target_id,
    effect_reference,
    damage,
    uid,
    element,
    cell,
    base_uid
):
    """Protect bound sacks from all other damage and capture eligible impacts.

    Other actors, effects and casts without a pending lesson batch must not
    kill a training sack; they are suppressed without advancing the lesson.
    """
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return False
    if not isinstance(contract, dict) or target_id not in contract.get("targets", ()):
        return False
    pending = getattr(fight, "_rii_area_pending", None)
    if (
        isinstance(pending, dict)
        and pending["action_id"] == action_id
        and pending["source_id"] == source_id == contract.get("owner")
        and effect_reference in AREA_EFFECTS
        and type(damage) is int
        and damage > 0
    ):
        pending["hits"].append(
            {
                "target_id": target_id,
                "effect_reference": effect_reference,
                "uid": uid,
                "element": element,
                "cell": cell,
                "base_uid": base_uid,
            }
        )
    return True


def finish(fight, packets):
    """Commit a four-sack batch and publish actual health and position changes."""
    pending = getattr(fight, "_rii_area_pending", None)
    if pending is None:
        return False
    del fight._rii_area_pending
    from .rii_area_contract import complete_cast

    hits = pending["hits"]
    effects = {row["effect_reference"] for row in hits}
    if len(effects) != 1 or not complete_cast(
        fight,
        action_id=pending["action_id"],
        source_id=pending["source_id"],
        effect_reference=next(iter(effects)),
        hit_ids=[row["target_id"] for row in hits],
    ):
        return False
    from wakfu_server.combat_effects import direct_damage

    with fight.effect_resolution():
        for row in hits:
            dealt = fight.apply_damage(pending["source_id"], row["target_id"], 25)
            packets.append(
                (
                    12613,
                    direct_damage(
                        fight.id,
                        pending["action_id"],
                        uid=row["uid"],
                        generic_effect=row["effect_reference"],
                        element=row["element"],
                        caster_id=pending["source_id"],
                        target_id=row["target_id"],
                        damage=dealt,
                        cell=row["cell"],
                        base_uid=row["base_uid"],
                    ),
                )
            )
    if fight.rii_area_lesson_contract["hits"] < REQUIRED_HITS:
        import struct
        from wakfu_server.combat_displacement import (
            displacement_additional,
            position_payload,
        )
        from wakfu_server.combat_effects import _integer, _varint
        from wakfu_server.combat_position_mutation import move_actor_position
        from wakfu_server.rii_lesson_spell_catalog import catalog

        owner = fight.actors[pending["source_id"]]
        targets = [fight.actors[row["target_id"]] for row in hits]
        occupied = {tuple(actor.position) for actor in fight.actors.values()}
        layout = formation(
            fight.walkable,
            occupied,
            anchor=tuple(owner.position),
            phase=fight.rii_area_lesson_contract["hits"],
            effects=catalog()["effects"],
        )
        if layout is None:
            raise ValueError("No reachable area lesson formation")
        _, cells = layout
        for actor, destination in zip(targets, cells):
            move_actor_position(fight, actor, destination)
            uid = fight.allocate_effect_uid()
            reference = (367185, 367188, 367177)[
                fight.rii_area_lesson_contract["hits"] - 1
            ]
            position = position_payload(destination)
            additional = displacement_additional(302, destination=destination)
            blob = (
                lambda field, data: _varint(field << 3 | 2) + _varint(len(data)) + data
            )
            effect = (
                b"".join(
                    _integer(k, v)
                    for k, v in ((1, uid), (2, uid), (3, reference), (4, 0))
                )
                + blob(5, position)
                + _integer(6, actor.id)
                + blob(8, additional)
            )
            packets.append(
                (
                    12613,
                    struct.pack(
                        ">iiiBih",
                        fight.id,
                        pending["action_id"],
                        -1,
                        0,
                        302,
                        len(effect),
                    )
                    + effect,
                )
            )
    return True


def prepare_population(fight, effect, population):
    """Use the captured prepare-all/consume-all order for this native lesson.

    Official frames 11556--11575 mark all four selected sacks with 8006;
    frames 11577--11585 then consume their damage. Other encounters retain
    their existing execution order. Partial selections are still prepared as
    selected; the native count condition suppresses their resulting damage.
    """
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if not isinstance(contract, dict) or contract.get("native_lesson") is not True:
        return False
    if effect.get("effect_class") != 1 or len(population) < 2:
        return False
    return all(
        selected.reference in AREA_EFFECTS
        and selected.caster_id == contract.get("owner")
        and selected.target_id in contract.get("targets", ())
        and selected.state_uid is None
        and selected.native_running_uid is None
        and selected.native_delayed_uid is None
        for selected in population
    )
