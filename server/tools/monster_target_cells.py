"""Tooling-only empty target candidates from actual native QI registration."""


def native_empty_target_predicate(fight):
    """Exclude actual registered QI extents in XY, independent of floor Z.

    Legacy unregistered advisory scenes retain their explicit center/obstacle
    filter. No radius or registered population is inferred for those scenes.
    """
    occupied = {tuple(actor.position) for actor in fight.actors.values()}
    obstacles = {tuple(cell) for cell in getattr(fight, "native_obstacle_cells", ())}
    qi = None
    if getattr(fight, "native_qi_slots", None) is not None:
        from wakfu_server.combat_qi_fight import current_registry

        qi = current_registry(fight).snapshot()

    def empty(cell):
        cell = tuple(cell)
        return (
            cell not in occupied
            and cell not in obstacles
            and (qi is None or (qi.aK(*cell[:2]) and not qi.U(*cell[:2])))
        )

    return empty
