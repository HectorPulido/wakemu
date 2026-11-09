"""Point-mover surface gates before paid movement commits.

Sm supplies physical transitions. Combat walking also excludes fight-sterile
surfaces as a server floor policy; mob-sterile alone remains usable. Special
jumps and ordinary encounter placement retain their separate restrictions.
"""
from types import SimpleNamespace

# Original Vy.bmd/bmg/bmj over exported native-sn-columns.bLF.
_MOB_STERILE = 1 << 1
_FIGHT_STERILE = 1 << 0
_SPECIAL_JUMP = 1 << 3
_SPECIAL_JUMP_ORIGIN = 1 << 4


def require_native_walk_surfaces(fight, actor, path):
    if not path:
        return
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if provenance is None:
        return  # Legacy geometry-only fixtures have no published Vy authority.
    if not isinstance(provenance, dict) or type(provenance.get("map_id")) is not int:
        raise ValueError("Missing native walking map provenance")
    radius = actor.physical_radius
    if type(radius) is not int or radius < 0:
        raise ValueError("Missing native walking radius")
    if radius:
        return  # Preserve the separately qualified native full-body branch.
    from .combat_sn_path import NativeSnColumns

    columns = NativeSnColumns.from_published(provenance["map_id"])
    if columns.source_sha256 != provenance.get("source_sha256"):
        raise ValueError("Native walking physical source differs from arena")
    status = getattr(actor, "native_death_status", None)
    kind = status.get("actor_kind") if isinstance(status, dict) else None
    if kind not in ("bjo", "bje"):
        raise ValueError("Missing original walking actor constructor kind")
    special_jump = None

    def surface(cell):
        rows = columns.column(*cell[:2]) or ()
        matches = [row for row in rows if row.z == cell[2]]
        if not matches:
            raise ValueError("Walking altitude has no native physical surface")
        # Original VA.a selects the last exact altitude (also used by the
        # existing NativeSnPathAuthority); duplicate-z columns are legitimate.
        return matches[-1]

    air_crossing_cells = set()
    previous = actor.position
    for destination in path:
        source, target = surface(previous), surface(destination)
        if kind == "bje" and target.blf & _FIGHT_STERILE:
            raise ValueError("Combat walking destination is fight-sterile")
        if target.blf & _SPECIAL_JUMP or source.blf & _SPECIAL_JUMP:
            if special_jump is None:
                from .combat_world_properties import has_world_property, registry

                row = registry().get("85")
                if not isinstance(row, dict) or row.get("name") != "RELIC_SPECIAL_JUMP":
                    raise ValueError("Missing published native special-jump property")
                world = getattr(actor, "native_world_properties", None)
                properties = getattr(actor, "native_fight_properties", None)
                if world is None or properties is None:
                    raise ValueError("Missing complete native walking properties")
                special_jump = kind == "bjo" and has_world_property(
                    SimpleNamespace(
                        world_properties=frozenset(world),
                        fight_properties=frozenset(properties),
                    ),
                    85,
                )
            # Original Sn expansion, Sp.bpJ from beS.dgu. A special crossing
            # needs its actual takeoff/landing surface, not just numeric height.
            entering_without_jump = bool(target.blf & _SPECIAL_JUMP) and (
                not special_jump or not source.blf & _SPECIAL_JUMP_ORIGIN
            )
            leaving_without_landing = (
                special_jump
                and bool(source.blf & _SPECIAL_JUMP)
                and not target.blf & _SPECIAL_JUMP_ORIGIN
            )
            if entering_without_jump or leaving_without_landing:
                raise ValueError(
                    "Native walking requires a valid special-jump crossing"
                )
        if special_jump and target.blf & _SPECIAL_JUMP:
            air_crossing_cells.add(destination)
        previous = destination
    from .combat_ground_support import require_walk

    require_walk(fight, actor, path, air_crossing_cells=air_crossing_cells)


def native_npc_point_placement_allowed(
    columns, cell, *, _matches=None, _ground_supported=None
):
    """Ordinary encounter policy; special spell birth contracts stay separate.

    Formation is reconstructed server policy. Its point NPC anchors must be
    normal native surfaces, rather than mob-sterile or special-jump surfaces.
    """
    matches = (
        _matches
        if _matches is not None
        else [row for row in columns.column(*cell[:2]) or () if row.z == cell[2]]
    )
    from .combat_ground_support import supported

    return (
        bool(matches)
        and not matches[-1].blf & (_MOB_STERILE | _SPECIAL_JUMP)
        and (
            supported(columns.map_id, cell, columns.source_sha256)
            if _ground_supported is None
            else _ground_supported
        )
    )


_NATIVE_POINT_PLACEMENT = native_npc_point_placement_allowed


def native_npc_walk_blocked_cells(fight, actor, cells, *, columns_observer=None):
    """Filter ordinary NPC planner anchors without changing displacement QI."""
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    status = getattr(actor, "native_death_status", None)
    if (
        provenance is None
        or getattr(actor, "physical_radius", None) != 0
        or not isinstance(status, dict)
        or status.get("actor_kind") != "bje"
    ):
        return set()
    if not isinstance(provenance, dict) or type(provenance.get("map_id")) is not int:
        raise ValueError("Missing native walking map provenance")
    from .combat_sn_path import NativeSnColumns

    columns = NativeSnColumns.from_published(provenance["map_id"])
    if columns.source_sha256 != provenance.get("source_sha256"):
        raise ValueError("Native walking physical source differs from arena")
    if columns_observer is not None:
        columns_observer(columns)
    from .combat_ground_support import escape_prefix_cells
    from .combat_ground_support import supported

    escape = escape_prefix_cells(fight, actor)
    blocked = set()
    for cell in cells:
        matches = [row for row in columns.column(*cell[:2]) or () if row.z == cell[2]]
        physical = bool(matches) and not matches[-1].blf & (
            _FIGHT_STERILE | _SPECIAL_JUMP
        )
        if (
            not physical
            or cell not in escape
            and not supported(columns.map_id, cell, columns.source_sha256)
        ):
            blocked.add(cell)
    return blocked
