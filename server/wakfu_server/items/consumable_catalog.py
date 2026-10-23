"""PostgreSQL authority for original native inventory consumable plans."""
import copy


def load_plan(db, reference):
    """Return a detached qualified plan; never invent missing native behavior."""
    if type(reference) is not int or reference <= 0:
        raise ValueError("Invalid consumable item reference")
    row = db.execute(
        "SELECT available,unsupported_reason,plan FROM native_consumable_actions WHERE item_ref=%s",
        (reference,),
    ).fetchone()
    if row is None:
        return None
    if not row["available"]:
        raise ValueError(
            "Native consumable is unsupported: " + row["unsupported_reason"]
        )
    plan = row["plan"]
    if not isinstance(plan, dict) or not isinstance(plan.get("states"), list):
        raise ValueError("Invalid native consumable plan")
    emotes = plan.get("emotes", [])
    if not isinstance(emotes, list) or any(
        not isinstance(emote, dict)
        or type(emote.get("emote_id")) is not int
        or emote["emote_id"] <= 0
        or type(emote.get("effect_id")) is not int
        or emote["effect_id"] <= 0
        or type(emote.get("forced")) is not bool
        for emote in emotes
    ):
        # World publishes these after the inventory transaction commits. Reject
        # malformed output before consumption, rather than failing publication.
        raise ValueError("Invalid native consumable emote plan")
    return copy.deepcopy(plan)
