"""Durable earned story7835 progression, independent of combat-win rewards.

This explicit reconstruction consumes the actual native duel's KO receipt.
It completes only the original final objective. Quest3797's completion criterion
and five rewards are outside this adapter; they are never inferred from a loss.
"""
from copy import deepcopy
from .combat_aguabrial_scene import POLICY, earned_story_continuation, story_admission
from .combat_quest_scene_authority import authenticated_quest_fact


def settle_aguabrial_story(store, db, fight, members):
    """Return account→native packets under the ordinary settlement transaction."""
    admission = story_admission(fight)
    if admission is None:
        return {}
    if fight.phase != "finished" or fight.winner not in (0, 1):
        raise ValueError("Story continuation requires actual resolved combat")
    receipt = earned_story_continuation(fight)
    if receipt is None:
        return {}
    identity, owner = receipt["participant_id"], receipt["account_id"]
    matching = [
        row
        for row in members
        if row["character_id"] == identity and row["account_id"] == owner
    ]
    if len(matching) != 1 or not matching[0].get("session_generation"):
        raise ValueError("Story continuation lacks actual fenced participant")
    member = matching[0]
    actor = fight.actors[identity]
    if actor.team == fight.winner or member.get("withdrawn", False):
        return {}
    participant = db.execute(
        "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
        "AND p.character_id=%s AND p.account_id=%s",
        (fight.id, identity, owner),
    ).fetchone()
    if (
        participant is None
        or participant["status"] != "finished"
        or participant["fight_kind"] != "pve"
        or participant["team"] != actor.team
    ):
        raise ValueError("Story continuation lacks durable ordinary fight participant")
    # Re-fence the live session and current original quest before any progress.
    # A changed unrelated objective does not invalidate this earned scene.
    fact = authenticated_quest_fact(
        store,
        db,
        account_id=owner,
        generation=member["session_generation"],
        character_id=identity,
        quest_id=3797,
        objective_id=7835,
        required_completed_objectives=(7834,),
    )
    from wakfu_server.achievements import storage, wire

    key = f"aguabrial-story:{fight.id}:{identity}"
    event = dict(receipt, kind=POLICY, quest_id=3797, objective_id=7835)
    before = storage.load_locked(db, identity)
    if fact is None:
        # A replay is allowed only if this exact earned event was committed;
        # arbitrary pre-existing objective completion is not scene authority.
        row = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (identity, key),
        ).fetchone()
        if row is not None and row["payload"] == event and 7835 in before["objectives"]:
            return {}
        return {}
    if not storage.record_event(db, identity, key, event):
        return {}
    after = deepcopy(before)
    after["objectives"] = sorted(set(after["objectives"]) | {7835})
    storage.store(db, identity, after)
    now_ms = int(store.now().timestamp() * 1000)
    packets = wire.changes(identity, before, after, [7835], [], now_ms)
    storage.enqueue_notifications(
        db,
        identity,
        key,
        [dict(opcode=opcode, payload_hex=body.hex()) for opcode, body in packets],
    )
    return {owner: packets}
