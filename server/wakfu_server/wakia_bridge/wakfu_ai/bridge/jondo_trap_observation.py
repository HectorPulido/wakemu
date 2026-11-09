"""Capture native area movement results on an already isolated fight.

These observations are partial: they do not assert that other native effects
are absent, or that an actor will choose this movement in a real turn.
"""
from copy import deepcopy
import random
import importlib
import sys
import time
from types import SimpleNamespace


def _resources(fight):
    actors = fight.actors
    if len(actors) > 32:
        raise ValueError("Too many actors for a trap observation")
    result = {}
    for identity, actor in actors.items():
        if actor.hp <= 0:
            continue
        if type(identity) is not int or actor.id != identity:
            raise ValueError("Unknown actor identity")
        result[identity] = {
            "hp": actor.hp,
            "armor": actor.effect_stats.get(97, 0),
            "ap": actor.ap,
            "mp": actor.mp,
            "maxAp": actor.max_ap,
            "maxMp": actor.max_mp,
        }
        if any(type(value) is not int for value in result[identity].values()):
            raise ValueError("Unknown native resources")
    return result


def detached_oracle(oracle):
    """Create private native authorities before submitting forecast work.

    Deepcopy is synchronous and has no strict time bound. Call only after a
    bounded queue slot has been reserved and a relevant trap candidate found.
    Unsupported callbacks, Rift fights and large rosters fail closed.
    """
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
    from wakfu_server.combat_retained_gc_authority import capture_native_callbacks

    kind = type(oracle)
    module = sys.modules.get(kind.__module__)
    if (
        kind.__name__ != "NativeOracle"
        or not kind.__module__.endswith(".native.native_oracle")
        or module is None
        or getattr(module, "_GC_ORACLE_TYPE", None) is not kind
    ):
        raise ValueError("Unsupported native oracle authority")
    package = kind.__module__.removesuffix(".native.native_oracle")
    bind_private_sources = importlib.import_module(
        package + ".bridge.world_sources"
    ).bind_private_sources

    runtime = oracle.runtime
    fight = runtime.fight
    provider = getattr(runtime, "expiration_runtime_factory", None)
    if (
        type(provider) is not OwnedExpirationFactory
        or getattr(runtime, "clock", None) is not time.monotonic
        or getattr(fight, "rift_wave_state", None) is not None
        or len(fight.actors) > 8
        or len(fight.walkable) > 8192
        or getattr(runtime, "awaiting_ack", None) is not None
        or getattr(runtime, "pending", None)
        or oracle.outcome_features_provider is not None
        or capture_native_callbacks(runtime) is None
    ):
        raise ValueError("Unsupported native trap preview source")
    viewer = provider.characters.get(oracle.viewer_id)
    if not isinstance(viewer, dict) or "account_id" not in viewer:
        raise ValueError("Missing native trap preview viewer")
    private = deepcopy(runtime)
    bind_private_sources(
        private,
        SimpleNamespace(character_id=oracle.viewer_id, account_id=viewer["account_id"]),
    )
    if (
        private is runtime
        or private.fight is fight
        or private.expiration_runtime_factory is provider
    ):
        raise ValueError("Native trap preview source remained shared")
    result = kind(
        private,
        characters=oracle.characters,
        monsters=oracle.monsters,
        decks=oracle.decks,
        excluded_decks=oracle.excluded_decks,
        viewer_id=oracle.viewer_id,
        flags=oracle.flags,
    )
    return result


def capture_area_movement(dispatcher, actor_id, from_cell, to_cell):
    """Run the existing area callback and capture its direct resource changes.

    Call exclusively with a dispatcher and fight detached from the live World.
    A caller must separately establish source identity, target visibility,
    ownership, path legality and whether unrepresented effects are acceptable.
    """
    fight = dispatcher.native_area_events.fight
    before = _resources(fight)
    if actor_id not in before:
        raise ValueError("Movement actor is not a living registered actor")
    stat_before = deepcopy(fight.owned_stat_effects)
    retained_before = deepcopy(fight.native_retained_records)
    area_effects_before = deepcopy(getattr(fight, "native_owned_area_effects", {}))
    positions_before = {
        identity: getattr(fight.actors[identity], "position", None)
        for identity in before
    }
    round_before = getattr(fight, "native_timeline_round", None)
    states_before = {
        identity: deepcopy(
            getattr(
                getattr(fight.actors[identity], "state_ledger", None), "entries", None
            )
        )
        for identity in before
    }
    outcome = dispatcher.native_area_events.movement(
        actor_id, from_cell=tuple(from_cell), to_cell=tuple(to_cell)
    )
    after = _resources(fight)
    if before.keys() != after.keys():
        raise ValueError("Area callback changed the living actor roster")
    delta = []
    for identity in before:
        changes = {
            name: after[identity][name] - value
            for name, value in before[identity].items()
        }
        if any(changes.values()):
            delta.append(dict(actorId=identity, **changes))
    changed_stats = {
        uid: deepcopy(entry)
        for uid, entry in fight.owned_stat_effects.items()
        if uid not in stat_before or stat_before[uid] != entry
    }
    removed_stats = [uid for uid in stat_before if uid not in fight.owned_stat_effects]
    moved = [
        identity
        for identity, position in positions_before.items()
        if getattr(fight.actors[identity], "position", None) != position
    ]
    changed_states = [
        identity
        for identity, entries in states_before.items()
        if getattr(
            getattr(fight.actors[identity], "state_ledger", None), "entries", None
        )
        != entries
    ]
    return {
        "complete": False,
        "certainty": "one_native_counterfactual_route",
        "outcome": outcome,
        "deltas": delta,
        "changedStatEffects": changed_stats,
        "removedStatEffects": removed_stats,
        "movedActorIds": moved,
        "changedStateActorIds": changed_states,
        "timelineRoundBefore": round_before,
        "timelineRoundAfter": getattr(fight, "native_timeline_round", None),
        "newRetainedIds": sorted(
            set(fight.native_retained_records) - set(retained_before)
        ),
        "removedRetainedIds": sorted(
            set(retained_before) - set(fight.native_retained_records)
        ),
        "changedRetainedIds": sorted(
            uid
            for uid in retained_before
            if uid in fight.native_retained_records
            and retained_before[uid] != fight.native_retained_records[uid]
        ),
        "removedRetainedRecords": {
            uid: retained_before[uid]
            for uid in retained_before
            if uid not in fight.native_retained_records
        },
        "removedAreaEffects": {
            uid: area_effects_before[uid]
            for uid in area_effects_before
            if uid not in getattr(fight, "native_owned_area_effects", {})
        },
    }


def compare_area_movement(
    oracle, fight, area_uid, actor_id, from_cell, to_cell, *, action_id, rng_state
):
    """Compare two private callback branches with identical initial RNG state.

    The control masks only the named area using the native forecast scope.
    This is an observation, not evidence that the proposed movement is legal,
    that all future harms are known, or that the source fight is still current.
    """
    from wakfu_server.combat_observation_scope import unobserved_area_forecast

    if type(area_uid) is not int or area_uid not in fight.native_effect_areas:
        raise ValueError("Missing observed native area")
    branches = []
    for masked in (False, True):
        private = deepcopy(fight)
        rng = random.Random()
        rng.setstate(rng_state)
        factory, _ = oracle.factory(private, action_id, rng)
        dispatcher, _ = factory(
            private, {"native_retained_container": {"present": False}}
        )
        if masked:
            with unobserved_area_forecast((area_uid,)):
                value = capture_area_movement(dispatcher, actor_id, from_cell, to_cell)
        else:
            value = capture_area_movement(dispatcher, actor_id, from_cell, to_cell)
        branches.append(value)
    observed, control = branches
    fields = ("hp", "armor", "ap", "mp", "maxAp", "maxMp")
    left = {item["actorId"]: item for item in observed["deltas"]}
    right = {item["actorId"]: item for item in control["deltas"]}
    deltas = []
    for identity in sorted(left.keys() | right.keys()):
        changes = {
            name: left.get(identity, {}).get(name, 0)
            - right.get(identity, {}).get(name, 0)
            for name in fields
        }
        if any(changes.values()):
            deltas.append(dict(actorId=identity, **changes))
    return dict(
        complete=False,
        certainty="one_native_counterfactual_route",
        deltas=deltas,
        observed=observed,
        control=control,
    )
