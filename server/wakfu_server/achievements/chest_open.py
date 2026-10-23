"""Reviewed original-object openings authenticated inside the claim transaction.

No client objective/event API or implicit empty-objective completion exists.
Bindings have no seed/fallback. Custom account item claims remain independent.
"""
import hashlib
import json
import struct

from psycopg.types.json import Jsonb

from . import catalog, chest_scripts, engine, rewards, storage, wire
from .service import _owner

POLICY = "authenticated_native_chest_open_v1"


def _digest(rule):
    return hashlib.sha256(
        json.dumps(
            rule, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _bindings(db, map_id, object_id):
    rows = db.execute(
        "SELECT b.*,s.native_payload_hex AS attested_payload_hex,s.catalog_revision,"
        "s.object_kind,s.object_family,s.original_name_en,s.native_action AS attested_action,"
        "s.native_parameter,s.native_direction,s.native_approach_mask,s.native_center_blocked,"
        "s.native_physical_sha256,s.source_sha256 AS attestation_source_sha256 FROM achievement_chest_bindings b "
        "JOIN achievement_chest_source_attestations s USING(map_id,object_id,native_definition) "
        "WHERE b.map_id=%s AND b.object_id=%s ORDER BY binding_id",
        (map_id, object_id),
    ).fetchall()
    result = []
    for row in rows:
        rule = dict(row)
        rule["approaches"] = [
            [r[k] for k in ("x", "y", "z")]
            for r in db.execute(
                "SELECT x,y,z FROM achievement_chest_approaches WHERE binding_id=%s ORDER BY x,y,z",
                (row["binding_id"],),
            ).fetchall()
        ]
        position = [rule[k] for k in ("x", "y", "z")]
        if (
            rule["native_action"] != rule["attested_action"]
            or rule["native_payload_hex"] != rule["attested_payload_hex"]
            or rule["object_kind"] not in ("chest", "emote_chest", "gemlock")
            or not rule["approaches"]
        ):
            raise ValueError("Unqualified native chest approach or criterion")
        rule["scripts"] = chest_scripts.programs(db, rule)
        result.append(rule)
    return result


def _native_source(rule):
    """Check a positively attested identity, never the generic Java family alone."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    if rule["catalog_revision"] != native_catalog.release():
        raise ValueError("Native chest attestation belongs to another catalog release")
    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(rule["object_id"])
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(rule["object_id"])
    )
    with native_catalog._database().connection() as db:
        terrain = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (rule["catalog_revision"], f"combat-maps/{rule['map_id']}.json"),
        ).fetchone()
    if (
        rule["object_family"] not in ("LootChest", "GenericActivableInteractiveElement")
        or original is None
        or original.get("type") != rule["object_family"]
        or original.get("map_id") != rule["map_id"]
        or [original.get(k) for k in ("x", "y", "z")]
        != [rule[k] for k in ("x", "y", "z")]
        or original.get("payload_hex") != rule["attested_payload_hex"]
        or terrain is None
        or terrain["sha256"] != rule["native_geometry_sha256"]
    ):
        raise ValueError("Native chest source differs from its positive attestation")
    if rule["native_state_payload_hex"] is None:
        if state is not None:
            raise ValueError("Native chest unexpectedly has a state record")
    elif (
        state is None
        or state.get("type") != rule["object_family"]
        or state.get("map_id") != rule["map_id"]
        or state.get("payload_hex") != rule["native_state_payload_hex"]
    ):
        raise ValueError("Native chest state differs from its original source")
    if rule["emote_id"] is not None:
        from wakfu_server.combat_sn_path import NativeSnColumns
        from wakfu_server.native_interaction_approaches import (
            native_interaction_approaches,
        )

        physical = NativeSnColumns.from_published(rule["map_id"])
        if physical.source_sha256 != rule["native_physical_sha256"]:
            raise ValueError("Native chest physical source changed")
        expected = native_interaction_approaches(
            native_catalog.load(DATA_ROOT / f"combat-maps/{rule['map_id']}.json"),
            [rule[k] for k in ("x", "y", "z")],
            direction=rule["native_direction"],
            approach_mask=rule["native_approach_mask"],
            physical_columns=physical,
            center_allowed=not rule["native_center_blocked"],
        )
        if sorted(map(tuple, rule["approaches"])) != sorted(expected):
            raise ValueError(
                "Native chest approach differs from original QV/VF authority"
            )


def _artifact(character, reference):
    if reference is None:
        return []
    # These are reloaded owned inventories, not a packet-supplied artifact flag.
    for key, owner_key, owner in (
        ("quest_items", "character_id", character["id"]),
        ("account_quest_items", "account_id", character["account_id"]),
    ):
        if any(
            row.get(owner_key) == owner
            and row.get("reference") == reference
            and type(row.get("quantity")) is int
            and row["quantity"] > 0
            for row in character.get(key, ())
        ):
            return [reference]
    raise ValueError("Native chest requires its owned artifact")


def _eligible(rule, rules, before, character, now_ms):
    from wakfu_server.transport_criteria import evaluate

    definition = rules["definitions"].get(rule["definition_id"])
    if (
        definition is None
        or definition.get("event_policy") != POLICY
        or {
            o["objective_id"]
            for o in definition["objectives"]
            if o.get("chest_binding_id") == rule["binding_id"]
        }
        != {rule["objective_id"]}
        or definition.get("source_criteria")
        != {"aHe": rule["activation_criterion"], "cjI": rule["completion_criterion"]}
    ):
        raise ValueError("Chest binding differs from its qualified original objective")
    return all(
        evaluate(
            rule[key],
            character,
            now_ms=now_ms,
            achievement_complete=lambda identity: identity in before["completed"],
        )
        for key in ("activation_criterion", "completion_criterion")
    )


def _direct_emote(db, rule):
    if rule["emote_id"] is None:
        return False
    if (
        rule["object_family"] != "GenericActivableInteractiveElement"
        or rule["binding_authority"] != "recovered_native_emote_effect7_v1"
        or rule["definition_id"] is not None
        or rule["objective_id"] is not None
        or rule["effect_criterion"] != f"not HasEmote({rule['emote_id']})"
        or type(rule["effect_reference"]) is not int
        or rule["effect_reference"] <= 0
        or rule["activation_criterion"]
        or rule["completion_criterion"]
    ):
        raise ValueError("Unqualified original emote effect7 binding")
    original = db.execute(
        "SELECT * FROM native_generic_emote_effect_sources "
        "WHERE descriptor_id=%s AND wire_action=%s AND effect_reference=%s",
        (rule["native_definition"], rule["native_action"], rule["effect_reference"]),
    ).fetchone()
    if (
        original is None
        or original["effect_type"] != 7
        or original["catalog_revision"] != rule["catalog_revision"]
        or original["source_sha256"] != rule["source_sha256"]
        or original["parameters"] != [str(rule["emote_id"])]
        or original["effect_criterion"] != rule["effect_criterion"]
        or original["action_criterion"] != rule["native_criterion"]
    ):
        raise ValueError(
            "Emote binding differs from its original descriptor/action/effect"
        )
    # cof selects the inventory used for costs. cog is retained raw: its unit
    # and server timing have not been recovered. Neither changes the original
    # type7 recipient or permits a fabricated cooldown. This adapter handles
    # only free actions with the attested probability.
    if original["raw_cob"] != 1.0 or any(
        original[k] != 0 for k in ("group_cnd", "group_cod", "group_coe")
    ):
        raise ValueError("Native emote action requires unsupported costs")
    return True


def claim(
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
    """Return None for an unbound object; caller owns commit and publication.

    This adapter must run before any custom once-account receipt early return.
    It requires the same original request/loaded-scene authority as that route,
    and independently rechecks ownership, session, position, idle and artifacts.
    """
    from wakfu_server.inventory_items import _lease
    from wakfu_server.simple_item_actions import _idle

    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Malformed native chest interaction")
    object_id, action, parameter = struct.unpack(">qHH", body)
    if account_id != character["account_id"]:
        raise ValueError("Foreign native chest owner")
    # Fence the selected session before taking account/character locks. Taking
    # _owner first would invert inventory's session->character order; calling
    # _lease first would invert offline settlement's account->character order.
    # This prefix holds no character lock while waiting for the account.
    session = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s "
        "AND generation=%s AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if session is None or session["character_id"] != character["id"]:
        raise ValueError("Invalid inventory session")
    _owner(db, character)
    _lease(store, db, account_id, generation, character["id"])
    db.execute(
        "LOCK TABLE achievement_chest_bindings,achievement_chest_approaches,"
        "achievement_chest_source_attestations,native_generic_emote_effect_sources,"
        "native_generic_chest_script_sources IN SHARE MODE"
    )
    rules = _bindings(db, character["map_id"], object_id)
    if not rules:
        return None
    if not loaded or blocked or type(is_hero) is not bool:
        raise ValueError("Native chest requires its authenticated loaded action")
    _idle(db, character["id"], store.now())
    actual = store.character(account_id, character["id"], db)
    if any(
        actual.get(key, 0) != character.get(key, 0)
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Native chest actor location changed")
    if db.execute(
        "SELECT 1 FROM environment_interaction_tickets "
        "WHERE character_id=%s AND state='active'",
        (actual["id"],),
    ).fetchone():
        raise ValueError("Another native occupation is active")
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s", (account_id,)
    ).fetchone()
    main = roster is None or roster["leader_id"] == actual["id"]
    before = storage.load_locked(db, actual["id"])
    qualified = catalog.load(db)
    now_ms = int(store.now().timestamp() * 1000)
    packets, visual_packets, opened, fresh_openings = [], [], [], 0
    for rule in rules:
        if action != rule["native_action"] or parameter != rule["native_parameter"]:
            raise ValueError("Native chest requires its attested original action")
        if [actual[k] for k in ("x", "y", "z")] not in rule["approaches"]:
            raise ValueError("Native chest approach or non-hero criterion failed")
        # Snapshot the actual pre-action account knowledge. Script selection
        # and type7 eligibility must see the same facts before learning.
        from wakfu_server import emotes

        known = frozenset(emotes.available(db, account_id))
        from wakfu_server.transport_criteria import evaluate

        def allowed(expression):
            return evaluate(
                expression,
                actual,
                now_ms=now_ms,
                achievement_complete=lambda identity: identity in before["completed"],
                objective_complete=lambda identity: identity in before["objectives"],
                emote_known=lambda identity: identity in known,
            )

        if rule["native_criterion"] == "not IsHero()":
            criterion_ok = not is_hero and main
        else:
            criterion_ok = allowed(rule["native_criterion"])
        if not criterion_ok:
            raise ValueError("Native chest original criterion failed")
        _native_source(rule)
        artifacts = _artifact(actual, rule["artifact_reference"])
        direct_emote = _direct_emote(db, rule)
        if not direct_emote and not _eligible(rule, qualified, before, actual, now_ms):
            raise ValueError("Native chest achievement eligibility failed")
        visual_packets.extend(
            chest_scripts.packets(rule, actual["id"], evaluate=allowed)
        )
        digest = _digest(rule)
        event = dict(
            kind=POLICY,
            binding_id=rule["binding_id"],
            objective_id=rule["objective_id"],
            eligible_definition_ids=[] if direct_emote else [rule["definition_id"]],
            account_id=account_id,
            character_id=actual["id"],
            session_generation=generation,
            map_id=actual["map_id"],
            instance_id=actual.get("instance_id", 0),
            object_id=object_id,
            action=action,
            rule_sha256=digest,
            position=[actual[k] for k in ("x", "y", "z")],
            artifacts=artifacts,
        )
        previous = db.execute(
            "SELECT rule_sha256,event_payload FROM character_achievement_chest_opens "
            "WHERE character_id=%s AND binding_id=%s",
            (actual["id"], rule["binding_id"]),
        ).fetchone()
        if previous is not None:
            if previous["rule_sha256"] != digest:
                raise ValueError("Native chest binding changed after its opening")
            event = previous["event_payload"]
        else:
            db.execute(
                "INSERT INTO character_achievement_chest_opens "
                "(character_id,binding_id,account_id,rule_sha256,event_payload) VALUES(%s,%s,%s,%s,%s)",
                (actual["id"], rule["binding_id"], account_id, digest, Jsonb(event)),
            )
        key = f"chest:{rule['binding_id']}:once"
        fresh = storage.record_event(db, actual["id"], key, event)
        if fresh:
            fresh_openings += 1
        if direct_emote:
            # Type7's original criterion is evaluated for every authenticated
            # action. A prior opening in the DEV unlock view must not consume
            # later real learning. Account knowledge itself remains idempotent.
            if allowed(rule["effect_criterion"]):
                packets.extend(rewards._emote(db, actual, rule["emote_id"]))
            else:
                packets.append(emotes.snapshot(db, account_id))
        elif fresh:
            after, grants, objectives, completed = engine.advance(
                before, event, qualified, now_ms=now_ms
            )
            for identity, reward in grants:
                storage.claim_reward(
                    db, actual["id"], identity, "once", reward["d"], reward
                )
            storage.store(db, actual["id"], after)
            packets.extend(
                wire.changes(actual["id"], before, after, objectives, completed, now_ms)
            )
            before = after
        opened.append(rule["binding_id"])
    # A chest opening is an optional action, unlike final fight settlement.
    # Capacity failure aborts the entire opening rather than consuming it.
    owners = {r["definition_id"] for r in rules if r["definition_id"] is not None}
    for pending in storage.pending_rewards(db, actual["id"]):
        if pending["achievement_id"] not in owners:
            continue
        current = store.character(account_id, actual["id"], db)
        packets.extend(
            rewards.grant(db, store, current, pending["payload"], entitlement=pending)
        )
        storage.mark_reward_delivered(
            db,
            actual["id"],
            pending["achievement_id"],
            pending["cycle_key"],
            pending["reward_key"],
        )
    if packets:
        envelopes = [
            {"opcode": op, "payload_hex": payload.hex()} for op, payload in packets
        ]
        key = (
            "chest-notice:"
            + hashlib.sha256(storage._json({"packets": envelopes}).encode()).hexdigest()
        )
        storage.enqueue_notifications(db, actual["id"], key, envelopes)
    else:
        key = None
    return dict(
        packets=packets,
        visual_packets=visual_packets,
        notification_key=key,
        opened=opened,
        replay=fresh_openings == 0,
        character=store.character(account_id, actual["id"], db),
    )
