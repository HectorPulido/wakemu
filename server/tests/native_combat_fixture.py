"""Owned synthetic placement producers for focused combat tests."""


def initialize_fixture_qi(fight):
    """Own a flat synthetic arena and register actors before placement ends."""
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )

    xs = [cell[0] for cell in fight.walkable]
    ys = [cell[1] for cell in fight.walkable]
    width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    fight.native_qi_snapshot = dict(
        x=min(xs),
        y=min(ys),
        width=width,
        height=height,
        cell_masks=[0] * (width * height),
    )
    for slot, actor in enumerate(fight.actors.values()):
        actor.native_obstacle_id = slot
        actor.physical_radius = 0
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                identity: actor.physical_radius
                for identity, actor in fight.actors.items()
            },
        ),
    )
