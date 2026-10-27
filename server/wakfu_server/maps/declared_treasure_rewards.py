"""User-declared treasure rewards with character-scoped, durable attempts.

Policy comes exclusively from normalized DB rows. A random outcome is reserved
in its own authenticated transaction before inventory settlement, so failed
capacity/retry cannot reroll it. Only successful settlement starts cooldown.
"""
from datetime import timedelta
from functools import lru_cache
import hashlib
import json
import secrets
import struct
import uuid
from psycopg.types.json import Jsonb


def _rule(db, map_id, object_id):
    row = db.execute(
        "SELECT l.*,p.reward_kind,p.quantity,p.kamas,p.cooldown_ms,p.once_only,p.authority,p.sealed "
        "FROM declared_treasure_locations l JOIN declared_treasure_policies p USING(policy_id) "
        "WHERE l.map_id=%s AND l.object_id=%s",
        (map_id, object_id),
    ).fetchone()
    if row is None:
        return None
    rule = dict(row)
    rule["approaches"] = [
        [r[k] for k in ("x", "y", "z")]
        for r in db.execute(
            "SELECT x,y,z FROM declared_treasure_approaches WHERE map_id=%s AND object_id=%s ORDER BY x,y,z",
            (map_id, object_id),
        ).fetchall()
    ]
    rule["outcomes"] = [
        dict(r)
        for r in db.execute(
            "SELECT ordinal,item_reference FROM declared_treasure_outcomes WHERE policy_id=%s ORDER BY ordinal",
            (rule["policy_id"],),
        ).fetchall()
    ]
    if not rule["client_action_available"]:
        from wakfu_server.treasure_definition_projections import binding

        override = binding(db, rule)
        if override is not None:
            rule["definition_override"] = override
            rule["client_action_available"] = True
            rule["wire_action"] = override["native_action"]
            rule["requires_nonhero"] = True
    if (
        rule["sealed"] is not True
        or not rule["authority"]
        or not rule["approaches"]
        or rule["reward_kind"] not in ("uniform_fragment", "kamas")
        or (
            rule["reward_kind"] == "uniform_fragment"
            and (
                not rule["outcomes"]
                or rule["quantity"] != 1
                or rule["cooldown_ms"] <= 0
                or rule["once_only"]
                or rule["kamas"] != 0
            )
        )
        or (
            rule["reward_kind"] == "kamas"
            and (
                rule["outcomes"]
                or rule["quantity"] != 0
                or rule["kamas"] <= 0
                or not rule["once_only"]
                or rule["cooldown_ms"] != 0
            )
        )
    ):
        raise ValueError("Unqualified declared treasure reward")
    return rule


def definition(store, map_id, object_id):
    with store.connection() as db:
        return _rule(db, map_id, object_id)


def _digest(rule):
    return hashlib.sha256(
        json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _source(
    revision, map_id, object_id, family, payload, state_payload, geometry_sha, x, y, z
):
    from wakfu_server import native_catalog

    return _source_cached(
        native_catalog.release(),
        revision,
        map_id,
        object_id,
        family,
        payload,
        state_payload,
        geometry_sha,
        x,
        y,
        z,
    )


@lru_cache(maxsize=128)
def _source_cached(
    publication,
    revision,
    map_id,
    object_id,
    family,
    payload,
    state_payload,
    geometry_sha,
    x,
    y,
    z,
):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        revision,
        (
            "native-map-objects.json",
            "native-interactive-states.json",
            f"combat-maps/{map_id}.json",
        ),
    )
    current_revision = native_catalog.release()
    if current_revision != publication:
        raise ValueError(
            "Declared treasure publication changed during source validation"
        )
    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(object_id)
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(object_id)
    )
    with native_catalog._database().connection() as db:
        terrain = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (current_revision, f"combat-maps/{map_id}.json"),
        ).fetchone()
    if (
        current_revision != native_catalog.release()
        or original is None
        or original.get("type") != family
        or original.get("map_id") != map_id
        or original.get("payload_hex") != payload
        or [original.get(k) for k in ("x", "y", "z")] != [x, y, z]
        or state is None
        or state.get("payload_hex") != state_payload
        or state.get("map_id") != map_id
        or terrain is None
        or terrain["sha256"] != geometry_sha
    ):
        raise ValueError("Declared treasure native source changed")
    return True


_source.cache_clear = _source_cached.cache_clear


def _admit(
    store, db, account_id, generation, character, body, *, loaded, blocked, is_hero
):
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.simple_item_actions import _idle

    if type(body) is not bytes or len(body) != 12 or not loaded or blocked:
        raise ValueError("Declared treasure needs its loaded native action")
    identity, action, parameter = struct.unpack(">qHH", body)
    _leased_owner(store, db, account_id, generation, character)
    rule = _rule(db, character["map_id"], identity)
    if (
        rule is None
        or not rule["client_action_available"]
        or action != rule["wire_action"]
        or parameter != 0
        or (rule["requires_nonhero"] and is_hero is not False)
    ):
        raise ValueError("Declared treasure action is unavailable")
    actual = store.character(account_id, character["id"], db)
    if (
        any(
            actual.get(k, 0) != character.get(k, 0)
            for k in ("map_id", "instance_id", "x", "y", "z")
        )
        or [actual[k] for k in ("x", "y", "z")] not in rule["approaches"]
    ):
        raise ValueError("Declared treasure requires its original native approach")
    _idle(db, actual["id"], store.now())
    if db.execute(
        "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
        (actual["id"],),
    ).fetchone():
        raise ValueError("Another environment occupation is active")
    _source(
        rule["catalog_revision"],
        rule["map_id"],
        identity,
        rule["native_family"],
        rule["payload_hex"],
        rule["state_payload_hex"],
        rule["geometry_sha256"],
        rule["x"],
        rule["y"],
        rule["z"],
    )
    return actual, rule


def _state(rule, claimed):
    from wakfu_server.environment_interactions import _packet

    return _packet(
        dict(object_id=rule["object_id"], state_payload_hex=rule["state_payload_hex"]),
        0 if claimed else 1,
    )


def _unavailable(rule, row, now):
    return row["last_claimed_at"] is not None and (
        rule["once_only"]
        or now < row["last_claimed_at"] + timedelta(milliseconds=rule["cooldown_ms"])
    )


def claim(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
    choose=None,
):
    """Reserve once, then atomically grant/inventory UID/wallet/receipt/cooldown."""
    choose = secrets.randbelow if choose is None else choose
    kwargs = dict(loaded=loaded, blocked=blocked, is_hero=is_hero)
    with store.connection() as db:
        actual, rule = _admit(
            store, db, account_id, generation, character, body, **kwargs
        )
        db.execute(
            "INSERT INTO declared_treasure_eligibility(character_id,account_id,map_id,object_id) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (actual["id"], account_id, rule["map_id"], rule["object_id"]),
        )
        gate = db.execute(
            "SELECT * FROM declared_treasure_eligibility WHERE character_id=%s AND map_id=%s "
            "AND object_id=%s FOR UPDATE",
            (actual["id"], rule["map_id"], rule["object_id"]),
        ).fetchone()
        if gate["account_id"] != account_id:
            raise ValueError("Foreign declared treasure eligibility")
        if _unavailable(rule, gate, store.now()):
            return dict(
                replay=True, character=actual, packets=[_state(rule, True)], receipt={}
            )
        digest = _digest(rule)
        if gate["pending_attempt"] is None:
            ordinal = None
            if rule["outcomes"]:
                selected = choose(len(rule["outcomes"]))
                if type(selected) is not int or not 0 <= selected < len(
                    rule["outcomes"]
                ):
                    raise ValueError("Invalid declared treasure uniform draw")
                ordinal = rule["outcomes"][selected]["ordinal"]
            token = uuid.uuid4()
            db.execute(
                "INSERT INTO declared_treasure_attempts(token,account_id,character_id,map_id,object_id,"
                "policy_id,selected_ordinal,rule_digest,prepared_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    token,
                    account_id,
                    actual["id"],
                    rule["map_id"],
                    rule["object_id"],
                    rule["policy_id"],
                    ordinal,
                    digest,
                    store.now(),
                ),
            )
            db.execute(
                "UPDATE declared_treasure_eligibility SET pending_attempt=%s WHERE character_id=%s "
                "AND map_id=%s AND object_id=%s",
                (token, actual["id"], rule["map_id"], rule["object_id"]),
            )
        else:
            token = gate["pending_attempt"]
    # The reserved outcome survives a failed second transaction. The successful
    # receipt and all grants still commit together; no reward escapes rollback.
    with store.connection() as db:
        actual, rule = _admit(
            store, db, account_id, generation, character, body, **kwargs
        )
        gate = db.execute(
            "SELECT * FROM declared_treasure_eligibility WHERE character_id=%s AND map_id=%s "
            "AND object_id=%s FOR UPDATE",
            (actual["id"], rule["map_id"], rule["object_id"]),
        ).fetchone()
        if _unavailable(rule, gate, store.now()):
            return dict(
                replay=True, character=actual, packets=[_state(rule, True)], receipt={}
            )
        attempt = db.execute(
            "SELECT * FROM declared_treasure_attempts WHERE token=%s FOR UPDATE",
            (token,),
        ).fetchone()
        if (
            gate["pending_attempt"] != token
            or attempt is None
            or attempt["completed_at"] is not None
            or attempt["rule_digest"] != _digest(rule)
            or attempt["account_id"] != account_id
            or attempt["character_id"] != actual["id"]
        ):
            raise ValueError("Declared treasure reservation changed")
        packets = []
        receipt = dict(token=str(token), kamas=0, item_reference=None, quantity=0)
        if rule["reward_kind"] == "uniform_fragment":
            from wakfu_server.achievements.rewards import _item

            outcome = next(
                (
                    r
                    for r in rule["outcomes"]
                    if r["ordinal"] == attempt["selected_ordinal"]
                ),
                None,
            )
            if outcome is None:
                raise ValueError("Missing reserved treasure fragment")
            packets.extend(
                _item(db, store, actual, outcome["item_reference"], rule["quantity"])
            )
            receipt.update(
                item_reference=outcome["item_reference"], quantity=rule["quantity"]
            )
        else:
            from wakfu_server.wire import account_kamas_update

            wallet = db.execute(
                "UPDATE account_wallets SET kamas=kamas+%s WHERE account_id=%s AND kamas<=%s "
                "RETURNING kamas",
                (rule["kamas"], account_id, 2**63 - 1 - rule["kamas"]),
            ).fetchone()
            if wallet is None:
                raise ValueError("Declared treasure wallet missing or overflowing")
            packets.append((12753, account_kamas_update(wallet["kamas"])))
            receipt["kamas"] = rule["kamas"]
        now = store.now()
        db.execute(
            "UPDATE declared_treasure_attempts SET completed_at=%s,receipt=%s WHERE token=%s",
            (now, Jsonb(receipt), token),
        )
        db.execute(
            "UPDATE declared_treasure_eligibility SET last_claimed_at=%s,pending_attempt=NULL "
            "WHERE character_id=%s AND map_id=%s AND object_id=%s",
            (now, actual["id"], rule["map_id"], rule["object_id"]),
        )
        from wakfu_server.achievements import storage

        key = f"declared-treasure:{token}"
        storage.enqueue_notifications(
            db,
            actual["id"],
            key,
            [
                dict(opcode=opcode, payload_hex=payload.hex())
                for opcode, payload in packets
            ],
        )
        packets.append(_state(rule, True))
        return dict(
            replay=False,
            character=store.character(account_id, actual["id"], db),
            packets=packets,
            notification_key=key,
            receipt=receipt,
        )


def snapshots(store, account_id, map_id, *, character_id):
    with store.connection() as db:
        if (
            db.execute(
                "SELECT 1 FROM characters WHERE account_id=%s AND id=%s",
                (account_id, character_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Foreign declared treasure snapshot owner")
        rows = db.execute(
            "SELECT object_id FROM declared_treasure_locations WHERE map_id=%s "
            "ORDER BY object_id",
            (map_id,),
        ).fetchall()
        result = []
        for row in rows:
            rule = _rule(db, map_id, row["object_id"])
            # Immutable native-source flags may be false while a separately
            # attested definition projection provides the effective menu.
            if rule is None or not rule["client_action_available"]:
                continue
            gate = db.execute(
                "SELECT last_claimed_at FROM declared_treasure_eligibility WHERE character_id=%s "
                "AND map_id=%s AND object_id=%s",
                (character_id, map_id, row["object_id"]),
            ).fetchone()
            result.append(
                _state(rule, gate is not None and _unavailable(rule, gate, store.now()))
            )
        return tuple(result)
