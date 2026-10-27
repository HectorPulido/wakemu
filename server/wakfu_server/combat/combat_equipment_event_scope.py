"""Event capability backed by existing ordinary combat producers.

This module neither publishes an event nor grants a trigger-Qe value context.
Native mask indices remain distinct from Qf delivery channels. Unsupported
source channels and source-scoped outcome events remain explicit unknowns.
"""

from collections.abc import Mapping


def damage_events(factory, routes, *, phase=1):
    """Return native baseline element events from installed damage routes.

    OrdinaryDamageEvents uses this same numerical producer at Qe phases1..4.
    Conditional flag/block/back events are admitted only at their actual phase;
    extra output metadata still requires its own native definition authority.
    """
    if routes is None:
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    if type(routes) is not FactoryOperationRoutes:
        return frozenset()
    from .combat_damage_events import (
        ELEMENT_EVENT_IDS,
        FLAG_EVENT_IDS,
        damage_event_ids,
    )
    from .combat_damage_handler import NativeDamageHandler
    from .combat_equipment_retained_lifecycle import _native_factory

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
    ):
        return frozenset()
    callback = runtime.contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    if not callable(runtime.contexts.damage) or runtime.contexts.damage is not getattr(
        getattr(adapter, "cast", None), "damage", None
    ):
        return frozenset()
    selected = set()
    for family in ELEMENT_EVENT_IDS:
        route = routes.routes.get(family)
        if (
            route is None
            or route.factory is not runtime
            or route.handler_type is not NativeDamageHandler
        ):
            continue
        for flags in ((), *((flag,) for flag in FLAG_EVENT_IDS)):
            selected.update(
                damage_event_ids(
                    {
                        "effect_class": family,
                        "native_effect_flags": flags,
                        "target_masks": (None,) * 7,
                    },
                    container_type=12,
                    phase=phase,
                    blocked=True,
                    localization="BACK",
                    context_is_native_fight=True,
                )
            )
    return frozenset(selected)


def healing_events(factory, routes):
    """Native eXs emits baseline1 and its element at every Qe phase1..4.

    Only the actual configured healing handler/adapter construction supplies
    this proof. Life steal24 has a separate dynamic identifier policy and is
    deliberately excluded; output metadata is not invented here.
    """
    if routes is None:
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    if type(routes) is not FactoryOperationRoutes:
        return frozenset()
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_healing_handler import NativeHealingHandler
    from .combat_event_replay import HEALING_ELEMENT_EVENT_IDS

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
    ):
        return frozenset()
    callback = runtime.contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    if not callable(
        runtime.contexts.healing
    ) or runtime.contexts.healing is not getattr(
        getattr(adapter, "cast", None), "healing", None
    ):
        return frozenset()
    selected = set()
    for family, element in HEALING_ELEMENT_EVENT_IDS.items():
        route = routes.routes.get(family)
        if (
            route is not None
            and route.factory is runtime
            and route.handler_type is NativeHealingHandler
        ):
            selected.update((0, 1, element))
    return frozenset(selected)


def displacement_events(factory, routes=None):
    """Existing displacement constructor/lifecycle emits its native base IDs."""
    if routes is None:
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    if type(routes) is not FactoryOperationRoutes:
        return frozenset()
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_summon import ordinary_roster_authority
    from .combat_displacement_events import BASE_EVENT_IDS

    runtime = _native_factory(factory)
    if runtime is None or routes.factory is not runtime:
        return frozenset()
    adapter = getattr(runtime.contexts.healing_events, "__self__", None)
    authority = getattr(adapter, "actor_authority", None)
    if (
        runtime.displacement_authority is not authority
        or not ordinary_roster_authority(authority)
    ):
        return frozenset()
    from .combat_displacement import NativeDisplacementHandler

    return frozenset(
        event
        for family, events in BASE_EVENT_IDS.items()
        if (route := routes.routes.get(family)) is not None
        and route.factory is runtime
        and route.handler_type is NativeDisplacementHandler
        for event in events
    )


def characteristic_events(factory, routes):
    """Return original prototype events emitted by actual current/max routes.

    Both consumers deliver their constructor event set at Qe phases1..4.
    This reads the same published metadata used by those consumers; it does
    not infer events from stat names or invent a characteristic notification.
    """
    if routes is None:
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_current_stat_consumer import _EVENTS as current_events
    from .combat_stat_handler import NativeStatHandler
    from .combat_maximum_resource import (
        FAMILIES,
        NativeMaximumResourceHandler,
        maximum_event_catalog,
    )

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
    ):
        return frozenset()
    callback = runtime.contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    # The retained preflight checks this exact adapter and its actor authority.
    # Stat calculation must come from that same configured adapter context.
    if not callable(runtime.contexts.stat) or runtime.contexts.stat is not getattr(
        getattr(adapter, "cast", None), "stat", None
    ):
        return frozenset()
    registry = runtime.characteristic_registry.get(
        "effects", runtime.characteristic_registry
    )
    maximum_events = maximum_event_catalog()
    selected = set()
    for family, route in routes.routes.items():
        if route.factory is not runtime:
            continue
        row = None
        if route.handler_type is NativeStatHandler:
            binding = registry.get(str(family))
            prototype = current_events.get(str(family))
            if (
                isinstance(binding, Mapping)
                and isinstance(prototype, Mapping)
                and binding.get("runner") in ("eWQ", "eWR")
                and prototype.get("runner") == binding["runner"]
                and prototype.get("fixed_stat_id") == binding.get("fixed_stat_id")
            ):
                row = prototype
        elif route.handler_type is NativeMaximumResourceHandler and family in FAMILIES:
            prototype = maximum_events.get(str(family))
            if (
                isinstance(prototype, Mapping)
                and prototype.get("runner") == "eWN"
                and prototype.get("fixed_stat_id") == FAMILIES[family][0]
            ):
                row = prototype
        if row is not None:
            events = row.get("events")
            if isinstance(events, (tuple, list)) and all(
                type(value) is int and value >= 0 for value in events
            ):
                selected.update(events)
    return frozenset(selected)


def assess(factory, effect, retained_container, *, routes=None):
    """Return True/False/None for proven/malformed/unknown event production."""
    masks = effect.get("target_masks") if isinstance(effect, Mapping) else None
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(
            row is not None
            and (
                not isinstance(row, (tuple, list))
                or any(type(event) is not int for event in row)
            )
            for row in masks
        )
    ):
        return False
    # Index6 is native aZO output metadata, not a subscription channel.
    # Its exact family must have an installed producer; it cannot borrow an
    # unrelated source's output identifiers or an external Qf publisher.

    # Preserve the existing established damage/turn scope boundary. Newly
    # exposed producers below require the exact retained constructor proof.
    legacy = not any(masks[index] for index in (0, 1, 2, 4))
    legacy = legacy and not (set(masks[3] or ()) - {2})
    legacy = legacy and not (set(masks[5] or ()) - {1001, 1002, 1003, 1037})
    legacy = legacy and not masks[6]
    if legacy:
        if masks[3] and not callable(getattr(factory.contexts, "damage", None)):
            return None
        return bool(masks[3] or masks[5])

    from wakfu_server.combat_equipment_retained_lifecycle import preflight

    # Exact ordinary adapter construction supplies NativeEventReplay and the
    # real lifecycle/clone authorities; no callback runs during this preflight.
    if not preflight(factory, retained_container):
        return None
    if masks[6]:
        from .combat_original_producer_events import available_original_events

        family = effect.get("effect_class")
        if type(family) is not int or any(
            set(masks[6])
            - available_original_events(factory, routes, phase=phase, family=family)
            for phase in (1, 2, 3, 4)
        ):
            return None

    from wakfu_server.combat_cost_payment_events import payment_event_ids

    payment = frozenset(
        payment_event_ids(
            {"ap": 1, "mp": 1, "wp": 1},
            special=True,
        )
    )
    # Paid receipt eWf is replayed ONLY at post-application phases3/4.
    # The spell boundary separately publishes1025 removal at4/40/41.
    allowed = {
        0: frozenset((2,)),
        1: frozenset((2,)),
        2: payment | {2, 1025},
        3: payment | {2},
        4: frozenset(),
        5: frozenset((1001, 1002, 1003, 1024, 1025, 1028, 1037)),
    }
    if 1005 in (masks[5] or ()) or 1005 in (masks[2] or ()):
        from .combat_voluntary_movement_events import deliver_voluntary_movement

        # The ordinary movement transaction calls this existing producer after
        # each committed nonzero step. It replays real moved-actor/manager
        # identities under committed_movement_recipient_scope. The retained
        # constructor preflight above proves the same ordinary actor/replay
        # machinery; this adds no movement event or triggering-Qe value.
        if not callable(deliver_voluntary_movement):
            return None
        allowed[5] = allowed[5] | {1005}
        # The same committed-step producer already emits4/40/41. Applied
        # scalar removal masks use the real immutable definition, not a fake
        # deferred activation listener.
        allowed[2] = allowed[2] | {1005}
    if 1016 in (masks[5] or ()) or 1016 in (masks[2] or ()):
        from .combat_critical_hit_events import preflight as critical_hit_preflight

        # Explicit Wakemu policy reconstructed from the installed description:
        # a completed actual critical damage application, not a client flag,
        # healing-only cast or a synthetic triggering Qe.
        if not critical_hit_preflight(factory, retained_container, routes=routes):
            return None
        allowed[5] = allowed[5] | {1016}
        allowed[2] = allowed[2] | {1016}
    if set(masks[2] or ()) & {1001, 1037}:
        from .combat_turn_boundary import execute_turn_delivery

        if not callable(execute_turn_delivery):
            return None
        allowed[2] = allowed[2] | {1001, 1037}
    if 1024 in (masks[2] or ()):
        from .combat_cast_events import cast_event_scope

        if not callable(cast_event_scope):
            return None
        allowed[2] = allowed[2] | {1024}
    if 74 in (masks[2] or ()) or 74 in (masks[3] or ()):
        from .combat_movement_payment_events import (
            consume_step_payment,
            replay_movement_payment,
        )

        # The real step receipt fixes mh=True and binds the actual payer,
        # amount and path. Spell costs never borrow this conditional event.
        if not callable(consume_step_payment) or not callable(replay_movement_payment):
            return None
        allowed[2] = allowed[2] | {74}
        allowed[3] = allowed[3] | {74}
    external_contracts = (
        (1018, 5),
        (1015, 2),
        (1004, 2),
        (1004, 5),
        (1032, 5),
        (1048, 5),
    )
    for event_id, index in external_contracts:
        if event_id not in (masks[index] or ()):
            continue
        from .combat_equipment_external_contracts import preflight as external_preflight

        if external_preflight(
            factory, retained_container, event_id, index, routes=routes
        ):
            allowed[index] = allowed[index] | {event_id}
    if 1010 in (masks[5] or ()):
        from .combat_death_events import deliver_owned_death

        if not callable(deliver_owned_death):
            return None
        allowed[5] = allowed[5] | {1010}
    if 1030 in (masks[5] or ()):
        from .combat_equipment_finish import preflight_equipment_finish

        # This is the explicit installed Wakemu settlement policy, not a
        # recovered official-server publisher. It targets qualified equipment
        # UIDs only, after rewards and before the terminal checkpoint.
        if not preflight_equipment_finish(factory, retained_container):
            return None
        allowed[5] = allowed[5] | {1030}
    # Only inspect additional producer metadata when the established matrix
    # does not already cover the listener. Old turn/payment paths keep their
    # existing cold-import behavior. The caller supplies its existing manifest.
    if any(set(masks[index] or ()) - allowed[index] for index in (0, 1, 2, 3)):
        resource_events = (
            characteristic_events(factory, routes)
            | healing_events(factory, routes)
            | displacement_events(factory, routes)
        )
        from .combat_maximum_reduction_events import available_reduction_events
        from .combat_dynamic_current_loss_events import (
            available_dynamic_current_loss_events,
        )
        from .combat_maximum_characteristic_events import (
            available_maximum_characteristic_events,
        )
        from .combat_original_producer_events import (
            available_original_events,
            available_paid_breeze_events,
        )

        for index, phase in ((0, 1), (1, 2), (2, 4), (3, 3)):
            allowed[index] = (
                allowed[index]
                | resource_events
                | damage_events(factory, routes, phase=phase)
                | available_reduction_events(factory, routes, phase=phase)
                | available_dynamic_current_loss_events(factory, routes, phase=phase)
                | available_maximum_characteristic_events(factory, routes, phase=phase)
                | available_original_events(factory, routes, phase=phase)
                | available_paid_breeze_events(
                    factory, routes, retained_container, phase=phase
                )
            )
    if 500 in (masks[0] or ()) or 500 in (masks[2] or ()):
        from .combat_attack_preparation import (
            completed_attack_preparation,
            deliver_attack_preparation,
        )

        # The established first-primary-damage policy publishes only L1.
        # Successful cast settlement closes its actual first-primary-attack
        # marker, after all recipients rather than between area hits.
        if callable(deliver_attack_preparation) and 2 in damage_events(factory, routes):
            allowed[0] = allowed[0] | {500}
            if callable(completed_attack_preparation):
                allowed[2] = allowed[2] | {500}
    # 1026 currently reaches only consumable descendants through eligible_uids
    # in prepare_outcome; an equipment listener must NOT borrow that producer.
    # Other external events still require their actual installed producer.
    if any(set(masks[index] or ()) - allowed[index] for index in range(6)):
        return None
    if any(2 in (masks[index] or ()) for index in (0, 1, 2, 3)):
        if not callable(getattr(factory.contexts, "damage", None)):
            return None
    return bool(any(masks[index] for index in range(7)))
