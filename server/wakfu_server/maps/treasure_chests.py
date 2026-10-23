"""Native chest interactions with explicit content and atomic account receipts.

Installed objects own appearance, action22 and non-hero eligibility. The small
normalized database identifies reconstructed rewards and repetition policy.
"""
from functools import lru_cache
import hashlib
import json
import struct

from psycopg.types.json import Jsonb

from wakfu_server.inventory_items import _lease


def _definition(db, map_id, object_id):
    row = db.execute(
        "SELECT * FROM treasure_chest_rules WHERE map_id=%s AND object_id=%s",
        (map_id, object_id),
    ).fetchone()
    if row is None:
        return None
    rule = dict(row)
    rule["position"] = [rule.pop(axis) for axis in ("x", "y", "z")]
    tool = rule.pop("native_required_tool_reference")
    rule["native_required_tools"] = [] if tool is None else [tool]
    rule["approach_cells"] = [
        [row[axis] for axis in ("x", "y", "z")]
        for row in db.execute(
            "SELECT x,y,z FROM treasure_chest_approaches WHERE map_id=%s AND object_id=%s ORDER BY x,y,z",
            (map_id, object_id),
        ).fetchall()
    ]
    rule["rewards"] = [
        dict(row)
        for row in db.execute(
            "SELECT reference,quantity FROM treasure_chest_rewards WHERE map_id=%s AND object_id=%s ORDER BY ordinal",
            (map_id, object_id),
        ).fetchall()
    ]
    if (
        rule["native_criterion"] != "not IsHero()"
        or rule["native_action"] != 22
        or rule["native_required_tools"]
        or any(
            rule[key] != 0
            for key in (
                "native_required_item",
                "native_required_quantity",
                "native_required_currency",
            )
        )
        or rule["claim_policy"] != "wakemu.once-per-account.v1"
        or rule["approach_policy"] != "wakemu.same-floor-cardinal-native-surface.v1"
        or not rule["rewards"]
        or not rule["approach_cells"]
        or any(
            cell[2] != rule["position"][2]
            or abs(cell[0] - rule["position"][0]) + abs(cell[1] - rule["position"][1])
            != 1
            for cell in rule["approach_cells"]
        )
    ):
        raise ValueError(
            "Unsupported treasure criterion, cost, approach or claim policy"
        )
    return rule


def definition(store, map_id, object_id):
    with store.connection() as db:
        custom = _definition(db, map_id, object_id)
        if custom is not None:
            return custom
        from wakfu_server.declared_treasure_rewards import _rule as declared_rule

        declared = declared_rule(db, map_id, object_id)
        if declared is not None:
            return declared
        from wakfu_server.achievements.chest_open import _bindings

        native = _bindings(db, map_id, object_id)
        return native[0] if native else None


def _digest(rule):
    return hashlib.sha256(
        json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=32)
def _native_authority(
    revision, map_id, object_id, native_payload, native_state, geometry_hash, position
):
    """Bounded source lookup; never import an entire map to claim one chest."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(object_id)
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(object_id)
    )
    with native_catalog._database().connection() as db:
        terrain = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, f"combat-maps/{map_id}.json"),
        ).fetchone()
    if (
        original is None
        or state is None
        or terrain is None
        or original.get("type") != "LootChest"
        or original.get("map_id") != map_id
        or [original.get(axis) for axis in ("x", "y", "z")] != list(position)
        or original.get("payload_hex") != native_payload
        or state.get("map_id") != map_id
        or state.get("type") != "LootChest"
        or state.get("payload_hex") != native_state
        or terrain["sha256"] != geometry_hash
        or native_catalog.release() != revision
    ):
        raise ValueError(
            "Treasure source no longer matches its declared native placement"
        )
    return True


def _packet(rule, *, claimed):
    from wakfu_server.environment_interactions import _packet as state_packet

    return state_packet(
        dict(
            object_id=rule["object_id"],
            state_payload_hex=rule["native_state_payload_hex"],
        ),
        0 if claimed else 1,
    )


def _claim_custom(
    db,
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
):
    """Fence the real selected main and atomically grant one account reward."""
    from wakfu_server import native_catalog
    from wakfu_server.harvest_inventory import grant
    from wakfu_server.simple_item_actions import _idle

    if not loaded or blocked or is_hero is not False or len(body) != 12:
        raise ValueError("Treasure interaction requires a loaded, idle non-hero actor")
    identity, action, parameter = struct.unpack(">qHH", body)
    rule = definition(store, character["map_id"], identity)
    if rule is None or action != rule["native_action"] or parameter != 0:
        raise ValueError("Unsupported native treasure action")
    if (
        character.get("instance_id", 0) != 0
        or [character[axis] for axis in ("x", "y", "z")] not in rule["approach_cells"]
    ):
        raise ValueError("Treasure requires its declared native approach surface")
    _native_authority(
        native_catalog.release(),
        rule["map_id"],
        identity,
        rule["native_payload_hex"],
        rule["native_state_payload_hex"],
        rule["native_geometry_sha256"],
        tuple(rule["position"]),
    )
    digest = _digest(rule)
    # The selected account-session lock also serializes different character
    # requests. The primary key independently enforces once-per-account.
    _lease(store, db, account_id, generation, character["id"])
    # Shared readers coexist; configuration writes wait until this grant
    # commits, including inserts into approach/reward child tables.
    db.execute(
        "LOCK TABLE treasure_chest_rules,treasure_chest_approaches,treasure_chest_rewards IN SHARE MODE"
    )
    current_rule = _definition(db, rule["map_id"], identity)
    if current_rule is None or _digest(current_rule) != digest:
        raise ValueError("Treasure content changed during preparation")
    _idle(db, character["id"], store.now())
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
        (account_id,),
    ).fetchone()
    if roster is not None and roster["leader_id"] != character["id"]:
        raise ValueError("Original treasure criterion excludes heroes")
    actual = store.character(account_id, character["id"], db)
    if any(
        actual.get(key, 0) != character.get(key, 0)
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Treasure actor location changed")
    if db.execute(
        "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
        (character["id"],),
    ).fetchone():
        raise ValueError("Another environment occupation is active")
    previous = db.execute(
        "SELECT * FROM account_treasure_claims WHERE account_id=%s AND content_id=%s",
        (account_id, rule["content_id"]),
    ).fetchone()
    if previous is not None:
        return dict(
            replay=True,
            packets=[_packet(rule, claimed=True)],
            character=actual,
            receipt=dict(previous),
        )
    packets, rewards = [], []
    for reward in rule["rewards"]:
        granted = grant(db, actual, reward["reference"], reward["quantity"])
        packets.append(granted["packet"])
        rewards.append(dict(reward, uid=granted["item"]["uid"]))
        actual = store.character(account_id, character["id"], db)
    receipt = db.execute(
        "INSERT INTO account_treasure_claims(account_id,content_id,character_id,rule_sha256,rewards,claimed_at) "
        "VALUES(%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            account_id,
            rule["content_id"],
            character["id"],
            digest,
            Jsonb(rewards),
            store.now(),
        ),
    ).fetchone()
    packets.append(_packet(rule, claimed=True))
    return dict(replay=False, packets=packets, character=actual, receipt=dict(receipt))


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
):
    """One transaction for original journal rewards and independent custom loot."""
    from wakfu_server.achievements import chest_open
    from wakfu_server import declared_treasure_rewards

    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid native treasure action length")
    identity = struct.unpack(">qHH", body)[0]
    if (
        declared_treasure_rewards.definition(store, character["map_id"], identity)
        is not None
    ):
        return declared_treasure_rewards.claim(
            store,
            account_id,
            generation,
            character,
            body,
            loaded=loaded,
            blocked=blocked,
            is_hero=is_hero,
        )
    with store.connection() as db:
        native = chest_open.claim(
            db,
            store,
            account_id,
            generation,
            character,
            body,
            loaded=loaded,
            blocked=blocked,
            is_hero=is_hero,
        )
        custom_rule = _definition(
            db, character["map_id"], struct.unpack(">qHH", body)[0]
        )
        if custom_rule is None:
            if native is None:
                raise ValueError("Unsupported native treasure action")
            return native
        custom = _claim_custom(
            db,
            store,
            account_id,
            generation,
            character,
            body,
            loaded=loaded,
            blocked=blocked,
            is_hero=is_hero,
        )
        if native is not None:
            custom["visual_packets"] = native.get("visual_packets", [])
            custom["packets"] = native["packets"] + custom["packets"]
            custom["character"] = store.character(account_id, character["id"], db)
            custom["notification_key"] = native["notification_key"]
            custom["opened"] = native["opened"]
        return custom


def snapshots(store, account_id, map_id, *, character_id=None):
    """Reconnect republishes this account's state, never a global depletion."""
    with store.connection() as db:
        identities = db.execute(
            "SELECT object_id FROM treasure_chest_rules WHERE map_id=%s ORDER BY object_id",
            (map_id,),
        ).fetchall()
        rules = [_definition(db, map_id, row["object_id"]) for row in identities]
        claimed = {
            row["content_id"]
            for row in db.execute(
                "SELECT content_id FROM account_treasure_claims WHERE account_id=%s AND content_id=ANY(%s)",
                (account_id, [rule["content_id"] for rule in rules]),
            ).fetchall()
        }
    packets = tuple(
        _packet(rule, claimed=rule["content_id"] in claimed) for rule in rules
    )
    if character_id is not None:
        from wakfu_server.declared_treasure_rewards import (
            snapshots as declared_snapshots,
        )

        packets += declared_snapshots(
            store, account_id, map_id, character_id=character_id
        )
    return packets
