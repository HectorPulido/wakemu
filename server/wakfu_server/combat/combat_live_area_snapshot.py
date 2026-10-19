"""Native myK/fec snapshot constructors for live non-retained Qs areas.

This projection never replays a vanished Qe, executes server effects or allocates
identities. Original faX/faW and accredited standard faZ appearance consumers
determine the encoding.
"""
import struct


def _appearance(row, definition):
    contract = row.get("native_area_contract")
    if contract == "faZ":
        # Independent original-JAR clones prove0000 only for these current
        # generic315 standard hours. Legacy eYM/eYT indexed hours and the
        # retained1558 marker have independent producers and are excluded.
        reference = row.get("reference")
        if (
            type(reference) is not int
            or not 1546 <= reference <= 1557
            or row.get("effect_class") != 315
        ):
            return None
        if (
            row.get("native_type_id") != 1
            or row.get("native_hour_contract") is not True
            or row.get("native_qq_guard_source") != "Qq.constructor"
            or type(row.get("native_qq_bhi")) is not bool
            or type(row.get("effect_uid")) is not int
            or row["effect_uid"] <= 0
            or type(row.get("effect_reference")) is not int
            or row["effect_reference"] <= 0
            or definition.get("type") != "HOUR"
            or definition.get("native_class") != "bcU"
            or definition.get("native_type_id") != 1
            or definition.get("native_hour_contract") is not True
            or definition.get("effect_ids")
            or definition.get("entry_masks")
            or definition.get("exit_masks")
        ):
            raise ValueError("Live standard hour lacks its native315 constructor")
        return b"\x00\x00"
    if contract == "faX" and row.get("native_type_id") == 19:
        if (
            definition.get("type") != "GATE"
            or definition.get("native_class") != "bcS"
            or definition.get("native_type_id") != 19
            or definition.get("effect_ids")
            or definition.get("entry_masks")
            or definition.get("exit_masks")
        ):
            raise ValueError("Live gate snapshot lacks its installed native prototype")
        # Original faX.fTl is EMPTY_BYTE_ARRAY; faX.fA is a no-op.
        return b""
    if contract != "faW" or row.get("native_type_id") != 15:
        return None
    from .combat_fake_fighter import verified_fake_fighter

    constructor = verified_fake_fighter(row, definition)
    if 1 not in constructor["characteristic_ids"]:
        return b""  # Original faW.fTl/fA emits nothing without sgC.
    from .combat_fake_fighter_resources import fake_fighter_hp_state

    hp = fake_fighter_hp_state(row, definition)
    return struct.pack(">ii", hp["maximum"], hp["current"])


def _retained_area_ids(fight):
    retained = getattr(fight, "native_retained_records", {})
    owned = getattr(fight, "native_owned_area_effects", {})
    if not isinstance(retained, dict) or not isinstance(owned, dict):
        raise ValueError("Live area snapshot lacks retained creator authority")
    result = set()
    for uid, record in owned.items():
        if not isinstance(record, dict):
            raise ValueError("Invalid live area retained creator record")
        if (
            uid in retained
            and record.get("executed") is True
            and record.get("native_private_area") is None
        ):
            registered = retained[uid]
            if (
                not isinstance(registered, dict)
                or record.get("uid") != uid
                or record.get("effect_class") != registered.get("effect_class")
                or type(record.get("area_uid")) is not int
            ):
                raise ValueError("Invalid retained live area creation identity")
            result.add(record["area_uid"])
    return result


def sections(fight):
    """Current-row faV constructors, excluding retained and private areas.

    Other area contracts retain their existing specialized snapshot paths until
    their native fTl/fA appearance encoders have been accredited.
    """
    rows = getattr(fight, "native_effect_areas", {})
    if not isinstance(rows, dict):
        raise ValueError("Live area snapshot lacks the actual Qs population")
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_area_order

        order = global_area_order(fight)
    else:
        order = tuple(rows)
    retained = _retained_area_ids(fight)
    result = []
    hidden = None
    owner_affiliations = {}
    definitions = None
    for identity in order:
        row = rows[identity]
        if (
            identity in retained
            or row.get("native_private_area") is not None
            or row.get("native_environment_source") is not None
        ):
            continue
        if row.get("native_area_contract") not in ("faX", "faW", "faZ"):
            continue
        if definitions is None:
            from .combat_effect_area import native_effect_areas

            definitions = native_effect_areas()
        appearance = _appearance(row, definitions.get(str(row.get("reference")), {}))
        if appearance is None:
            continue
        reference, level = row.get("reference"), row.get("level")
        direction, obstacle = row.get("direction"), row.get("native_obstacle_id")
        cell, owner_id = row.get("cell"), row.get("owner_id")
        if (
            row.get("uid") != identity
            or any(
                type(value) is not int or not -(1 << 63) <= value < (1 << 63)
                for value in (reference, identity)
            )
            or reference <= 0
            or identity == 0
            or type(level) is not int
            or not -32768 <= level <= 32767
            or type(direction) is not int
            or not -1 <= direction <= 9
            or type(obstacle) is not int
            or not -1 <= obstacle <= 126
            or not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in cell[:2]
            )
            or type(cell[2]) is not int
            or not -32768 <= cell[2] <= 32767
        ):
            raise ValueError("Invalid current native faV snapshot constructor")
        affiliation = row.get("native_fight_affiliation")
        if owner_id is None:
            if (
                affiliation != -1
                or row.get("native_fight_affiliation_source")
                != "faV.constructor.null_owner"
            ):
                raise ValueError("Unowned live area lacks native null-owner capture")
            owner_wire = 0
        else:
            from .combat_effective_control import effective_affiliation
            from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

            if (
                type(owner_id) is not int
                or owner_id == 0
                or not -(1 << 63) <= owner_id < 1 << 63
            ):
                raise ValueError("Invalid native live area owner identity")
            owner = fight.actors.get(owner_id)
            if hidden is None:
                hidden = hidden_snapshot_actor_ids(fight)
            if owner is not None and owner_id not in owner_affiliations:
                owner_affiliations[owner_id] = effective_affiliation(fight, owner)
            if (
                owner is None
                or owner_id in hidden
                or row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
                or type(affiliation) is not int
                or affiliation != owner_affiliations[owner_id]
            ):
                raise ValueError(
                    "Live area capture cannot be reconstructed from its owner"
                )
            owner_wire = owner_id
        # buK reads the prototype first; fec.a then reads this exact fbm layout.
        result.append(
            struct.pack(
                ">qqiihqhib",
                reference,
                identity,
                *cell,
                owner_wire,
                level,
                direction,
                obstacle,
            )
            + appearance
        )
    return result
