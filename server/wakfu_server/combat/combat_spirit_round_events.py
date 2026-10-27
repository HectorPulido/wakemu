"""Reviewed Spirit-only completed-round publisher; not an original server claim.

Guide175/478 requires thirteen completed rounds. Original player carrier9145
owns native root410946, whose body still chooses its success/failure branch.
Other1004 publishers, equipment clocks and the actual SU table remain unchanged.
"""
from collections.abc import Mapping
import hashlib
import json

POLICY = "wakemu-spirit-completed-round-clock-v1"
OBJECTIVE = "wakemu-spirit-thirteen-rounds-v1"
SCENE = "wakemu-spirit-scenario2710-v1"
CARRIER = 9145
ROOT = 410946


def has_round_interest(fight):
    """Cheap queue interest; full custody is independently checked at delivery."""
    frozen = getattr(fight, "native_encounter_objective_policy", None)
    scene = getattr(fight, "native_spirit_scene_admission", None)
    return (
        isinstance(frozen, Mapping)
        and frozen.get("policy") == OBJECTIVE
        and isinstance(scene, Mapping)
        and scene.get("status") == "granted"
    )


def _digest(source):
    return hashlib.sha256(
        json.dumps(
            source, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def prepare_scope(dispatcher):
    """Bind remaining original Ready carriers and their shared result leader."""
    fight = dispatcher.native_retention.fight
    frozen = getattr(fight, "native_encounter_objective_policy", None)
    if not isinstance(frozen, Mapping) or frozen.get("policy") != OBJECTIVE:
        return None
    from .combat_encounter_objective_policy import require_admitted_policy
    from .combat_encounter_objective import _score_scope, _admission
    from .combat_encounter_objective_spirit import (
        spirit_admission,
        spirit_result_player,
    )

    policy = require_admitted_policy(frozen)
    if (
        policy.reference != 5848
        or policy.native_player_state != CARRIER
        or policy.scene_contract_policy != SCENE
        or not policy.observe_native_producer
        or policy.boundary != "completed_round"
    ):
        raise ValueError("Spirit round publisher lost its exact frozen objective")
    profile, _ = _score_scope(fight, policy)
    _, admission_digest, _ = _admission(fight, policy)
    original = getattr(fight, "native_encounter_objective_player_id", None)
    scene = spirit_admission(fight)
    source = scene.get("source") if isinstance(scene, Mapping) else None
    ready = scene.get("ready_participants") if isinstance(scene, Mapping) else None
    ready_source = ready.get("source") if isinstance(ready, Mapping) else None
    if (
        not isinstance(source, Mapping)
        or scene.get("status") not in ("granted", "cleaned")
        or scene.get("source_digest") != _digest(source)
        or source.get("policy") != SCENE
        or source.get("scenario_id") != 2710
        or source.get("guide_id") != 175
        or source.get("fight_id") != fight.id
        or source.get("map_id") != policy.map_id
        or source.get("admission_digest") != admission_digest
        or source.get("participant_id") != original
        or not isinstance(ready_source, Mapping)
        or ready.get("source_digest") != _digest(ready_source)
        or ready_source.get("authority")
        != "existing_ready_refreshed_owned_participant_provider"
        or ready_source.get("fight_id") != fight.id
        or ready_source.get("admission_digest") != admission_digest
    ):
        raise ValueError(
            "Spirit round publisher lacks its actual scene and Ready admission"
        )
    players = ready_source.get("players", ())
    if (
        not isinstance(players, (tuple, list))
        or any(
            not isinstance(row, Mapping)
            or type(row.get("actor_id")) is not int
            or type(row.get("account_id")) is not int
            for row in players
        )
        or len({row["actor_id"] for row in players}) != len(players)
        or sorted(row["actor_id"] for row in players) != sorted(profile["player_ids"])
    ):
        raise ValueError(
            "Spirit clock participant scope differs from its original Ready humans"
        )
    if scene["status"] == "cleaned":
        if scene.get("carrier_uids"):
            raise ValueError("Cleaned Spirit scene still claims source carriers")
        return None
    entries = tuple(dispatcher.native_retention.view().entries)
    bindings = []
    for participant in players:
        identity = participant["actor_id"]
        player = fight.actors.get(identity)
        if (
            player is None
            or player.controlled is not True
            or player.owner_id != participant["account_id"]
            or getattr(player, "pve_withdrawn", False)
            or not fight._in_play(player)
        ):
            continue
        carriers = [
            entry for entry in player.state_ledger.entries if entry.reference == CARRIER
        ]
        if not carriers:
            continue  # Actual partial cleanup can precede the off-play update.
        if (
            len(carriers) != 1
            or carriers[0].caster_id != identity
            or carriers[0].target_id != identity
            or scene.get("carrier_uids", {}).get(str(identity)) != carriers[0].uid
        ):
            raise ValueError(
                "Spirit round publisher lacks its exact original player carrier"
            )
        roots = [
            entry
            for entry in entries
            if entry.generic_effect == ROOT
            and entry.owner_uid == carriers[0].uid
            and entry.manager_id == identity
        ]
        if len(roots) != 1:
            raise ValueError(
                "Spirit round publisher requires one actual native root410946"
            )
        bindings.append(
            dict(player_id=identity, carrier_uid=carriers[0].uid, root_uid=roots[0].uid)
        )
    leader = spirit_result_player(fight)
    if leader is None:
        return None
    selected = next(
        (binding for binding in bindings if binding["player_id"] == leader.id), None
    )
    if selected is None:
        raise ValueError(
            "Spirit clock leader lacks an original remaining Ready carrier"
        )
    definition = dispatcher.effects.get(str(ROOT))
    masks = (
        definition.get("target_masks", ()) if isinstance(definition, Mapping) else ()
    )
    if len(masks) != 7 or 1004 not in (masks[5] or ()):
        raise ValueError(
            "Spirit round listener lost its original native1004 subscription"
        )
    owned = {binding["root_uid"] for binding in bindings}
    records = {}
    for name in (
        "native_owned_group_effects",
        "owned_stat_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
    ):
        records.update(getattr(fight, name, {}))
    while True:
        before = len(owned)
        for entry in entries:
            record = records.get(entry.uid, {})
            invocation = record.get("invocation", {})
            if entry.owner_uid in owned or invocation.get("base_uid") in owned:
                owned.add(entry.uid)
        if len(owned) == before:
            break
    return dict(
        **selected,
        sources=tuple(bindings),
        eligible_uids=frozenset(owned),
        source_digest=scene["source_digest"],
        ready_digest=ready["source_digest"]
    )


def deliver_completed_round(dispatcher, receipt, recipients, scope):
    """Replay the exact native listener once with its completed receipt clock."""
    if scope is None:
        return ()
    from .combat_equipment_external_events import ROUND_POLICY
    from .combat_event_replay import NativeExternalEvent

    fight = dispatcher.native_retention.fight
    completed = receipt.get("completed_round")
    if (
        receipt.get("policy") != ROUND_POLICY
        or type(completed) is not int
        or completed != fight.native_timeline_round - 1
        or receipt.get("ending_turn") != fight.turn_id - 1
        or receipt.get("ending_actor") not in fight.actors
        or receipt.get("delivered") is not True
    ):
        raise ValueError("Spirit clock lacks the actual completed SU receipt")
    live = {entry.uid for entry in dispatcher.native_retention.view().entries}
    if not any(binding["root_uid"] in live for binding in scope["sources"]):
        return ()
    # Ordinary callbacks can retire a leader. Rebind only to an actual
    # remaining subset; a newly manufactured source cannot join this boundary.
    current = prepare_scope(dispatcher)
    if current is None:
        return ()
    original_sources = {tuple(sorted(binding.items())) for binding in scope["sources"]}
    current_sources = {tuple(sorted(binding.items())) for binding in current["sources"]}
    if (
        current["source_digest"] != scope["source_digest"]
        or current["ready_digest"] != scope["ready_digest"]
        or not current_sources <= original_sources
    ):
        raise ValueError("Spirit round source changed during ordinary callbacks")
    scope = current
    key = str(completed)
    journal = getattr(fight, "native_spirit_completed_round_events", {})
    record = dict(
        policy=POLICY,
        completed_round=completed,
        ending_turn=receipt["ending_turn"],
        ending_actor=receipt["ending_actor"],
        player_id=scope["player_id"],
        carrier_uid=scope["carrier_uid"],
        root_uid=scope["root_uid"],
        source_digest=scope["source_digest"],
        ready_digest=scope["ready_digest"],
        sources=[dict(binding) for binding in scope["sources"]],
    )
    previous = journal.get(key)
    if previous is not None:
        if previous != record:
            raise ValueError("Spirit completed-round source receipt changed")
        return ()
    # The caller owns this transaction preview. A rejected native callback
    # discards this journal and its outbox; the mark also blocks recursion.
    original_clock = fight.native_table_turn
    if type(original_clock) is not int or original_clock != fight.native_timeline_round:
        raise ValueError("Spirit completed boundary lacks its actual next SU table")
    from .combat_encounter_objective import deliver_objective_score_marker

    # Ordinary callbacks may retire the prior marker owner or finish earning
    # the quota. The original paid boundary and remaining Ready carrier are
    # revalidated by the shared director before the native listener runs.
    deliver_objective_score_marker(
        dispatcher,
        actor_id=fight.current.id,
        allow_delivered_round=True,
    )
    fight.native_spirit_completed_round_events = {**journal, key: record}
    outcomes = []
    try:
        fight.native_table_turn = completed
        for identity, channel in recipients:
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(identity, (1004,), channel),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=scope["eligible_uids"],
                )
            )
    finally:
        fight.native_table_turn = original_clock
    return tuple(outcomes)
