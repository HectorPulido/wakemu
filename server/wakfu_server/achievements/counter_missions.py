"""Counter objectives from native mission definitions.

An event producer must authenticate the gameplay event and map it to a reviewed
native variable id. A variable id found in a definition alone is not that mapping.
This module never starts missions and does not authenticate events itself.
"""
import re
from copy import deepcopy

from .mission_progress import advance_objective

_CONDITION = re.compile(r'GetAchievementVariable\("([^"\\]+)"\)\s*>=\s*(\d+)\Z')


def bindings(definitions):
    """Extract supported one-counter objectives; unsupported forms remain inert."""
    result = {}
    variables = {}
    for definition in definitions:
        if (
            definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
        ):
            continue
        quest_id = definition["d"]
        for objective in definition["cjJ"]:
            conditions = objective.get("ckf") or []
            if len(conditions) != 1:
                continue
            condition = conditions[0]
            match = _CONDITION.fullmatch(condition.get("ckm", "").strip())
            sources = condition.get("ckn")
            if (
                match is None
                or not isinstance(sources, list)
                or len(sources) != 1
                or type(sources[0]) is not int
                or sources[0] <= 0
            ):
                continue
            variable = sources[0]
            threshold = int(match[2])
            if threshold <= 0 or threshold >= 2**63:
                continue
            key = (variable, match[1])
            if variable in variables and variables[variable] != key:
                raise ValueError("Conflicting native counter identity")
            variables[variable] = key
            for source in set(sources):
                result.setdefault(source, []).append(
                    (quest_id, objective["d"], variable, threshold)
                )
    return result


def advance(state, definitions, source, *, character, store, now_ms):
    """Plan one already-qualified gameplay event and native counter changes.

    The caller must deduplicate a durable event receipt in the same transaction
    and persist/send the returned state through the shared mission settlement.
    Only active quests contribute; a duplicate source/objective is rejected.
    """
    if type(source) is not int or source <= 0:
        raise ValueError("Invalid native counter variable")
    by_id = {definition["d"]: definition for definition in definitions}
    if len(by_id) != len(definitions):
        raise ValueError("Duplicate native mission definitions")
    matches = [
        row
        for row in bindings(definitions).get(source, ())
        if row[0] in state["running"] and row[1] not in state["objectives"]
    ]
    if len({(row[0], row[1]) for row in matches}) != len(matches):
        raise ValueError("Duplicate native counter objective")
    candidate = deepcopy(state)
    for variable in {row[2] for row in matches}:
        key = str(variable)
        count = candidate["variables"].get(key, 0)
        if type(count) is not int or count < 0 or count >= 2**63 - 1:
            raise ValueError("Invalid native counter value")
        candidate["variables"][key] = count + 1
    intents, objectives, completed = [], [], []
    for quest_id, objective_id, variable, threshold in matches:
        if candidate["variables"][str(variable)] < threshold:
            continue
        from wakfu_server import dungeon_criteria
        from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

        definition = by_id[quest_id]
        objective = next(row for row in definition["cjJ"] if row["d"] == objective_id)
        queries = queries_from_snapshot(
            {key: candidate[key] for key in ("running", "completed", "objectives")}
        )
        try:
            eligible = all(
                dungeon_criteria.evaluate(
                    store,
                    criterion,
                    character=character,
                    queries=queries,
                    now_ms=now_ms,
                )
                for criterion in (definition["cjI"], objective["ckc"], objective["cke"])
            )
        except (ValueError, NotImplementedError, KeyError):
            continue
        if not eligible:
            continue
        candidate, new_intents, new_objectives, new_completed = advance_objective(
            candidate,
            definition,
            objective_id,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        intents.extend(new_intents)
        objectives.extend(new_objectives)
        completed.extend(new_completed)
    return candidate, intents, objectives, completed


# Client item localization and native objective conditions identify these joins.
# One count per successful operation is a reconstruction, not a server capture.
_RII_EVENTS = {
    ("monster_harvest", 30927): (5145, 10597, 756, 3),
    ("resource_harvest", 31007): (5155, 10598, 759, 3),
    ("resource_harvest", 31006): (5155, 10599, 758, 3),
    ("planting", 30927): (5145, 10578, 757, 2),
    ("planting", 31007): (5155, 10600, 760, 3),
}


def settle_rii_event(db, store, character, *, token, kind, item_reference):
    """Settle an authenticated successful Rii ecosystem event transactionally.

    The producer is responsible for authenticating, deduplicating and committing
    the actual harvest or successful planting in this very transaction.
    """
    binding = _RII_EVENTS.get((kind, item_reference))
    if character.get("map_id") != 1385 or binding is None:
        return []
    if not isinstance(token, str) or not token:
        raise ValueError("Missing committed ecosystem event identity")
    from hashlib import sha256
    from . import storage, wire

    # The producer already authenticated the session and locked its character.
    # Taking the account lock here would invert its character-first lock order.
    before = storage.load_locked(db, character["id"])
    quest_id, objective_id, variable_id, threshold = binding
    if quest_id not in before["running"] or objective_id in before["objectives"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (quest_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing ecosystem quest definition")
    definition = row["data"]["native"]
    if binding not in bindings([definition]).get(variable_id, ()):
        raise ValueError("Ecosystem counter differs from native definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = advance(
        before,
        [definition],
        variable_id,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if intents or completed:
        raise ValueError("Unexpected ecosystem event quest completion")
    receipt = f"rii-ecosystem:{kind}:" + sha256(token.encode()).hexdigest()
    if not storage.record_event(
        db,
        character["id"],
        receipt,
        {"kind": kind, "item": item_reference, "variable": variable_id},
    ):
        raise ValueError("Duplicate ecosystem mission receipt")
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"],
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions={quest_id: definition},
    )


def settle_wodent_harvest(db, store, character, *, token, item_reference):
    """Compatibility wrapper for monster harvest producer."""
    return settle_rii_event(
        db,
        store,
        character,
        token=token,
        kind="monster_harvest",
        item_reference=item_reference,
    )
