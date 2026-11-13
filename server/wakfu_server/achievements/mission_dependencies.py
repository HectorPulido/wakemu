"""Propagate explicitly reviewed child-quest completions to parent objectives.

The native client does not encode these edges in the objective prerequisites;
the links must therefore be published from independent evidence.  Call this
inside the transaction that records a qualified objective or quest completion.
"""
from copy import deepcopy

from .mission_progress import advance_objective


# Rii's localized objective names match the respective native quest names.
# These are reconstructed links, not recovered original server scripts.
RII_LINKS = (
    (5160, 10616, 5143),
    (5160, 10617, 5145),
    (5160, 10618, 5155),
    (5160, 10619, 5156),
    (5160, 10622, 5146),
)


def reconcile(state, definitions, links, *, character, store, now_ms):
    """Return state, reward intents, new objectives and completed parents.

    A child already completed before its parent's prerequisite is also applied
    when this function is called after that prerequisite changes. No parent is
    activated, and unrelated parents or incomplete children are untouched.
    """
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

    links = tuple(links)
    targets = set()
    for link in links:
        if (
            not isinstance(link, tuple)
            or len(link) != 3
            or any(type(value) is not int or value <= 0 for value in link)
        ):
            raise ValueError("Invalid mission dependency")
        parent, objective_id, child = link
        if parent == child or (parent, objective_id) in targets:
            raise ValueError("Conflicting mission dependency")
        targets.add((parent, objective_id))
        definition = definitions.get(parent)
        child_definition = definitions.get(child)
        if (
            not isinstance(definition, dict)
            or definition.get("d") != parent
            or definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or not isinstance(child_definition, dict)
            or child_definition.get("d") != child
            or child_definition.get("native_class") != "aJM"
            or not isinstance(definition.get("cjJ"), list)
            or sum(row.get("d") == objective_id for row in definition["cjJ"]) != 1
        ):
            raise ValueError("Mission dependency differs from native definitions")
        objective = next(row for row in definition["cjJ"] if row["d"] == objective_id)
        if objective.get("ckf"):
            raise ValueError("Mission dependency has unsupported native counters")

    current = deepcopy(state)
    all_intents, all_objectives, all_completed = [], [], []
    while True:
        changed = False
        for parent, objective_id, child in links:
            if (
                parent not in current["running"]
                or child not in current["completed"]
                or objective_id in current["objectives"]
            ):
                continue
            definition = definitions[parent]
            objective = next(
                row for row in definition["cjJ"] if row["d"] == objective_id
            )
            queries = queries_from_snapshot(
                {key: current[key] for key in ("running", "completed", "objectives")}
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
                    for criterion in (
                        definition["cjI"],
                        objective["ckc"],
                        objective["cke"],
                    )
                )
            except (ValueError, NotImplementedError, KeyError):
                # Unknown native conditions cannot block the source event.
                continue
            if not eligible:
                continue
            current, intents, added, completed = advance_objective(
                current,
                definition,
                objective_id,
                character=character,
                store=store,
                now_ms=now_ms,
            )
            all_intents.extend(intents)
            all_objectives.extend(added)
            all_completed.extend(completed)
            changed = changed or bool(added)
        if not changed:
            return current, all_intents, all_objectives, all_completed


def settle(db, store, character, before, planned, definitions, links, *, now_ms):
    """Commit a qualified producer's plan together with dependent objectives.

    ``planned`` is the four-tuple returned by a producer that already checked
    its own owner, event receipt, inventory and native conditions. The caller
    owns that transaction and must not publish a separate progress packet for
    the same plan. Nothing in this API authorizes an event or activates a quest.
    """
    from . import rewards, storage, wire
    from .service import _owner, drain_rewards

    _owner(db, character)
    if not isinstance(planned, tuple) or len(planned) != 4:
        raise ValueError("Invalid mission settlement plan")
    after, intents, objectives, completed = planned
    after, extra_intents, extra_objectives, extra_completed = reconcile(
        after, definitions, links, character=character, store=store, now_ms=now_ms
    )
    intents = list(intents) + extra_intents
    objectives = list(objectives) + extra_objectives
    completed = list(completed) + extra_completed
    for identity, reward in intents:
        rewards.validate(reward)
        if not storage.claim_reward(
            db, character["id"], identity, "once", reward["d"], reward
        ):
            raise ValueError("Mission reward already claimed before completion")
    storage.store(db, character["id"], after)
    packets = wire.changes(
        character["id"],
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions=definitions,
    )
    packets.extend(drain_rewards(db, store, character))
    return {
        "state": after,
        "packets": packets,
        "new_objectives": objectives,
        "completed": completed,
    }
