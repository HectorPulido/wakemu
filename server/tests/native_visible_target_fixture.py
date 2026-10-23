"""Plan native footprint endpoints without changing actors or LOS authority."""
from wakfu_server.combat_casting_alignment import native_casting_alignment
from wakfu_server.combat_casting_los import native_casting_ray
from wakfu_server.combat_obstacle_condition import footprint


def visible_target_cells(
    fight,
    actor_authority,
    map_id,
    caster,
    target,
    *,
    minimum,
    maximum,
    source_cell=None,
    casting_flags=None,
    require_los=True,
    path_query=None,
):
    """Return ordered real target-footprint cells for a paid fixture planner.

    A hypothetical source is only a BFS query: the caller must pay its actual
    movement before casting. Target QK stays in the ray; only the caster and
    the fight's existing native ignored slots are excluded. Casting flags and
    effective range must come from the selected spell's actual authority.
    """
    source = caster.position if source_cell is None else tuple(source_cell)
    candidates = []
    for x, y in footprint(target.position, target.physical_radius):
        cell = (x, y, target.position[2])
        distance = abs(x - source[0]) + abs(y - source[1])
        if not minimum <= distance <= maximum:
            continue
        if casting_flags is not None and not native_casting_alignment(
            source,
            cell,
            path_query=path_query,
            **{
                key: casting_flags[key]
                for key in ("linear", "diagonal", "linear_path", "path_option")
            },
        ):
            continue
        if require_los and not native_casting_ray(
            fight,
            actor_authority,
            map_id,
            source,
            cell,
            source_height=caster.native_los_height,
            target_height=target.native_los_height,
            ignored_slots=(
                *fight.native_qi_visibility_ignored_slots,
                caster.native_obstacle_id,
            ),
        ):
            continue
        candidates.append((distance, cell))
    return tuple(cell for _, cell in sorted(candidates))
