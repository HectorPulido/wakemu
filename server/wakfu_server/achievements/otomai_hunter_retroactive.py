"""Reconcile accepted Otomai hunts with previously recorded victorious fights.

Native dialogue 2406 states that boss-kill objectives validate on reconnect if
already achieved. Only authenticated fight receipts in the existing achievement
ledger qualify; a quest must already be running, and inventory is untouched.
The caller owns the transaction and account/session authorization.
"""
from . import combat_missions, storage, wire

QUESTS = frozenset((1695, 1708, 1715))


def reconcile(db, store, character, *, now_ms):
    """Return journal/reward packets, updating only supported accepted hunts."""
    from .service import _owner, drain_rewards
    from . import rewards

    _owner(db, character)
    before = storage.load_locked(db, character["id"])
    active = set(before["running"]) & QUESTS
    if not active:
        return []
    publication = combat_missions.load(db)
    if publication is None:
        return []
    rules, definitions = publication
    rules = [
        r
        for r in rules
        if r["quest_id"] in active
        and r.get("acceptance") == "explicit"
        and r["kind"] == "monster"
        and r["count"] == 1
    ]
    if not rules:
        return []
    desired = {r["target_id"] for r in rules}
    histories = db.execute(
        "SELECT event_key,payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key LIKE 'fight:%%' ORDER BY event_key",
        (character["id"],),
    ).fetchall()
    # These are authenticated, deduplicated victory facts already produced by
    # the combat service; use only their native original monster identities.
    evidence = {}
    for receipt in histories:
        payload = receipt["payload"]
        if not isinstance(payload, dict) or not isinstance(
            payload.get("original_breeds"), list
        ):
            continue
        for breed in payload["original_breeds"]:
            if type(breed) is int and breed in desired:
                evidence.setdefault(breed, receipt["event_key"])
    selected = [r for r in rules if r["target_id"] in evidence]
    if not selected:
        return []
    event = {"original_breeds": sorted(evidence), "completed_dungeon_id": None}
    after, intents, objectives, completed, _ = combat_missions.advance(
        before,
        event,
        selected,
        definitions,
        character=character,
        store=store,
        now_ms=now_ms,
        counts={},
    )
    if not objectives:
        return []
    for objective in objectives:
        binding = next(r for r in selected if r["objective_id"] == objective)
        payload = {
            "quest_id": binding["quest_id"],
            "objective_id": objective,
            "boss_reference": binding["target_id"],
            "victory_receipt": evidence[binding["target_id"]],
        }
        if not storage.record_event(
            db,
            character["id"],
            f'otomai-hunter-retroactive:{binding["quest_id"]}:{objective}',
            payload,
        ):
            raise ValueError("Retroactive boss receipt exists without its objective")
    for identity, reward in intents:
        rewards.validate(reward)
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    packets = wire.changes(
        character["id"], before, after, objectives, completed, now_ms
    )
    packets.extend(drain_rewards(db, store, character))
    return packets
