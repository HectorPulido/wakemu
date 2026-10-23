"""Declared entity binding from accredited committed gameplay producers.

Profiles opt into producers through sealed SQL authority. A resource planted
by a player becomes a counted member, never an event-owned disposable spawn.
"""
from . import environmental_presence as presence
from . import environmental_runtime as rules


def committed_planting(db, fact):
    """Bind a just-authenticated successful receipt in its existing transaction."""
    from . import environmental_storage as storage
    from .environmental_gameplay import GameplayFact

    if type(fact) is not GameplayFact or fact.kind != "resource_planted":
        raise ValueError("Environmental planting binding requires its committed fact")
    occupied = presence.capture(fact.map_id, fact.instance_id)
    if occupied is None or fact.region_id is None:
        return ()
    storage._transaction(db)
    storage._scope_lock(db, fact.map_id, fact.instance_id)
    if not presence.current(occupied, fact.map_id, fact.instance_id):
        return ()
    events = db.execute(
        "SELECT e.* FROM environmental_event_instances e "
        "JOIN environmental_participants p ON p.instance_id=e.instance_id "
        "JOIN environmental_runtime_profiles r ON (r.profile_key,r.version)=(e.profile_key,e.version) "
        "JOIN environmental_profile_bindings b ON (b.profile_key,b.version)=(r.profile_key,r.version) "
        "WHERE b.producer='committed_planting' AND r.family='resource_plant' AND r.sealed AND r.enabled "
        "AND e.state='active' AND e.map_id=%s AND e.world_instance_id=%s AND e.region_id=%s "
        "AND p.account_id=%s AND p.character_id=%s AND p.eligible AND p.completed_at_ms IS NULL "
        "AND p.joined_at_ms<=%s AND e.started_at_ms<=%s AND e.deadline_ms>%s "
        "ORDER BY e.instance_id FOR UPDATE OF e",
        (
            fact.map_id,
            fact.instance_id,
            fact.region_id,
            fact.account_id,
            fact.character_id,
            fact.occurred_at_ms,
            fact.occurred_at_ms,
            fact.occurred_at_ms,
        ),
    ).fetchall()
    membership = dict(
        entity_kind="resource",
        entity_id=fact.entity_id,
        reference=fact.reference,
        source_key=fact.receipt_key,
        spawn_owned=False,
    )
    bound = []
    for event in events:
        objectives = storage._objectives(db, storage._event_profile(db, event))
        if not any(
            rules.objective_increment(row, fact, membership=membership) > 0
            for row in objectives
        ):
            continue
        if (
            storage.register_memberships(db, event["instance_id"], [membership])
            is False
        ):
            continue
        bound.append(event["instance_id"])
    return tuple(bound)
