"""Native group outbox batches scoped to current occupied World generations.

Use publish() for delivery: PersistentGroups' claim lock spans preparation,
require-all broadcast and acknowledgement. Pending rows are never completed
merely because a character, group or empty map was observed in PostgreSQL.
"""
from dataclasses import dataclass

from . import environmental_presence as presence
from . import environmental_storage as storage
from .environmental_group_population import _remaining_destroy_members, _roster_digest
from .environmental_runtime import integer


@dataclass(frozen=True)
class GroupPublication:
    instance_id: int
    group_ordinal: int
    kind: str
    group_id: int
    revision: int | None
    roster_sha256: str
    packets: tuple
    scope_token: tuple


def _current(db, row, *, map_id, instance_id):
    owned = db.execute(
        "SELECT * FROM environmental_owned_groups WHERE instance_id=%s AND group_ordinal=%s",
        (row["instance_id"], row["group_ordinal"]),
    ).fetchone()
    if owned is None or (owned["map_id"], owned["world_instance_id"]) != (
        map_id,
        instance_id,
    ):
        raise ValueError("Environmental group publication has foreign ownership")
    membership = db.execute(
        "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind='group' AND entity_id=%s",
        (owned["instance_id"], owned["group_id"]),
    ).fetchone()
    if (
        membership is None
        or not membership["spawn_owned"]
        or membership["source_key"] != owned["source_key"]
        or membership["reference"] != owned["group_reference"]
    ):
        raise ValueError(
            "Environmental group publication lacks original event ownership"
        )
    identities = db.execute(
        "SELECT monster_id,monster_reference,native_level FROM environmental_owned_group_members "
        "WHERE instance_id=%s AND group_ordinal=%s ORDER BY monster_id",
        (owned["instance_id"], owned["group_ordinal"]),
    ).fetchall()
    frozen = db.execute(
        "SELECT monster_id,monster_reference FROM environmental_event_group_members "
        "WHERE instance_id=%s AND group_id=%s",
        (owned["instance_id"], owned["group_id"]),
    ).fetchall()
    if not identities or {
        (r["monster_id"], r["monster_reference"]) for r in identities
    } != {(r["monster_id"], r["monster_reference"]) for r in frozen}:
        raise ValueError("Environmental publication frozen group members changed")
    group = db.execute(
        "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        (map_id, instance_id, owned["group_id"]),
    ).fetchone()
    remaining = _remaining_destroy_members(db, owned, group)
    if group is not None and remaining is None:
        actual = {(r["id"], r["ref"], r["level"]) for r in group["members"]}
        expected = {
            (r["monster_id"], r["monster_reference"], r["native_level"])
            for r in identities
        }
        if (
            actual != expected
            or _roster_digest(group["members"]) != owned["roster_sha256"]
        ):
            raise ValueError(
                "Environmental group publication physical incarnation changed"
            )
    if remaining is not None:
        if not remaining and group is not None and group["status"] != "defeated":
            raise ValueError(
                "Fully consumed environmental group is not retired from availability"
            )
        native_ids = tuple(member["id"] for member in remaining)
    else:
        native_ids = tuple(r["monster_id"] for r in identities)
    return owned, group, native_ids


def pending(db, *, map_id, instance_id, now_ms, limit=64):
    """Prepare exact current native batches; caller must serialize group claims."""
    token = presence.capture(map_id, instance_id)
    if token is None:
        return ()
    storage._transaction(db)
    integer(now_ms, "group publication clock")
    integer(limit, "group publication limit", minimum=1)
    if limit > 256:
        raise ValueError("Environmental group publication exceeds its bound")
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(token, map_id, instance_id):
        return ()
    rows = db.execute(
        "SELECT p.*,e.state FROM environmental_group_publications p "
        "JOIN environmental_owned_groups o USING(instance_id,group_ordinal) "
        "JOIN environmental_event_instances e ON e.instance_id=o.instance_id "
        "WHERE o.map_id=%s AND o.world_instance_id=%s AND p.published_at_ms IS NULL "
        "AND p.superseded_at_ms IS NULL ORDER BY p.created_at_ms,p.instance_id,p.group_ordinal,p.kind "
        "LIMIT %s FOR UPDATE OF p",
        (map_id, instance_id, limit),
    ).fetchall()
    from wakfu_server.combat_monster_world import spawn_group, remove_message

    result = []
    for row in rows:
        owned, group, identities = _current(
            db, row, map_id=map_id, instance_id=instance_id
        )
        if row["kind"] == "spawn":
            if owned["retired_at_ms"] is not None or (
                group is not None and group["status"] == "defeated"
            ):
                db.execute(
                    "UPDATE environmental_group_publications SET superseded_at_ms=%s "
                    "WHERE instance_id=%s AND group_ordinal=%s AND kind='spawn'",
                    (now_ms, owned["instance_id"], owned["group_ordinal"]),
                )
                continue
            if group is None:
                raise ValueError("Environmental unretired group disappeared")
            if group["status"] == "fighting" or row["state"] != "active":
                continue  # Preserve pending authority; never respawn a claimed fight.
            packets = (
                (12608, spawn_group(group["members"], group_id=owned["group_id"])),
            )
            revision = group["revision"]
        else:
            if owned["retired_at_ms"] is None or group is not None:
                raise ValueError(
                    "Environmental despawn lacks exact completed retirement"
                )
            if not identities:
                # A final idempotent removal also covers a peer that missed an
                # earlier individual removal. Native12304 disallows empty lists.
                identities = tuple(
                    member["monster_id"]
                    for member in db.execute(
                        "SELECT monster_id FROM environmental_owned_group_members "
                        "WHERE instance_id=%s AND group_ordinal=%s ORDER BY monster_id",
                        (owned["instance_id"], owned["group_ordinal"]),
                    ).fetchall()
                )
            packets = (remove_message(identities),)
            revision = None
        result.append(
            GroupPublication(
                owned["instance_id"],
                owned["group_ordinal"],
                row["kind"],
                owned["group_id"],
                revision,
                owned["roster_sha256"],
                packets,
                token,
            )
        )
    return tuple(result)


def acknowledge(db, *, map_id, instance_id, deliveries, now_ms):
    """Complete only batches already delivered to all captured map recipients.

    publish() supplies that delivery guarantee. This lower-level API does no
    socket I/O and must never be called on preparation or partial delivery.
    """
    storage._transaction(db)
    integer(now_ms, "group acknowledgement clock")
    if not deliveries:
        return 0
    storage._scope_lock(db, map_id, instance_id)
    count = 0
    for delivery in deliveries:
        if not isinstance(delivery, GroupPublication) or not presence.current(
            delivery.scope_token, map_id, instance_id
        ):
            continue
        row = dict(
            instance_id=delivery.instance_id, group_ordinal=delivery.group_ordinal
        )
        owned, group, _ = _current(db, row, map_id=map_id, instance_id=instance_id)
        if (
            owned["group_id"] != delivery.group_id
            or owned["roster_sha256"] != delivery.roster_sha256
            or (
                delivery.kind == "spawn"
                and (
                    group is None
                    or group["status"] != "available"
                    or group["revision"] != delivery.revision
                    or owned["retired_at_ms"] is not None
                )
            )
            or (
                delivery.kind == "despawn"
                and (group is not None or owned["retired_at_ms"] is None)
            )
        ):
            continue
        count += db.execute(
            "UPDATE environmental_group_publications SET published_at_ms=%s "
            "WHERE instance_id=%s AND group_ordinal=%s AND kind=%s AND published_at_ms IS NULL "
            "AND superseded_at_ms IS NULL",
            (now_ms, delivery.instance_id, delivery.group_ordinal, delivery.kind),
        ).rowcount
    return count


def publish(store, world, groups, *, map_id, instance_id, now_ms, limit=64):
    """Broadcast native owned batches once durable; retain failures for retry."""
    if groups.store is not store:
        raise ValueError(
            "Environmental publication group registry belongs to another store"
        )
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
            if not presence.current(delivery.scope_token, map_id, instance_id):
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
