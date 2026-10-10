"""Database-configured exploration remains with atomic native resource claims.

Native world NPC death also requires rK/eHQ.DEAD (19): pW.isDead
alone is ignored by the exploration eGZ provider. cgN then selects the
native bje.dsq/AnimStatiqueCadavre branch; no fight death event is replayed.
"""
import struct

from psycopg.types.json import Jsonb
from psycopg.pq import TransactionStatus

from .monsters import owned_instance
from .npc_actor_identity import allocate_block
from wakfu_server.combat_monster_world import world_actor, remove_message

DEFAULT_LIFETIME_SECONDS = 3600
MAX_LIFETIME_SECONDS = 2678400


def lifetime_seconds(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='monster_corpse_policy'"
    ).fetchone()
    policy = None if row is None else row["value"]
    value = policy.get("lifetime_seconds") if isinstance(policy, dict) else None
    if type(value) is not int or not 1 <= value <= MAX_LIFETIME_SECONDS:
        raise ValueError(
            "Invalid monster corpse lifetime policy; expected 1..2678400 seconds"
        )
    return value


def defeated_members(fight, members):
    """Validate the complete original roster before retaining any dead member."""
    if fight.phase != "finished":
        raise ValueError("Corpses require a resolved fight")
    members = tuple(members)
    if not members or len({member["id"] for member in members}) != len(members):
        raise ValueError("Expected a unique original monster roster")
    result = []
    for member in members:
        actor = fight.actors.get(member["id"])
        verified = owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            **{
                key: member[key]
                for key in ("map_id", "instance_id", "x", "y", "z", "team")
            },
        )
        if member != verified or actor is None or actor.controlled or member["id"] >= 0:
            raise ValueError("Corpse roster contains a foreign actor")
        if actor.hp == 0:
            result.append(member)
    return tuple(result)


def retain(db, fight, members):
    """Commit with settlement. Retries never revive or extend an expired corpse."""
    selected = defeated_members(fight, members)
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Corpse retention requires settlement transaction")
    duration = lifetime_seconds(db)
    db.execute("SELECT pg_advisory_xact_lock(%s,%s)", (40, fight.id))
    for member in selected:
        existing = db.execute(
            "SELECT actor_id FROM monster_corpses WHERE fight_id=%s AND source_actor_id=%s",
            (fight.id, member["id"]),
        ).fetchone()
        if existing is not None:
            continue
        magnitude = allocate_block(db, 1)
        corpse = dict(member, id=-magnitude)
        db.execute(
            "INSERT INTO monster_corpses(fight_id,source_actor_id,actor_id,map_id,instance_id,monster,"
            "lifetime_seconds,created_at,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,"
            "CURRENT_TIMESTAMP+make_interval(secs=>%s)) "
            "ON CONFLICT(fight_id,source_actor_id) DO NOTHING",
            (
                fight.id,
                member["id"],
                corpse["id"],
                member["map_id"],
                member["instance_id"],
                Jsonb(corpse),
                duration,
                duration,
            ),
        )
    return len(selected)


def spawn(row):
    """ctE12608 with a separate presentation identity and native isDead flag."""
    monster = row["monster"]
    if (monster["id"], monster["map_id"], monster["instance_id"]) != (
        row["actor_id"],
        row["map_id"],
        row["instance_id"],
    ):
        raise ValueError("Corpse appearance scope mismatch")
    body = world_actor(monster, group_id=-monster["id"], dead=True)
    return 12608, b"\x00\x01" + struct.pack(">BqH", 1, monster["id"], len(body)) + body


def resolve_target(db, character, actor_id):
    """Resolve only a durable unclaimed corpse in the character's scene."""
    row = db.execute(
        "SELECT monster FROM monster_corpses WHERE actor_id=%s AND map_id=%s "
        "AND instance_id=%s AND consumed_at IS NULL AND expires_at>CURRENT_TIMESTAMP",
        (actor_id, character["map_id"], character["instance_id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Corpse unavailable, expired or already harvested")
    return dict(row["monster"], hp=0, corpse=True)


def consume(db, monster, *, character_id, token):
    """Claim once within the inventory/receipt transaction; rollback restores it."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Corpse harvesting requires an inventory transaction")
    row = db.execute(
        "UPDATE monster_corpses SET consumed_at=CURRENT_TIMESTAMP,harvest_token=%s,"
        "harvested_by=%s WHERE actor_id=%s AND map_id=%s AND instance_id=%s "
        "AND consumed_at IS NULL AND expires_at>CURRENT_TIMESTAMP RETURNING actor_id",
        (token, character_id, monster["id"], monster["map_id"], monster["instance_id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Corpse unavailable, expired or already harvested")
    return remove_message((row["actor_id"],))


def reconcile(db, map_id, instance_id, known_actor_ids=()):
    """Reconcile only identities actually published to this retained scene.

    Fresh connections pass an empty set. A long-running combat/spectator may
    retain an older scene; keep its known IDs until this reconciliation rather
    than applying a time cutoff that could strand a corpse indefinitely.
    """
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
    ):
        raise ValueError("Invalid corpse visibility scope")
    known = frozenset(known_actor_ids)
    if any(
        type(identity) is not int or not -(1 << 53) <= identity < 0
        for identity in known
    ):
        raise ValueError("Invalid known corpse identities")
    rows = tuple(
        db.execute(
            "SELECT actor_id,map_id,instance_id,monster FROM monster_corpses "
            "WHERE map_id=%s AND instance_id=%s AND consumed_at IS NULL "
            "AND expires_at>CURRENT_TIMESTAMP ORDER BY actor_id",
            (map_id, instance_id),
        )
    )
    active = frozenset(row["actor_id"] for row in rows)
    stale = sorted(known - active)
    packets = tuple(
        remove_message(stale[start : start + 255])
        for start in range(0, len(stale), 255)
    ) + tuple(spawn(row) for row in rows)
    return packets, active


def snapshots(db, map_id, instance_id):
    return reconcile(db, map_id, instance_id)[0]


def expired_removals(db, map_id, instance_id, known_actor_ids=()):
    """Remove only expired identities known by the caller, never all history."""
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
    ):
        raise ValueError("Invalid corpse expiry scope")
    known = tuple(known_actor_ids)
    if not known:
        return ()
    if any(
        type(identity) is not int or not -(1 << 53) <= identity < 0
        for identity in known
    ):
        raise ValueError("Invalid known corpse identities")
    rows = db.execute(
        "SELECT actor_id FROM monster_corpses WHERE map_id=%s AND instance_id=%s "
        "AND actor_id=ANY(%s) AND (expires_at<=CURRENT_TIMESTAMP OR consumed_at IS NOT NULL) ORDER BY actor_id",
        (map_id, instance_id, list(known)),
    )
    identities = [row["actor_id"] for row in rows]
    return tuple(
        remove_message(identities[start : start + 255])
        for start in range(0, len(identities), 255)
    )


def expire(db):
    """Claim newly expired remains once; caller publishes to scoped world peers."""
    rows = db.execute(
        "UPDATE monster_corpses SET expiry_published=true "
        "WHERE NOT expiry_published AND (expires_at<=CURRENT_TIMESTAMP OR consumed_at IS NOT NULL) "
        "RETURNING map_id,instance_id,actor_id"
    )
    scopes = {}
    for row in rows:
        scopes.setdefault((row["map_id"], row["instance_id"]), []).append(
            row["actor_id"]
        )
    return {
        scope: tuple(
            remove_message(ids[start : start + 255])
            for start in range(0, len(ids), 255)
        )
        for scope, ids in scopes.items()
    }
