"""Bounded, occupied-scope release of counted wild/player-owned memberships.

Release keeps the physical entity and audit membership. Event-owned despawn
requires its separate qualified producer/identity consumer and stays pending.
"""
from . import environmental_presence as presence
from .environmental_runtime import integer


def release_memberships(db, *, map_id, instance_id, now_ms, limit=128):
    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return ()
    integer(now_ms, "cleanup clock")
    integer(limit, "cleanup limit", minimum=1)
    if limit > 1024:
        raise ValueError("Environmental cleanup batch exceeds its bound")
    from . import environmental_storage as storage

    storage._transaction(db)
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        return ()
    return tuple(
        db.execute(
            "WITH pending AS (SELECT c.instance_id,c.entity_kind,c.entity_id "
            "FROM environmental_cleanup_outbox c JOIN environmental_event_instances e USING(instance_id) "
            "WHERE e.map_id=%s AND e.world_instance_id=%s AND e.state IN ('completed','expired','cancelled') "
            "AND c.action='release_membership' AND c.completed_at_ms IS NULL "
            "ORDER BY c.requested_at_ms,c.instance_id,c.entity_kind,c.entity_id "
            "LIMIT %s FOR UPDATE OF c SKIP LOCKED) "
            "UPDATE environmental_cleanup_outbox c SET completed_at_ms=%s FROM pending p "
            "WHERE (c.instance_id,c.entity_kind,c.entity_id)=(p.instance_id,p.entity_kind,p.entity_id) "
            "RETURNING c.instance_id,c.entity_kind,c.entity_id",
            (map_id, instance_id, limit, now_ms),
        ).fetchall()
    )
