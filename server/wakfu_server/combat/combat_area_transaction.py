"""Atomic server policy for native owned-area callbacks.

The session commits the returned preview and emits its packets together. Movement
must already be applied on the supplied authoritative fight; turn start requires
its actual current fighter. Removed areas are handled by their owned315 removal
path, not by a second synthetic event here.
"""
import os
from copy import deepcopy
from .combat_random_transaction import rollback_external_rng


@rollback_external_rng
def prepare_area_event(
    character,
    monsters,
    fight,
    deck_blob,
    *,
    actor_id,
    action_id,
    event,
    rng=None,
    from_cell=None,
    to_cell=None,
    player_characters=None,
    deck_blobs=None,
):
    from .combat_server_spell import server_runtime

    if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") != "1":
        raise ValueError("Owned effect-area callbacks are disabled")
    if event not in ("turn_start", "movement"):
        raise ValueError("Unknown owned effect-area lifecycle boundary")
    actor = fight.actors.get(actor_id)
    if actor is None:
        raise ValueError("Missing registered effect-area boundary fighter")
    if event == "movement":
        if (
            from_cell is None
            or to_cell is None
            or len(from_cell) != 3
            or len(to_cell) != 3
            or any(type(v) is not int for v in (*from_cell, *to_cell))
            or tuple(actor.position) != tuple(to_cell)
        ):
            raise ValueError(
                "Effect-area movement requires committed native coordinates"
            )
    elif from_cell is not None or to_cell is not None:
        raise ValueError("Turn boundary does not accept movement coordinates")
    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        if event == "turn_start":
            dispatcher.native_area_events.turn_start(actor_id)
        else:
            dispatcher.native_area_events.movement(
                actor_id, from_cell=from_cell, to_cell=to_cell
            )
    return preview, tuple(packets)


@rollback_external_rng
def prepare_area_movement(
    character,
    monsters,
    fight,
    deck_blob,
    *,
    actor_id,
    action_id,
    path,
    origin,
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    """Qs callbacks for each native step, on one unpublished final-move Fight."""
    from .combat_server_spell import server_runtime

    if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") != "1":
        raise ValueError("Owned effect-area callbacks are disabled")
    if (
        not path
        or any(len(cell) != 3 for cell in (origin, *path))
        or any(type(v) is not int for cell in (origin, *path) for v in cell)
    ):
        raise ValueError("Invalid native effect-area movement path")
    actor = fight.actors.get(actor_id)
    if actor is None or tuple(actor.position) != tuple(path[-1]):
        raise ValueError("Effect-area movement requires committed final path")
    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    previous = tuple(origin)
    with preview.effect_resolution():
        for index, cell in enumerate(path):
            from .combat_qi_fight import move_registered_actor

            move_registered_actor(preview, preview.actors[actor_id], cell)
            from .combat_voluntary_movement_events import deliver_voluntary_movement

            deliver_voluntary_movement(
                dispatcher, actor_id=actor_id, from_cell=previous, to_cell=cell
            )
            dispatcher.native_area_events.movement(
                actor_id, from_cell=previous, to_cell=cell
            )
            if (
                preview.phase != "active" or preview.actors[actor_id].hp <= 0
            ) and index != len(path) - 1:
                raise ValueError("Early lethal area movement animation is unaudited")
            previous = tuple(cell)
    return preview, tuple(packets)
