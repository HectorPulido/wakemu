"""Read-only eligibility for the native QI checkpoint's hidden pointer graph."""


def pointer_sources(checkpoint, fight, plain):
    """Return explicit hidden roots, or None for an unproved owner graph.

    Never call checkpoint.validate(): rebinding replaces QI topology. The
    canonical encoder is read-only after exact owner/payload checks below.
    """
    from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
    from .combat_pointer_qi_actor import ActualActorQI, ActorQK, AreaQK
    from .combat_pointer_qi_plain import encode
    from .combat_trove_byte_set import NativeTroveByteSet
    from .combat_state import Actor
    from .combat_area_membership import OwnedAreaRow
    from .combat_retained_collections import (
        bound_collections,
        bound_area_collections,
        OwnedMap,
    )

    if type(checkpoint) is not NativePointerCheckpoint:
        return None
    fields = vars(checkpoint)
    if set(fields) != {"_qi", "_lineage"} or type(fields["_lineage"]) is not object:
        return None
    qi = fields["_qi"]
    if type(qi) is not ActualActorQI:
        return None
    fields = dict(vars(qi))
    from weakref import ReferenceType

    owner_ref = fields.get("_fight_ref")
    if (
        type(owner_ref) is not ReferenceType
        or owner_ref.__callback__ is not None
        or owner_ref() is not fight
    ):
        return None
    # A live checkpoint has no standalone-copy lease or opaque owner fields.
    # Normalize only the certified weak owner for the existing exact schema.
    del fields["_fight_ref"]
    fields["fight"] = fight
    if set(fields) != {
        "width",
        "height",
        "origin",
        "slots",
        "cells",
        "anchors",
        "fight",
        "objects",
        "area_objects",
        "pending_constructor_actors",
        "movement_blocking",
    }:
        return None
    if fields["fight"] is not fight:
        return None
    for name in (
        "objects",
        "area_objects",
        "pending_constructor_actors",
        "movement_blocking",
        "cells",
        "anchors",
    ):
        if type(fields[name]) is not dict:
            return None
    if (
        type(fields["width"]) is not int
        or type(fields["height"]) is not int
        or type(fields["origin"]) is not tuple
        or len(fields["origin"]) != 2
        or any(type(n) is not int for n in fields["origin"])
        or type(fields["slots"]) is not list
        or len(fields["slots"]) != 127
    ):
        return None
    # Canonical actor aliases expose only identity/position/radius/byte. They
    # do not imply execution of the historical actor's Qf. Pending actors and
    # area-owned sources below remain operative roots. Actual typed937 rows
    # remain opaque to the graph gate, so their callbacks conservatively defer.
    roots, objects = [], []
    pending = fields["pending_constructor_actors"]
    # Pending actors are real native objects not yet present in Fight. Preserve
    # their entire canonical payload as an operative source, not only their ID.
    for identity, actor in pending.items():
        if (
            type(identity) is not int
            or type(actor) is not Actor
            or type(vars(actor).get("id")) is not int
            or vars(actor).get("id") != identity
            or not plain(vars(actor))
        ):
            return None
        roots.append(vars(actor))
    for identity, obj in fields["objects"].items():
        if (
            type(identity) is not int
            or type(obj) is not ActorQK
            or set(vars(obj)) != {"actor"}
        ):
            return None
        actor = vars(obj)["actor"]
        if (
            type(actor) is not Actor
            or type(vars(actor).get("id")) is not int
            or vars(actor).get("id") != identity
            or not (
                dict.get(fight.actors, identity) is actor
                or (
                    dict.get(fight.actors, identity) is None
                    and pending.get(identity) is actor
                )
            )
            or not plain(vars(actor))
        ):
            return None
        objects.append(obj)
    for identity, obj in fields["area_objects"].items():
        if (
            type(identity) is not int
            or type(obj) is not AreaQK
            or set(vars(obj)) != {"row"}
        ):
            return None
        row = vars(obj)["row"]
        if (
            (type(row) is not dict and type(row) is not OwnedAreaRow)
            or not plain(row)
            or type(row.get("uid")) is not int
            or row.get("uid") != identity
        ):
            return None
        for name in ("native_effect_areas", "native_retired_area_managers"):
            rows = vars(fight).get(name, {})
            if type(rows) is not dict:
                owner = bound_collections(vars(fight))
                if (
                    type(rows) is not OwnedMap
                    or owner is None
                    or not bound_area_collections(vars(fight), owner)
                    or owner.area_sources[name] is not rows
                ):
                    return None
            current = rows.get(identity)
            if current is not None and current is not row:
                return None
        objects.append(obj)
        roots.append(row)  # Qq rows may retain child runners/callback sources.
    object_ids = {id(obj) for obj in objects}
    if (
        any(type(key) is not int for key in fields["movement_blocking"])
        or set(fields["movement_blocking"]) != object_ids
        or any(
            type(value) is not bool for value in fields["movement_blocking"].values()
        )
        or any(obj is not None and id(obj) not in object_ids for obj in fields["slots"])
        or not plain(fields["anchors"])
    ):
        return None
    for cell, values in fields["cells"].items():
        if (
            type(cell) is not tuple
            or len(cell) != 2
            or any(type(n) is not int for n in cell)
            or type(values) is not NativeTroveByteSet
            or set(vars(values)) != {"contract", "state"}
            or not plain(vars(values))
        ):
            return None
    if not plain(dict(checkpoint)):
        return None
    try:
        if dict(checkpoint) != encode(qi):
            return None
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return roots
