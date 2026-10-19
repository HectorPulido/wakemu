"""Explicit non-attack Wakemu lifetime policy for authenticated summon owners.

An actual settled owner KO ends qualified descendant fighter summons. This is
not damage or a native spell28 runner, and earns no attack/KO/finisher credit.
"""
SOURCE = "wakemu.summon_owner_death.settled_relationship.v1"


def _source_registration(fight, identity):
    from .combat_summon_retirement import _registration

    actor, row, source, _, _ = _registration(fight, identity)
    if any(
        type(value) is not int
        for value in (identity, row["caster_id"], row["controller_id"])
    ):
        raise ValueError("Invalid owner-death summon identity")
    return actor, dict(
        actor_id=identity,
        caster_id=row["caster_id"],
        controller_id=row["controller_id"],
        reference=source["ref"],
        level=source["level"],
        relation_source=source["native_relation_source"],
        symbiot_source=source["native_symbiot_source"],
    )


def verify_transition(fight, update, death):
    """Authenticate retained relationship death without requiring owner HP now.

    A later legitimate owner resurrection does not invalidate a child's
    historical death. Its exact earlier parent death sequence remains proof.
    """
    from .combat_ordinary_death import _registered_death_event

    identity = death.get("actor_id")
    actor, registration = _source_registration(fight, identity)
    sequence = update.get("parent_death_sequence")
    if (
        update.get("policy") != SOURCE
        or update.get("source_registration") != registration
        or update.get("target_id") != actor.id
        or update.get("source_id") != registration["caster_id"]
        or type(update.get("hp_before")) is not int
        or update["hp_before"] <= 0
        or type(update.get("minimum")) is not int
        or update["minimum"] != 0
        or type(update.get("hp")) is not int
        or update["hp"] != 0
        or type(sequence) is not int
        or type(update.get("sequence")) is not int
        or not sequence < update["sequence"]
    ):
        raise ValueError("Unverified summon owner-death relationship transition")
    return _registered_death_event(fight, registration["caster_id"], sequence=sequence)


def settle(fight):
    """Cascade before retirement, timeline reconciliation and victory selection.

    Unknown/protected life contracts are preserved: only currently IN_PLAY
    summons with actual zero KO_TIME, mutable zero-minimum HP and no NO_DEATH
    property qualify. The ordinary death wire and retirement own cleanup.
    """
    from .combat_global_pv_collections import (
        global_fighter_guards,
        set_global_fighter_status,
    )
    from .combat_ordinary_death import registered_ordinary_death
    from .combat_summon_retirement import _ko_current
    from .combat_hp_raw import hp_raw_present, set_hp_raw_current
    from .combat_pve_departure import retired_pve_actor_ids

    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Malformed owner-death summon registration checkpoint")
    if not registrations or not hasattr(fight, "native_global_pv_collections"):
        return ()
    if getattr(fight, "_resolution_depth", 0) != 0:
        raise ValueError("Owner-death cascade requires outer effect settlement")
    # Rebuild a work index, never a cached ownership or death authority. Known
    # terminal children need no new transition; absent actors remain candidates
    # so their actual source validation still fails closed for a dead parent.
    children = {}
    for identity, row in registrations.items():
        if not isinstance(row, dict):
            raise ValueError("Malformed owner-death summon registration")
        actor = fight.actors.get(identity)
        if actor is None or actor.hp > 0:
            children.setdefault(row.get("caster_id"), []).append(identity)
    potential_roots = {
        identity
        for identity in children
        if identity in fight.actors and fight.actors[identity].hp == 0
    }
    if not potential_roots:
        return ()
    departed = retired_pve_actor_ids(fight)
    deaths = {
        event["actor_id"]: event["sequence"]
        for event in fight.events
        if event.get("kind") == "death"
    }
    roots = []
    for identity in deaths:
        if identity not in potential_roots:
            continue
        actor = fight.actors.get(identity)
        if (
            identity in deaths
            and actor is not None
            and identity not in departed
            and actor.hp == 0
            and global_fighter_guards(fight, identity)
            == dict(baF=False, baG=True, baK=False)
            and registered_ordinary_death(fight, actor)
        ):
            roots.append(identity)
    # Plan the complete authenticated closure before mutating any child.
    planned = []
    closed = set(roots)
    for parent_id in roots:
        for identity in children.get(parent_id, ()):
            if identity in closed or identity in departed:
                continue
            actor, receipt = _source_registration(fight, identity)
            world = getattr(actor, "native_world_properties", None)
            if (
                actor.hp <= 0
                or global_fighter_guards(fight, identity)
                != dict(baF=True, baG=False, baK=False)
                or not isinstance(world, frozenset)
                or 12 in world
                or _ko_current(actor) != 0
                or not isinstance(actor.effect_frozen, frozenset)
                or 1 in actor.effect_frozen
                or not isinstance(actor.effect_minima, dict)
                or type(actor.effect_minima.get(1)) is not int
                or actor.effect_minima[1] != 0
                or not isinstance(actor.effect_stats, dict)
                or actor.effect_stats.get(1) != actor.hp
            ):
                continue
            planned.append((identity, parent_id, receipt))
            roots.append(identity)
            closed.add(identity)
    for identity, parent_id, receipt in planned:
        actor = fight.actors[identity]
        hp_before = actor.hp
        if hp_raw_present(actor):
            set_hp_raw_current(actor, 0)
        else:
            actor.hp = 0
        fight._sync_resources(actor)
        fight._event(
            "owner_death_hp_minimum_update",
            policy=SOURCE,
            source_id=parent_id,
            target_id=identity,
            hp_before=hp_before,
            minimum=0,
            hp=0,
            parent_death_sequence=deaths[parent_id],
            source_registration=receipt,
        )
        death = fight._event("death", actor_id=identity)
        deaths[identity] = death["sequence"]
        set_global_fighter_status(fight, identity, "OFF_PLAY")
    return tuple(identity for identity, _, _ in planned)
