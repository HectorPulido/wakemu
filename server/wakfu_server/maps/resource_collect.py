"""Native flora request and stage-specific action authorization.

This module does not infer yield, XP or stage transitions from client metadata.
The occupation coordinator owns location, leases and reward transactions.
"""
from copy import deepcopy
import struct
import uuid
from datetime import timedelta
from psycopg.types.json import Jsonb

from .planting import RESOURCES
from .wire import proto_fields
from .inventory_items import _lease


def decode_result(body):
    if len(body) != 3:
        raise ValueError("Invalid resource occupation result")
    result, kind = struct.unpack(">Bh", body)
    if kind != 3 or result not in (2, 3):
        raise ValueError("Unsupported resource occupation result")
    return result


def start_packet(character, resource, rule):
    """cyJ12230/chT type3, verified against successful native captures.

    ivx is the occupation duration in milliseconds (a long). The capture's
    status2 starts a normal, non-cooperative collection with modifier0.
    """
    actor_id = character["id"]
    profession = rule["profession_id"]
    duration = rule["duration_ms"]
    action_id = rule["action_id"]
    if (
        type(actor_id) is not int
        or not 0 < actor_id < 2**63
        or type(profession) is not int
        or not 0 <= profession < 128
        or type(duration) is not int
        or not 0 <= duration < 2**63
        or type(action_id) is not int
        or not 0 < action_id < 2**31
        or any(
            type(resource[k]) is not int or not -(2**31) <= resource[k] < 2**31
            for k in ("x", "y")
        )
    ):
        raise ValueError("Invalid resource occupation start")
    return 12230, struct.pack(
        ">BhqqBiiBiBdi",
        1,
        3,
        actor_id,
        duration,
        2,
        resource["x"],
        resource["y"],
        profession,
        action_id,
        1,
        0.0,
        0,
    )


def decode_request(body):
    fields = list(proto_fields(body))
    if len(fields) != 3 or {tag for tag, _ in fields} != {8, 16, 24}:
        raise ValueError("Invalid resource harvest protobuf")
    values = dict(fields)
    action = values[8]
    if type(action) is not int or not 0 < action < 2**31:
        raise ValueError("Invalid resource harvest action")

    def coordinate(value):
        # zg uses signed int32 protobuf fields. Negative values may have
        # the native ten-byte sign extension rather than five-byte encoding.
        if type(value) is not int or not 0 <= value < 2**64:
            raise ValueError("Invalid resource harvest coordinate")
        if value >= 2**63:
            value -= 2**64
        elif 2**31 <= value < 2**32:
            value -= 2**32
        if not -(2**31) <= value < 2**31:
            raise ValueError("Invalid resource harvest coordinate")
        return value

    return dict(action_id=action, x=coordinate(values[16]), y=coordinate(values[24]))


def action(resource_reference, stage, action_id):
    if any(type(v) is not int for v in (resource_reference, stage, action_id)):
        raise ValueError("Invalid resource action identity")
    definition = RESOURCES.get(resource_reference)
    if definition is None or definition["monster_resource"]:
        raise ValueError("Unknown vegetal resource")
    if stage == 16:
        raise ValueError("Resource stage is not harvestable")
    step = next(
        (s for s in definition["stage_definitions"] if s["stage_id"] == stage),
        None,
    )
    native = (
        None
        if step is None
        else next((a for a in step["actions"] if a["action_id"] == action_id), None)
    )
    if native is None:
        raise ValueError("Action does not belong to this resource stage")
    return deepcopy(native)


def authorize(rule, *, profession_id, profession_level):
    if (
        type(profession_id) is not int
        or profession_id != rule["profession_id"]
        or type(profession_level) is not int
        or profession_level < rule["minimum_level"]
    ):
        raise ValueError("Resource harvest profession requirement not met")
    if rule["criteria"].strip():
        raise ValueError("Resource harvest criteria require authoritative evaluation")
    return rule


def prepare(store, account_id, generation, character_id, body, *, reachable):
    """Resolve the target from leased SQL state, never supplied client metadata.

    This read snapshot does not reserve the cell or grant a harvest. Completion
    must lock and compare the resource again before applying its transaction.
    """
    request = decode_request(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        resource = db.execute(
            "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s "
            "AND x=%s AND y=%s",
            (character["map_id"], character["instance_id"], request["x"], request["y"]),
        ).fetchone()
        if resource is None:
            raise ValueError("Resource harvest target is unavailable")
        resource = dict(resource)
        rule = action(
            resource["resource_reference"], resource["stage"], request["action_id"]
        )
        from .profession_store import stored_level

        profession = stored_level(db, account_id, rule["profession_id"])
        if profession is None:
            raise ValueError("Resource harvest profession is unlearned")
        authorize(
            rule,
            profession_id=rule["profession_id"],
            profession_level=profession,
        )
    if reachable(character, resource) is not True:
        raise ValueError("Resource harvest target is unreachable")
    return dict(character=character, resource=resource, request=request, rule=rule)


def reserve(store, account_id, generation, prepared):
    """Reserve an unchanged target; one cell and occupation per character."""
    character_id = prepared["character"]["id"]
    expected = prepared["resource"]
    rule = prepared["rule"]
    now = store.now()
    token = uuid.uuid4().hex
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if any(
            character[k] != prepared["character"][k]
            for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Resource harvest actor moved before reservation")
        setting = db.execute(
            "SELECT value FROM settings WHERE name='resource_harvest_occupation'"
        ).fetchone()
        configuration = None if setting is None else setting["value"]
        if (
            not isinstance(configuration, dict)
            or set(configuration) != {"completion_grace_ms"}
            or type(configuration["completion_grace_ms"]) is not int
            or not 0 < configuration["completion_grace_ms"] <= 60000
        ):
            raise ValueError("Invalid resource occupation policy")
        resource = db.execute(
            "SELECT * FROM planted_resources WHERE resource_uid=%s FOR UPDATE",
            (expected["resource_uid"],),
        ).fetchone()
        if resource is None or dict(resource) != expected:
            raise ValueError("Resource changed before harvest reservation")
        current_rule = action(
            resource["resource_reference"],
            resource["stage"],
            prepared["request"]["action_id"],
        )
        if current_rule != rule:
            raise ValueError("Resource harvest action changed before reservation")
        from .profession_store import stored_level

        profession = stored_level(db, account_id, rule["profession_id"])
        if profession is None:
            raise ValueError("Resource harvest profession is unlearned")
        authorize(
            rule, profession_id=rule["profession_id"], profession_level=profession
        )
        db.execute(
            "DELETE FROM resource_harvest_occupations "
            "WHERE (resource_uid=%s OR character_id=%s) AND "
            "(expires_at<=%s OR (character_id=%s AND generation<>%s))",
            (expected["resource_uid"], character_id, now, character_id, generation),
        )
        if db.execute(
            "SELECT 1 FROM resource_harvest_occupations "
            "WHERE resource_uid=%s OR character_id=%s",
            (expected["resource_uid"], character_id),
        ).fetchone():
            raise ValueError("Resource harvest occupation busy")
        due = now + timedelta(milliseconds=rule["duration_ms"])
        expiry = due + timedelta(milliseconds=configuration["completion_grace_ms"])
        db.execute(
            "INSERT INTO resource_harvest_occupations "
            "(resource_uid,token,account_id,generation,character_id,action_id,"
            "started_at,completes_at,expires_at,resource_snapshot,"
            "actor_map_id,actor_instance_id,actor_x,actor_y,actor_z) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                expected["resource_uid"],
                token,
                account_id,
                generation,
                character_id,
                rule["action_id"],
                now,
                due,
                expiry,
                Jsonb(expected),
                character["map_id"],
                character["instance_id"],
                character["x"],
                character["y"],
                character["z"],
            ),
        )
    return dict(
        token=token,
        resource_uid=expected["resource_uid"],
        character_id=character_id,
        account_id=account_id,
        generation=generation,
        action_id=rule["action_id"],
        completes_at=due,
        expires_at=expiry,
    )


def validate_actor_position(character, occupation):
    """Reject completion after movement, including instance and elevation.

    Call with the character loaded under the completion transaction's lease.
    The durable reservation supplies every expected coordinate.
    """
    for key in ("map_id", "instance_id", "x", "y", "z"):
        if character[key] != occupation["actor_" + key]:
            raise ValueError("Resource harvest actor moved during occupation")


def cancel(store, ticket):
    """An expired session may release its ticket, never a replacement ticket."""
    with store.connection() as db:
        row = db.execute(
            "DELETE FROM resource_harvest_occupations WHERE resource_uid=%s "
            "AND token=%s AND account_id=%s AND generation=%s AND character_id=%s "
            "RETURNING token",
            tuple(
                ticket[k]
                for k in (
                    "resource_uid",
                    "token",
                    "account_id",
                    "generation",
                    "character_id",
                )
            ),
        ).fetchone()
    return row is not None


def pending(store, account_id, generation, character_id):
    """Find this generation's durable occupation after reopening storage.

    A replacement login cannot take over the previous generation's ticket.
    """
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        row = db.execute(
            "SELECT * FROM resource_harvest_occupations "
            "WHERE account_id=%s AND generation=%s AND character_id=%s",
            (account_id, generation, character_id),
        ).fetchone()
    return None if row is None else dict(row)


def complete(store, ticket, body):
    """Commit a successful flora occupation and its rewards exactly once.

    Catalog cvF is an explicit local transition policy, supported by captured
    examples, not a claim about all official transition rules. Only the primary
    catalog product is granted; bonus/rare references are not guaranteed drops.
    """
    result = decode_result(body)
    account, generation, actor = (
        ticket[k] for k in ("account_id", "generation", "character_id")
    )
    token = ticket["token"]
    if type(token) is not str or not 1 <= len(token) <= 128:
        raise ValueError("Invalid resource harvest identity")
    with store.connection() as db:
        _lease(store, db, account, generation, actor)
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("resource-harvest:" + token,),
        )
        previous = db.execute(
            "SELECT * FROM resource_harvest_receipts WHERE token=%s", (token,)
        ).fetchone()
        if previous is not None:
            if any(
                previous[k] != ticket[k]
                for k in ("account_id", "character_id", "resource_uid", "action_id")
            ):
                raise ValueError("Foreign resource harvest receipt")
            return dict(applied=False, packets=[], world_packets=[])
        resource = db.execute(
            "SELECT * FROM planted_resources WHERE resource_uid=%s FOR UPDATE",
            (ticket["resource_uid"],),
        ).fetchone()
        occupation = db.execute(
            "SELECT * FROM resource_harvest_occupations WHERE token=%s FOR UPDATE",
            (token,),
        ).fetchone()
        if occupation is None:
            return dict(applied=False, packets=[], world_packets=[])
        if any(
            occupation[k] != ticket[k]
            for k in (
                "account_id",
                "generation",
                "character_id",
                "resource_uid",
                "action_id",
            )
        ):
            raise ValueError("Foreign resource harvest occupation")
        if result == 3:
            db.execute(
                "DELETE FROM resource_harvest_occupations WHERE token=%s", (token,)
            )
            return dict(applied=False, packets=[], world_packets=[])
        now = store.now()
        if now < occupation["completes_at"]:
            raise ValueError("Resource harvest completed before duration")
        if now >= occupation["expires_at"]:
            raise ValueError("Resource harvest occupation expired")
        if resource is None or dict(resource) != occupation["resource_snapshot"]:
            raise ValueError("Resource changed during harvest occupation")
        character = store.character(account, actor, db)
        validate_actor_position(character, occupation)
        rule = action(
            resource["resource_reference"], resource["stage"], occupation["action_id"]
        )
        from .profession_store import stored_level, award
        from .profession_rewards import base_xp
        from .harvest_inventory import grant
        from .planting_runtime import state_packet
        from hashlib import sha256

        profession = stored_level(db, account, rule["profession_id"])
        if profession is None:
            raise ValueError("Resource harvest profession is unlearned")
        authorize(
            rule, profession_id=rule["profession_id"], profession_level=profession
        )
        setting = db.execute(
            "SELECT value FROM settings WHERE name='resource_harvest_rewards'"
        ).fetchone()
        policy = None if setting is None else setting["value"]
        if (
            not isinstance(policy, dict)
            or set(policy) != {"version", "product_quantity", "stage_policy"}
            or type(policy["version"]) is not int
            or policy["version"] != 1
            or type(policy["product_quantity"]) is not int
            or not 1 <= policy["product_quantity"] <= 32767
            or policy["stage_policy"] != "catalog_cvF"
        ):
            raise ValueError("Invalid resource harvest reward policy")
        stage = rule["raw_getters"]["cvF"]
        if type(stage) is not int or (
            stage != 0
            and stage not in RESOURCES[resource["resource_reference"]]["stages"]
        ):
            raise ValueError("Unsupported resource harvest destination stage")
        from .flora_ecology import change as ecological_change

        ecology = ecological_change(
            db,
            actor,
            dict(resource),
            operation="flora:" + sha256(token.encode()).hexdigest(),
            action="remove" if stage == 0 else "harvest",
        )
        item_reference = rule["item_reference"]
        packets = []
        product = None
        if item_reference:
            product = grant(db, character, item_reference, policy["product_quantity"])
            packets.append(product["packet"])
        from wakfu_server.territory_bonuses import current_region, profession_xp_percent

        territory = current_region(db, character)
        territory_percent = profession_xp_percent(territory, "harvest")
        reward = award(
            store,
            db,
            account,
            generation,
            actor,
            rule["profession_id"],
            base_xp=base_xp(db, "harvest") if product else 0,
            operation="flora:" + sha256(token.encode()).hexdigest(),
            territory_percent=territory_percent,
        )
        packets.extend(reward["packets"])
        packets.extend(ecology["packets"])
        # Supersede the prior growth event before changing/removing its target.
        # The world coordinator serializes this with the growth publisher.
        db.execute(
            "DELETE FROM planting_growth_outbox WHERE resource_uid=%s",
            (resource["resource_uid"],),
        )
        if stage == 0:
            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s",
                (resource["resource_uid"],),
            )
            event = dict(resource, stage=0)
        else:
            creation_time = int(store.clock() * 1000)
            db.execute(
                "UPDATE planted_resources SET stage=%s,creation_time=%s WHERE resource_uid=%s",
                (stage, creation_time, resource["resource_uid"]),
            )
            event = dict(resource, stage=stage, creation_time=creation_time)
        db.execute(
            "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL)",
            (resource["resource_uid"], Jsonb(event)),
        )
        db.execute("DELETE FROM resource_harvest_occupations WHERE token=%s", (token,))
        outcome = dict(
            stage=stage,
            item_reference=item_reference,
            quantity=policy["product_quantity"] if product else 0,
            xp=reward["xp"],
            ecology={key: val for key, val in ecology.items() if key != "packets"},
        )
        db.execute(
            "INSERT INTO resource_harvest_receipts(token,account_id,character_id,resource_uid,action_id,result,completed_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                token,
                account,
                actor,
                resource["resource_uid"],
                rule["action_id"],
                Jsonb(outcome),
                now,
            ),
        )
    return dict(
        applied=True,
        packets=packets,
        world_packets=[state_packet(event, stage)],
        event=event,
        map_id=resource["map_id"],
        instance_id=resource["instance_id"],
        outcome=outcome,
    )


def acknowledge_publication(store, result):
    """Acknowledge this event only; a subsequent transition retains its outbox.

    The caller holds the world's growth publisher lock while delivering and
    acknowledging. Delivery failure leaves a durable retry for that publisher.
    """
    if not result["applied"]:
        return
    event = result["event"]
    with store.connection() as db:
        db.execute(
            "UPDATE planting_growth_outbox SET published=TRUE "
            "WHERE resource_uid=%s AND resource=%s",
            (event["resource_uid"], Jsonb(event)),
        )
