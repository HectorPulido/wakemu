"""Ruel's assigned archmonster hunts, independent of NPC placement.

NPC-to-dialogue edges and the daily selection algorithm are local
reconstructions. The server must authenticate the NPC session and combat
receipt before calling these pure transitions; this module is not a public API.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

PREREQUISITE = 3974
CATEGORY = 681
VARIABLE = 693
# Native choices from dialogue 4146: exclusive upper level, completion limit.
_BANDS = (
    (35, 3, 10346),
    (50, 5, 10451),
    (65, 7, 10452),
    (80, 11, 10453),
    (95, 15, 10454),
    (110, 19, 10455),
    (125, 22, 10456),
    (140, 26, 10457),
    (155, 30, 10458),
    (170, 33, 10459),
    (200, 36, 10461),
    (2**31, 57, 10462),
)


def load_catalog():
    doc = json.loads(
        (
            Path(__file__).parent / "quest_interactions" / "ruel_arch_hunts.json"
        ).read_text()
    )
    if doc.get("schema") != "ruel-arch-hunts-v1":
        raise ValueError("Invalid Ruel hunt catalog")
    rows = doc.get("hunts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing Ruel hunts")
    for row in rows:
        if set(row) != {
            "quest_id",
            "objective_id",
            "minimum_level",
            "target_id",
        } or any(type(row[k]) is not int or not 0 < row[k] < 2**31 for k in row):
            raise ValueError("Invalid Ruel hunt")
    if any(
        len({row[key] for row in rows}) != len(rows)
        for key in ("quest_id", "objective_id", "target_id")
    ):
        raise ValueError("Duplicate Ruel hunt identity")
    return rows


def native_choice(level, completed_count):
    if (
        type(level) is not int
        or level < 15
        or type(completed_count) is not int
        or completed_count < 0
    ):
        return None
    for upper, threshold, choice in _BANDS:
        if level < upper:
            return choice if completed_count < threshold else None
    return None


def available(state, hunts, *, level, now_ms):
    """Return (native choice, candidate rows); no mission starts here."""
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid Ruel offer time")
    ids = {h["quest_id"] for h in hunts} | {3984}  # native hidden member
    if PREREQUISITE not in state["completed"] or ids.intersection(state["running"]):
        return None, []
    completed = ids.intersection(state["completed"])
    # Local policy: at most one completed hunt per UTC day.
    if any(
        state.get("completion_dates", {}).get(str(identity), -86400000) // 86400000
        == now_ms // 86400000
        for identity in completed
    ):
        return None, []
    choice = native_choice(level, len(completed))
    if choice is None:
        return None, []
    return choice, [
        h
        for h in hunts
        if h["minimum_level"] <= level and h["quest_id"] not in completed
    ]


def assign(state, hunts, *, character_id, level, offered_choice, now_ms):
    """Assign exactly one eligible hunt after Ruel's authorized choice.

    Target choice is deterministic per owner/day for reproducibility and is
    explicitly a local reconstruction, not the original server algorithm.
    """
    if (
        type(character_id) is not int
        or character_id <= 0
        or type(now_ms) is not int
        or now_ms < 0
    ):
        raise ValueError("Invalid hunt owner or time")
    choice, candidates = available(state, hunts, level=level, now_ms=now_ms)
    if offered_choice != choice or not candidates:
        raise ValueError("Ruel hunt offer is unavailable")
    candidates = sorted(candidates, key=lambda row: row["quest_id"])
    seed = hashlib.sha256(f"{character_id}:{now_ms // 86400000}:ruel".encode()).digest()
    selected = candidates[int.from_bytes(seed[:8], "big") % len(candidates)]
    result = deepcopy(state)
    result["running"] = sorted(set(result["running"]) | {selected["quest_id"]})
    from .mission_progress import auto_track

    auto_track(result, selected["quest_id"])
    return result, selected


def complete(state, hunts, definitions, event, *, character, store, now_ms):
    """Advance only an already assigned hunt for a qualified winning event."""
    from .mission_progress import advance_objective

    active = [h for h in hunts if h["quest_id"] in state["running"]]
    if len(active) > 1:
        raise ValueError("More than one Ruel hunt is active")
    if not active or active[0]["target_id"] not in event.get("original_breeds", ()):
        return deepcopy(state), [], [], []
    hunt = active[0]
    definition = definitions[hunt["quest_id"]]
    after, rewards, objectives, completed = advance_objective(
        state,
        definition,
        hunt["objective_id"],
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if completed:
        key = str(VARIABLE)
        value = after["variables"].get(key, 0)
        if type(value) is not int or not 0 <= value < 2**63 - 1:
            raise ValueError("Invalid Ruel completion counter")
        after["variables"][key] = value + 1
    return after, rewards, objectives, completed


SETTING = "reconstructed_ruel_hunt_v1"


def settle(db, store, character, event):
    """Settle a verified winning event for its owner's assigned hunt.

    Caller owns the fight transaction and must isolate errors in a savepoint.
    No receipt is fabricated and no unassigned hunt can advance.
    """
    from . import rewards, storage, wire
    from .service import _owner, drain_rewards

    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return []
    policy = row["value"]
    if (
        not isinstance(policy, dict)
        or policy.get("enabled") is not True
        or policy.get("schema") != SETTING
    ):
        raise ValueError("Invalid Ruel hunt policy")
    revision = policy.get("revision")
    if not isinstance(revision, str) or len(revision) != 64:
        raise ValueError("Missing pinned Ruel native revision")
    _owner(db, character)
    state = storage.load_locked(db, character["id"])
    hunts = load_catalog()
    active = [h for h in hunts if h["quest_id"] in state["running"]]
    if len(active) > 1:
        raise ValueError("More than one Ruel hunt is active")
    if not active or active[0]["target_id"] not in event.get("original_breeds", ()):
        return []
    hunt = active[0]
    source = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
        (revision, hunt["quest_id"]),
    ).fetchone()
    if source is None:
        raise ValueError("Missing pinned Ruel hunt definition")
    definition = source["data"]["native"]
    if (
        definition.get("d") != hunt["quest_id"]
        or definition.get("cjG") != CATEGORY
        or definition.get("cjP") != hunt["minimum_level"]
        or [o.get("d") for o in definition.get("cjJ", [])] != [hunt["objective_id"]]
    ):
        raise ValueError("Pinned Ruel hunt definition changed")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = complete(
        state,
        hunts,
        {hunt["quest_id"]: definition},
        event,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if not completed:
        return []
    fact = {
        "kind": "assigned_ruel_hunt_v1",
        "fight_id": event["fight_id"],
        "quest_id": hunt["quest_id"],
        "objective_id": hunt["objective_id"],
        "target_id": hunt["target_id"],
        "revision": revision,
    }
    if not storage.record_event(
        db, character["id"], f"ruel-hunt:{hunt['quest_id']}", fact
    ):
        raise ValueError("Ruel hunt receipt exists without completed progress")
    for identity, reward in intents:
        rewards.validate(reward)
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    packets = wire.changes(character["id"], state, after, objectives, completed, now_ms)
    packets.extend(drain_rewards(db, store, character))
    return packets
