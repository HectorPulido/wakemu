"""Earn native aggregate achievements from owned durable completed quest sets.

The native objective wording supplies the reviewed set relationship. Owning a
journal marker or viewing a dialogue is insufficient: every declared source
quest must already be completed in the character's durable achievement state.
Completion dates remain presentation data, never an extra native earning gate.
Visibility criteria are presentation data; native earning criteria and ordered
rewards remain unchanged and settle through the existing outbox transaction.
"""

from . import native_effective_eligibility

from functools import lru_cache
import json
from pathlib import Path

from . import storage, mission_dependencies
from .earned_achievement_links import plan

SCHEMA = "native-achievement-completed-sets-v1"
PROFILE = Path(__file__).with_name("achievement_set_profiles") / "otomai-hunter.json"


def validate(document):
    if (
        type(document) is not dict
        or set(document) != {"schema", "native_revision", "bindings"}
        or document["schema"] != SCHEMA
        or type(document["native_revision"]) is not str
        or len(document["native_revision"]) != 64
        or any(char not in "0123456789abcdef" for char in document["native_revision"])
        or not isinstance(document["bindings"], list)
        or not document["bindings"]
    ):
        raise ValueError("Invalid native completed-set profile")
    seen = set()
    for row in document["bindings"]:
        if (
            type(row) is not dict
            or set(row)
            != {"achievement_id", "objective_id", "all_completed", "evidence"}
            or any(
                type(row[key]) is not int or not 0 < row[key] < 2**31
                for key in ("achievement_id", "objective_id")
            )
            or not isinstance(row["all_completed"], list)
            or not row["all_completed"]
            or any(
                type(value) is not int or not 0 < value < 2**31
                for value in row["all_completed"]
            )
            or len(set(row["all_completed"])) != len(row["all_completed"])
            or row["achievement_id"] in row["all_completed"]
            or row["achievement_id"] in seen
            or type(row["evidence"]) is not str
            or not row["evidence"].strip()
        ):
            raise ValueError("Invalid native completed-set binding")
        seen.add(row["achievement_id"])
    return document


@lru_cache(maxsize=1)
def profile():
    return validate(json.loads(PROFILE.read_text()))


def _earned(state, identities):
    return set(identities) <= set(state["completed"])


def _eligible(state, definition, objective_id, *, character, store, now_ms):
    """An unsupported earning predicate defers this aggregate, not its source."""
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    objective = next(
        (row for row in definition.get("cjJ", ()) if row.get("d") == objective_id), None
    )
    if objective is None:
        raise ValueError("Completed-set objective differs from native metadata")
    authority = queries_from_state(state)
    try:
        return all(
            dungeon_criteria.evaluate(
                store, criterion, character=character, queries=authority, now_ms=now_ms
            )
            for criterion in (
                native_effective_eligibility.criterion(definition),
                objective["ckc"],
                objective["cke"],
            )
        )
    except (ValueError, NotImplementedError, KeyError):
        return False


def settle(db, store, character, *, completed=None, document=None):
    """Publish aggregate entitlements after a committed source or at selection.

    ``completed`` filters ordinary producer calls before any database work.
    ``None`` reconciles previously earned sets, retaining every existing source
    quest and reward. Unknown or older native metadata revisions stay inert.
    """
    document = profile() if document is None else validate(document)
    sources = {
        identity for row in document["bindings"] for identity in row["all_completed"]
    }
    if completed is not None:
        completed = list(completed)
        if any(type(identity) is not int or identity <= 0 for identity in completed):
            raise ValueError("Invalid completed-set producer identities")
        if not sources.intersection(completed):
            return []
    from .service import _owner

    _owner(db, character)
    state = storage.load_locked(db, character["id"])
    possible = [
        row
        for row in document["bindings"]
        if row["achievement_id"] not in state["completed"]
        and _earned(state, row["all_completed"])
    ]
    if not possible:
        return []
    revision = db.execute(
        "SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
    ).fetchone()
    if revision is None or revision["revision"] != document["native_revision"]:
        return []
    identities = sources | {row["achievement_id"] for row in possible}
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=ANY(%s)",
        (document["native_revision"], sorted(identities)),
    ).fetchall()
    native = {row["definition_id"]: row["data"]["native"] for row in rows}
    if set(native) != identities or any(
        native[identity].get("d") != identity
        or native[identity].get("native_class") != "aJM"
        or native[identity].get("aqb") is not False
        for identity in sources
    ):
        raise ValueError("Completed-set source differs from native quest metadata")
    packets = []
    while True:
        changed = False
        for binding in possible:
            before = storage.load_locked(db, character["id"])
            identity = binding["achievement_id"]
            if identity in before["completed"] or not _earned(
                before, binding["all_completed"]
            ):
                continue
            definition = native[identity]
            now_ms = int(store.now().timestamp() * 1000)
            if not _eligible(
                before,
                definition,
                binding["objective_id"],
                character=character,
                store=store,
                now_ms=now_ms,
            ):
                continue
            planned = plan(
                before,
                definition,
                binding["objective_id"],
                character=character,
                store=store,
                now_ms=now_ms,
            )
            if not planned[2]:
                continue
            result = mission_dependencies.settle(
                db,
                store,
                character,
                before,
                planned,
                {identity: definition},
                (),
                now_ms=now_ms,
                publish_completions=False,
            )
            packets.extend(result["packets"])
            changed = True
        if not changed:
            return packets


def recover(db, store, character):
    return settle(db, store, character)
