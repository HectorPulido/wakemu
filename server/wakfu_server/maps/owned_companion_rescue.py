"""Optional native companion rescue, separate from the main story's once steps.

The caller retains the ordinary owned action transaction and position barrier.
Completion grants the original token through quest settlement; learning it and
company equipment remain exclusively the normal native companion item action.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server.achievements import storage, mission_dependencies, mission_progress

ROOT = Path(__file__).with_name("owned_companion_rescues")


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=8)
def _load(path, digest):
    if Path(path).name != path or not path.endswith(".json"):
        raise ValueError("Companion rescue source escapes its reviewed directory")
    raw = (ROOT / path).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Companion rescue source attestation changed")
    value = json.loads(raw)
    required = (
        "map_id",
        "source_id",
        "descriptor_id",
        "admission_quest_id",
        "victory_quest_id",
        "preferred_quest_id",
        "token_item_id",
        "activation_action_id",
        "companion_reference",
    )
    variants = value.get("variants", [])
    if (
        value.get("schema") != "owned-companion-rescue-v1"
        or any(type(value.get(key)) is not int or value[key] <= 0 for key in required)
        or value.get("action_id") != 0
        or not isinstance(value.get("criterion"), str)
        or len(value.get("position", [])) != 3
        or not variants
        or any(
            set(row) != {"quest_id", "objective_id", "native_sha256"}
            or type(row["quest_id"]) is not int
            or type(row["objective_id"]) is not int
            for row in variants
        )
        or len({row["quest_id"] for row in variants}) != len(variants)
        or value["preferred_quest_id"] not in {row["quest_id"] for row in variants}
        or not value.get("provenance")
    ):
        raise ValueError("Invalid native companion rescue policy")
    return value


@lru_cache(maxsize=1)
def _compatibility():
    value = json.loads((ROOT / "compatible_controllers.json").read_text())
    if (
        value.get("schema") != "owned-companion-rescue-compatibility-v1"
        or type(value.get("controllers")) is not dict
        or not value.get("provenance")
        or any(
            len(key) != 64 or any(c not in "0123456789abcdef" for c in key)
            for key in value["controllers"]
        )
    ):
        raise ValueError("Invalid reviewed optional companion compatibility index")
    return value["controllers"]


def policy(selected):
    pin = selected.get("optional_companion")
    if pin is None:
        # Explicit compatibility attaches only this optional adapter to the
        # identical immutable old controller, never a map-wide policy override.
        pin = _compatibility().get(_digest(selected))
    if pin is None:
        return None
    if (
        type(pin) is not dict
        or set(pin) != {"path", "sha256"}
        or type(pin["path"]) is not str
        or type(pin["sha256"]) is not str
        or len(pin["sha256"]) != 64
        or any(value not in "0123456789abcdef" for value in pin["sha256"])
    ):
        raise ValueError("Malformed native companion rescue source pin")
    result = _load(pin["path"], pin["sha256"])
    if result["map_id"] != selected["map_id"]:
        raise ValueError("Companion rescue belongs to another native map")
    return result


def can_reenter(selected, state):
    """A missed optional rescue can reuse its genuinely paid completed run."""
    declared = policy(selected)
    if declared is None:
        return False
    completed = set(state["completed"])
    return {
        declared["admission_quest_id"],
        declared["victory_quest_id"],
    } <= completed and not {row["quest_id"] for row in declared["variants"]} & completed


def _context(db, store, character, selected, declared):
    actual, _ = controller._scope(db, store, character)
    if actual != selected or character["map_id"] != declared["map_id"]:
        raise ValueError("Companion rescue lacks its exact owned story scope")
    native = mechanics.sources(selected)
    program = native["programs"].get(str(declared["source_id"]), {})
    objects = [row for row in native["objects"] if row["id"] == declared["source_id"]]
    if (
        program.get("descriptor_id") != declared["descriptor_id"]
        or len(objects) != 1
        or [objects[0][key] for key in ("x", "y", "z")] != declared["position"]
    ):
        raise ValueError("Companion rescue lacks its original cage descriptor")
    return mechanics.allowed(db, store, character, declared["criterion"])


def _definition(db, variant, declared):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) AND definition_id=%s",
        (variant["quest_id"],),
    ).fetchone()
    if row is None or _digest(row["data"]["native"]) != variant["native_sha256"]:
        raise ValueError("Native companion quest definition changed")
    definition = row["data"]["native"]
    if [item["d"] for item in definition["cjJ"]] != [
        variant["objective_id"]
    ] or not any(
        reward["aeV"] == 5 and reward["ckl"] == [declared["token_item_id"], 1]
        for reward in definition["cjK"]
    ):
        raise ValueError("Native rescue objective or token reward changed")
    return definition


def _variant(declared, state):
    family = {row["quest_id"] for row in declared["variants"]}
    if family & set(state["completed"]):
        return None
    running = [
        row for row in declared["variants"] if row["quest_id"] in state["running"]
    ]
    if len(running) > 1:
        # Never reward both mutually exclusive versions of one rescued actor.
        return None
    return running[0] if running else None


def admit(db, store, character, selected):
    """Admit one reviewed variant after actual native temple entry, once."""
    declared = policy(selected)
    if declared is None or not _context(db, store, character, selected, declared):
        return []
    before = storage.load_locked(db, character["id"])
    family = {row["quest_id"] for row in declared["variants"]}
    if family & (set(before["running"]) | set(before["completed"])):
        return []
    if declared["admission_quest_id"] not in before["completed"] or declared[
        "victory_quest_id"
    ] not in set(before["running"]) | set(before["completed"]):
        # Physical access is independent of optional quest admission.
        return []
    variant = next(
        row
        for row in declared["variants"]
        if row["quest_id"] == declared["preferred_quest_id"]
    )
    definition = _definition(db, variant, declared)
    from wakfu_server.achievements import native_effective_eligibility

    if not mechanics.allowed(
        db, store, character, native_effective_eligibility.criterion(definition)
    ):
        return []
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {variant["quest_id"]})
    mission_progress.seed_counters(after, definition)
    mission_progress.auto_track(after, variant["quest_id"])
    if not storage.record_event(
        db,
        character["id"],
        f'owned-companion-admission:{variant["quest_id"]}',
        dict(
            schema=declared["schema"],
            quest_id=variant["quest_id"],
            instance_id=character["instance_id"],
            source_id=declared["source_id"],
        ),
    ):
        raise ValueError(
            "Companion admission receipt conflicts with missing quest state"
        )
    result = mission_dependencies.settle(
        db,
        store,
        character,
        before,
        (after, [], [], []),
        {variant["quest_id"]: definition},
        (),
        now_ms=int(store.now().timestamp() * 1000),
    )
    return list(result["packets"])


def interact(db, store, character, selected, source_id, action_id):
    """Settle a physically opened cage after victory, even on a later visit."""
    declared = policy(selected)
    if declared is None or source_id != declared["source_id"]:
        return []
    if action_id != declared["action_id"]:
        raise ValueError("Invalid native companion rescue action")
    if not _context(db, store, character, selected, declared):
        return []
    x, y, z = declared["position"]
    if (
        abs(character["z"] - z) > 1
        or abs(character["x"] - x) + abs(character["y"] - y) > 1
    ):
        raise ValueError("Companion rescue cage is outside interaction range")
    mechanics.authorize_action(db, store, character, selected, source_id, action_id)
    before = storage.load_locked(db, character["id"])
    variant = _variant(declared, before)
    if variant is None or declared["victory_quest_id"] not in before["completed"]:
        return []
    _definition(db, variant, declared)
    from wakfu_server.achievements.owned_quest_encounters import _advance

    return _advance(
        db,
        store,
        character,
        dict(quest_id=variant["quest_id"]),
        variant["objective_id"],
        f'owned-companion-rescue:{variant["quest_id"]}',
        dict(
            source_id=source_id,
            instance_id=character["instance_id"],
            descriptor_id=declared["descriptor_id"],
        ),
    )
