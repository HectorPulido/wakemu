"""Selected daily hunter acceptance at a qualified hunter dialogue choice.

The installed native offer combines a weekly reset predicate with the daily
category active count. Its server-side effect was not recovered. This opt-in
policy reconstructs the choice as accepting today's daily for that category,
without fabricating victory or bypassing the native selected-offer backend.
"""
from wakfu_server.achievements import storage
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_recurring_storage as recurring

SETTING = "reconstructed_daily_hunter_npc_v1"
POLICY = "wakemu.hunter-choice-daily-and-weekly-v1"


def enabled(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return False
    if row["value"] != {"enabled": True, "policy": POLICY}:
        raise ValueError("Invalid daily hunter NPC policy")
    return True


def accept_for_choice(
    db, store, character, offer, *, actor_id, reference_id, action_id
):
    """Accept exactly the shared daily choice in the offered category.

    The caller authenticated and locked the owner and validated the NPC session,
    offered native node/choice and range. This function must execute in the same
    transaction as that validation and journal publication.
    """
    if not enabled(db):
        return []
    category = offer["category_id"]
    selected = [
        row
        for row in selection.select_for_character(db, store, character)
        if row["category_id"] == category
    ]
    if not selected:
        return []
    if len(selected) != 1:
        raise ValueError("Ambiguous daily hunter category selection")
    choice = selected[0]
    if not choice["eligible"]:
        return []
    identity, version = choice["definition_id"], choice["version"]
    source, contract, _ = recurring._load(db, identity, version)
    if (
        source["interpretation_policy"]
        not in (recurring.DAILY_POLICY, recurring.DAILY_NATIVE_POLICY)
        or source["daily_target_authority"]["category_id"] != category
    ):
        raise ValueError("Daily hunter selected source differs from offered category")
    now_ms = recurring._now(db)
    period = contract.period(now_ms)
    if period is None:
        raise ValueError("Daily hunter period unavailable")
    previous = db.execute(
        "SELECT 1 FROM recurring_hunter_acceptances WHERE character_id=%s AND definition_id=%s AND period_index=%s",
        (character["id"], identity, period),
    ).fetchone()
    if previous is not None:
        return []
    state = storage.load_locked(db, character["id"])
    if identity in state["running"] or identity in state["completed"]:
        raise ValueError("Daily hunter journal has no matching acceptance")
    key = f"native-hunter-daily-npc:{identity}:{period}"
    fact = {
        "kind": "native_recurring_acceptance",
        "definition_id": identity,
        "real_level": character["level"],
        "source_kind": "npc_dialogue",
        "source_reference": reference_id,
        "action_id": action_id,
        "node_id": offer["node_id"],
        "choice_id": offer["choice_id"],
        "actor_id": actor_id,
        "reconstruction": POLICY,
        "selected_utc_day": choice["utc_day"],
        "category_id": category,
    }
    if not storage.record_event(db, character["id"], key, fact):
        raise ValueError("Daily hunter acceptance receipt lacks progress")
    return recurring.accept_from_receipt(
        db, store, character, identity, receipt_key=key
    )["packets"]
