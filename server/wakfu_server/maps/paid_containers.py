"""Leased paid native containers with explicitly reconstructed DB economics.

The original13905/13429 occupation has no client ticket field. The server's
connection-owned UUID identifies the sole current attempt; completion cannot
choose an object, output, inventory UID or policy. Item settlement is atomic.
"""
from datetime import timedelta
import hashlib
import json
import secrets
import struct
import uuid

from psycopg.types.json import Jsonb

from wakfu_server.inventory_items import _lease


def _rule(db, map_id, object_id):
    row = db.execute(
        "SELECT l.*,p.version,p.authority_label,p.reconstruction_label,p.occupation_type,"
        "p.duration_ms,p.debit_timing,p.repetition,p.sealed FROM paid_container_locations l "
        "JOIN paid_container_policies p USING(policy_id) WHERE l.map_id=%s AND l.object_id=%s",
        (map_id, object_id),
    ).fetchone()
    if row is None:
        return None
    rule = dict(row)
    rule["approaches"] = [
        [r[k] for k in ("x", "y", "z")]
        for r in db.execute(
            "SELECT x,y,z FROM paid_container_approaches WHERE map_id=%s AND object_id=%s ORDER BY x,y,z",
            (map_id, object_id),
        ).fetchall()
    ]
    rule["outcomes"] = [
        dict(r)
        for r in db.execute(
            "SELECT ordinal,itemref,quantity,weight FROM paid_container_outcomes WHERE policy_id=%s ORDER BY ordinal",
            (rule["policy_id"],),
        ).fetchall()
    ]
    if (
        rule["sealed"] is not True
        or not rule["authority_label"]
        or not rule["reconstruction_label"]
        or rule["occupation_type"] not in (13, 28)
        or type(rule["duration_ms"]) is not int
        or not 1 <= rule["duration_ms"] < 2**31
        or rule["debit_timing"] != "finish"
        or rule["repetition"] != "new_paid_attempt"
        or (
            rule["ready_state"],
            rule["transient_state"],
            rule["action"],
            rule["parameter"],
        )
        != (1, 3, 22, 0)
        or type(rule["requireditem"]) is not int
        or rule["requireditem"] <= 0
        or type(rule["qty"]) is not int
        or not 1 <= rule["qty"] <= 32767
        or rule["kamas"] != 0
        or rule["criterion"] != "not IsHero()"
        or rule["approach_policy"] != "wakemu.reconstructed-cardinal-native-walkable.v1"
        or not rule["approaches"]
        or not rule["outcomes"]
        or any(
            type(r["ordinal"]) is not int or r["ordinal"] < 0 for r in rule["outcomes"]
        )
        or any(
            type(r[k]) is not int or r[k] <= 0
            for r in rule["outcomes"]
            for k in ("itemref", "quantity", "weight")
        )
    ):
        raise ValueError("Unsupported paid container authority")
    return rule


def definition(store, map_id, object_id):
    with store.connection() as db:
        return _rule(db, map_id, object_id)


def _source(rule):
    from wakfu_server.treasure_chests import _native_authority

    _native_authority(
        rule["catalog_revision"],
        rule["map_id"],
        rule["object_id"],
        rule["payload_hex"],
        rule["native_state_payload_hex"],
        rule["geometry_sha256"],
        (rule["x"], rule["y"], rule["z"]),
    )


def _digest(rule):
    return hashlib.sha256(
        json.dumps(
            rule, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _state(rule, value):
    from wakfu_server.environment_interactions import _packet

    return _packet(
        dict(
            object_id=rule["object_id"],
            state_payload_hex=rule["native_state_payload_hex"],
        ),
        value,
    )


def _current_state(db, store, rule, instance_id):
    active = db.execute(
        "SELECT 1 FROM paid_container_attempts a JOIN sessions s "
        "ON s.account_id=a.account_id AND s.generation=a.generation "
        "WHERE a.map_id=%s AND a.instance_id=%s AND a.object_id=%s AND a.state='active' "
        "AND a.expires_at>%s AND s.expires_at>%s LIMIT 1",
        (rule["map_id"], instance_id, rule["object_id"], store.now(), store.now()),
    ).fetchone()
    return _state(rule, 3 if active is not None else 1)


def _start(rule, actor_id):
    return 13905, struct.pack(
        ">bhqqq",
        1,
        rule["occupation_type"],
        actor_id,
        rule["object_id"],
        rule["duration_ms"],
    )


def _owner(store, db, account_id, generation, character, rule, *, is_hero):
    from wakfu_server.simple_item_actions import _idle

    _lease(store, db, account_id, generation, character["id"])
    actual = store.character(account_id, character["id"], db)
    if (
        type(is_hero) is not bool
        or is_hero
        or any(
            actual.get(k, 0) != character.get(k, 0)
            for k in ("map_id", "instance_id", "x", "y", "z")
        )
        or actual["map_id"] != rule["map_id"]
        or [actual[k] for k in ("x", "y", "z")] not in rule["approaches"]
    ):
        raise ValueError("Paid container requires its owned non-hero approach")
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s", (account_id,)
    ).fetchone()
    if roster is not None and roster["leader_id"] != actual["id"]:
        raise ValueError("Paid container requires the selected main character")
    _idle(db, actual["id"], store.now())
    if db.execute(
        "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s "
        "AND state='active'",
        (actual["id"],),
    ).fetchone():
        raise ValueError("Another native occupation is active")
    _source(rule)
    return actual


def _leased_owner(store, db, account_id, generation, character):
    """Use the established session -> account -> character settlement order."""
    from wakfu_server.achievements.service import _owner as lock_owner

    if account_id != character.get("account_id"):
        raise ValueError("Foreign paid container owner")
    session = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s "
        "AND generation=%s AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if session is None or session["character_id"] != character["id"]:
        raise ValueError("Invalid inventory session")
    lock_owner(db, character)
    _lease(store, db, account_id, generation, character["id"])


def _materials(character, rule):
    # Native Mimikibble is a regular item. Restrict payment to real owned bags;
    # no equipment, quest or account/chest inventory is silently substituted.
    containers = {row["uid"] for row in character["inventory_containers"]}
    items = sorted(
        (
            row
            for row in character["inventory_items"]
            if row["reference"] == rule["requireditem"]
            and row["container"] in containers
        ),
        key=lambda row: row["uid"],
    )
    remaining, result = rule["qty"], []
    for item in items:
        quantity = min(remaining, item["quantity"])
        if quantity > 0:
            result.append((item, quantity))
            remaining -= quantity
        if remaining == 0:
            return result
    raise ValueError("Missing original paid-container input")


def begin(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
    choose=secrets.randbelow,
):
    if type(body) is not bytes or len(body) != 12 or not loaded or blocked:
        raise ValueError("Paid container requires its authenticated loaded action")
    object_id, action, parameter = struct.unpack(">qHH", body)
    now = store.now()
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        rule = _rule(db, character["map_id"], object_id)
        if rule is None or (action, parameter) != (rule["action"], rule["parameter"]):
            raise ValueError("Unsupported paid-container action")
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                f"paid-container:{rule['map_id']}:{character.get('instance_id', 0)}:{object_id}",
            ),
        )
        db.execute(
            "UPDATE paid_container_attempts SET state='canceled',finished_at=%s "
            "WHERE state='active' AND (character_id=%s OR "
            "(map_id=%s AND instance_id=%s AND object_id=%s)) AND (expires_at<=%s OR NOT EXISTS "
            "(SELECT 1 FROM sessions s WHERE s.account_id=paid_container_attempts.account_id "
            "AND s.generation=paid_container_attempts.generation AND s.expires_at>%s))",
            (
                now,
                character["id"],
                character["map_id"],
                character.get("instance_id", 0),
                object_id,
                now,
                now,
            ),
        )
        actual = _owner(
            store, db, account_id, generation, character, rule, is_hero=is_hero
        )
        _materials(actual, rule)
        active = db.execute(
            "SELECT * FROM paid_container_attempts WHERE state='active' AND "
            "(character_id=%s OR (map_id=%s AND instance_id=%s AND object_id=%s)) FOR UPDATE",
            (actual["id"], actual["map_id"], actual.get("instance_id", 0), object_id),
        ).fetchall()
        if active:
            row = active[0]
            if (
                len(active) != 1
                or row["account_id"] != account_id
                or row["generation"] != generation
                or row["character_id"] != actual["id"]
                or row["object_id"] != object_id
                or row["rule_digest"] != _digest(rule)
                or any(row["origin_" + k] != actual[k] for k in ("x", "y", "z"))
            ):
                raise ValueError("Another paid container occupation is active")
            return dict(
                token=row["token"],
                replay=True,
                character=actual,
                location=(actual["map_id"], actual.get("instance_id", 0)),
                packets=[_state(rule, 3), _start(rule, actual["id"])],
            )
        total = sum(row["weight"] for row in rule["outcomes"])
        draw = choose(total)
        if type(draw) is not int or not 0 <= draw < total:
            raise ValueError("Invalid container random draw")
        for outcome in rule["outcomes"]:
            draw -= outcome["weight"]
            if draw < 0:
                break
        token = uuid.uuid4()
        due = now + timedelta(milliseconds=rule["duration_ms"])
        db.execute(
            "INSERT INTO paid_container_attempts(token,account_id,generation,character_id,"
            "policy_id,map_id,instance_id,object_id,origin_x,origin_y,origin_z,rule_digest,"
            "selected_ordinal,state,started_at,due_at,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s,%s)",
            (
                token,
                account_id,
                generation,
                actual["id"],
                rule["policy_id"],
                actual["map_id"],
                actual.get("instance_id", 0),
                object_id,
                actual["x"],
                actual["y"],
                actual["z"],
                _digest(rule),
                outcome["ordinal"],
                now,
                due,
                due + timedelta(seconds=30),
            ),
        )
        return dict(
            token=token,
            replay=False,
            character=actual,
            location=(actual["map_id"], actual.get("instance_id", 0)),
            packets=[_state(rule, 3), _start(rule, actual["id"])],
        )


def finish(
    store,
    account_id,
    generation,
    character,
    token,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
):
    if (
        not isinstance(token, uuid.UUID)
        or type(body) is not bytes
        or len(body) != 3
        or not loaded
        or blocked
    ):
        raise ValueError("Missing connection-owned paid occupation")
    status, kind = struct.unpack(">bh", body)
    if status not in (2, 3) or kind not in (13, 28):
        raise ValueError("Foreign paid occupation result")
    now = store.now()
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        row = db.execute(
            "SELECT * FROM paid_container_attempts WHERE token=%s FOR UPDATE", (token,)
        ).fetchone()
        if row is None or (
            row["account_id"],
            row["generation"],
            row["character_id"],
        ) != (account_id, generation, character["id"]):
            raise ValueError("Paid occupation belongs to another lease")
        rule = _rule(db, row["map_id"], row["object_id"])
        if rule is None or row["rule_digest"] != _digest(rule):
            raise ValueError("Paid occupation authority changed")
        if kind != rule["occupation_type"]:
            raise ValueError("Foreign paid occupation type")
        if row["state"] != "active":
            return dict(
                token=token,
                replay=True,
                character=store.character(account_id, character["id"], db),
                location=(row["map_id"], row["instance_id"]),
                packets=[_current_state(db, store, rule, row["instance_id"])],
                state=row["state"],
            )
        if status == 3 or now >= row["expires_at"]:
            db.execute(
                "UPDATE paid_container_attempts SET state='canceled',finished_at=%s WHERE token=%s",
                (now, token),
            )
            return dict(
                token=token,
                replay=False,
                character=store.character(account_id, character["id"], db),
                location=(row["map_id"], row["instance_id"]),
                packets=[_current_state(db, store, rule, row["instance_id"])],
                state="canceled",
            )
        if now < row["due_at"]:
            raise ValueError("Paid occupation finished before its duration")
        actual = _owner(
            store, db, account_id, generation, character, rule, is_hero=is_hero
        )
        if actual.get("instance_id", 0) != row["instance_id"] or any(
            actual[k] != row["origin_" + k] for k in ("x", "y", "z")
        ):
            raise ValueError("Paid occupation moved from its authenticated origin")
        outcome = next(
            r for r in rule["outcomes"] if r["ordinal"] == row["selected_ordinal"]
        )
        packets, consumed = [], []
        for item, quantity in _materials(actual, rule):
            if item["quantity"] == quantity:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], actual["id"]),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s AND character_id=%s",
                    (quantity, item["uid"], actual["id"]),
                )
            consumed.append(dict(uid=item["uid"], quantity=quantity))
            packets.append((12470, struct.pack(">qh", item["uid"], -quantity)))
        actual = store.character(account_id, actual["id"], db)
        from wakfu_server.achievements.rewards import _item

        packets.extend(
            _item(db, store, actual, outcome["itemref"], outcome["quantity"])
        )
        receipt = dict(
            consumed=consumed,
            ordinal=outcome["ordinal"],
            reference=outcome["itemref"],
            quantity=outcome["quantity"],
            rule_digest=row["rule_digest"],
        )
        db.execute(
            "UPDATE paid_container_attempts SET state='completed',finished_at=%s,receipt=%s WHERE token=%s",
            (now, Jsonb(receipt), token),
        )
        return dict(
            token=token,
            replay=False,
            character=store.character(account_id, actual["id"], db),
            location=(row["map_id"], row["instance_id"]),
            packets=packets + [_current_state(db, store, rule, row["instance_id"])],
            state="completed",
            receipt=receipt,
        )


def snapshots(store, map_id, instance_id):
    with store.connection() as db:
        rows = db.execute(
            "SELECT l.*,EXISTS(SELECT 1 FROM paid_container_attempts a "
            "JOIN sessions s ON s.account_id=a.account_id AND s.generation=a.generation "
            "WHERE a.map_id=l.map_id AND a.object_id=l.object_id AND a.instance_id=%s AND a.state='active' "
            "AND a.expires_at>%s AND s.expires_at>%s) AS opening FROM paid_container_locations l "
            "JOIN paid_container_policies p USING(policy_id) WHERE l.map_id=%s AND p.sealed",
            (instance_id, store.now(), store.now(), map_id),
        ).fetchall()
        return [_state(dict(row), 3 if row["opening"] else 1) for row in rows]


def cancel(store, account_id, generation, character, token):
    """Server interruption uses the same leased terminal transition, no charge."""
    with store.connection() as db:
        row = db.execute(
            "SELECT p.occupation_type FROM paid_container_attempts a "
            "JOIN paid_container_policies p USING(policy_id) WHERE a.token=%s",
            (token,),
        ).fetchone()
    if row is None:
        raise ValueError("Missing paid occupation")
    return finish(
        store,
        account_id,
        generation,
        character,
        token,
        struct.pack(">bh", 3, row["occupation_type"]),
        loaded=True,
    )
