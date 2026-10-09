"""Resolve registered PVs or the exact transient native construction PV."""


def native_actor(fight, identity):
    actor = fight.actors.get(identity)
    if actor is not None:
        return actor
    from .combat_summon_initialization import detached_actor

    return detached_actor(fight, identity)


def native_actor_population(fight):
    from .combat_summon_initialization import detached_actors

    construction = detached_actors(fight)
    if construction:
        # Fresh eZQ/PO owns beg=[SELF], not the surrounding battle roster.
        return (construction[-1],)
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_pv_iterator

        # faH receives PN.bab(), whose native PV collection includes IN_PLAY
        # and OFF_PLAY but omits OUT_OF_PLAY. Preserve native order and use the
        # registered producer instead of filtering by numeric HP.
        identities = global_pv_iterator(fight, caster_id=None)
        return tuple(
            fight.actors[identity]
            for identity in identities
            if identity in fight.actors
            and not getattr(fight.actors[identity], "pve_withdrawn", False)
        )
    return tuple(
        actor
        for actor in fight.actors.values()
        if not getattr(actor, "pve_withdrawn", False)
    )


def detached_authority(fight, actor):
    from .combat_summon_initialization import detached_actor_authority

    return detached_actor_authority(fight, actor)
