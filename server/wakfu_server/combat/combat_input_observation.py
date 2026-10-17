"""Passive request-local input evidence; never changes gameplay inputs.

The disabled path does not read RNG state or any additional clocks. Diagnostic
errors and bounds make evidence explicitly incomplete without raising into the
gameplay operation. Snapshots contain private facts and belong in private files.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import math
import random
import time


_active = ContextVar("combat_input_observation", default=None)
_replaying = ContextVar("combat_input_replay", default=None)


class InputReplayMismatch(RuntimeError):
    """Observed inputs cannot reproduce this execution; infrastructure error."""


class _InputReplay:
    def __init__(self, snapshot):
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema") != "wakemu-combat-observed-inputs-v1"
        ):
            raise InputReplayMismatch("Unsupported observed input snapshot")
        if (
            set(snapshot) != {"schema", "events", "rng_streams", "incomplete"}
            or snapshot["incomplete"] != []
        ):
            raise InputReplayMismatch("Incomplete observed input evidence")
        if not isinstance(snapshot["events"], list) or not isinstance(
            snapshot["rng_streams"], list
        ):
            raise InputReplayMismatch("Malformed observed input evidence")
        self.events = []
        self.streams = {}
        self.final_states = {}
        self.index = 0
        self.ownership_known = True
        self.ownership_unknown = []
        for expected_id, stream in enumerate(snapshot["rng_streams"]):
            if (
                not isinstance(stream, dict)
                or set(stream) != {"stream_id", "initial_state", "final_state"}
                or type(stream["stream_id"]) is not int
                or stream["stream_id"] != expected_id
            ):
                raise InputReplayMismatch("Malformed observed RNG stream")
            try:
                rng = random.Random(0)
                rng.setstate(stream["initial_state"])
                validator = random.Random(0)
                validator.setstate(stream["final_state"])
            except Exception as error:
                raise InputReplayMismatch("Invalid observed RNG state") from error
            self.streams[expected_id] = rng
            self.final_states[expected_id] = deepcopy(stream["final_state"])
        bound_streams = set()
        for sequence, event in enumerate(snapshot["events"], 1):
            if (
                not isinstance(event, dict)
                or type(event.get("sequence")) is not int
                or event["sequence"] != sequence
                or type(event.get("label")) is not str
            ):
                raise InputReplayMismatch("Malformed observed input event")
            kind = event.get("kind")
            if type(kind) is not str:
                raise InputReplayMismatch("Malformed observed input kind")
            if kind == "rng":
                identity = event.get("stream_id")
                base_fields = {"sequence", "kind", "label", "stream_id", "state"}
                if (
                    set(event) not in (base_fields, base_fields | {"external"})
                    or type(identity) is not int
                    or identity not in self.streams
                ):
                    raise InputReplayMismatch("Observed RNG binding has no stream")
                external = event.get("external")
                if external is not None and type(external) is not bool:
                    raise InputReplayMismatch("Invalid observed RNG ownership")
                if external is None:
                    self._unknown_ownership("capture", event)
                bound_streams.add(identity)
            elif kind == "clock":
                value = event.get("value")
                if (
                    set(event) != {"sequence", "kind", "label", "value"}
                    or type(value) not in (int, float)
                    or (type(value) is float and not math.isfinite(value))
                ):
                    raise InputReplayMismatch("Invalid observed gameplay clock")
            elif kind in {"fact", "authority", "catalog", "failure"}:
                continue
            else:
                raise InputReplayMismatch("Unknown observed input event kind")
            self.events.append(deepcopy(event))
        if bound_streams != set(self.streams):
            raise InputReplayMismatch("Observed RNG stream has no binding")

    def _peek(self, kind, label):
        if self.index >= len(self.events):
            raise InputReplayMismatch("Execution requested an unobserved input")
        event = self.events[self.index]
        if event["kind"] != kind or event["label"] != label:
            raise InputReplayMismatch("Observed input order or label differs")
        return event

    def _next(self, kind, label):
        event = self._peek(kind, label)
        self.index += 1
        return event

    def rng_argument(self, label):
        event = self._peek("rng", label)
        external = event.get("external")
        if type(external) is not bool:
            raise InputReplayMismatch("RNG argument ownership is unknown")
        rng = self.streams[event["stream_id"]]
        if rng.getstate() != event["state"]:
            raise InputReplayMismatch("Observed RNG argument state differs")
        return rng if external else None

    def prepare_rng_argument(self, label, fallback):
        # Public prepare functions may reject a malformed request before they
        # construct/bind any RNG. Peek ahead without consuming intervening
        # clocks; the actual observe_rng hook remains strictly ordered and
        # validates the exact stream state if execution reaches that seam.
        for event in self.events[self.index :]:
            if event["kind"] != "rng" or event["label"] != label:
                continue
            external = event.get("external")
            if type(external) is not bool:
                raise InputReplayMismatch("RNG argument ownership is unknown")
            return self.streams[event["stream_id"]] if external else None
        return fallback

    def _unknown_ownership(self, source, event):
        self.ownership_known = False
        self.ownership_unknown.append(
            dict(source=source, sequence=event["sequence"], label=event["label"])
        )

    def rng(self, label, external):
        if external is not None and type(external) is not bool:
            raise InputReplayMismatch("Invalid replay RNG ownership")
        event = self._next("rng", label)
        if external is None:
            self._unknown_ownership("replay", event)
        elif event.get("external") is not None and event["external"] != external:
            raise InputReplayMismatch("Observed RNG ownership differs")
        rng = self.streams[event["stream_id"]]
        if rng.getstate() != event["state"]:
            raise InputReplayMismatch("Observed RNG binding state differs")
        return rng

    def clock(self, label):
        return self._next("clock", label)["value"]

    def complete(self):
        if self.index != len(self.events):
            raise InputReplayMismatch("Execution left observed inputs unused")
        for identity, rng in self.streams.items():
            if rng.getstate() != self.final_states[identity]:
                raise InputReplayMismatch("Observed final RNG state differs")


@contextmanager
def replay_combat_inputs(snapshot):
    """Use exact observed RNG/clock inputs in an isolated replay execution.

    Enter after diagnostic provider preparation, immediately around the actual
    action. Authority and catalog equivalence require separate verification.
    The yielded receipt's ownership_known must be true before RNG ownership
    can be qualified; historical or unannotated bindings remain unknown.
    Never install this context for live gameplay or silently repair a mismatch.
    """
    if _replaying.get() is not None:
        raise InputReplayMismatch("Nested combat input replay is unsupported")
    replay = _InputReplay(snapshot)
    token = _replaying.set(replay)
    mismatched = False
    try:
        yield replay
    except InputReplayMismatch:
        mismatched = True
        raise
    finally:
        _replaying.reset(token)
        if not mismatched:
            replay.complete()


class CombatInputObservation:
    def __init__(self, limit=512, max_value_bytes=1_000_000):
        if type(limit) is not int or limit < 1:
            raise ValueError("Positive combat observation limit required")
        if type(max_value_bytes) is not int or max_value_bytes < 1:
            raise ValueError("Positive combat observation byte bound required")
        self.limit = limit
        self.max_value_bytes = max_value_bytes
        self.events = []
        self.incomplete = []
        self._streams = []
        self._stream_ids = {}

    def _missing(self, reason):
        if reason not in self.incomplete and len(self.incomplete) < 32:
            self.incomplete.append(reason)

    def _append(self, kind, label, **facts):
        if len(self.events) >= self.limit:
            self._missing("event_limit_exceeded")
            return
        self.events.append(
            dict(sequence=len(self.events) + 1, kind=kind, label=label, **facts)
        )

    def rng(self, label, rng, external=None):
        if external is not None and type(external) is not bool:
            raise ValueError("Invalid RNG ownership observation")
        if len(self.events) >= self.limit:
            self._missing("event_limit_exceeded")
            return
        state = rng.getstate()
        identity = id(rng)
        stream_id = self._stream_ids.get(identity)
        if stream_id is None:
            stream_id = len(self._streams)
            self._stream_ids[identity] = stream_id
            # Keep a strong scoped reference: Python IDs cannot be recycled.
            self._streams.append((rng, deepcopy(state)))
        self._append(
            "rng", label, stream_id=stream_id, state=deepcopy(state), external=external
        )

    def value(self, kind, label, value, **facts):
        if len(self.events) >= self.limit:
            self._missing("event_limit_exceeded")
            return
        budget = [self.max_value_bytes, 10000]
        active = set()

        def plain(item):
            budget[1] -= 1
            budget[0] -= len(item) if type(item) in (bytes, str) else 16
            if budget[0] < 0 or budget[1] < 0:
                raise ValueError("Observation value exceeds bounds")
            if item is None or type(item) in (bool, int, str, bytes):
                return item
            if type(item) is float and math.isfinite(item):
                return item
            if type(item) not in (dict, list, tuple, set, frozenset):
                raise TypeError("Observation requires typed plain facts")
            if id(item) in active:
                raise ValueError("Observation facts must be acyclic")
            active.add(id(item))
            try:
                if type(item) is dict:
                    return {plain(key): plain(value) for key, value in item.items()}
                return type(item)(plain(value) for value in item)
            finally:
                active.remove(id(item))

        self._append(kind, label, value=plain(value), **facts)

    def failure(self, label, error):
        self._append(
            "failure",
            label,
            exception_type=type(error).__module__ + "." + type(error).__name__,
        )

    def snapshot(self):
        """Plain data, including current/final state of every observed RNG."""
        streams = []
        for stream_id, (rng, initial) in enumerate(self._streams):
            try:
                final = deepcopy(rng.getstate())
            except Exception as error:
                self._missing("rng_final_state_failed:" + type(error).__name__)
                final = None
            streams.append(
                dict(
                    stream_id=stream_id,
                    initial_state=deepcopy(initial),
                    final_state=final,
                )
            )
        return dict(
            schema="wakemu-combat-observed-inputs-v1",
            events=deepcopy(self.events),
            rng_streams=streams,
            incomplete=list(self.incomplete),
        )


def _observe(method, *args, **kwargs):
    observation = _active.get()
    if observation is None:
        return
    try:
        getattr(observation, method)(*args, **kwargs)
    except Exception as error:
        # Do not call an external diagnostic sink, or stringify an exception
        # which could contain credentials. Recording failure is best effort.
        try:
            observation._missing("observer_failed:" + type(error).__name__)
        except Exception:
            pass


@contextmanager
def observe_combat_inputs(*, limit=512, max_value_bytes=1_000_000):
    observation = CombatInputObservation(limit, max_value_bytes)
    token = _active.set(observation)
    try:
        yield observation
    except BaseException as error:
        observe_failure("operation", error)
        raise
    finally:
        _active.reset(token)


def observe_rng(label, rng, *, external=None):
    replay = _replaying.get()
    if replay is not None:
        rng = replay.rng(label, external)
    _observe("rng", label, rng, external=external)
    return rng


def replay_rng_argument(expected_label, fallback):
    """Select the original caller's RNG argument before rollback decorators.

    Peeking never consumes a binding or draws randomness. The engine's later
    observe_rng hook still validates and consumes that binding. Without a tape
    return the caller's original fallback object, preserving legacy execution.
    """
    replay = _replaying.get()
    return fallback if replay is None else replay.rng_argument(expected_label)


def replay_prepare_rng_argument(expected_label, fallback):
    """Defer a public prepare entry's binding until its actual engine hook.

    A decoder can reject before creating an RNG. In that case an absent future
    binding does not preempt its real error. If execution instead reaches an
    unobserved binding, observe_rng still raises InputReplayMismatch; missing
    evidence cannot become a successful gameplay rejection.
    """
    replay = _replaying.get()
    return (
        fallback
        if replay is None
        else replay.prepare_rng_argument(expected_label, fallback)
    )


@contextmanager
def suspend_input_replay():
    """Trusted diagnostic binding only; never wrap actual gameplay execution."""
    token = _replaying.set(None)
    try:
        yield
    finally:
        _replaying.reset(token)


def observe_clock(label, value):
    replay = _replaying.get()
    if replay is not None:
        value = replay.clock(label)
    _observe("value", "clock", label, value)
    return value


def wall_time(label):
    if _replaying.get() is not None:
        return observe_clock(label, None)
    return observe_clock(label, time.time())


def wall_time_ns(label):
    if _replaying.get() is not None:
        return observe_clock(label, None)
    return observe_clock(label, time.time_ns())


def observe_failure(label, error):
    _observe(
        "_append",
        "failure",
        label,
        exception_type=type(error).__module__ + "." + type(error).__name__,
    )


def observe_authority(label, value):
    _observe("value", "authority", label, value)
    return value


def observe_fact(label, value):
    _observe("value", "fact", label, value)
    return value


def observe_catalog(
    operation, path, value, *, revision=None, collection=None, record_key=None
):
    _observe(
        "value",
        "catalog",
        operation,
        value,
        path=str(path),
        revision=revision,
        collection=collection,
        record_key=record_key,
    )
    return value
