"""Publish native kind-six rail areas from the owned fdp/fdq network.

The client computes movement topology but its fdo callback is a no-op. The
server therefore owns this projection, using the installed rail prototype and
native direct eYQ factory delivery rather than a fabricated spell definition.
"""
import struct

SOURCE = "fdq.server_projection.eYQ.direct.385"
RAIL_REFERENCE = 385


def rail_cells(network):
    """Keep both cardinal tracks at crossings; altitude comes from native QI."""
    from .combat_microbot_network import SOURCE as NETWORK_SOURCE

    if not isinstance(network, dict) or network.get("source") != NETWORK_SOURCE:
        raise ValueError("Missing actual microbot network projection")
    raw_cells = network.get("cells")
    segments = network.get("segments")
    if not isinstance(raw_cells, (tuple, list)) or not isinstance(
        segments, (tuple, list)
    ):
        raise ValueError("Missing native microbot network geometry")
    for cell in raw_cells:
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
        ):
            raise ValueError("Invalid native microbot network cell")
    cells = {tuple(cell[:2]): tuple(cell) for cell in raw_cells}
    selected = set()
    for segment in segments:
        if (
            not isinstance(segment, (tuple, list))
            or len(segment) != 2
            or any(
                not isinstance(point, (tuple, list))
                or len(point) != 3
                or any(type(value) is not int for value in point)
                for point in segment
            )
        ):
            raise ValueError("Invalid native microbot rail segment")
        lo, hi = segment
        if lo[0] == hi[0] and lo[1] != hi[1]:
            axis, direction = 1, 3
        elif lo[1] == hi[1] and lo[0] != hi[0]:
            axis, direction = 0, 1
        else:
            raise ValueError("Invalid native microbot rail segment")
        for value in range(min(lo[axis], hi[axis]), max(lo[axis], hi[axis]) + 1):
            xy = (value, lo[1]) if axis == 0 else (lo[0], value)
            if xy not in cells:
                raise ValueError("Missing native rail surface altitude")
            selected.add((*cells[xy], direction))
    return tuple(sorted(selected))


def direct_rail_payload(*, uid, area_uid, owner_id, cell, direction):
    """Original eYQ.a(PN,aBn,int): absent definition/container, level minus one."""
    from .combat_effects import _integer, _varint
    from .combat_displacement import position_payload

    if (
        any(
            type(value) is not int or not 0 < value < 1 << 63
            for value in (uid, area_uid)
        )
        or type(owner_id) is not int
        or not -(1 << 63) <= owner_id < 1 << 63
        or owner_id == 0
        or type(direction) is not int
        or direction not in (1, 3)
    ):
        raise ValueError("Invalid native direct rail identity")
    position = position_payload(cell)
    body = b"".join(
        _integer(tag, value)
        for tag, value in ((1, uid), (2, -1), (3, -1), (4, RAIL_REFERENCE))
    )
    body += b"\x2a" + _varint(len(position)) + position
    body += _integer(6, owner_id)
    additional = b"".join(
        _integer(tag, value)
        for tag, value in ((14, -1), (16, direction), (17, 0), (21, area_uid))
    )
    # Native fresh eZR.QH, captured from original direct factory; no PL clock.
    timing = bytes.fromhex(
        "080010ffffffffffffffffff011a0f080010ffffffffffffffffff011800"
        "20ffffffffffffffffff012800"
    )
    return (
        body
        + b"\x42"
        + _varint(len(additional))
        + additional
        + b"\x5a"
        + _varint(len(timing))
        + timing
    )


def rail_despawn(fight_id, action_id, area_uid):
    """Compatibility entry for native area retirement, including rails."""
    from .combat_effect_area_codec import area_retirement

    return area_retirement(fight_id, action_id, area_uid)


def synchronize_microbot_rails(
    fight,
    owner_id,
    *,
    packets,
    action_id,
    allocate_uid,
    allocate_area_uid,
    affiliation,
    callbacks,
):
    """Diff one owner inside the caller's private transaction and preserve other owners."""
    from .combat_effect_area import native_effect_areas, remove_owned_hour_area
    from .combat_fake_fighter import fake_fighter_constructor
    from .combat_microbot_network import _networks
    from .combat_state_ledger import StateLedger
    from .combat_entity_creation_delivery import immediate_entity_creation

    network = _networks(fight).get(owner_id)
    if network is None or network.get("owner_id") != owner_id:
        raise ValueError("Missing changed native microbot network")
    if type(affiliation) is not int or not -128 <= affiliation <= 127:
        raise ValueError("Missing native rail captured affiliation")
    definition = native_effect_areas().get(str(RAIL_REFERENCE), {})
    constructor = fake_fighter_constructor(definition, -1)
    if (
        constructor["kind"] != 6
        or constructor["obstacle"]
        or definition.get("effect_ids") != [168102]
        or definition.get("native_shape_class") != "anD"
        or definition.get("entry_masks")
        or definition.get("exit_masks")
    ):
        raise ValueError("Missing installed native rail prototype contract")
    desired = set(rail_cells(network))
    areas = fight.native_effect_areas
    existing = {}
    for identity, row in tuple(areas.items()):
        if (
            row.get("native_microbot_rail_source") != SOURCE
            or row.get("owner_id") != owner_id
        ):
            continue
        key = (*row["cell"], row["direction"])
        if key in existing or row.get("reference") != RAIL_REFERENCE:
            raise ValueError("Conflicting owned native rail projection")
        existing[key] = identity
    for key in sorted(set(existing) - desired):
        identity = existing[key]
        remove_owned_hour_area(fight, identity, callbacks=callbacks)
    for key in sorted(desired - set(existing)):
        cell, direction = key[:3], key[3]
        area_uid, uid = allocate_area_uid(), allocate_uid()
        if area_uid in areas:
            raise ValueError("Duplicate native rail area UID")
        payload = direct_rail_payload(
            uid=uid,
            area_uid=area_uid,
            owner_id=owner_id,
            cell=cell,
            direction=direction,
        )
        areas[area_uid] = dict(
            uid=area_uid,
            reference=RAIL_REFERENCE,
            level=-1,
            cell=cell,
            owner_id=owner_id,
            direction=direction,
            keep_after=False,
            native_obstacle_id=-1,
            native_obstacle_source="fbm.constructor",
            native_hour_contract=False,
            native_area_contract="faW",
            native_qq_bhi=False,
            native_qq_guard_source="Qq.constructor",
            native_type_id=definition["native_type_id"],
            native_removal_masks=(),
            native_cells_xy=(cell[:2],),
            native_geometry_reference=cell,
            native_geometry_reference_source="Qq.bcT.bcU_bcV_bcW",
            remaining_activations=definition["raw_bde"],
            native_running_effect_manager=constructor["running_effect_manager"],
            native_faw_constructor=constructor,
            child_effect_uids={},
            executing=False,
            effect_uid=uid,
            effect_class=339,
            target_id=None,
            effect_reference=-1,
            native_fight_affiliation=affiliation,
            native_fight_affiliation_source="faV.j(PV).bcM",
            native_microbot_rail_source=SOURCE,
            state_ledger=StateLedger(area_uid),
        )
        if hasattr(fight, "native_global_pv_collections"):
            from .combat_global_pv_collections import register_global_area

            register_global_area(fight, area_uid)
        packets.append(immediate_entity_creation(fight.id, action_id, 339, payload))
        callbacks.created(areas[area_uid])
