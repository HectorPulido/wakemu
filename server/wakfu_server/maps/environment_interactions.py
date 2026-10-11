"""Leased native well rewards and persistent ordinary light switches.

Definitions are imported from installed object/state/action data by migration129.
The caller owns live position, timers, scene publication and occupation exclusion.
"""
import struct
import uuid
from datetime import timedelta

from wakfu_server.inventory_items import _lease


def request(body):
    if len(body) != 12:
        raise ValueError("Invalid environment interaction request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if identity <= 0 or action != 0 or parameter != 0:
        raise ValueError("Unsupported environment action")
    return identity


def definition(store, map_id, object_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT * FROM environment_interaction_definitions WHERE map_id=%s AND object_id=%s",
            (map_id, object_id),
        ).fetchone()
    return None if row is None else dict(row)


def _position(character, rule):
    if (
        character.get("instance_id", 0) != 0
        or character["map_id"] != rule["map_id"]
        or abs(character["z"] - rule["z"]) > 1
        or abs(character["x"] - rule["x"]) + abs(character["y"] - rule["y"]) > 4
    ):
        raise ValueError("Environment object is outside the current interaction range")


def _guard(db, character_id):
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Environment interaction is unavailable during combat")


def _rule(db, character, identity):
    row = db.execute(
        "SELECT * FROM environment_interaction_definitions WHERE map_id=%s AND object_id=%s",
        (character["map_id"], identity),
    ).fetchone()
    if row is None:
        raise ValueError("Unsupported native environment object")
    rule = dict(row)
    _position(character, rule)
    return rule


def _packet(rule, state):
    payload = bytes.fromhex(rule["state_payload_hex"])
    if len(payload) < 9 or payload[:7] != bytes.fromhex("01020000000602"):
        raise ValueError("Invalid native environment state")
    payload = payload[:7] + struct.pack(">h", state) + payload[9:]
    return 12344, struct.pack(">qH", rule["object_id"], len(payload)) + payload


def begin(
    store, account_id, generation, character, body, *, blocked=False, is_hero=None
):
    """Start a native well timer; unchanged retries reuse its durable ticket."""
    if blocked:
        raise ValueError("Environment interaction is unavailable during an occupation")
    identity = request(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        rule = _rule(db, character, identity)
        if rule["kind"] != "well":
            raise ValueError("Environment object is not a well")
        if rule["requires_nonhero"] and (type(is_hero) is not bool or is_hero):
            raise ValueError("Well requires an authoritative non-hero actor")
        active = db.execute(
            "SELECT * FROM environment_interaction_tickets WHERE character_id=%s AND state='active' FOR UPDATE",
            (character["id"],),
        ).fetchone()
        if active is not None and active["generation"] != generation:
            db.execute(
                "UPDATE environment_interaction_tickets SET state='cancelled' WHERE token=%s",
                (active["token"],),
            )
            active = None
        if active is not None:
            if active["object_id"] != identity or any(
                active[k] != character[k] for k in ("map_id", "x", "y", "z")
            ):
                raise ValueError("Another environment occupation is active")
            return dict(active, replay=True, packets=[])
        token = uuid.uuid4()
        due = store.now() + timedelta(milliseconds=rule["duration_ms"])
        row = db.execute(
            "INSERT INTO environment_interaction_tickets(token,account_id,generation,character_id,map_id,object_id,"
            "x,y,z,due_at,is_hero) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                token,
                account_id,
                generation,
                character["id"],
                character["map_id"],
                identity,
                character["x"],
                character["y"],
                character["z"],
                due,
                is_hero,
            ),
        ).fetchone()
        return dict(row, replay=False, packets=[])


def cancel(store, account_id, generation, character_id):
    with store.connection() as db:
        db.execute(
            "UPDATE environment_interaction_tickets SET state='cancelled' "
            "WHERE account_id=%s AND generation=%s AND character_id=%s AND state='active'",
            (account_id, generation, character_id),
        )


def complete(
    store,
    account_id,
    generation,
    character_id,
    token,
    *,
    location,
    blocked=False,
    is_hero=None
):
    """Commit one elapsed, stationary, live-session reward exactly once."""
    from wakfu_server.harvest_inventory import grant

    if blocked or not isinstance(token, uuid.UUID):
        raise ValueError("Invalid or unavailable environment completion")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        _guard(db, character_id)
        row = db.execute(
            "SELECT * FROM environment_interaction_tickets WHERE token=%s AND account_id=%s "
            "AND generation=%s AND character_id=%s FOR UPDATE",
            (token, account_id, generation, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown environment occupation")
        if row["state"] == "completed":
            return dict(replay=True, packets=[])
        if row["state"] != "active" or store.now() < row["due_at"]:
            raise ValueError("Environment occupation is cancelled or not yet complete")
        if location["id"] != character_id or any(
            location[k] != row[k] for k in ("map_id", "x", "y", "z")
        ):
            raise ValueError("Actor moved during environment occupation")
        rule = _rule(db, location, row["object_id"])
        if rule["requires_nonhero"] and (
            type(is_hero) is not bool or is_hero or row["is_hero"]
        ):
            raise ValueError("Well requires an authoritative non-hero actor")
        character = store.character(account_id, character_id, db)
        reward = grant(db, character, rule["item_reference"], rule["quantity"])
        db.execute(
            "UPDATE environment_interaction_tickets SET state='completed' WHERE token=%s",
            (token,),
        )
        return dict(
            replay=False,
            packets=[reward["packet"]],
            character=store.character(account_id, character_id, db),
        )


def toggle(store, account_id, generation, character, body, *, blocked=False):
    if blocked:
        raise ValueError("Environment interaction is unavailable during an occupation")
    identity = request(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        rule = _rule(db, character, identity)
        if rule["kind"] != "light":
            raise ValueError("Environment object is not a light")
        db.execute(
            "INSERT INTO environment_interaction_states(map_id,object_id,state) VALUES(%s,%s,%s) "
            "ON CONFLICT(map_id,object_id) DO NOTHING",
            (rule["map_id"], identity, rule["initial_state"]),
        )
        row = db.execute(
            "SELECT * FROM environment_interaction_states WHERE map_id=%s AND object_id=%s FOR UPDATE",
            (rule["map_id"], identity),
        ).fetchone()
        state = row["state"]
        if row["expires_at"] is not None and row["expires_at"] <= store.now():
            state = 1 - state
        state = 1 - state
        timeout = rule["on_timeout_ms"] if state else rule["off_timeout_ms"]
        expiry = store.now() + timedelta(milliseconds=timeout) if timeout else None
        db.execute(
            "UPDATE environment_interaction_states SET state=%s,expires_at=%s WHERE map_id=%s AND object_id=%s",
            (state, expiry, rule["map_id"], identity),
        )
        return dict(
            kind="light", packets=[_packet(rule, state)], state=state, expires_at=expiry
        )


def snapshots(store, map_id):
    """Return modified light states, applying native timed reversions atomically."""
    with store.connection() as db:
        rows = db.execute(
            "SELECT s.state,s.expires_at,d.* FROM environment_interaction_states s "
            "JOIN environment_interaction_definitions d USING(map_id,object_id) "
            "WHERE s.map_id=%s ORDER BY s.object_id FOR UPDATE OF s",
            (map_id,),
        ).fetchall()
        packets = []
        for row in rows:
            state = row["state"]
            if row["expires_at"] is not None and row["expires_at"] <= store.now():
                state = 1 - state
                db.execute(
                    "UPDATE environment_interaction_states SET state=%s,expires_at=NULL WHERE map_id=%s AND object_id=%s",
                    (state, map_id, row["object_id"]),
                )
            packets.append(_packet(row, state))
        return tuple(packets)
