"""Persistent per-character delivery of automatic cinematics and native guides.

Historical offered-presentation receipts backfill the same stable identity.
Mechanical receipts with suppressed presentations can be explicitly excluded.
Manual client help controls do not pass through this automatic-delivery ledger.
"""

import struct
import re
import time

from . import storage


def register_context(db, character, token):
    """Record one authenticated loaded client context, not every visible chunk."""
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid presentation client context")
    storage._lock(db, character["id"])
    key = f'presentation-context:{character["instance_id"]}:{token}'
    if (
        db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], key),
        ).fetchone()
        is None
    ):
        storage.record_event(
            db,
            character["id"],
            key,
            dict(
                kind="presentation_client_context",
                token=token,
                instance_id=character["instance_id"],
                order_ns=time.time_ns(),
            ),
        )


def claim_group_event(db, character, group, scenario, event):
    """Deliver an atomic narrative only in its first owned run/client context.

    Mixed native initialization must precede dependent crew dialogue. A new
    connection never replays initialization or addresses its vanished actors.
    Mechanical progression belongs to the caller and is never gated here.
    """
    if (
        type(group) is not dict
        or not re.fullmatch(r"[a-z0-9-]{1,80}", group.get("id", ""))
        or type(group.get("start_event")) is not int
        or type(group.get("initializers")) is not dict
        or type(group.get("events")) is not list
        or event not in group["events"]
        or any(type(value) is not int or value <= 0 for value in group["events"])
        or any(
            not str(key).isdigit()
            or type(value) is not int
            or value not in group["events"]
            for key, value in group["initializers"].items()
        )
        or group["start_event"] not in group["initializers"].values()
        or str(scenario) not in group["initializers"]
    ):
        raise ValueError("Invalid native presentation group")
    storage._lock(db, character["id"])
    prefix = f'presentation-context:{character["instance_id"]}:'
    context = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s "
        "AND left(event_key,%s)=%s ORDER BY (payload->>'order_ns')::numeric DESC LIMIT 1",
        (character["id"], len(prefix), prefix),
    ).fetchone()
    if context is None:
        return False
    key = f'tutorial-presentation-group:{group["id"]}'
    admission = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], key),
    ).fetchone()
    identity = dict(
        kind="tutorial_presentation_group",
        instance_id=character["instance_id"],
        token=context["payload"]["token"],
    )
    if admission is None:
        if event != group["start_event"]:
            return False
        storage.record_event(db, character["id"], key, identity)
    elif admission["payload"] != identity:
        return False
    initializer = group["initializers"][str(scenario)]
    if (
        event != initializer
        and db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], f"{key}:event:{scenario}:{initializer}"),
        ).fetchone()
        is None
    ):
        return False
    return storage.record_event(
        db,
        character["id"],
        f"{key}:event:{scenario}:{event}",
        dict(kind="tutorial_presentation_group_event", scenario=scenario, event=event),
    )


def _claim(db, character_id, key, payload, legacy):
    historical = False
    for witness in legacy:
        if (
            type(witness) is not dict
            or set(witness)
            not in ({"prefix", "payload"}, {"prefix", "payload", "exclude_payload"})
            or type(witness["prefix"]) is not str
            or not witness["prefix"]
            or type(witness["payload"]) is not dict
            or not witness["payload"]
            or (
                "exclude_payload" in witness
                and (
                    type(witness["exclude_payload"]) is not dict
                    or not witness["exclude_payload"]
                )
            )
        ):
            raise ValueError("Invalid historical presentation witness")
        from psycopg.types.json import Jsonb

        query = (
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s "
            "AND left(event_key,%s)=%s AND payload @> %s"
        )
        params = (
            character_id,
            len(witness["prefix"]),
            witness["prefix"],
            Jsonb(witness["payload"]),
        )
        if "exclude_payload" in witness:
            query += " AND NOT payload @> %s"
            params += (Jsonb(witness["exclude_payload"]),)
        historical = (
            historical or db.execute(query + " LIMIT 1", params).fetchone() is not None
        )
    inserted = storage.record_event(db, character_id, key, payload)
    return inserted and not historical


def claim(db, character_id, scenario_id, event_id, variant=0, *, legacy=()):
    """Reserve a single presentation without suppressing gameplay events."""
    if any(
        type(value) is not int
        for value in (character_id, scenario_id, event_id, variant)
    ):
        raise ValueError("Invalid tutorial presentation identity")
    if character_id <= 0 or scenario_id <= 0 or event_id <= 0:
        raise ValueError("Invalid tutorial presentation identity")
    payload = {
        "kind": "tutorial_presentation",
        "scenario_id": scenario_id,
        "event_id": event_id,
        "variant": variant,
    }
    return _claim(
        db,
        character_id,
        f"tutorial-presentation:{scenario_id}:{event_id}:{variant}",
        payload,
        legacy,
    )


def claim_guide(db, character_id, guide_id, *, legacy=()):
    """Claim the native guide itself, independently of its map or trigger."""
    if any(type(value) is not int or value <= 0 for value in (character_id, guide_id)):
        raise ValueError("Invalid native guide identity")
    return _claim(
        db,
        character_id,
        f"tutorial-guide:{guide_id}",
        {"kind": "tutorial_guide", "guide_id": guide_id},
        legacy,
    )


def filter_packets(db, character_id, packets):
    """Deduplicate scenario presentations by event and optional first argument."""
    result = []
    for opcode, payload in packets:
        if opcode != 13411 or len(payload) < 10:
            raise ValueError("Invalid tutorial presentation packet")
        mode, event_id, scenario_id, count = struct.unpack(">BiiB", payload[:10])
        if mode != 0 or len(payload) != 10 + count * 8:
            raise ValueError("Invalid tutorial presentation packet")
        # Fight IDs are dynamic, while 22529's argument denotes the tutorial step.
        variant = (
            struct.unpack(">q", payload[10:18])[0] if event_id == 22529 and count else 0
        )
        if claim(db, character_id, scenario_id, event_id, variant):
            result.append((opcode, payload))
    return result
