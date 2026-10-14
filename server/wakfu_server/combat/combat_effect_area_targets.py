"""Qq targets for the resolver, distinct from fighters and their resources."""
from dataclasses import dataclass
from .combat_effect_area_queries import _rows
from .combat_area_affiliation import area_affiliation


@dataclass(frozen=True)
class NativeAreaTarget:
    id: int
    position: tuple
    team: int
    owner_id: int
    physical_radius: int = 0
    direction: int = 7
    native_obstacle_id: int = -1
    native_movement_blocking: bool = False
    native_is_obstacle: bool = False
    native_los_height: int = 0


def area_targets(fight):
    targets = []
    for row in _rows(fight):
        constructor = (
            row.get("native_faw_constructor")
            if row.get("native_area_contract") == "faW"
            else row.get("native_wall_constructor")
            if row.get("native_area_contract") == "fbd"
            else None
        )
        owner = fight.actors.get(row["owner_id"])
        border = row.get("native_area_contract") == "faP"
        environment = row.get("native_environment_source") is not None
        if environment:
            from .combat_environment_glyphs import verify_environment_glyph

            verify_environment_glyph(fight, row)
        if border:
            from .combat_battleground_border import SOURCE

            if (
                row.get("owner_id") is not None
                or row.get("native_border_source") != SOURCE
            ):
                raise ValueError("Missing native faP null-owner constructor")
        elif owner is None and not environment:
            raise ValueError("Missing authoritative Qq owner affiliation")
        targets.append(
            NativeAreaTarget(
                row["uid"],
                tuple(row["cell"]),
                -1 if border or environment else area_affiliation(fight, row),
                row["owner_id"],
                direction=row["direction"],
                native_obstacle_id=row.get("native_obstacle_id", -1),
                native_movement_blocking=constructor["movement_blocking"]
                if constructor is not None
                else False,
                native_is_obstacle=constructor["obstacle"]
                if constructor is not None
                else False,
                native_los_height=(
                    constructor["height"]
                    if row.get("native_area_contract") == "faW"
                    else constructor["bcK_value"]
                    if row.get("native_area_contract") == "fbd"
                    else 0
                ),
            )
        )
    return tuple(targets)


def retained_area_source_target(fight, identity):
    """Resolve a selected Qq source pointer without restoring Qs membership."""
    from .combat_state_managers import registered_area_pv, retained_area_pv_row

    if identity in fight.actors:
        return None
    pv = registered_area_pv(fight, identity)
    if pv is None:
        return None
    row = retained_area_pv_row(fight, identity)
    affiliation = area_affiliation(fight, row)
    return NativeAreaTarget(
        identity,
        pv.position,
        affiliation,
        row.get("owner_id"),
        direction=row["direction"],
        native_los_height=pv.native_los_height,
    )


def area_target_context(target):
    if not isinstance(target, NativeAreaTarget):
        raise ValueError("Unknown native area target")
    # faW/bcQ inherit faV.bEe=true and Qq.bcL=0. Their registered
    # obstacle byte and bcO/bcP override remain distinct from Qq defaults.
    return dict(
        is_Qq=True,
        is_eGj=False,
        is_eHH=False,
        is_amO=True,
        bEe=True,
        bcR=False,
        bcN=target.native_obstacle_id,
        bcO=target.native_is_obstacle,
        bcP=target.native_movement_blocking,
        q_owner_id=target.owner_id,
    )


def target_available(target):
    # Native Qq has no HP resource. Its presence in Qs, not a fabricated
    # positive HP field, determines whether the resolver can inspect it.
    return isinstance(target, NativeAreaTarget) or target.hp > 0
