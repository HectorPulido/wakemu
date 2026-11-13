"""Reconstructed, opt-in acceptance of source-backed daily and Modulox hunts.

A qualified server victory replaces the unrecovered quest-giver action. This
local policy does not claim the original offer rotation: all matching daily
hunts may be earned. Existing recurring settlement owns cycles and rewards.
"""
from copy import deepcopy

from wakfu_server.achievements import storage, wire
from wakfu_server.achievements.service import _owner
from . import environmental_recurring_storage as recurring

SETTING = "recurring_hunter_combat_auto_v1"
POLICY = "wakemu.daily-modulox-implicit-victory-v1"


def accept_matching(db, store, character, fight, event):
    """Accept eligible hunts from the same authenticated final-room receipt.

    This function is transaction-scoped and must precede recurring.settle_combat
    for the *same* fight. It never synthesizes an NPC/share receipt.
    """
    policy = db.execute(
        "SELECT value FROM settings WHERE name=%s", (SETTING,)
    ).fetchone()
    if policy is None:
        return []
    value = policy["value"]
    if value != {"policy": POLICY, "enabled": True}:
        raise ValueError("Invalid reconstructed daily hunter policy")
    if event.get("completed_dungeon_id") is None:
        return []
    _owner(db, character)
    receipt = db.execute(
        "SELECT payload,created_at FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], "fight:" + str(fight.id)),
    ).fetchone()
    if receipt is None or receipt["payload"] != event:
        raise ValueError("Daily hunt requires its authentic victory receipt")
    from wakfu_server.achievements.service import _event

    original = [{"id": i, "ref": r} for i, r in event["original_monsters"]]
    if _event(db, character, fight, original) != event:
        raise ValueError("Daily hunt victory source changed")
    occurred = recurring._milliseconds(receipt["created_at"])
    now = recurring._now(db)
    from wakfu_server import world_clock

    is_day = world_clock.daytime(occurred + world_clock.configured_offset_ms())
    run = db.execute(
        "SELECT r.rooms,e.room_order FROM dungeon_room_encounters e "
        "JOIN dungeon_room_runs r ON r.instance_id=e.instance_id "
        "WHERE e.fight_id=%s AND e.status='victory' AND r.status='completed'",
        (fight.id,),
    ).fetchone()
    if run is None:
        return []
    room = next((r for r in run["rooms"] if r["order"] == run["room_order"]), None)
    if room is None:
        return []
    references = {reference for _, reference in event["original_monsters"]}
    final_bosses = {
        r["ref_id"] for r in room["monsters"] if r["role"] == "boss"
    } & references
    if not references:
        return []
    candidates = db.execute(
        "SELECT DISTINCT c.definition_id,c.version FROM recurring_hunter_contracts c "
        "JOIN recurring_hunter_targets t USING(definition_id,version) "
        "WHERE c.period_ms=86400000 AND c.interpretation_policy=ANY(%s) "
        "AND t.boss_reference=ANY(%s) AND c.minimum_level<=%s "
        "AND c.version=(SELECT max(c2.version) FROM recurring_hunter_contracts c2 "
        "WHERE c2.definition_id=c.definition_id) ORDER BY c.definition_id",
        (
            [
                recurring.DAILY_POLICY,
                recurring.DAILY_NATIVE_POLICY,
                recurring.MODULOX_POLICY,
            ],
            list(references),
            character["level"],
        ),
    ).fetchall()
    packets = recurring.synchronize(db, store, character)
    before = storage.load_locked(db, character["id"])
    after = deepcopy(before)
    accepted_categories = set()
    for row in candidates:
        source, contract, _ = recurring._load(db, row["definition_id"], row["version"])
        authority = source["daily_target_authority"]
        is_modulox = source["interpretation_policy"] == recurring.MODULOX_POLICY
        if not is_modulox and not is_day:
            continue
        if authority["dungeon_definition_id"] != event["completed_dungeon_id"]:
            continue
        targets = final_bosses
        if source["interpretation_policy"] in (
            recurring.DAILY_NATIVE_POLICY,
            recurring.MODULOX_POLICY,
        ):
            from .environmental_modulox_contracts import native_boss_targets

            native_targets = native_boss_targets(
                db,
                fight,
                event,
                authority,
                room,
                room_order=run["room_order"],
                kind="modulox" if is_modulox else "daily",
            )
            if native_targets is not None:
                targets = native_targets
        if not set(contract.boss_references).intersection(targets):
            continue
        period = contract.period(occurred)
        if period is None or contract.period(now) != period:
            continue
        identity = contract.definition_id
        existing = db.execute(
            "SELECT 1 FROM recurring_hunter_acceptances WHERE character_id=%s AND definition_id=%s AND period_index=%s",
            (character["id"], identity, period),
        ).fetchone()
        if (
            existing is not None
            or identity in after["running"]
            or identity in after["completed"]
        ):
            continue
        if is_modulox:
            from .environmental_modulox_contracts import accept_category, victory

            category = authority["category_id"]
            if category in accepted_categories:
                continue
            try:
                allowed = accept_category(db, character, authority, now_ms=now)
            except ValueError:
                # Unqualified category state must not prevent other hunts.
                continue
            if not allowed or not victory(db, character, fight, authority):
                continue
            accepted_categories.add(category)
        key = f"auto-daily-hunter:{identity}:{period}"
        fact = {
            "kind": "reconstructed_hunter_victory_acceptance_v1",
            "policy": POLICY,
            "definition_id": identity,
            "version": row["version"],
            "period": period,
            "fight_id": fight.id,
            "victory_receipt": "fight:" + str(fight.id),
        }
        if not storage.record_event(db, character["id"], key, fact):
            raise ValueError("Daily hunt acceptance receipt lacks its period state")
        db.execute(
            "INSERT INTO recurring_hunter_acceptances(character_id,definition_id,version,period_index,"
            "account_id,accepted_at_ms,real_level,acceptance_event_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                character["id"],
                identity,
                row["version"],
                period,
                character["account_id"],
                occurred,
                character["level"],
                key,
            ),
        )
        after["running"] = sorted(set(after["running"]) | {identity})
        from wakfu_server.achievements.mission_progress import auto_track

        auto_track(after, identity)
    if after != before:
        storage.store(db, character["id"], after)
        packets += wire.changes(character["id"], before, after, [], [], occurred)
    return packets
