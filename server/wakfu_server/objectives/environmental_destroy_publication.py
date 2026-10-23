"""Durable native action3 removal and current remaining-roster publication.

Registry claims precede database scope locks. Failed or obsolete deliveries stay
pending; a retry never republishes an historical roster containing removed UIDs.
"""
from dataclasses import dataclass

from . import environmental_presence as presence
from . import environmental_storage as storage
from .environmental_runtime import integer


@dataclass(frozen=True)
class DestroyPublication:
    instance_id: int
    group_ordinal: int
    group_revision: int
    monster_id: int
    destruction_token: str
    group_id: int
    current_revision: int | None
    current_status: str | None
    roster_sha256: str
    packets: tuple
    scope_token: tuple


def _delivery(db, row, *, map_id, instance_id, scope_token):
    from .environmental_group_publication import _current
    from .environmental_group_population import _roster_digest
    from .environmental_monster_destroy import _receipt
    from .environmental_monster_actions import native_action_response
    from wakfu_server.combat_monster_world import remove_message, spawn_group

    owned, group, identities = _current(db, row, map_id=map_id, instance_id=instance_id)
    # The same typed frozen-target verifier used by action replay validates the
    # publication's immutable UID, reference and original world incarnation.
    _receipt(row, owned)
    if row["monster_id"] in identities:
        raise ValueError("Destroyed environmental UID remains in its current roster")
    if group is not None and group["revision"] < row["group_revision"]:
        raise ValueError(
            "Environmental destruction publication precedes its physical revision"
        )
    # cyl resolves both world actors before scheduling its native animation.
    # Preserve the physical performer even if it has since left: a missing
    # client lookup must not prevent the following idempotent removal retry.
    packets = [
        native_action_response(
            row["monster_id"], row["character_id"], row["action_id"]
        ),
        remove_message((row["monster_id"],)),
    ]
    if group is not None and group["status"] == "available":
        if owned["retired_at_ms"] is not None or not group["members"]:
            raise ValueError("Environmental destruction has an invalid available group")
        packets.append(
            (12608, spawn_group(group["members"], group_id=owned["group_id"]))
        )
    elif group is None and owned["retired_at_ms"] is None:
        raise ValueError(
            "Environmental destruction group disappeared before retirement"
        )
    return DestroyPublication(
        row["instance_id"],
        row["group_ordinal"],
        row["group_revision"],
        row["monster_id"],
        row["token"],
        owned["group_id"],
        None if group is None else group["revision"],
        None if group is None else group["status"],
        owned["roster_sha256"] if group is None else _roster_digest(group["members"]),
        tuple(packets),
        scope_token,
    )


def pending(db, *, map_id, instance_id, now_ms, limit=64):
    """Prepare current batches under the caller's pre-held group registry lock."""
    integer(map_id, "destroy publication map", minimum=1)
    integer(instance_id, "destroy publication world instance")
    integer(now_ms, "destroy publication clock")
    integer(limit, "destroy publication limit", minimum=1)
    if limit > 256:
        raise ValueError("Environmental destruction publication exceeds its bound")
    token = presence.capture(map_id, instance_id)
    if token is None:
        return ()
    storage._transaction(db)
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(token, map_id, instance_id):
        return ()
    rows = db.execute(
        "SELECT d.*,p.created_at_ms,p.published_at_ms FROM environmental_destroy_publications p "
        "JOIN environmental_monster_destructions d USING(instance_id,group_ordinal,group_revision) "
        "JOIN environmental_owned_groups o USING(instance_id,group_ordinal) "
        "WHERE o.map_id=%s AND o.world_instance_id=%s AND p.published_at_ms IS NULL "
        "ORDER BY p.created_at_ms,p.instance_id,p.group_ordinal,p.group_revision "
        "LIMIT %s FOR UPDATE OF p",
        (map_id, instance_id, limit),
    ).fetchall()
    return tuple(
        _delivery(db, row, map_id=map_id, instance_id=instance_id, scope_token=token)
        for row in rows
    )


def acknowledge(db, *, map_id, instance_id, deliveries, now_ms):
    """Acknowledge only actual require-all deliveries of the same incarnation."""
    integer(now_ms, "destroy publication acknowledgement clock")
    storage._transaction(db)
    if not deliveries:
        return 0
    storage._scope_lock(db, map_id, instance_id)
    count = 0
    for delivery in deliveries:
        if not isinstance(delivery, DestroyPublication) or not presence.current(
            delivery.scope_token, map_id, instance_id
        ):
            continue
        row = db.execute(
            "SELECT d.*,p.created_at_ms,p.published_at_ms FROM environmental_destroy_publications p "
            "JOIN environmental_monster_destructions d USING(instance_id,group_ordinal,group_revision) "
            "JOIN environmental_owned_groups o USING(instance_id,group_ordinal) "
            "WHERE p.instance_id=%s AND p.group_ordinal=%s AND p.group_revision=%s "
            "AND o.map_id=%s AND o.world_instance_id=%s AND p.published_at_ms IS NULL FOR UPDATE OF p",
            (
                delivery.instance_id,
                delivery.group_ordinal,
                delivery.group_revision,
                map_id,
                instance_id,
            ),
        ).fetchone()
        if row is None:
            continue
        current = _delivery(
            db,
            row,
            map_id=map_id,
            instance_id=instance_id,
            scope_token=delivery.scope_token,
        )
        if current != delivery or not presence.current(
            delivery.scope_token, map_id, instance_id
        ):
            continue
        count += db.execute(
            "UPDATE environmental_destroy_publications SET published_at_ms=%s "
            "WHERE instance_id=%s AND group_ordinal=%s AND group_revision=%s AND published_at_ms IS NULL",
            (
                now_ms,
                delivery.instance_id,
                delivery.group_ordinal,
                delivery.group_revision,
            ),
        ).rowcount
    return count


def publish(store, world, groups, *, map_id, instance_id, now_ms, limit=64):
    """Deliver ordered native removal/remaining-roster batches, retaining retries."""
    if groups.store is not store:
        raise ValueError("Environmental destruction registry belongs to another store")
    token = presence.capture(map_id, instance_id)
    if token is None or token[0] is not world:
        return 0
    with groups.lock:
        with store.connection() as db:
            deliveries = pending(
                db, map_id=map_id, instance_id=instance_id, now_ms=now_ms, limit=limit
            )
        count = 0
        for delivery in deliveries:
            if delivery.scope_token[0] is not world or not presence.current(
                delivery.scope_token, map_id, instance_id
            ):
                break
            sent = world.emit_location_batch(
                map_id, instance_id, delivery.packets, require_all=True
            )
            if not sent or not presence.current(
                delivery.scope_token, map_id, instance_id
            ):
                continue
            with store.connection() as db:
                count += acknowledge(
                    db,
                    map_id=map_id,
                    instance_id=instance_id,
                    deliveries=(delivery,),
                    now_ms=now_ms,
                )
        return count
