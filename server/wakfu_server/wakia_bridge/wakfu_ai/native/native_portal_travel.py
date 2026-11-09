"""Explicit native gate travel; ordinary walking never gains synthetic edges."""
import random

from .native_control import effective_input_owner, effective_server_controlled
from .native_deadline import check
from .native_stats import NativeStats


def _visible_gates(oracle, runtime):
    from wakfu_server.combat_effect_area_queries import _rows
    from wakfu_server.combat_observation_scope import area_is_unobserved

    provider = getattr(oracle, "unobserved_areas", None)
    hidden = provider(runtime) if callable(provider) else frozenset()
    return tuple(
        row
        for row in _rows(runtime.fight)
        if row.get("native_type_id") == 19
        and row["uid"] not in hidden
        and not area_is_unobserved(row["uid"])
    )


def portal_destinations(oracle, runtime, actor_id, *, source_state):
    """Enumerate current portal endpoints as hints, never authorize travel."""
    from wakfu_server.combat_effect_area_queries import _rows
    from wakfu_server.combat_effect_area_geometry import contains_area_cell
    from wakfu_server.combat_portal_travel import portal_network_pair

    fight = runtime.fight
    result = dict(
        schema="native-portal-travel-v1",
        sourceState=source_state,
        stateRevision=fight.sequence,
        actorId=actor_id,
        destinations=[],
    )
    actor = fight.current
    if actor is None or actor.id != actor_id or actor.mp < 1:
        return result
    raw = getattr(fight, "native_effect_areas", {})
    if not isinstance(raw, dict) or not any(
        isinstance(row, dict) and row.get("native_type_id") == 19
        for row in raw.values()
    ):
        return result
    # Area geometry refresh operates on a private native state, so advisory
    # enumeration cannot change the source protected by the session guard.
    private = oracle.fork(runtime=runtime)
    fight = private.fight
    actor = fight.current
    gates = _visible_gates(oracle, private)
    entries = tuple(row for row in gates if contains_area_cell(row, actor.position))
    if not entries:
        return result
    for cell in sorted(fight.walkable):
        check()
        if tuple(cell) == tuple(actor.position):
            continue
        exits = tuple(row for row in gates if contains_area_cell(row, cell))
        if portal_network_pair(entries, exits) is not None:
            result["destinations"].append(list(cell))
    return result


def apply_portal_travel(oracle, private, action, *, forecast, stats_serializer=None):
    """Execute exactly the owned 12161 gate transaction on a private runtime."""
    if (
        not isinstance(action, dict)
        or set(action) != {"type", "destination"}
        or action.get("type") != "portal_travel"
        or not isinstance(action["destination"], list)
        or len(action["destination"]) != 3
        or any(type(value) is not int for value in action["destination"])
    ):
        raise ValueError("Invalid native portal travel action")
    from wakfu_server.combat_input_observation import observe_rng
    from wakfu_server.combat_portal_travel import try_apply_portal_travel
    from wakfu_server.combat_movement_runtime import _with_areas

    actor = private.fight.current
    if actor is None or private.fight.phase != "active" or actor.hp <= 0:
        raise ValueError("Missing active native portal traveler")
    from wakfu_server.combat_effect_area_geometry import contains_area_cell
    from wakfu_server.combat_portal_travel import portal_network_pair

    gates = _visible_gates(oracle, private)
    if (
        portal_network_pair(
            tuple(row for row in gates if contains_area_cell(row, actor.position)),
            tuple(
                row for row in gates if contains_area_cell(row, action["destination"])
            ),
        )
        is None
    ):
        raise ValueError("No observed native portal pair for requested travel")
    movement_rng = (
        oracle._rng(private.fight, action)
        if forecast
        else observe_rng("native_oracle.portal_travel", random.Random(), external=False)
    )
    factory, _ = oracle.factory(private.fight, private.action_id + 2, movement_rng)
    private.fight.native_rail_movement_authority = (
        factory.native_rail_movement_authority
    )
    if stats_serializer is None:
        stats_serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=private.fight.id,
            registrations=getattr(private.fight, "native_summon_registrations", {}),
            map_id=oracle.characters[oracle.viewer_id].get("map_id"),
        )
    if isinstance(stats_serializer, NativeStats):
        private.stats_serializer = stats_serializer.for_fight(private.fight)
        private.runtime_stats_serializer = private.stats_serializer
    else:
        private.runtime_stats_serializer = stats_serializer
        private.stats_serializer = lambda moving: stats_serializer(
            moving, private.fight
        )

    def operation(candidate, callback):
        traveler = candidate.fight.current
        server = effective_server_controlled(candidate.fight, traveler)
        outcome = try_apply_portal_travel(
            candidate,
            None if server else effective_input_owner(candidate.fight, traveler),
            traveler.id,
            [tuple(action["destination"])],
            lambda moving: stats_serializer(moving, candidate.fight),
            runtime_stats_serializer=stats_serializer,
            step_callback=callback,
            server_controlled=server,
        )
        if outcome is None:
            raise ValueError("No native portal pair for requested travel")
        return outcome

    if oracle.flags.get("native_area_callbacks", False):
        from wakfu_server.combat_area_transaction import prepare_area_movement

        def provider(fight, **kwargs):
            return prepare_area_movement(
                oracle.characters[oracle.viewer_id],
                oracle.monsters,
                fight,
                oracle.decks[oracle.viewer_id],
                rng=movement_rng,
                player_characters=oracle.characters,
                deck_blobs=oracle.decks,
                **kwargs
            )

        packets, _ = _with_areas(private, provider, operation)
    else:
        packets, _ = operation(private, None)
    check()
    return private, tuple(packets), None
