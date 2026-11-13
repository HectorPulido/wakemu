"""Automatic combat mission acceptance under explicit reconstructed policy.

An accepted mission must be in the published, reviewed combat binding set. The
same authenticated winning event that first matches its target may then advance
it. No history is backfilled and no mission state is inferred from client text.
"""
from copy import deepcopy

from wakfu_server import dungeon_criteria
from wakfu_server.dungeon_achievement_authority import queries_from_snapshot
from .mission_progress import auto_track


def _matches(rule, event):
    if rule["kind"] == "monster":
        return rule["target_id"] in event.get("original_breeds", ())
    if rule["kind"] == "dungeon":
        return rule["target_id"] == event.get("completed_dungeon_id")
    if rule["kind"] == "boss":
        return rule["target_id"] in event.get("original_breeds", ()) and rule[
            "dungeon_id"
        ] == event.get("completed_dungeon_id")
    return False


def auto_accept(state, event, rules, definitions, *, character, store, now_ms):
    """Accept eligible matched missions once; caller owns transaction and wire.

    This is a Wakemu reconstruction: a qualifying victory is considered an
    implicit acceptance, not a claim about the original game's quest giver.
    Only non-recurring, non-timed definitions are supported here. Native
    prerequisites are evaluated against the original authoritative snapshot.
    """
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid combat mission acceptance time")
    if type(character.get("level")) is not int or character["level"] <= 0:
        raise ValueError("Missing character real level")
    before = deepcopy(state)
    result = deepcopy(state)
    queries = queries_from_snapshot(
        {k: before[k] for k in ("running", "completed", "objectives")}
    )
    started = set()
    for rule in rules:
        if rule.get("acceptance", "on_matching_victory") != "on_matching_victory":
            continue
        if not _matches(rule, event):
            continue
        identity = rule["quest_id"]
        definition = definitions[identity]
        if (
            identity in before["running"]
            or identity in before["completed"]
            or identity in started
            or definition.get("d") != identity
            or definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or definition.get("cjU") != 0
            or definition.get("cjL") != 0
            or type(definition.get("cjP")) is not int
            or character["level"] < definition["cjP"]
        ):
            continue
        # Availability and objective conditions are authoritative; in
        # particular, never evaluate a visibility criterion IsActive(id)
        # as an acceptance requirement. A false/unknown criterion is not met.
        try:
            allowed = dungeon_criteria.evaluate(
                store,
                definition["cjI"],
                character=character,
                queries=queries,
                now_ms=now_ms,
            )
        except (ValueError, NotImplementedError, KeyError):
            continue
        if not allowed:
            continue
        result["running"] = sorted(set(result["running"]) | {identity})
        auto_track(result, identity)
        started.add(identity)
    return result, sorted(started)
