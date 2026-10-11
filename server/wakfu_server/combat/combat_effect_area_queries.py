"""Qs/Qq predicates with explicit registered-area snapshots.

Specific range count uses Qq.bct, the prototype reference (eLn).
Registered faV geometry and captured affiliations remain explicit authority.
"""
from .combat_effect_area_geometry import contains_area_cell, refresh_area_geometry
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS


def _rows(fight):
    rows = getattr(fight, "native_effect_areas", {})
    if not isinstance(rows, dict):
        raise ValueError("Missing native area manager")
    for uid, row in rows.items():
        if (
            not isinstance(row, dict)
            or row.get("uid") != uid
            or (
                row.get("native_hour_contract") is not True
                and row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
            )
        ):
            raise ValueError("Unaudited native effect-area snapshot")
        if row.get("native_area_contract") == "faW":
            from .combat_effect_area import native_effect_areas
            from .combat_fake_fighter import verified_fake_fighter

            verified_fake_fighter(
                row, native_effect_areas().get(str(row["reference"]), {})
            )
        if row.get("native_area_contract") == "faP":
            from .combat_battleground_border import verify_battleground_border

            verify_battleground_border(fight, row)
        if row.get("native_area_contract") == "faU":
            from .combat_effect_area import native_effect_areas
            from .combat_area_contracts import verified_deposit_grade

            verified_deposit_grade(
                row, native_effect_areas().get(str(row["reference"]), {})
            )
        if row.get("native_area_contract") == "fbd":
            from .combat_effect_area import native_effect_areas
            from .combat_wall_area import verified_wall_constructor

            verified_wall_constructor(
                row, native_effect_areas().get(str(row["reference"]), {})
            )
        if row.get("native_area_contract") == "faX" and (
            type(row.get("native_fight_affiliation")) is not int
            or not -128 <= row["native_fight_affiliation"] <= 127
            or row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
        ):
            raise ValueError("Missing captured native faX bcM authority")
        if row.get("native_environment_source") is not None:
            from .combat_environment_glyphs import verify_environment_glyph

            verify_environment_glyph(fight, row)
        refresh_area_geometry(fight, row)
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_area_order

        return tuple(rows[identity] for identity in global_area_order(fight))
    return tuple(rows.values())


def specific_area_count(
    fight, *, source_id, center, area_reference, minimum, maximum, owned=False
):
    """eLn/eJW: Prototype filter, optional owner, radius-zero ala.c distance.

    Native max<0 bypasses both minimum and maximum. Missing center returns0.
    """
    if (
        any(type(v) is not int for v in (area_reference, minimum, maximum))
        or type(owned) is not bool
    ):
        raise ValueError("Invalid native area range predicate")
    if center is None:
        return 0
    count = 0
    for row in _rows(fight):
        if row["uid"] == source_id or row["reference"] != area_reference:
            continue
        if owned and row["owner_id"] != source_id:
            continue
        distance = abs(row["cell"][0] - center[0]) + abs(row["cell"][1] - center[1])
        if maximum < 0 or minimum <= distance <= maximum:
            count += 1
    return count


def cell_contains_type(fight, *, cell, area_type, source_id=None, owned=False):
    """eID: hour aeV=fbp.rNI.aIc()=1; Qq.bcT/d tests XY only."""
    if type(area_type) is not int or type(owned) is not bool:
        raise ValueError("Invalid native area type predicate")
    if cell is None:
        return False
    for row in _rows(fight):
        if area_type != row.get("native_type_id", 1) or (
            owned and row["owner_id"] != source_id
        ):
            continue
        from .combat_effect_area_geometry import contains_area_cell

        if contains_area_cell(row, cell):
            return True
    return False


def own_specific_area(fight, *, reference, selector, caster_id, target_id, cell):
    """eOF: selected Qz area, or supplied target cell; compare PV owners."""
    rows = {row["uid"]: row for row in _rows(fight)}
    from .combat_state_managers import retained_area_pv_row, registered_area_pv

    selected_rows = {}
    for identity in (caster_id, target_id):
        if identity is None or identity in fight.actors:
            continue
        row = retained_area_pv_row(fight, identity)
        if row is not None:
            registered_area_pv(fight, identity)
            selected_rows[identity] = row
    source_owner = (
        selected_rows[caster_id]["owner_id"]
        if caster_id in selected_rows
        else caster_id
    )
    target_owner = (
        selected_rows[target_id]["owner_id"]
        if target_id in selected_rows
        else target_id
    )
    selected = caster_id if selector.lower() == "caster" else target_id
    if selected in selected_rows:
        return (
            selected_rows[selected]["reference"] == reference
            and source_owner == target_owner
        )
    if selected is not None:
        return False
    if caster_id is None:
        return False
    # Production cell routing supplies the native target aBn; it is not a
    # literal null-target scan. Missing cell remains unknown explicitly.
    if cell is None:
        raise ValueError("Missing native area criterion target form")
    return any(
        row["reference"] == reference
        and row["owner_id"] == source_owner
        and contains_area_cell(row, cell)
        for row in rows.values()
    )


def cell_contains_specific(fight, *, cell, reference, source_id=None, owned=False):
    """eIE: prototype identity and Qq.d, with optional PV owner identity."""
    if type(reference) is not int or type(owned) is not bool:
        raise ValueError("Invalid native specific-area predicate")
    if cell is None:
        return False
    rows = _rows(fight)
    source_owner = next(
        (r["owner_id"] for r in rows if r["uid"] == source_id), source_id
    )
    return any(
        r["reference"] == reference
        and (not owned or r["owner_id"] == source_owner)
        and contains_area_cell(r, cell)
        for r in rows
    )


def team_area_count(fight, *, source_id, center, area_type, minimum, maximum):
    """eLw: filter aeV type and caster bcM, excluding caster Qq itself."""
    if any(type(v) is not int for v in (area_type, minimum, maximum)):
        raise ValueError("Invalid native team-area range predicate")
    if center is None or source_id is None:
        return 0
    rows = _rows(fight)
    by_uid = {r["uid"]: r for r in rows}
    source_row = by_uid.get(source_id)
    if source_row is not None and "native_fight_affiliation" in source_row:
        source_affiliation = source_row["native_fight_affiliation"]
    else:
        owner = source_row["owner_id"] if source_row is not None else source_id
        source = getattr(fight, "actors", {}).get(owner)
        if source is None:
            raise ValueError("Missing native source area team")
        source_affiliation = getattr(
            source, "native_fight_affiliation", getattr(source, "team", None)
        )
    count = 0
    for row in rows:
        if row["uid"] == source_id or area_type != row.get("native_type_id", 1):
            continue
        if "native_fight_affiliation" in row:
            affiliation = row["native_fight_affiliation"]
        else:
            row_owner = getattr(fight, "actors", {}).get(row["owner_id"])
            if row_owner is None:
                raise ValueError("Missing native registered area team")
            affiliation = getattr(
                row_owner, "native_fight_affiliation", getattr(row_owner, "team", None)
            )
        if type(affiliation) is not int or type(source_affiliation) is not int:
            raise ValueError("Missing native registered area bcM")
        if affiliation != source_affiliation:
            continue
        distance = abs(row["cell"][0] - center[0]) + abs(row["cell"][1] - center[1])
        if maximum < 0 or minimum <= distance <= maximum:
            count += 1
    return count


def area_type_count(
    fight, *, source_id, center, area_type, minimum, maximum, owned=False
):
    """eJW: exact long aeV filter, caster ownership and inclusive ala.c range."""
    if (
        any(type(v) is not int for v in (area_type, minimum, maximum))
        or type(owned) is not bool
    ):
        raise ValueError("Invalid native area-type range predicate")
    if center is None:
        return 0
    count = 0
    for row in _rows(fight):
        if row["uid"] == source_id or row.get("native_type_id", 1) != area_type:
            continue
        if owned and row["owner_id"] != source_id:
            continue
        distance = abs(row["cell"][0] - center[0]) + abs(row["cell"][1] - center[1])
        if maximum < 0 or minimum <= distance <= maximum:
            count += 1
    return count


NATIVE_AREA_TYPE_IDS = frozenset(
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 18, 19, 20)
)


def actor_on_area_type(fight, *, actor_id, area_type, owned=False):
    """eOs selects eGj, validates fbp enum, uses that actor as ownership anchor."""
    if type(area_type) is not int or type(owned) is not bool:
        raise ValueError("Invalid native actor-area predicate")
    # alP.longValue -> Java int before fbp.To lookup.
    area_type = ((area_type + (1 << 31)) % (1 << 32)) - (1 << 31)
    if area_type not in NATIVE_AREA_TYPE_IDS or actor_id is None:
        return False
    actor = getattr(fight, "actors", {}).get(actor_id)
    if actor is None:
        if any(r["uid"] == actor_id for r in _rows(fight)):
            return False  # A Qq PV is not the eGj required by eII.a.
        raise ValueError("Missing native selected fighter for area predicate")
    return cell_contains_type(
        fight, cell=actor.position, area_type=area_type, source_id=actor_id, owned=owned
    )


def areas_with_base_id(fight, *, reference, owner_id=None, all_owners=False):
    """ePj/ePi: count Qs.bdm matching long bct; optional exact PV owner."""
    if type(reference) is not int or type(all_owners) is not bool:
        raise ValueError("Invalid native base-area count")
    return sum(
        row["reference"] == reference
        and (all_owners or owner_id is not None and row.get("owner_id") == owner_id)
        for row in _rows(fight)
    )


def actor_on_specific_area(
    fight,
    *,
    actor_id,
    reference,
    ownership="all",
    selected_controller_id=None,
    owner_root_query=None
):
    """eOv: exact prototype and selected eHg geometry, own/team filter."""
    if ownership not in ("all", "own", "team") or type(reference) is not int:
        raise ValueError("Invalid native specific actor-area predicate")
    if actor_id is None:
        return False
    actor = fight.actors.get(actor_id)
    if selected_controller_id is not None and type(selected_controller_id) is not int:
        raise ValueError("Invalid verified native selected controller")
    selected_owner = (
        actor_id if selected_controller_id is None else selected_controller_id
    )
    selected_affiliation = None
    if actor is None:
        from .combat_state_managers import selected_native_area_entity

        actor = selected_native_area_entity(fight, actor_id)
        if actor is None:
            raise ValueError("Missing native selected area actor")
        selected_owner = actor.owner_id
        selected_affiliation = actor.native_fight_affiliation
    else:
        selected_affiliation = getattr(actor, "native_fight_affiliation", actor.team)
    if owner_root_query is not None and not callable(owner_root_query):
        raise ValueError("Invalid native owner root authority")
    if ownership == "own" and owner_root_query is not None:
        selected_owner = owner_root_query(selected_owner)
    rows = _rows(fight)
    for row in rows:
        if row["reference"] != reference:
            continue
        area_owner = row.get("owner_id")
        if ownership == "own" and owner_root_query is not None:
            area_owner = owner_root_query(area_owner)
        if ownership == "own" and area_owner != selected_owner:
            continue
        if ownership == "team":
            owner = fight.actors.get(row.get("owner_id"))
            if owner is None:
                raise ValueError("Missing native area affiliation")
            if getattr(owner, "native_fight_affiliation", owner.team) != getattr(
                actor, "native_fight_affiliation", selected_affiliation
            ):
                continue
        radius = actor.physical_radius
        if type(radius) is not int or radius != 0:
            raise ValueError("Unaudited native eOv Qq.a nonzero actor radius")
        if contains_area_cell(row, actor.position):
            return True
    return False


def closest_specific_area_distance(
    fight, *, selected_id, reference, use_path, owner_id=None, path_distance=None
):
    """eJT/eIw: exact prototype/direct owner, positive distances only."""
    if (
        type(reference) is not int
        or not -(1 << 63) <= reference < (1 << 63)
        or type(use_path) is not bool
    ):
        raise ValueError("Invalid native closest-area arguments")
    if selected_id is None:
        return -1
    actor = fight.actors.get(selected_id)
    if actor is None:
        if any(row["uid"] == selected_id for row in _rows(fight)):
            return -1  # Native eIw requires eGj, not faV eHg.
        raise ValueError("Unregistered native closest-area selected actor")
    center = actor.position
    found = []
    for row in _rows(fight):
        if row["reference"] != reference or (
            owner_id is not None and row["owner_id"] != owner_id
        ):
            continue
        if use_path:
            if not callable(path_distance):
                raise ValueError(
                    "Missing native Sn closest-area path-distance authority"
                )
            distance = path_distance(actor, row)
        else:
            # aBn.A, with Java signed-int subtraction/absolute/addition.
            wrap = lambda v: ((v + (1 << 31)) % (1 << 32)) - (1 << 31)
            absolute = lambda v: v if v == -(1 << 31) else abs(v)
            distance = wrap(
                sum(absolute(wrap(a - b)) for a, b in zip(center[:2], row["cell"][:2]))
            )
        if type(distance) is not int or not -(1 << 31) <= distance < (1 << 31):
            raise ValueError("Missing native signed closest-area distance")
        if distance > 0:
            found.append(distance)
    return min(found, default=-1)
