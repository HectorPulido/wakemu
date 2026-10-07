"""Encounter-local coordination derived only from published native outcomes."""
from copy import deepcopy

from .corridor_reservations import valid as valid_corridor

HISTORY_LIMIT = 32


def observe(fight):
    return dict(
        actorId=fight.current.id if fight.current is not None else None,
        team=fight.current.team if fight.current is not None else None,
        turnId=fight.turn_id,
        actors={
            identity: dict(
                team=actor.team,
                hp=actor.hp,
                armor=(
                    actor.effect_stats.get(97)
                    if isinstance(getattr(actor, "effect_stats", None), dict)
                    else None
                ),
            )
            for identity, actor in fight.actors.items()
        },
    )


def team_context(fight, instance_id, actor_id):
    actor = fight.actors[actor_id]
    result = dict(
        fightInstanceId=instance_id,
        stateRevision=fight.sequence,
        team=actor.team,
        focusId=None,
        reservedCells=[],
    )
    if getattr(fight, "native_ai_fight_uuid", None) != instance_id:
        return result
    book = getattr(fight, "native_ai_team_context", {}).get(str(actor.team))
    if (
        not isinstance(book, dict)
        or book.get("instanceId") != instance_id
        or type(book.get("sourceRevision")) is not int
        or not 0 <= book["sourceRevision"] <= fight.sequence
        or type(book.get("expiresRound")) is not int
        or book["expiresRound"] < getattr(fight, "native_table_turn", 0)
    ):
        return result
    focus = fight.actors.get(book.get("focusId"))
    if focus is not None and focus.team != actor.team and focus.hp > 0:
        result["focusId"] = focus.id
    corridors = [
        row
        for row in book.get("corridors", [])
        if isinstance(row, dict)
        and row.get("ownerId") != actor_id
        and row.get("instanceId") == instance_id
        and valid_corridor(row, fight, actor.team)
    ]
    result["corridors"] = deepcopy(corridors)
    result["reservedCells"] = [
        list(cell)
        for cell in sorted({tuple(cell) for row in corridors for cell in row["cells"]})
    ]
    return result


def confirm(runtime, before, diagnostics):
    """Called after local sends or shared broadcast/ACK authority succeed."""
    fight = runtime.fight
    instance = getattr(runtime, "tactical_encounter_id", None)
    if not isinstance(instance, str) or not instance or before["team"] is None:
        return
    records = deepcopy(getattr(fight, "native_ai_team_context", {}))
    if getattr(fight, "native_ai_fight_uuid", instance) != instance:
        records = {}
    team = before["team"]
    existing = (
        team_context(fight, instance, before["actorId"])
        if before["actorId"] in fight.actors
        else dict(focusId=None)
    )
    victims, allies = [], []
    for identity, previous in before["actors"].items():
        actor = fight.actors.get(identity)
        if actor is None:
            continue
        damage = previous["hp"] - actor.hp
        armor = (
            actor.effect_stats.get(97)
            if isinstance(getattr(actor, "effect_stats", None), dict)
            else None
        )
        armor_loss = (
            previous["armor"] - armor
            if previous["armor"] is not None and armor is not None
            else None
        )
        if previous["team"] == team:
            if damage < 0 or armor_loss is not None and armor_loss < 0:
                allies.append(
                    dict(
                        actorId=identity,
                        hpGain=-damage,
                        armorGain=-armor_loss if armor_loss is not None else None,
                    )
                )
        elif damage > 0 or armor_loss is not None and armor_loss > 0:
            victims.append((damage, armor_loss, identity))
    survivors = [row for row in victims if fight.actors[row[2]].hp > 0]
    focus = (
        sorted(survivors, key=lambda row: (-row[0], -(row[1] or 0), row[2]))[0][2]
        if survivors
        else existing["focusId"]
    )
    previous = records.get(str(team), {})
    if (
        not isinstance(previous, dict)
        or previous.get("instanceId") != instance
        or type(previous.get("sourceRevision")) is not int
        or not 0 <= previous["sourceRevision"] <= fight.sequence
        or type(previous.get("expiresRound")) is not int
        or previous["expiresRound"] < getattr(fight, "native_table_turn", 0)
    ):
        previous = {}
    history = deepcopy(previous.get("history", []))
    corridors = [
        row
        for row in previous.get("corridors", [])
        if isinstance(row, dict)
        and row.get("instanceId") == instance
        and valid_corridor(row, fight, team)
    ]
    for diagnostic in diagnostics:
        action = diagnostic.get("action") or {}
        if action.get("type") in ("cast", "move"):
            corridors = [
                row for row in corridors if row.get("ownerId") != before["actorId"]
            ]
        proposed = diagnostic.get("coordinationDraft")
        if not isinstance(proposed, dict):
            continue
        row = deepcopy(proposed)
        row["expiresRound"] = getattr(fight, "native_table_turn", 0) + 1
        if (
            row.get("instanceId") == instance
            and row.get("ownerId") == before["actorId"]
            and type(row.get("sourceRevision")) is int
            and 0 <= row["sourceRevision"] <= fight.sequence
            and action.get("type") == "cast"
            and row.get("spellId") == action.get("spellId")
            and row.get("level") == action.get("level")
            and row.get("target") == action.get("target")
            and valid_corridor(row, fight, team)
        ):
            corridors.append(row)
    history.append(
        dict(
            turnActorId=before["actorId"],
            turnId=before["turnId"],
            attribution="published_transition_net_outcome",
            stateRevision=fight.sequence,
            actions=[deepcopy(row.get("action")) for row in diagnostics],
            affectedAllies=allies,
            affectedEnemies=[
                dict(actorId=identity, hpLoss=damage, armorLoss=armor)
                for damage, armor, identity in victims
            ],
        )
    )
    # Coordination memory is a recent window, not the combat event ledger.
    # The complete native ledger/context remains unchanged and transmitted.
    history = history[-HISTORY_LIMIT:]
    records[str(team)] = dict(
        previous,
        instanceId=instance,
        sourceRevision=fight.sequence,
        expiresRound=getattr(fight, "native_table_turn", 0) + 1,
        focusId=focus,
        history=history,
        corridors=corridors,
    )
    fight.native_ai_fight_uuid = instance
    fight.native_ai_team_context = records
