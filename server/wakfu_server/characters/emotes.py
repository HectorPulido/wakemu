"""Account-owned native emotes with an explicitly configurable DEV unlock view."""
import struct
import time
from wakfu_server.items.inventory_items import _varint


def allowed_ids(db, account_id):
    row = db.execute("SELECT value FROM settings WHERE name='emote_policy'").fetchone()
    policy = None if row is None else row["value"]
    if not isinstance(policy, dict) or type(policy.get("unlock_all")) is not bool:
        raise ValueError("Invalid emote unlock policy")
    if policy["unlock_all"]:
        return tuple(
            r["emote_id"]
            for r in db.execute(
                "SELECT emote_id FROM native_emote_definitions WHERE unlock_default ORDER BY emote_id"
            )
        )
    return tuple(
        r["emote_id"]
        for r in db.execute(
            "SELECT k.emote_id FROM account_emote_knowledge k JOIN native_emote_definitions n "
            "ON n.emote_id=k.emote_id WHERE k.account_id=%s ORDER BY k.emote_id",
            (account_id,),
        )
    )


def snapshot(db, account_id):
    """Native account section10: length-prefixed hI with repeated hE(id) records."""
    payload = b""
    for emote_id in allowed_ids(db, account_id):
        record = b"\x08" + _varint(emote_id)
        payload += b"\x0a" + _varint(len(record)) + record
    return 13873, struct.pack(">III", 1, 10, len(payload)) + payload


def packet(store, account_id):
    with store.connection() as db:
        return snapshot(db, account_id)


def authorize(db, account_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Native emote request requires twelve bytes")
    emote_id, target_id = struct.unpack(">iq", body)
    if emote_id not in allowed_ids(db, account_id):
        raise ValueError("Emote is not unlocked for this account")
    return emote_id, target_id


def occupation(actor_id, emote_id, parameters=()):
    payload = struct.pack(">iB", emote_id, len(parameters))
    for key, value in parameters:
        encoded = key.encode("utf-8")
        payload += struct.pack(">I", len(encoded)) + encoded + struct.pack(">q", value)
    return 12088, struct.pack(">BhqI", 1, 20, actor_id, len(payload)) + payload


def prepare_play(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    resolve_target,
    in_fight,
    occupied=lambda actor_id: False
):
    """Validate own lease and target scope before creating a native occupation."""
    if (
        character.get("hp", 0) <= 0
        or in_fight(character["id"])
        or occupied(character["id"])
    ):
        raise ValueError("World emotes cannot interrupt combat")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character["id"])
        if db.execute(
            "SELECT 1 FROM craft_occupations WHERE character_id=%s AND state='active'",
            (character["id"],),
        ).fetchone():
            raise ValueError("Emotes cannot interrupt crafting")
        emote_id, target_id = authorize(db, account_id, body)
        definition = db.execute(
            "SELECT * FROM native_emote_definitions WHERE emote_id=%s", (emote_id,)
        ).fetchone()
        metadata = definition["metadata"]
        if metadata.get("ehu") not in ("", "not IsBattleground()"):
            raise ValueError("Unverified native emote criterion")
        if character.get("_emote_until", 0) > time.monotonic() and (
            metadata["eiW"] or metadata["eiV"]
        ):
            raise ValueError("Native emote is incompatible with the active occupation")
        parameters = []
        if metadata["eiV"]:
            target = resolve_target(target_id)
            if (
                target is None
                or target["id"] == character["id"]
                or (target["map_id"], target["instance_id"])
                != (character["map_id"], character["instance_id"])
                or target.get("hp", 0) <= 0
                or in_fight(target_id)
                or occupied(target_id)
                or target.get("_emote_until", 0) > time.monotonic()
            ):
                raise ValueError("Native emote target is unavailable")
            if db.execute(
                "SELECT 1 FROM craft_occupations WHERE character_id=%s AND state='active'",
                (target_id,),
            ).fetchone():
                raise ValueError("Target is occupied with crafting")
            parameters.append(("targetId", target_id))
        elif target_id != -1:
            raise ValueError("Untargeted native emote cannot specify a target")
        expressions = metadata.get("eiY", [])
        if expressions:
            if len(expressions) != 3 or expressions[0] != "true":
                raise ValueError("Unverified native emote parameters")
            import json
            import re
            import secrets

            key = json.loads(expressions[1])
            random = re.fullmatch(r"GetRandomNumber\((\d+)\)", expressions[2])
            if random and 0 < int(random[1]) <= 1000:
                value = secrets.randbelow(int(random[1]))
            elif expressions[2] == "GetNationId()":
                # Own characters currently have native nation0 (wire identity).
                value = 0
            else:
                raise ValueError("Unverified native emote expression")
            parameters.append((key, value))
    return {
        "packet": occupation(character["id"], emote_id, parameters),
        "duration_ms": metadata["bKb"],
    }


def retained(character):
    import time

    if character.get("_emote_until", 0) > time.monotonic():
        return (character["_emote_packet"],)
    return ()


def stopped(actor_id):
    return 12088, struct.pack(">BhqI", 2, 20, actor_id, 0)
