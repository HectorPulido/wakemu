"""Bounded private evidence of real bootstraps, mailboxes and send attempts.

History is out of band: it never changes SharedFight, consumes a gameplay
iterator, reads Store, or regenerates missing bootstrap bytes. Returned socket
calls establish attempts only, never client receipt or reconstruction.
"""
from collections import OrderedDict, deque
import os
import threading
import uuid

from .combat_shared import Session, Batch
from .combat_reproduction_state import encode_state

PROCESS_BOOT_ID = uuid.uuid4().hex
HISTORY_SCHEMA = "wakemu-combat-delivery-history-v1"
SIDECAR_SCHEMA = "wakemu-combat-delivery-incident-v1"
MAX_STREAMS = 128
MAX_EVENTS = 128
MAX_BYTES = 16 * 1024 * 1024
MAX_EVENT_BYTES = 2 * 1024 * 1024


def _enabled():
    if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
        return False
    from .combat_shared_incident_capture import shared_incidents_suppressed

    return not shared_incidents_suppressed()


def _session(session):
    if type(session) is not Session:
        raise ValueError("Actual delivery Session required")
    return dict(
        account_id=session.account_id,
        character_id=session.character_id,
        generation=session.generation,
        map_id=session.map_id,
        instance_id=session.instance_id,
    )


def _packets(packets):
    if type(packets) not in (list, tuple):
        raise ValueError("Delivery evidence requires a materialized packet batch")
    if len(packets) > 4096:
        raise ValueError("Delivery packet count exceeds evidence bound")
    result = tuple(packets)
    if any(
        type(row) is not tuple
        or len(row) != 2
        or type(row[0]) is not int
        or type(row[1]) is not bytes
        for row in result
    ):
        raise ValueError("Invalid actual delivery packet")
    return result


def _batches(batches):
    if type(batches) is Batch:
        batches = (batches,)
    if type(batches) not in (list, tuple):
        raise ValueError("Delivery evidence requires materialized batches")
    if len(batches) > 1024:
        raise ValueError("Delivery batch count exceeds evidence bound")
    if any(type(batch) is not Batch for batch in batches):
        raise ValueError("Actual typed mailbox batches required")
    return tuple(
        dict(sequence=batch.sequence, packets=_packets(batch.packets))
        for batch in batches
    )


def _size(value):
    if type(value) in (bytes, str):
        return len(value) + 16
    if type(value) is dict:
        return 32 + sum(_size(key) + _size(item) for key, item in value.items())
    if type(value) in (tuple, list):
        return 16 + sum(_size(item) for item in value)
    return 16


def _error(error):
    if error is None:
        return None
    message = str(error)
    return dict(
        type=type(error).__module__ + "." + type(error).__name__,
        message=message[:4096],
        message_truncated=len(message) > 4096,
    )


class DeliveryHistory:
    """A bounded FIFO stream inventory; eviction is explicit evidence loss."""

    def __init__(
        self,
        *,
        max_streams=MAX_STREAMS,
        max_events=MAX_EVENTS,
        max_bytes=MAX_BYTES,
        max_event_bytes=MAX_EVENT_BYTES
    ):
        if any(
            type(value) is not int or value < 1
            for value in (max_streams, max_events, max_bytes, max_event_bytes)
        ):
            raise ValueError("Positive delivery retention bounds required")
        self.max_streams, self.max_events = max_streams, max_events
        self.max_bytes, self.max_event_bytes = max_bytes, max_event_bytes
        self.streams, self.evicted = OrderedDict(), OrderedDict()
        self.bytes = self.evictions = self.counter = 0
        self.lock = threading.RLock()

    def record(self, fight_id, session, kind, **facts):
        fact = _session(session)
        key = (fight_id, session.account_id, session.generation)
        row = dict(kind=kind, **facts)
        size = _size(row) + 32
        with self.lock:
            if key not in self.streams:
                while len(self.streams) >= self.max_streams:
                    self._evict()
                self.streams[key] = dict(
                    session=fact,
                    bootstrap=None,
                    events=deque(),
                    gap=key in self.evicted,
                    oversized=False,
                    bytes=0,
                )
            stream = self.streams[key]
            self.counter += 1
            row["observation_id"] = self.counter
            if size > self.max_event_bytes or size > self.max_bytes:
                stream["gap"] = stream["oversized"] = True
                return None
            while self.bytes + size > self.max_bytes and len(self.streams) > 1:
                # Protect this operation's stream while evicting old peers.
                if next(iter(self.streams)) == key:
                    self.streams.move_to_end(key)
                self._evict()
            while stream["events"] and (
                len(stream["events"]) >= self.max_events
                or self.bytes + size > self.max_bytes
            ):
                old, old_size = stream["events"].popleft()
                stream["bytes"] -= old_size
                self.bytes -= old_size
                stream["gap"] = True
                if stream["bootstrap"] is old:
                    stream["bootstrap"] = None
            stream["events"].append((row, size))
            stream["bytes"] += size
            self.bytes += size
            if kind == "bootstrap":
                stream["bootstrap"] = row
            return row["observation_id"]

    def _evict(self):
        key, stream = self.streams.popitem(last=False)
        self.bytes -= stream["bytes"]
        self.evictions += 1
        self.evicted[key] = True
        while len(self.evicted) > self.max_streams:
            self.evicted.popitem(last=False)

    def snapshot(self, fight_id, sessions):
        with self.lock:
            result = []
            for session in sessions:
                fact = _session(session)
                key = (fight_id, session.account_id, session.generation)
                stream = self.streams.get(key)
                bootstrap = None if stream is None else stream["bootstrap"]
                # Freeze facts through typed serialization, detached from future
                # queue mutations and diagnostic retention changes.
                result.append(
                    dict(
                        session=fact,
                        bootstrap=bootstrap,
                        events=()
                        if stream is None
                        else tuple(row for row, size in stream["events"]),
                        bootstrap_missing=bootstrap is None,
                        history_gap=bootstrap is None
                        or stream is None
                        or stream["gap"],
                        history_evicted=key in self.evicted,
                        oversized=False if stream is None else stream["oversized"],
                    )
                )
            return encode_state(
                dict(
                    schema=HISTORY_SCHEMA,
                    process_boot_id=PROCESS_BOOT_ID,
                    fight_id=fight_id,
                    streams=tuple(result),
                    eviction_count=self.evictions,
                    boundary="observed-bytes-and-attempts-not-client-reconstruction",
                )
            )


_HISTORY = DeliveryHistory()


def _gap(fight_id, session, reason):
    try:
        if not _enabled():
            return
        _HISTORY.record(fight_id, session, "evidence_gap", reason=reason)
        with _HISTORY.lock:
            stream = _HISTORY.streams.get(
                (fight_id, session.account_id, session.generation)
            )
            if stream is not None:
                stream["gap"] = True
    except Exception:
        pass


def record_bootstrap(
    fight_id, session, packets, *, sequence=None, producer, previous_generation=None
):
    try:
        if _enabled():
            _HISTORY.record(
                fight_id,
                session,
                "bootstrap",
                packets=_packets(packets),
                sequence=sequence,
                producer=producer,
                previous_generation=previous_generation,
            )
    except Exception:
        _gap(fight_id, session, "bootstrap_observation_failed")


def record_enqueue(fight_id, session, batches):
    try:
        if _enabled():
            _HISTORY.record(fight_id, session, "enqueue", batches=_batches(batches))
    except Exception:
        _gap(fight_id, session, "enqueue_observation_failed")


def record_drain(fight_id, session, batches, *, producer="drain", dispatch_id=None):
    try:
        if _enabled():
            _HISTORY.record(
                fight_id,
                session,
                "drain",
                batches=_batches(batches),
                producer=producer,
                dispatch_id=dispatch_id,
            )
    except Exception:
        _gap(fight_id, session, "drain_observation_failed")


def delivery_history(shared):
    """Preceding available evidence only; never fills gaps with new snapshots."""
    if not _enabled():
        return None
    return _HISTORY.snapshot(shared.fight.id, tuple(shared.participants.values()))


class DispatchObservation:
    def __init__(self, fight_id, recipients, *, producer):
        self.fight_id, self.producer = fight_id, producer
        self.dispatch_id = uuid.uuid4().hex
        self.plan = tuple(
            dict(session=_session(session), batches=_batches(batches))
            for session, batches in recipients
        )
        if len(self.plan) > MAX_STREAMS or _size(self.plan) > MAX_EVENT_BYTES:
            raise ValueError("Dispatch evidence exceeds bounded plan size")
        self.attempts = []
        for session, batches in recipients:
            record_drain(
                fight_id,
                session,
                batches,
                producer=producer,
                dispatch_id=self.dispatch_id,
            )

    def attempt(self, session, batches, *, error=None):
        try:
            row = dict(
                session=_session(session),
                batches=_batches(batches),
                status="returned" if error is None else "raised",
                error=_error(error),
            )
            boundary = (
                "serialized-registry-callback-completion"
                if self.producer == "dispatch_connected"
                else "callback-completion-without-invocation-order"
            )
            ordinal = _HISTORY.record(
                self.fight_id,
                session,
                "dispatch_attempt",
                dispatch_id=self.dispatch_id,
                batches=row["batches"],
                status=row["status"],
                error=row["error"],
                ordinal_boundary=boundary,
            )
            # Registry holds dispatch_lock across the entire original callback
            # loop: completions establish its serial per-stream attempt order.
            # This is not a clock or an inferred UUID/file ordering.
            row.update(observation_id=ordinal, ordinal_boundary=boundary)
            self.attempts.append(row)
        except Exception:
            _gap(self.fight_id, session, "dispatch_attempt_observation_failed")

    def finish(self):
        try:
            root = os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
            if not root or not _enabled():
                return
            if (
                not any(row["error"] is not None for row in self.attempts)
                and os.environ.get("WAKFU_COMBAT_INCIDENT_MODE", "failures") != "all"
            ):
                return
            from .combat_incident_capture import _enqueue

            _enqueue(
                root,
                dict(
                    schema=SIDECAR_SCHEMA,
                    incident_id=self.dispatch_id,
                    process_boot_id=PROCESS_BOOT_ID,
                    fight_id=self.fight_id,
                    producer=self.producer,
                    plan=encode_state(self.plan),
                    attempts=encode_state(tuple(self.attempts)),
                    boundary="actual-delivery-callback-return-not-client-receipt",
                    client_receipt_confirmed=False,
                    replay_qualified=False,
                ),
            )
        except Exception:
            pass


def begin_dispatch(fight_id, recipients, *, producer="dispatch_connected"):
    try:
        if _enabled() and recipients:
            return DispatchObservation(fight_id, recipients, producer=producer)
    except Exception:
        if type(recipients) in (tuple, list):
            for session, batches in recipients[:MAX_STREAMS]:
                _gap(fight_id, session, "dispatch_plan_observation_failed")
    return None


def record_dispatch_attempt(observation, session, batches, *, error=None):
    try:
        if observation is not None and _enabled():
            observation.attempt(session, batches, error=error)
    except Exception:
        pass


def finish_dispatch(observation):
    try:
        if observation is not None and _enabled():
            observation.finish()
    except Exception:
        pass


def begin_direct_bootstrap(fight_id, session, packets):
    """The caller sends exactly its existing materialized native bootstrap."""
    try:
        if not _enabled():
            return None
        packets = _packets(packets)
        record_bootstrap(
            fight_id, session, packets, producer="starter-placement-direct-send"
        )
        if _size(packets) > MAX_EVENT_BYTES:
            return None
        # Direct bootstrap has no shared batch sequence: never invent one.
        observation = DispatchObservation(
            fight_id, (), producer="starter-placement-direct-send"
        )
        observation.plan = (
            dict(session=_session(session), sequence=None, packets=packets),
        )
        observation.direct_session, observation.direct_packets = session, packets
        return observation
    except Exception:
        _gap(fight_id, session, "direct_bootstrap_observation_failed")
        return None


def finish_direct_bootstrap(observation, *, error=None):
    try:
        if observation is None or not _enabled():
            return
        row = dict(
            session=_session(observation.direct_session),
            sequence=None,
            packets=observation.direct_packets,
            status="returned" if error is None else "raised",
            error=_error(error),
        )
        boundary = "direct-bootstrap-send-loop-completion-without-invocation-order"
        ordinal = _HISTORY.record(
            observation.fight_id,
            observation.direct_session,
            "dispatch_attempt",
            dispatch_id=observation.dispatch_id,
            ordinal_boundary=boundary,
            **{key: value for key, value in row.items() if key != "session"}
        )
        row.update(observation_id=ordinal, ordinal_boundary=boundary)
        observation.attempts.append(row)
        observation.finish()
    except Exception:
        pass
