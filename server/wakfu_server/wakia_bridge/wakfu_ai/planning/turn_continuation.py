"""Turn-local custody of advisory plans after actual native publication.

No runtime or forecast is adopted here. A continuation only changes which
actions the remote planner may try first through fresh native previews.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import json
import math
import struct


SCHEMA = "verified-turn-continuation-v1"
RECOVERY_SCHEMA = "verified-recovery-continuation-v1"
MAX_ACTIONS = 3
_HOLDER = ContextVar("native_turn_continuation", default=None)
_UNSET = object()


def current():
    return _HOLDER.get()


def _boundary(runtime):
    fight = getattr(runtime, "fight", None)
    actor = getattr(fight, "current", None)
    hp = getattr(actor, "hp", None)
    if (
        getattr(fight, "phase", None) != "active"
        or actor is None
        or type(hp) not in (int, float)
        or hp <= 0
        or (type(hp) is float and not math.isfinite(hp))
        or getattr(runtime, "awaiting_ack", _UNSET) is not None
        or getattr(runtime, "pending", True)
    ):
        return None
    identity = (
        getattr(fight, "id", None),
        getattr(actor, "id", None),
        getattr(fight, "turn_id", None),
        getattr(fight, "sequence", None),
    )
    if any(type(value) is not int for value in identity):
        return None
    return identity


def binding(
    runtime, *, instance, catalog, policy_version, policy, source, root, request
):
    """Capture provenance from a guarded, fresh NativeSession root."""
    boundary = _boundary(runtime)
    if boundary is None or any(
        not isinstance(value, str) or not value
        for value in (instance, catalog, source, root, request)
    ):
        return None
    try:
        policy_digest = hashlib.sha256(
            json.dumps(
                policy, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    except (ValueError, TypeError):
        return None
    return dict(
        identity=(instance, *boundary[:3], catalog, policy_version, policy_digest),
        boundary=boundary,
        source=source,
        root=root,
        request=request,
    )


def _tail(decision):
    """Copy only a bounded, well-shaped suffix of the selected plan."""
    plan = decision.get("plan")
    if not isinstance(plan, list) or len(plan) < 2 or plan[0] != decision.get("action"):
        proposal = decision.get("recoveryContinuation")
        if (
            plan != [decision.get("action")]
            or not isinstance(proposal, dict)
            or set(proposal)
            != {
                "schema",
                "rootAction",
                "actions",
                "sourceKey",
                "rootState",
                "requestId",
            }
            or proposal.get("schema") != RECOVERY_SCHEMA
            or proposal.get("rootAction") != decision.get("action")
            or any(
                proposal.get(key) != decision.get(key)
                for key in ("sourceKey", "rootState", "requestId")
            )
            or not isinstance(proposal.get("actions"), list)
            or not 1 <= len(proposal["actions"]) <= MAX_ACTIONS
        ):
            return []
        return _copy_actions(proposal["actions"])
    return _copy_actions(plan[1 : MAX_ACTIONS + 1])


def recovery_proposal(actions, *, root_action, source, root, request):
    """Bind bounded advice to the selected first action, never its utility."""
    if (
        not isinstance(actions, list)
        or not actions
        or any(
            not isinstance(value, str) or not value for value in (source, root, request)
        )
    ):
        return None
    tail = _copy_actions(actions[:MAX_ACTIONS])
    if not tail:
        return None
    return dict(
        schema=RECOVERY_SCHEMA,
        rootAction=deepcopy(root_action),
        actions=tail,
        sourceKey=source,
        rootState=root,
        requestId=request,
    )


def _copy_actions(actions):
    result = []
    for action in actions:
        if not isinstance(action, dict):
            return []
        kind = action.get("type")
        if kind == "cast":
            if (
                set(action) - {"type", "spellId", "level", "targetId", "target"}
                or type(action.get("spellId")) is not int
                or type(action.get("level")) is not int
                or not _cell(action.get("target"))
                or ("targetId" in action and type(action["targetId"]) is not int)
            ):
                return []
        elif kind == "move":
            path = action.get("path")
            if (
                set(action) != {"type", "path"}
                or not isinstance(path, list)
                or not 1 <= len(path) <= 256
                or not all(_cell(cell) for cell in path)
            ):
                return []
        elif kind == "portal_travel":
            if set(action) != {"type", "destination"} or not _cell(
                action.get("destination")
            ):
                return []
        else:
            return []
        result.append(deepcopy(action))
    return result


def _cell(value):
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(type(coordinate) is int for coordinate in value)
    )


def published_movement_cells(fight_id, actor_id, packets):
    """Read actual movement cells from native 13624 packets, not proposed paths."""
    cells = set()
    for packet in packets:
        if (
            not isinstance(packet, (tuple, list))
            or len(packet) != 2
            or packet[0] != 13624
        ):
            continue
        body = packet[1]
        if (
            not isinstance(body, (bytes, bytearray, memoryview))
            or len(body) < 42
            or (len(body) - 22) % 10
        ):
            continue
        try:
            packet_fight, _, _, packet_actor, _, _ = struct.unpack_from(">iiiqBB", body)
            if (packet_fight, packet_actor) != (fight_id, actor_id):
                continue
            cells.update(
                struct.unpack_from(">iih", body, offset)
                for offset in range(22, len(body), 10)
            )
        except (TypeError, ValueError, struct.error):
            continue
    return cells


class TurnContinuation:
    def __init__(self, *, publication_required=False):
        self.publication_required = publication_required
        self.pending = None
        self.published = None
        self.publication_revision = None
        self.owner = None
        self.history_owner = None
        self.movement_destinations = set()
        self.turn_actions = []

    def discard(self):
        self.pending = self.published = None

    def begin(self, runtime, *, publication_revision=_UNSET):
        self.pending = None
        boundary = _boundary(runtime)
        owner = boundary[:3] if boundary is not None else None
        if owner != self.history_owner:
            self.history_owner = owner
            self.movement_destinations = set()
            self.turn_actions = []
            if owner is not None:
                position = getattr(runtime.fight.current, "position", None)
                if position is not None:
                    self.movement_destinations.add(tuple(position))
        if self.owner is not None and owner != self.owner:
            self.discard()
        self.owner = owner
        if self.published is not None and (
            boundary != self.published["boundary"]
            or (
                publication_revision is not _UNSET
                and publication_revision != self.publication_revision
            )
        ):
            self.discard()
        if publication_revision is not _UNSET:
            self.publication_revision = publication_revision

    def confirmed_actions(self, runtime):
        """Return only history published for this shared actor and turn."""
        boundary = _boundary(runtime)
        if boundary is None or boundary[:3] != self.history_owner:
            return set(), []
        return set(self.movement_destinations), deepcopy(self.turn_actions)

    def record_published_action(self, runtime, action, *, packets=()):
        """Remember an action only after Registry accepted its publication."""
        if not isinstance(action, dict) or action.get("type") not in (
            "move",
            "portal_travel",
            "cast",
        ):
            return
        fight = getattr(runtime, "fight", None)
        actor = getattr(fight, "current", None)
        if actor is None or self.history_owner != (
            getattr(fight, "id", None),
            getattr(actor, "id", None),
            getattr(fight, "turn_id", None),
        ):
            return
        position = tuple(actor.position)
        observed = dict(type=action["type"])
        if action["type"] == "cast" and type(action.get("spellId")) is int:
            observed["spellId"] = action["spellId"]
        if type(action.get("targetId")) is int:
            observed["targetId"] = action["targetId"]
        if isinstance(action.get("target"), (tuple, list)):
            observed["target"] = list(action["target"])
        elif action["type"] in ("move", "portal_travel"):
            observed["target"] = list(position)
        self.turn_actions.append(observed)
        if action["type"] == "cast":
            self.movement_destinations = {position}
        else:
            self.movement_destinations.update(
                published_movement_cells(fight.id, actor.id, packets)
            )
            self.movement_destinations.add(position)

    def stage(self, decision, source_binding, runtime):
        self.pending = None
        self.published = None
        tail = _tail(decision)
        boundary = _boundary(runtime)
        if (
            not tail
            or source_binding is None
            or boundary is None
            or boundary[:3] != source_binding["boundary"][:3]
            or decision.get("sourceKey") != source_binding["source"]
            or decision.get("rootState") != source_binding["root"]
            or decision.get("requestId") != source_binding["request"]
        ):
            return
        self.pending = dict(
            identity=source_binding["identity"],
            boundary=boundary,
            actions=tail,
            committedAction=deepcopy(decision["action"]),
            provenance=deepcopy(source_binding),
        )

    def confirm(self, runtime, *, action=_UNSET, publication_revision=_UNSET):
        staged, self.pending = self.pending, None
        self.published = None
        if (
            staged is not None
            and _boundary(runtime) == staged["boundary"]
            and (action is _UNSET or action == staged["committedAction"])
        ):
            self.published = staged
        if publication_revision is not _UNSET:
            self.publication_revision = publication_revision

    def proposal(self, runtime, source_binding):
        published = self.published
        if (
            published is None
            or source_binding is None
            or _boundary(runtime) != published["boundary"]
            or source_binding["boundary"] != published["boundary"]
            or source_binding["identity"] != published["identity"]
        ):
            self.discard()
            return None
        return dict(schema=SCHEMA, actions=deepcopy(published["actions"]))

    def owns(self, runtime):
        boundary = _boundary(runtime)
        return boundary is not None and self.owner == boundary[:3]


@contextmanager
def scope(*, publication_required=False, reuse=False):
    existing = current()
    if reuse and existing is not None:
        yield existing
        return
    holder = TurnContinuation(publication_required=publication_required)
    token = _HOLDER.set(holder)
    try:
        yield holder
    finally:
        holder.discard()
        _HOLDER.reset(token)


def turn_scope(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        runtime = args[0] if args else kwargs.get("runtime")
        publisher = current()
        shared = (
            publisher is not None
            and publisher.publication_required
            and publisher.owns(runtime)
        )
        holder = publisher if shared else TurnContinuation()
        iterator = function(*args, **kwargs)
        incoming, thrown = None, None
        try:
            while True:
                # A generator can remain suspended while another encounter
                # runs on the same thread. Activate its holder only while its
                # code executes; never leave a ContextVar token across yield.
                token = _HOLDER.set(holder)
                try:
                    if thrown is None:
                        outgoing = iterator.send(incoming)
                    else:
                        error, thrown = thrown, None
                        outgoing = iterator.throw(error)
                except StopIteration as completed:
                    return completed.value
                finally:
                    _HOLDER.reset(token)
                try:
                    incoming = yield outgoing
                except GeneratorExit:
                    token = _HOLDER.set(holder)
                    try:
                        iterator.close()
                    finally:
                        _HOLDER.reset(token)
                    raise
                except BaseException as error:
                    incoming, thrown = None, error
        finally:
            if not shared:
                holder.discard()

    return wrapped
