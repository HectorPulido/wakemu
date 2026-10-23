"""Qualified gate-specific Wakemu voluntary callbacks, not ordinary walking.

Original byL/byS/cpa/cvP proves gate travel. The original server callback
publisher is unavailable; reusing voluntary1005 and area entry/exit is explicit
Wakemu policy, attested by the actual paid portal/QI transaction.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass

_SCOPE = "_wakemu_native_gate_movement_boundary"
POLICY = "wakemu.native-gate-movement-boundary-v1"


@dataclass(frozen=True)
class NativeGateMovementBoundary:
    policy: str
    actor_id: int
    owner_id: int | None
    turn_id: int
    from_cell: tuple
    to_cell: tuple
    entry_uid: int
    exit_uid: int
    affiliation: int
    ap_before: int
    mp_before: int
    ap_after: int
    mp_after: int
    tackle_ap: int
    tackle_mp: int
    obstacle_id: int
    ap_paid: int
    mp_paid: int
    ap_effective_after: int
    mp_effective_after: int
    ap_raw_post: int
    mp_raw_post: int

    def facts(self):
        return asdict(self)


def validate_gate_boundary_facts(facts):
    if not isinstance(facts, dict) or set(facts) != set(
        NativeGateMovementBoundary.__dataclass_fields__
    ):
        raise ValueError("Invalid native gate movement receipt fields")
    receipt = NativeGateMovementBoundary(**facts)
    if (
        receipt.policy != POLICY
        or any(
            type(getattr(receipt, key)) is not int
            for key in (
                "actor_id",
                "turn_id",
                "entry_uid",
                "exit_uid",
                "affiliation",
                "ap_before",
                "mp_before",
                "ap_after",
                "mp_after",
                "tackle_ap",
                "tackle_mp",
                "obstacle_id",
                "ap_paid",
                "mp_paid",
                "ap_effective_after",
                "mp_effective_after",
                "ap_raw_post",
                "mp_raw_post",
            )
        )
        or (receipt.owner_id is not None and type(receipt.owner_id) is not int)
        or receipt.actor_id == 0
        or receipt.affiliation == -1
        or not -128 <= receipt.affiliation <= 127
        or not -1 <= receipt.obstacle_id <= 126
        or receipt.tackle_ap < 0
        or receipt.tackle_mp < 0
        or min(receipt.ap_after, receipt.mp_after) < 0
        or not 0 <= receipt.ap_paid <= 127
        or not 0 <= receipt.mp_paid <= 127
        or receipt.ap_before - receipt.ap_after != receipt.ap_paid
        or receipt.mp_before - receipt.mp_after != receipt.mp_paid
        or any(
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            for cell in (receipt.from_cell, receipt.to_cell)
        )
        or tuple(receipt.from_cell) == tuple(receipt.to_cell)
    ):
        raise ValueError("Invalid native gate movement receipt")
    return receipt


def validate_gate_movement_boundary(fight, receipt, *, committed=False):
    validate_gate_boundary_facts(receipt.facts())
    from .combat_portal_travel import _gate_actor

    actor = _gate_actor(
        fight,
        receipt.owner_id,
        receipt.actor_id,
        server_controlled=receipt.owner_id is None,
    )
    if fight.turn_id != receipt.turn_id or tuple(actor.position) != tuple(
        receipt.to_cell
    ):
        raise ValueError("Native gate receipt differs from actual participant")
    from .combat_qi_fight import current_registry

    slot = (
        current_registry(fight).slots[receipt.obstacle_id]
        if receipt.obstacle_id >= 0
        else None
    )
    if (
        actor.native_obstacle_id != receipt.obstacle_id
        or slot is None
        or slot["identity"] != ["actor", actor.id]
        or tuple(slot["position"]) != tuple(receipt.to_cell[:2])
    ):
        raise ValueError("Native gate receipt differs from committed QI")
    # Resources/portal geometry attest the boundary before any subscribed effect
    # can legitimately mutate them. Repeated deliveries require that same scope.
    if not committed:
        from .combat_movement_payment_events import _raw_resources

        if (actor.ap, actor.mp) != (
            receipt.ap_effective_after,
            receipt.mp_effective_after,
        ) or _raw_resources(actor) != (receipt.ap_raw_post, receipt.mp_raw_post):
            raise ValueError("Native gate receipt differs from actual payment")
        from .combat_effect_area_queries import _rows
        from .combat_effect_area_geometry import contains_area_cell
        from .combat_portal_travel import portal_network_pair

        gates = tuple(row for row in _rows(fight) if row.get("native_type_id") == 19)
        entries = tuple(
            row for row in gates if contains_area_cell(row, receipt.from_cell)
        )
        exits = tuple(row for row in gates if contains_area_cell(row, receipt.to_cell))
        if (
            portal_network_pair(entries, exits) != (receipt.entry_uid, receipt.exit_uid)
            or entries[0]["native_fight_affiliation"] != receipt.affiliation
        ):
            raise ValueError("Native gate receipt differs from actual portal pair")
        authority = getattr(fight, "native_rail_movement_authority", None)
        if not callable(authority) or not callable(
            getattr(authority, "properties", None)
        ):
            raise ValueError("Missing actual native gate movement authority")
        if authority.properties(fight, actor) & {3, 88, 105}:
            raise ValueError("Native gate receipt violates movement properties")
    return receipt


@contextmanager
def native_gate_movement_scope(fight, receipt):
    if getattr(fight, _SCOPE, None) is not None:
        raise ValueError("Nested native gate movement publication")
    validate_gate_movement_boundary(fight, receipt)
    setattr(fight, _SCOPE, receipt)
    try:
        from .combat_movement_payment_events import committed_step_payment

        actor = fight.actors[receipt.actor_id]
        with committed_step_payment(
            fight,
            actor,
            origin=receipt.from_cell,
            destination=receipt.to_cell,
            index=0,
            ap_before=receipt.ap_before,
            ap_after=receipt.ap_after,
            mp_before=receipt.mp_before,
            mp_after=receipt.mp_after,
            ap_paid=receipt.ap_paid,
            mp_paid=receipt.mp_paid,
        ):
            yield
    finally:
        delattr(fight, _SCOPE)


def current_gate_movement_boundary(fight, actor_id, origin, destination):
    receipt = getattr(fight, _SCOPE, None)
    if receipt is None:
        return None
    if (
        not isinstance(receipt, NativeGateMovementBoundary)
        or receipt.actor_id != actor_id
        or tuple(receipt.from_cell) != tuple(origin)
        or tuple(receipt.to_cell) != tuple(destination)
    ):
        raise ValueError("Native gate scope differs from requested boundary")
    validate_gate_movement_boundary(fight, receipt, committed=True)
    return receipt
