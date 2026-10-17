"""Private, typed Registry execute/ACK reproduction without Store or sockets.

This projection supports ordinary existing fights only. It preserves the live
Fight/runtime graph, membership fences, ACK and ordered mailbox batches. Locks
are fresh. Withdrawal payloads are deliberately represented by membership keys:
withdrawal, join, takeover, settlement and dispatch are separate boundaries.
Trusted callers bind providers and supply operations; payloads select no code.
"""
from collections import deque
from copy import deepcopy

from .combat_reproduction_state import encode_state, decode_state
from .combat_runtime_messages import RuntimeMessages
from .combat_shared import Registry, SharedFight, Session, Batch
from .combat_ack_barrier import AckBarrier
from .combat_state import Fight

SCHEMA = "wakemu-shared-combat-reproduction-v1"
BOUNDARY = "ordinary-registry-execute-and-ack-mailboxes"
_DATA_FIELDS = frozenset(
    {
        "fight",
        "map_id",
        "instance_id",
        "runtime",
        "group_lease",
        "participants",
        "connected",
        "sequence",
        "auto_locked",
        "ack",
        "join_aliases",
        "settlement_ready",
        "settlement_batches",
        "returned",
        "checkpoint_revision",
        "checkpoint_terminal",
        "disconnect_abort_pending",
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "is_duel",
        "duel_leaders",
        "duel_disconnected_character_id",
        "duel_finish_reason",
        "reconnect_turn_end_packets",
        "reconnect_remaining_turn_seconds",
        "native_ai_turn_claim",
    }
)
_EXCLUDED_FIELDS = frozenset(
    {"lock", "dispatch_lock", "withdrawals", "outboxes", "join_context"}
)
_SESSION_FIELDS = ("account_id", "character_id", "generation", "map_id", "instance_id")
_ERRORS = {
    cls.__module__ + "." + cls.__name__: cls
    for cls in (
        ValueError,
        RuntimeError,
        LookupError,
        KeyError,
        IndexError,
        PermissionError,
        TimeoutError,
        ConnectionError,
        OSError,
        FileNotFoundError,
        TypeError,
    )
}


class UnsupportedSharedReproduction(RuntimeError):
    """A provider or lifecycle boundary lacks a trusted offline recipe."""


class LeaseReplayMismatch(RuntimeError):
    """The actual lease checks differ from the captured observation tape."""


def _session_fact(session):
    if type(session) is not Session:
        raise LeaseReplayMismatch("Lease observation requires an exact Session")
    if (
        any(
            type(getattr(session, field)) is not int
            for field in _SESSION_FIELDS
            if field != "generation"
        )
        or type(session.generation) is not str
    ):
        raise LeaseReplayMismatch("Lease session fields have invalid types")
    return {field: getattr(session, field) for field in _SESSION_FIELDS}


def lease_result(session, *, result=None, error=None):
    """Plain observation of an existing lease call; never performs a lease read."""
    if error is None and type(result) is not bool:
        raise LeaseReplayMismatch("Lease result must be an explicit boolean")
    if error is not None and not isinstance(error, Exception):
        raise LeaseReplayMismatch("Lease exception evidence requires an Exception")
    return {
        "session": _session_fact(session),
        "result": result if error is None else None,
        "error": None
        if error is None
        else {
            "type": type(error).__module__ + "." + type(error).__name__,
            "message": str(error),
            "args": tuple(error.args),
        },
    }


class ObservedLeaseTape:
    """Consume exact ordered session checks with no default live verdict."""

    def __init__(self, rows):
        if type(rows) not in (list, tuple):
            raise LeaseReplayMismatch("Explicit ordered lease observations required")
        self.rows = []
        self.position = 0
        for row in rows:
            if type(row) is not dict or set(row) != {"session", "result", "error"}:
                raise LeaseReplayMismatch("Invalid lease observation fields")
            fact = row["session"]
            if type(fact) is not dict or set(fact) != set(_SESSION_FIELDS):
                raise LeaseReplayMismatch("Invalid lease session evidence")
            try:
                session = Session(**fact)
            except (ValueError, TypeError) as failure:
                raise LeaseReplayMismatch("Invalid lease session identity") from failure
            error = row["error"]
            if error is None:
                if type(row["result"]) is not bool:
                    raise LeaseReplayMismatch("Invalid lease result evidence")
            elif (
                type(error) is not dict
                or set(error) != {"type", "message", "args"}
                or error["type"] not in _ERRORS
                or type(error["message"]) is not str
                or type(error["args"]) not in (tuple, list)
                or row["result"] is not None
            ):
                raise LeaseReplayMismatch("Unsupported lease exception evidence")
            if (
                error is not None
                and str(_ERRORS[error["type"]](*error["args"])) != error["message"]
            ):
                raise LeaseReplayMismatch(
                    "Lease exception requires additional native fields"
                )
            self.rows.append(
                (session, row["result"], None if error is None else deepcopy(error))
            )

    def __call__(self, session):
        if self.position >= len(self.rows):
            raise LeaseReplayMismatch("Replay requested an unobserved lease check")
        expected, result, error = self.rows[self.position]
        if _session_fact(session) != _session_fact(expected):
            raise LeaseReplayMismatch("Lease session identity/order differs")
        self.position += 1
        if error is not None:
            raise _ERRORS[error["type"]](*error["args"])
        return result

    def assert_consumed(self):
        if self.position != len(self.rows):
            raise LeaseReplayMismatch("Replay left unused lease observations")


def _check_boundary(shared):
    if type(shared) is not SharedFight:
        raise UnsupportedSharedReproduction("Actual SharedFight required")
    if (
        type(shared.fight) is not Fight
        or not isinstance(shared.runtime, RuntimeMessages)
        or shared.runtime.fight is not shared.fight
    ):
        raise UnsupportedSharedReproduction(
            "Shared runtime must own the exact shared Fight"
        )
    if getattr(shared.fight, "rift_wave_state", None) is not None:
        raise UnsupportedSharedReproduction(
            "Rift accepted-action providers need a separate recipe"
        )
    if vars(shared).keys() - (_DATA_FIELDS | _OPTIONAL_FIELDS | _EXCLUDED_FIELDS):
        raise UnsupportedSharedReproduction("Unknown shared lifecycle fields")
    if shared.join_context is not None and type(shared.join_context) is not dict:
        raise UnsupportedSharedReproduction("Shared context must be explicit data")
    if any(
        callable(value) and key != "hero_appearance"
        for key, value in (shared.join_context or {}).items()
    ):
        raise UnsupportedSharedReproduction(
            "Shared context callbacks need a separate recipe"
        )


def _context_projection(context):
    if context is None:
        return None
    result = dict(context)
    provider = result.get("hero_appearance")
    if callable(provider):
        # This provider is never consulted by execute or acknowledge. Preserve
        # its identity as inert evidence; join/bootstrap is not supported here.
        result["hero_appearance"] = {
            "reproduction_omitted_service": {
                "module": getattr(provider, "__module__", type(provider).__module__),
                "qualname": getattr(
                    provider, "__qualname__", type(provider).__qualname__
                ),
            }
        }
    return result


def capture_shared_state(shared, *, registry=None, preserve_scalars=False):
    """Freeze under the action lock; optionally retain exact attribute order.

    Native SDK checkpoints require scalar aliases and original attribute order.
    Ordinary shared callers retain the legacy encoding by default.
    """
    _check_boundary(shared)
    state = {field: getattr(shared, field) for field in sorted(_DATA_FIELDS)}
    state["optional"] = {
        field: getattr(shared, field)
        for field in sorted(_OPTIONAL_FIELDS)
        if hasattr(shared, field)
    }
    state["join_context"] = _context_projection(shared.join_context)
    state["withdrawal_accounts"] = tuple(shared.withdrawals)
    state["outboxes"] = {
        account: tuple(queue) for account, queue in shared.outboxes.items()
    }
    # Only the selected fight's registry aliases can be used by this boundary.
    state["indices"] = (
        None
        if registry is None
        else {
            "by_actor": {
                key: value
                for key, value in registry.by_actor.items()
                if value == shared.fight.id
            },
            "by_character": {
                key: value
                for key, value in registry.by_character.items()
                if value == shared.fight.id
            },
            "join_aliases": {
                key: {shared.fight.id}
                for key, value in registry.join_aliases.items()
                if shared.fight.id in value
            },
        }
    )
    return {
        "schema": SCHEMA,
        "boundary": BOUNDARY,
        "graph": encode_state(state, preserve_scalars=preserve_scalars),
    }


def _validate_state(state):
    expected = _DATA_FIELDS | {
        "optional",
        "join_context",
        "withdrawal_accounts",
        "outboxes",
        "indices",
    }
    if type(state) is not dict or set(state) != expected:
        raise UnsupportedSharedReproduction("Incomplete shared state fields")
    fight, runtime = state["fight"], state["runtime"]
    if (
        type(fight) is not Fight
        or not isinstance(runtime, RuntimeMessages)
        or runtime.fight is not fight
    ):
        raise UnsupportedSharedReproduction("Restored runtime/Fight identity differs")
    if type(state["sequence"]) is not int:
        raise UnsupportedSharedReproduction("Invalid shared sequence")
    if type(state["participants"]) is not dict or type(state["outboxes"]) is not dict:
        raise UnsupportedSharedReproduction("Invalid shared membership/mailboxes")
    for account, session in state["participants"].items():
        if type(account) is not int or type(session) is not Session:
            raise UnsupportedSharedReproduction("Invalid participant identity")
        try:
            Session(**_session_fact(session))
        except (TypeError, ValueError, LeaseReplayMismatch) as error:
            raise UnsupportedSharedReproduction(
                "Invalid nominal Session fields"
            ) from error
    if type(state["connected"]) is not set or any(
        type(account) is not int for account in state["connected"]
    ):
        raise UnsupportedSharedReproduction("Invalid connected identity collection")
    for account, queue in state["outboxes"].items():
        if type(account) is not int:
            raise UnsupportedSharedReproduction("Invalid mailbox account type")
        if type(queue) is not tuple:
            raise UnsupportedSharedReproduction("Ordered mailbox batches required")
        for batch in queue:
            if type(batch) is not Batch or type(batch.sequence) is not int:
                raise UnsupportedSharedReproduction("Invalid mailbox sequence")
            Registry._packets(batch.packets)
    if type(state["ack"]) is not AckBarrier:
        raise UnsupportedSharedReproduction("Exact shared ACK barrier required")
    ack = state["ack"]
    if (
        type(ack.expected) is not dict
        or type(ack.received) is not set
        or any(
            type(account) is not int or type(generation) is not str
            for account, generation in ack.expected.items()
        )
        or any(type(account) is not int for account in ack.received)
    ):
        raise UnsupportedSharedReproduction("Invalid ACK membership")
    if ack.turn is not None and type(ack.turn) is not int:
        raise UnsupportedSharedReproduction("Invalid pending ACK counter")
    if (
        type(state["optional"]) is not dict
        or not state["optional"].keys() <= _OPTIONAL_FIELDS
    ):
        raise UnsupportedSharedReproduction("Unknown optional lifecycle facts")
    if type(state["withdrawal_accounts"]) is not tuple or any(
        type(account) is not int for account in state["withdrawal_accounts"]
    ):
        raise UnsupportedSharedReproduction("Invalid withdrawal membership projection")


def restore_shared_state(payload, lease_rows, *, bind_runtime=None):
    """Restore private locks/deques; never register, read leases or bootstrap.

    ``bind_runtime(runtime, shared)`` is trusted caller code, never a symbol
    selected by the payload. It must supply every recorded runtime service.
    Return ``(registry, shared, lease_tape)`` for explicit result inspection.
    """
    if (
        type(payload) is not dict
        or set(payload) != {"schema", "boundary", "graph"}
        or payload["schema"] != SCHEMA
        or payload["boundary"] != BOUNDARY
    ):
        raise UnsupportedSharedReproduction(
            "Unsupported shared reproduction schema/boundary"
        )
    state = decode_state(payload["graph"])
    _validate_state(state)
    tape = ObservedLeaseTape(lease_rows)
    registry = Registry(tape)
    shared = SharedFight(
        state["fight"], state["map_id"], state["instance_id"], state["runtime"]
    )
    for field in _DATA_FIELDS:
        setattr(shared, field, state[field])
    for field, value in state["optional"].items():
        setattr(shared, field, value)
    shared.join_context = state["join_context"]
    shared.withdrawals = dict.fromkeys(state["withdrawal_accounts"])
    shared.outboxes = {
        account: deque(queue) for account, queue in state["outboxes"].items()
    }
    _check_boundary(shared)
    registry.fights[shared.fight.id] = shared
    indices = state["indices"]
    if indices is None:
        registry.by_actor = {
            identity: shared.fight.id for identity in shared.fight.actors
        }
        registry.by_character = {
            actor.id: shared.fight.id
            for actor in shared.fight.actors.values()
            if actor.controlled
        }
        registry.join_aliases = {
            identity: {shared.fight.id} for identity in shared.join_aliases
        }
    else:
        if type(indices) is not dict or set(indices) != {
            "by_actor",
            "by_character",
            "join_aliases",
        }:
            raise UnsupportedSharedReproduction("Invalid registry alias projection")
        for field in ("by_actor", "by_character"):
            if type(indices[field]) is not dict or any(
                type(key) is not int or value != shared.fight.id
                for key, value in indices[field].items()
            ):
                raise UnsupportedSharedReproduction(
                    "Registry index belongs to another fight"
                )
        if type(indices["join_aliases"]) is not dict or any(
            type(key) is not int or value != {shared.fight.id}
            for key, value in indices["join_aliases"].items()
        ):
            raise UnsupportedSharedReproduction("Invalid registry join alias")
        registry.by_actor, registry.by_character, registry.join_aliases = (
            indices["by_actor"],
            indices["by_character"],
            indices["join_aliases"],
        )
    if bind_runtime is not None:
        if not callable(bind_runtime):
            raise UnsupportedSharedReproduction(
                "Trusted runtime binder must be callable"
            )
        bind_runtime(shared.runtime, shared)
    _check_boundary(shared)
    graph = payload["graph"]
    root = graph["nodes"][graph["root"]["ref"]]
    service_owners = {}
    for field, reference in root["items"]:
        # decode_state has already validated references and exact root fields.
        # Scalar-preserving checkpoints encode these keys as string nodes.
        if type(field) is dict and set(field) == {"ref"}:
            node = graph["nodes"][field["ref"]]
            field = node["value"] if node["kind"] == "str" else None
        if field in ("runtime", "fight"):
            service_owners[reference["ref"]] = (
                shared.runtime if field == "runtime" else shared.fight
            )
    for row in payload["graph"]["services"]:
        owner = service_owners.get(row["node"])
        if owner is None:
            raise UnsupportedSharedReproduction(
                "Nested runtime services require a separate trusted recipe"
            )
        if not callable(getattr(owner, row["field"], None)):
            raise UnsupportedSharedReproduction(
                "Captured service lacks an explicit trusted binding: " + row["field"]
            )
    return registry, shared, tape


def replay_execute(
    restored, session, actor_id, operation, *, expected_sequence=None, require_turn=True
):
    """Use the real Registry action path; exceptions retain their actual state."""
    registry, shared, tape = restored
    if not callable(operation):
        raise UnsupportedSharedReproduction("A trusted operation is required")
    from .combat_shared_incident_capture import suppress_shared_incidents

    with suppress_shared_incidents():
        try:
            return registry.execute(
                shared.fight.id,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
            )
        finally:
            tape.assert_consumed()


def replay_acknowledge(restored, session, body, *, release_packets=None):
    """Use the real collective barrier, including partial ACK return values."""
    registry, shared, tape = restored
    if release_packets is None:
        release_packets = lambda fight, runtime, ack_body: runtime.acknowledge_turn(
            ack_body
        )
    if not callable(release_packets):
        raise UnsupportedSharedReproduction(
            "A trusted ACK release operation is required"
        )
    from .combat_shared_incident_capture import suppress_shared_incidents

    with suppress_shared_incidents():
        try:
            return registry.acknowledge(shared.fight.id, session, body, release_packets)
        finally:
            tape.assert_consumed()
