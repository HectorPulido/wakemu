"""Transactional legacy world-NPC rekeying without replacing live rows."""
from copy import deepcopy
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from .npc_actor_identity import allocate_block, lua_exact_identity


def actor_aliases(db, key):
    return {
        row["old_actor_id"]: row["new_actor_id"]
        for row in db.execute(
            "SELECT old_actor_id,new_actor_id FROM npc_actor_identity_aliases "
            "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            tuple(key),
        )
    }


def aliased_members(members, aliases):
    result = deepcopy(list(members))
    for member in result:
        member["id"] = aliases.get(member["id"], member["id"])
    return result


def identity_lineage(db, map_id, instance_id, identity):
    rows = db.execute(
        "SELECT old_actor_id,new_actor_id FROM npc_actor_identity_aliases "
        "WHERE map_id=%s AND instance_id=%s AND (old_actor_id=%s OR new_actor_id=%s)",
        (map_id, instance_id, identity, identity),
    )
    return sorted(
        {
            identity,
            *(
                value
                for row in rows
                for value in (row["old_actor_id"], row["new_actor_id"])
            ),
        }
    )


def repair_available_group(db, key):
    """Caller owns commit; row/status/claim checks precede all allocation."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("NPC identity repair requires an active transaction")
    key = tuple(key)
    if len(key) != 3 or any(type(value) is not int for value in key):
        raise ValueError("Invalid NPC repair group identity")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("monster-population:" + ":".join(map(str, key[:2])),),
    )
    row = db.execute(
        "SELECT members,status FROM combat_groups WHERE "
        "map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if row is None or row["status"] != "available":
        return dict(status="skipped_unavailable", key=key, aliases={})
    members = row["members"]
    if (
        type(members) is not list
        or not 1 <= len(members) <= 128
        or any(
            not isinstance(member, dict)
            or type(member.get("id")) is not int
            or member["id"] >= 0
            for member in members
        )
        or len({member["id"] for member in members}) != len(members)
    ):
        raise ValueError("Malformed durable NPC repair roster")
    unsafe = [
        member["id"] for member in members if not lua_exact_identity(member["id"])
    ]
    if not unsafe:
        return dict(status="already_exact", key=key, aliases={})
    for table in ("monster_maturation_outbox", "monster_reproduction_outbox"):
        if db.execute(
            f"SELECT 1 FROM {table} WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s AND NOT published LIMIT 1",
            key,
        ).fetchone():
            return dict(
                status="skipped_pending_ecology_publication", key=key, aliases={}
            )
    claims = tuple(
        db.execute(
            "SELECT monster_id FROM combat_group_members WHERE "
            "map_id=%s AND instance_id=%s AND group_id=%s ORDER BY monster_id FOR UPDATE",
            key,
        )
    )
    if {claim["monster_id"] for claim in claims} != {
        member["id"] for member in members
    }:
        raise ValueError("NPC repair claims differ from durable roster")
    previous = actor_aliases(db, key)
    if any(identity in previous for identity in unsafe):
        raise ValueError("Already remapped NPC identity remains in current roster")
    base = allocate_block(db, len(unsafe))
    aliases = {identity: -(base + index) for index, identity in enumerate(unsafe)}
    for old, new in aliases.items():
        db.execute(
            "INSERT INTO npc_actor_identity_aliases "
            "(map_id,instance_id,group_id,old_actor_id,new_actor_id) VALUES(%s,%s,%s,%s,%s)",
            (*key, old, new),
        )
        updated = db.execute(
            "UPDATE combat_group_members SET monster_id=%s WHERE "
            "map_id=%s AND instance_id=%s AND group_id=%s AND monster_id=%s",
            (new, *key, old),
        )
        if updated.rowcount != 1:
            raise ValueError("NPC repair member claim changed")
    replacement = aliased_members(members, aliases)
    changed = db.execute(
        "UPDATE combat_groups SET members=%s,revision=revision+1 "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='available'",
        (Jsonb(replacement), *key),
    )
    if changed.rowcount != 1:
        raise ValueError("NPC repair group is no longer available")
    return dict(status="remapped", key=key, aliases=aliases)


def repair_pending_birth(db, resource_uid):
    """Rekey a mutable, unpublished birth outbox; historical receipts stay intact."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("NPC birth repair requires an active transaction")
    row = db.execute(
        "SELECT group_payload,published FROM planting_growth_outbox "
        "WHERE resource_uid=%s FOR UPDATE",
        (resource_uid,),
    ).fetchone()
    if row is None or row["published"] or row["group_payload"] is None:
        return dict(status="skipped_birth_unavailable", resource_uid=resource_uid)
    payload = row["group_payload"]
    key = tuple(payload["key"])
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("monster-population:" + ":".join(map(str, key[:2])),),
    )
    group = db.execute(
        "SELECT members,status FROM combat_groups WHERE "
        "map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if group is not None:
        if group["status"] != "available":
            return dict(
                status="skipped_birth_group_unavailable",
                key=key,
                resource_uid=resource_uid,
            )
        result = repair_available_group(db, key)
        if result["status"].startswith("skipped_"):
            return dict(result, resource_uid=resource_uid)
    aliases = actor_aliases(db, key)
    members = aliased_members(payload["members"], aliases)
    unsafe = [
        member["id"] for member in members if not lua_exact_identity(member["id"])
    ]
    if unsafe and group is not None:
        raise ValueError("Birth outbox identity differs from repaired group")
    if unsafe:
        if (
            not 1 <= len(unsafe) <= 128
            or len(set(unsafe)) != len(unsafe)
            or any(type(value) is not int or value >= 0 for value in unsafe)
        ):
            raise ValueError("Malformed pending NPC birth identities")
        base = allocate_block(db, len(unsafe))
        for index, old in enumerate(unsafe):
            new = -(base + index)
            db.execute(
                "INSERT INTO npc_actor_identity_aliases "
                "(map_id,instance_id,group_id,old_actor_id,new_actor_id) VALUES(%s,%s,%s,%s,%s)",
                (*key, old, new),
            )
            aliases[old] = new
        members = aliased_members(payload["members"], aliases)
    if members == payload["members"]:
        return dict(status="birth_already_exact", key=key, resource_uid=resource_uid)
    db.execute(
        "UPDATE planting_growth_outbox SET group_payload=%s "
        "WHERE resource_uid=%s AND NOT published",
        (Jsonb(dict(payload, members=members)), resource_uid),
    )
    return dict(
        status="birth_remapped", key=key, resource_uid=resource_uid, aliases=aliases
    )
