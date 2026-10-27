"""Factory-bound declarations for guarded equipment boundary producers.

These contracts prove source wiring before pinning. Actual delivery still
requires each producer's transaction-local receipt and equipment UID scope;
the declaration cannot manufacture a completed round, paid departure or wave.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class EquipmentBoundaryProducer:
    event_id: int
    functions: tuple
    channels: tuple


@dataclass(frozen=True)
class EquipmentProducerRoutes:
    factory: object
    operation_routes: object
    contracts: object


def _source_contracts():
    from .combat_equipment_external_events import (
        deliver_completed_round,
        deliver_scoped_pairs,
        qualified_uids,
        queue_completed_round,
    )
    from .combat_equipment_tackle_events import (
        committed_tackle_departure,
        deliver_tackle_boundary,
    )
    from .combat_equipment_wave_events import deliver_registered_wave
    from .combat_tackle_movement import movement_tackle_cost
    from .combat_weapon_events import weapon_event_scope
    from .combat_weapon import prepare_server_weapon

    scope = (qualified_uids, deliver_scoped_pairs)
    return {
        1018: EquipmentBoundaryProducer(
            1018,
            (weapon_event_scope, prepare_server_weapon),
            ((5, (6, 60, 61)),),
        ),
        1015: EquipmentBoundaryProducer(
            1015,
            (weapon_event_scope, prepare_server_weapon),
            ((2, (4, 40, 41)),),
        ),
        1004: EquipmentBoundaryProducer(
            1004,
            (queue_completed_round, deliver_completed_round) + scope,
            ((5, (6, 60, 61)), (2, (4, 40, 41))),
        ),
        1032: EquipmentBoundaryProducer(
            1032,
            (movement_tackle_cost, committed_tackle_departure, deliver_tackle_boundary)
            + scope,
            ((5, (6, 60)),),
        ),
        1048: EquipmentBoundaryProducer(
            1048,
            (deliver_registered_wave,) + scope,
            ((5, (6, 60, 61)),),
        ),
    }


def _valid_routes(runtime, routes):
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    return (
        type(routes) is FactoryOperationRoutes
        and routes.factory is runtime
        and all(route.factory is runtime for route in routes.routes.values())
    )


def bind_owned_equipment_producers(factory, routes=None):
    """Called by the real runtime constructor and its bounded test constructor."""
    from .combat_equipment_retained_lifecycle import _native_factory

    runtime = _native_factory(factory)
    if runtime is None:
        raise ValueError("Equipment boundary producers require the native factory")
    if routes is None:
        routes, _ = runtime.equipment_operation_capability()
    if not _valid_routes(runtime, routes):
        raise ValueError("Equipment boundary routes belong to another factory")
    binding = EquipmentProducerRoutes(
        runtime,
        routes,
        MappingProxyType(_source_contracts()),
    )
    previous = getattr(runtime, "owned_equipment_boundary_producers", None)
    if previous is not None:
        if (
            type(previous) is not EquipmentProducerRoutes
            or previous.factory is not runtime
            or previous.contracts != binding.contracts
            or not _valid_routes(runtime, previous.operation_routes)
        ):
            raise ValueError("Equipment boundary producer binding changed")
        return previous
    runtime.owned_equipment_boundary_producers = binding
    return binding


def preflight(factory, retained_container, event_id, mask_index, *, routes=None):
    """Admit only an explicitly bound source family and its native mask phase."""
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_equipment_retained_lifecycle import preflight as retained

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(event_id) is not int
        or type(mask_index) is not int
        or not retained(factory, retained_container)
    ):
        return False
    binding = getattr(runtime, "owned_equipment_boundary_producers", None)
    if (
        type(binding) is not EquipmentProducerRoutes
        or binding.factory is not runtime
        or not _valid_routes(runtime, binding.operation_routes)
        or (routes is not None and not _valid_routes(runtime, routes))
    ):
        return False
    source = binding.contracts.get(event_id)
    expected = _source_contracts().get(event_id)
    return (
        type(source) is EquipmentBoundaryProducer
        and source == expected
        and any(index == mask_index for index, _ in source.channels)
    )


def rebind_owned_equipment_producers(source_factory, cloned_factory):
    """Rebind a verified definition-only owned-factory clone, never a new role.

    Ordinary arbitrary copies retain an invalid old binding until this explicit
    constructor seam checks their execution authorities. Definition overlays
    and cloned group definition views may differ; actor/cast/RNG authorities,
    registry and action identity must remain exactly those of the source.
    """
    from .combat_equipment_retained_lifecycle import _native_factory

    source = _native_factory(source_factory)
    target = _native_factory(cloned_factory)
    previous = getattr(source_factory, "owned_equipment_boundary_producers", None)
    inherited = getattr(cloned_factory, "owned_equipment_boundary_producers", None)
    if previous is None and inherited is None:
        return None  # Existing unbound focused factories gain no new authority.
    if (
        source is None
        or target is None
        or source is target
        or type(previous) is not EquipmentProducerRoutes
        or previous.factory is not source
        or not _valid_routes(source, previous.operation_routes)
        or previous.contracts != _source_contracts()
    ):
        raise ValueError("Owned equipment producer clone lacks its source binding")
    same_authorities = (
        "contexts",
        "state_catalog",
        "characteristic_registry",
        "displacement_authority",
        "summon_authority",
        "healing_event_authority",
        "transaction_rng",
        "native_rail_movement_authority",
    )
    if (
        any(
            getattr(target, name, None) is not getattr(source, name, None)
            for name in same_authorities
        )
        or target.action_id != source.action_id
    ):
        raise ValueError("Owned equipment producer clone changed execution authority")
    # OwnedEquipmentRuntimeFactory changes only each group's definition view.
    # Preserve its exact typed callbacks and random draws through that copy.
    from .combat_relative_probability import RelativeGroupAuthority
    from .combat_random_group import RandomGroupAuthority

    for name, kind, callbacks in (
        (
            "relative_group_children",
            RelativeGroupAuthority,
            ("actors", "conditions", "draw_integer", "draw_fraction"),
        ),
        ("random_group_children", RandomGroupAuthority, ("conditions", "draw")),
    ):
        original = getattr(source, name, None)
        copied = getattr(target, name, None)
        if copied is original:
            continue
        if (
            type(original) is not kind
            or type(copied) is not kind
            or any(
                getattr(copied, callback) is not getattr(original, callback)
                for callback in callbacks
            )
        ):
            raise ValueError("Owned equipment clone changed native group authority")
    if inherited is not previous:
        if (
            type(inherited) is EquipmentProducerRoutes
            and inherited.factory is target
            and inherited.contracts == previous.contracts
            and _valid_routes(target, inherited.operation_routes)
        ):
            return inherited
        raise ValueError("Owned equipment clone contains another producer binding")
    target.owned_equipment_boundary_producers = None
    try:
        return bind_owned_equipment_producers(target)
    except Exception:
        target.owned_equipment_boundary_producers = inherited
        raise
