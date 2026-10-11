"""Shared SQL restoration for fixed mineral and fishing resource identities."""
from psycopg.types.json import Jsonb


RESOURCE_KEYS = (
    "resource_uid",
    "map_id",
    "instance_id",
    "x",
    "y",
    "z",
    "resource_reference",
    "stage",
)


def restore_resource(db, slot, now, *, spawn_flag, empty_stage=None):
    """Insert a fixed resource, or revive its guarded empty-stage row.

    ``empty_stage`` is used by fishing, whose native exhausted spot remains as
    a stage-1 resource. Mining deletes the harvested row and leaves it unset.
    Cell conflicts and mismatched existing identities are left for a later tick.
    """
    resource = {key: slot[key] for key in RESOURCE_KEYS}
    resource["creation_time"] = int(now.timestamp() * 1000)
    restored = False
    inserted_new = False
    if empty_stage is not None:
        revived = db.execute(
            "UPDATE planted_resources SET stage=%s,creation_time=%s "
            "WHERE resource_uid=%s AND map_id=%s AND instance_id=%s "
            "AND x=%s AND y=%s AND z=%s AND resource_reference=%s AND stage=%s "
            "RETURNING resource_uid",
            (
                resource["stage"],
                resource["creation_time"],
                resource["resource_uid"],
                resource["map_id"],
                resource["instance_id"],
                resource["x"],
                resource["y"],
                resource["z"],
                resource["resource_reference"],
                empty_stage,
            ),
        ).fetchone()
        restored = revived is not None
    if not restored:
        # An existing UID that is not the guarded exhausted row must never be
        # overwritten or shadowed by a second insert attempt.
        if (
            db.execute(
                "SELECT 1 FROM planted_resources WHERE resource_uid=%s",
                (resource["resource_uid"],),
            ).fetchone()
            is not None
        ):
            return False
        inserted = db.execute(
            "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING resource_uid",
            tuple(resource[key] for key in RESOURCE_KEYS)
            + (resource["creation_time"],),
        ).fetchone()
        if inserted is None:
            return False
        restored = True
        inserted_new = True
    if not restored:
        return False
    event = dict(resource)
    if inserted_new:
        event[spawn_flag] = True
    db.execute(
        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL) "
        "ON CONFLICT(resource_uid) DO UPDATE SET resource=EXCLUDED.resource,group_payload=NULL,published=FALSE",
        (resource["resource_uid"], Jsonb(event)),
    )
    return True
