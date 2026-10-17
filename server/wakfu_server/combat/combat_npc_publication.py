"""Bounded private NPC provenance and real Registry publication reproduction.

A chosen action is recomputed by NativeOracle before its fresh Transition is
published. Recorded packets are comparison evidence, never an attack producer.
Fallback server turn-end is a distinct trusted runtime operation.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import importlib
import inspect
import json
import logging
import os
import threading
import uuid
import weakref

from .combat_input_observation import (
    InputReplayMismatch,
    observe_combat_inputs,
    replay_combat_inputs,
)
from .combat_reproduction_state import encode_state as _encode_state, decode_state
from .combat_shared_reproduction import (
    capture_shared_state,
    restore_shared_state,
    lease_result,
)

SCHEMA = "wakemu-combat-npc-publication-v1"
RECIPE = "native-npc-publication-v1"
BARRIER_SCHEMA = "wakemu-combat-npc-private-end-turn-v1"
CHOSEN = "chosen-native-commit"
FALLBACK = "live-server-end-turn"
MAX_PENDING_BYTES = 64 * 1024 * 1024
MAX_CAPSULE_BYTES = 16 * 1024 * 1024
MAX_PENDING_RUNTIMES = 16
MAX_LEASES = 512
_PENDING = OrderedDict()
_PENDING_LOCK = threading.RLock()
_ACTIVE = ContextVar("npc_publication_capture", default=None)
_REPLAY = ContextVar("npc_publication_replay", default=False)
LOGGER = logging.getLogger(__name__)


def encode_state(value):
    return _encode_state(value, preserve_scalars=True)


class UnsupportedNPCPublication(InputReplayMismatch):
    """Missing provenance/provider data is never a reproduced attack result."""


def _forget(reference):
    with _PENDING_LOCK:
        _PENDING.pop(reference, None)


def remember_private_commit(runtime, receipt):
    """Retain one immutable accepted capsule per runtime under global bounds."""
    from .combat_npc_reproduction import SCHEMA as NPC_SCHEMA

    if (
        type(receipt) is not dict
        or receipt.get("schema") not in (NPC_SCHEMA, BARRIER_SCHEMA)
        or receipt.get("status") != "accepted"
    ):
        return False
    raw = json.dumps(receipt, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > min(MAX_CAPSULE_BYTES, MAX_PENDING_BYTES):
        return False
    reference = weakref.ref(runtime, _forget)
    with _PENDING_LOCK:
        _PENDING.pop(reference, None)
        while _PENDING and (
            len(_PENDING) >= MAX_PENDING_RUNTIMES
            or sum(len(value) for value in _PENDING.values()) + len(raw)
            > MAX_PENDING_BYTES
        ):
            _PENDING.popitem(last=False)
        _PENDING[reference] = raw
    return True


def pending_private_commit(runtime, *, consume=False):
    reference = weakref.ref(runtime)
    with _PENDING_LOCK:
        raw = _PENDING.pop(reference, None) if consume else _PENDING.get(reference)
    return None if raw is None else json.loads(raw)


def pending_usage():
    with _PENDING_LOCK:
        return dict(
            runtimes=len(_PENDING), bytes=sum(len(value) for value in _PENDING.values())
        )


def _error(error):
    return (
        None
        if error is None
        else dict(
            type=type(error).__module__ + "." + type(error).__name__, message=str(error)
        )
    )


def _providers(runtime):
    from .combat_npc_reproduction import _PROVIDER_FIELDS, _provider

    return {
        field: _provider(getattr(runtime, field, None)) for field in _PROVIDER_FIELDS
    }


def _turn_start_policy(runtime, providers):
    identity = providers["turn_start_provider"]
    if identity is None or identity["module"].endswith(".native.native_oracle"):
        return {}
    ready = (
        identity["module"] == "wakfu_server.combat_session_adapter"
        and identity["qualname"]
        == "CombatSessionAdapter.ready_transition.<locals>.turn_start"
    )
    if ready:
        callback = runtime.turn_start_provider
        cells = dict(zip(callback.__code__.co_freevars, callback.__closure__ or ()))
        policy = {}
        for output, source in (
            ("native_events", "fight_start"),
            ("area_callbacks", "area_callbacks"),
        ):
            cell = cells.get(source)
            if cell is None or type(cell.cell_contents) is not bool:
                raise UnsupportedNPCPublication(
                    "Missing actual ready turn-start policy"
                )
            policy[output] = cell.cell_contents
        return policy
    local = (
        identity["module"] in ("local_game_server", "__main__")
        and identity["qualname"] == "session.<locals>.area_boundary_provider"
    )
    if local:
        # These two explicit reads are the known provider's policy expressions;
        # never retain the environment or any unconsumed configuration values.
        policy = {}
        for output, name in (
            ("native_events", "WAKFU_COMBAT_START_EVENTS"),
            ("area_callbacks", "WAKFU_NATIVE_AREA_CALLBACKS"),
        ):
            value = os.environ.get(name, "1")
            if value not in ("0", "1"):
                raise UnsupportedNPCPublication(
                    "Invalid actual local turn-start policy"
                )
            policy[output] = value == "1"
        return policy
    raise UnsupportedNPCPublication("Unqualified turn-start policy provider")


def _fallback_facts(runtime):
    from .combat_npc_reproduction import _native_stats_inputs, _rail_inputs, ENVIRONMENT

    providers = _providers(runtime)
    native = None
    for field in ("turn_start_provider", "turn_end_provider"):
        callback = getattr(runtime, field, None)
        owner = getattr(callback, "__self__", None)
        if (
            owner is not None
            and type(owner).__name__ == "NativeOracle"
            and type(owner).__module__.endswith(".native.native_oracle")
        ):
            if owner.outcome_features_provider is not None:
                raise UnsupportedNPCPublication(
                    "Custom native fallback feature provider"
                )
            facts = dict(
                authorities=owner.authorities(runtime), flags=deepcopy(owner.flags)
            )
            if native is not None and native != facts:
                raise UnsupportedNPCPublication(
                    "Conflicting native fallback authorities"
                )
            native = facts
    if native is not None:
        native["authorities"].pop("outcomeFeaturesProvider", None)
        flags = native["flags"]
        if set(flags) - {
            "native_start_events",
            "native_area_callbacks",
            "native_environment",
        }:
            raise UnsupportedNPCPublication("Unknown native fallback flags")
        environment = flags.get("native_environment", {})
        if (
            type(environment) is not dict
            or set(environment) - set(ENVIRONMENT)
            or any(value not in ("0", "1") for value in environment.values())
        ):
            # Reject before serializing unknown environment names or values.
            raise UnsupportedNPCPublication("Unknown native fallback environment")
    return dict(
        providers=providers,
        native=native,
        turn_policy=_turn_start_policy(runtime, providers),
        rail_inputs=_rail_inputs(runtime),
        stats_inputs=_native_stats_inputs(getattr(runtime, "stats_serializer", None)),
    )


class PrivateBarrierCapture:
    def __init__(self, runtime, actor_id, turn_id):
        from .combat_incident_capture import _identity
        from .combat_reproduction import capture_clocks
        from .combat_npc_reproduction import ENVIRONMENT, sdk_identity, _sdk_modules

        self.runtime = runtime
        self.packets_value = ()
        self.before = encode_state(
            dict(
                runtime=runtime,
                actor_id=actor_id,
                turn_id=turn_id,
                facts=_fallback_facts(runtime),
            )
        )
        self.identity = deepcopy(_identity())
        self.sdk_source = sdk_identity(_sdk_modules()[2])
        self.clocks = capture_clocks()
        self.policies = {
            key: os.environ.get(key, value) for key, value in ENVIRONMENT.items()
        }
        if any(value not in ("0", "1") for value in self.policies.values()):
            raise UnsupportedNPCPublication(
                "Invalid private barrier execution policies"
            )

    def packets(self, packets):
        try:
            if type(packets) in (tuple, list):
                self.packets_value = tuple(packets)
        except Exception:
            pass

    def receipt(self, observation, error):
        snapshot = observation.snapshot()
        return dict(
            schema=BARRIER_SCHEMA,
            incident_id=uuid.uuid4().hex,
            before=self.before,
            after=encode_state(dict(runtime=self.runtime, packets=self.packets_value)),
            identity=self.identity,
            sdk_source=self.sdk_source,
            clocks=self.clocks,
            policies=self.policies,
            observations=encode_state(snapshot),
            status="accepted" if error is None else "raised",
            error=_error(error),
            incomplete=list(snapshot["incomplete"]),
        )


@contextmanager
def npc_fallback_scope(runtime, actor_id, turn_id):
    """Observe the real private action-budget barrier before it is published."""
    if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR") or _REPLAY.get():
        yield None
        return
    try:
        capture = PrivateBarrierCapture(runtime, actor_id, turn_id)
    except Exception as error:
        LOGGER.warning(
            "npc_private_barrier_capture_failed type=%s", type(error).__name__
        )
        yield None
        return
    error = None
    with observe_combat_inputs(limit=8192) as observation:
        try:
            yield capture
        except BaseException as failure:
            error = failure
            raise
        finally:
            try:
                receipt = capture.receipt(observation, error)
                if error is None:
                    remember_private_commit(runtime, receipt)
            except Exception as failure:
                LOGGER.warning(
                    "npc_private_barrier_capture_failed type=%s", type(failure).__name__
                )


class NPCPublicationCapture:
    def __init__(
        self,
        shared,
        registry,
        actor_id,
        expected_sequence,
        *,
        prepared_runtime,
        prepared_packets,
        initiating_session,
        recipe,
        turn_id
    ):
        from .combat_incident_capture import _identity
        from .combat_reproduction import capture_clocks
        from .combat_npc_reproduction import ENVIRONMENT, sdk_identity

        self.shared, self.registry = shared, registry
        self.prepared_runtime = prepared_runtime
        self.identity = deepcopy(_identity())
        self.clocks = capture_clocks()
        self.policies = {
            key: os.environ.get(key, value) for key, value in ENVIRONMENT.items()
        }
        self.incomplete = []
        if any(value not in ("0", "1") for value in self.policies.values()):
            self.policies = {}
            self.incomplete.append("invalid_publication_execution_policies")
        self.leases = []
        self.transition_state = None
        self.return_value = None
        self.return_recorded = False
        self.private = None
        self.prepared = None
        self.fallback = None
        self.sdk_source = None
        self.request = encode_state(
            dict(
                actor_id=actor_id,
                expected_sequence=expected_sequence,
                initiating_session=initiating_session,
                recipe=recipe,
                turn_id=turn_id,
            )
        )
        self.before = None
        try:
            # Direct server fallback executes on Registry's deepcopy of this
            # source. Preserve object insertion order and aliases before that
            # copy, just as the chosen private checkpoint does.
            self.before = capture_shared_state(
                shared, registry=registry, preserve_scalars=True
            )
        except Exception as failure:
            self.incomplete.append(
                "before_shared_capture_failed:" + type(failure).__name__
            )
        from .combat_shared import Registry

        if type(registry) is not Registry or any(
            name in vars(registry)
            for name in (
                "_broadcast",
                "_prepare_accepted",
                "_accepted_ack",
                "_synchronize_defeated_current",
            )
        ):
            self.incomplete.append("unqualified_registry_publication_provider")
        if recipe == CHOSEN:
            if prepared_runtime is None or type(prepared_packets) not in (tuple, list):
                self.incomplete.append("missing_prepared_native_transition")
            else:
                self.prepared = encode_state(
                    dict(runtime=prepared_runtime, packets=tuple(prepared_packets))
                )
                self.private = pending_private_commit(prepared_runtime)
                if self.private is None:
                    self.incomplete.append("missing_bounded_private_commit_capsule")
                elif self.private["after"] != self.prepared:
                    self.incomplete.append("private_commit_transition_mismatch")
                else:
                    self.sdk_source = self.private["sdk_source"]
                    self.incomplete.extend(self.private["incomplete"])
        elif recipe == FALLBACK:
            if prepared_runtime is not None:
                self.prepared = encode_state(
                    dict(runtime=prepared_runtime, packets=tuple(prepared_packets))
                )
                self.private = pending_private_commit(prepared_runtime)
                if (
                    self.private is None
                    or self.private.get("schema") != BARRIER_SCHEMA
                    or self.private["after"] != self.prepared
                ):
                    self.incomplete.append(
                        "missing_matching_private_server_end_capsule"
                    )
                else:
                    self.sdk_source = self.private["sdk_source"]
                    self.incomplete.extend(self.private["incomplete"])
            else:
                try:
                    self.fallback = encode_state(_fallback_facts(shared.runtime))
                    if decode_state(self.fallback)["native"] is not None:
                        from .combat_npc_reproduction import _sdk_modules

                        self.sdk_source = sdk_identity(_sdk_modules()[2])
                except Exception as failure:
                    self.incomplete.append(
                        "fallback_authority_capture_failed:" + type(failure).__name__
                    )
        else:
            self.incomplete.append("unknown_server_publication_recipe")

    def transition(self, candidate, runtime, packets):
        try:
            if runtime.fight is not candidate or type(packets) not in (tuple, list):
                self.incomplete.append("invalid_actual_publication_transition")
                return
            self.transition_state = encode_state(
                dict(runtime=runtime, packets=tuple(packets))
            )
            if self.prepared is not None and self.transition_state != self.prepared:
                self.incomplete.append("actual_transition_differs_from_prepared_commit")
        except Exception as error:
            self.incomplete.append("transition_capture_failed:" + type(error).__name__)

    def lease(self, session, *, result=None, error=None):
        if len(self.leases) >= MAX_LEASES:
            self.incomplete.append("lease_observation_limit_exceeded")
            return
        self.leases.append(lease_result(session, result=result, error=error))

    def result(self, value):
        try:
            if type(value) is not int:
                self.incomplete.append("invalid_publication_return")
                return
            self.return_value, self.return_recorded = value, True
        except Exception:
            pass

    def receipt(self, observation, error):
        if error is None and not self.return_recorded:
            self.incomplete.append("publication_return_not_observed")
        after = None
        try:
            after = capture_shared_state(self.shared, registry=self.registry)
        except Exception as failure:
            self.incomplete.append(
                "after_shared_capture_failed:" + type(failure).__name__
            )
        return dict(
            schema=SCHEMA,
            incident_id=uuid.uuid4().hex,
            identity=self.identity,
            sdk_source=self.sdk_source,
            request=self.request,
            before=self.before,
            after=after,
            prepared=self.prepared,
            private_commit=self.private,
            fallback=self.fallback,
            transition=self.transition_state,
            lease_observations=encode_state(self.leases),
            observations=encode_state(observation.snapshot()),
            clocks=self.clocks,
            policies=self.policies,
            return_value=self.return_value,
            return_recorded=self.return_recorded,
            error=_error(error),
            status="returned" if error is None else "raised",
            incomplete=list(
                dict.fromkeys(self.incomplete + observation.snapshot()["incomplete"])
            ),
            replay_qualified=False,
            dispatch_observed=False,
            delivery_boundary="registry_execute_server_mailboxes_after_shared_postprocessing",
        )


def observe_npc_publication_lease(session, *, result=None, error=None):
    capture = _ACTIVE.get()
    if capture is not None:
        try:
            capture.lease(session, result=result, error=error)
        except Exception:
            capture.incomplete.append("lease_observation_failed")


@contextmanager
def npc_publication_scope(
    shared,
    registry,
    actor_id,
    expected_sequence,
    *,
    prepared_runtime=None,
    prepared_packets=(),
    initiating_session=None,
    recipe=CHOSEN,
    turn_id=None
):
    """Enter under shared.lock before sequence/actor validation; never rerun live."""
    root = os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
    if not root or _REPLAY.get():
        yield None
        return
    try:
        capture = NPCPublicationCapture(
            shared,
            registry,
            actor_id,
            expected_sequence,
            prepared_runtime=prepared_runtime,
            prepared_packets=prepared_packets,
            initiating_session=initiating_session,
            recipe=recipe,
            turn_id=turn_id,
        )
    except Exception as error:
        LOGGER.warning(
            "npc_publication_capture_setup_failed type=%s", type(error).__name__
        )
        yield None
        return
    error = None
    token = _ACTIVE.set(capture)
    try:
        with observe_combat_inputs(limit=8192) as observation:
            try:
                yield capture
            except BaseException as failure:
                error = failure
                raise
            finally:
                if (
                    error is not None
                    or os.environ.get("WAKFU_COMBAT_INCIDENT_MODE", "failures") == "all"
                ):
                    try:
                        from .combat_incident_capture import _enqueue

                        _enqueue(root, capture.receipt(observation, error))
                    except Exception as failure:
                        LOGGER.warning(
                            "npc_publication_capture_failed type=%s",
                            type(failure).__name__,
                        )
    finally:
        _ACTIVE.reset(token)
        if prepared_runtime is not None:
            pending_private_commit(prepared_runtime, consume=True)


def _strict_tape(observations):
    tape = deepcopy(observations)
    tape["events"] = [
        event for event in tape["events"] if event["kind"] in ("rng", "clock")
    ]
    for sequence, event in enumerate(tape["events"], 1):
        event["sequence"] = sequence
    return tape


def _unused_provider(*args, **kwargs):
    raise UnsupportedNPCPublication(
        "Original shared provider unexpectedly executed during prepared publication"
    )


def _restore_shared_bindings(runtime, shared, fields):
    # execute_server copies this source pair, then the chosen recipe returns a
    # freshly recomputed Transition. Source services are not invoked. A stale
    # guard fails before the copy; any unexpected consultation must fail closed.
    from .combat_npc_reproduction import _PROVIDER_FIELDS

    for field in _PROVIDER_FIELDS:
        setattr(runtime, field, _unused_provider if field in fields else None)
    if "native_rail_movement_authority" in fields:
        runtime.fight.native_rail_movement_authority = _unused_provider


def _bind_execution(runtime, facts, observations, clock, *, keep_native=False):
    from .combat_live_reproduction import prepare_live_context
    from .combat_npc_reproduction import _sdk_modules, _restore_rail

    providers = facts["providers"]
    native = facts.get("native")
    native_fields = set()
    for name in ("turn_start_provider", "turn_end_provider"):
        identity = providers[name]
        if identity is not None and identity["module"].endswith(
            ".native.native_oracle"
        ):
            expected = (
                "NativeOracle.live_start_boundary"
                if name == "turn_start_provider"
                else "NativeOracle.live_end_boundary"
            )
            if identity["qualname"] != expected or native is None:
                raise UnsupportedNPCPublication("Unknown native publication callback")
            native_fields.add(name)
    identities = {
        name: value
        for name, value in providers.items()
        if value is not None
        and name not in native_fields
        and name != "clock"
        and not (name == "stats_serializer" and facts["stats_inputs"] is not None)
    }
    saved = {
        name: getattr(runtime, name, None)
        for name in ("turn_start_provider", "turn_end_provider", "stats_serializer")
    }
    rail_present = hasattr(runtime.fight, "native_rail_movement_authority")
    inputs = dict(live_provider_identity=identities, **facts.get("turn_policy", {}))
    context = prepare_live_context(runtime, None, inputs, clock, observations)
    if not rail_present and hasattr(runtime.fight, "native_rail_movement_authority"):
        del runtime.fight.native_rail_movement_authority
    if native_fields:
        oracle_module, _, _ = _sdk_modules()
        authority = native["authorities"]
        oracle = oracle_module.NativeOracle(
            runtime,
            characters=authority["characters"],
            monsters=authority["monsters"],
            decks=authority["decks"],
            excluded_decks=authority["excludedDecks"],
            viewer_id=authority["viewerId"],
            flags=native["flags"],
        )
        for name in native_fields:
            setattr(
                runtime,
                name,
                oracle.live_start_boundary
                if name == "turn_start_provider"
                else oracle.live_end_boundary,
            )
    if facts["stats_inputs"] is not None:
        _, stats_module, _ = _sdk_modules()
        runtime.stats_serializer = stats_module.NativeStats(**facts["stats_inputs"])
    if keep_native:
        for name, provider in saved.items():
            setattr(runtime, name, provider)
    if "rail_inputs" in facts:
        _restore_rail(runtime, facts["rail_inputs"])
    return context


@contextmanager
def _policies(policies):
    from unittest.mock import patch
    from .combat_npc_reproduction import ENVIRONMENT

    if (
        type(policies) is not dict
        or set(policies) != set(ENVIRONMENT)
        or any(value not in ("0", "1") for value in policies.values())
    ):
        raise UnsupportedNPCPublication("Invalid publication execution policies")
    with patch.dict(os.environ, policies):
        yield


def _replay_private_barrier(receipt):
    from .combat_npc_reproduction import (
        sdk_identity,
        _sdk_modules,
        after_state_projection,
    )
    from .combat_reproduction import (
        source_identity,
        catalog_identity,
        ReproductionClock,
    )

    if receipt.get("schema") != BARRIER_SCHEMA or receipt.get("incomplete") != []:
        raise UnsupportedNPCPublication("Incomplete private end-turn evidence")
    if (
        receipt["identity"]["source"] != source_identity()
        or receipt["identity"]["catalog"] != catalog_identity()
        or receipt["sdk_source"] != sdk_identity(_sdk_modules()[2])
    ):
        raise UnsupportedNPCPublication("Private end-turn source or catalog changed")
    state = decode_state(receipt["before"])
    native = state["runtime"]
    observations = decode_state(receipt["observations"])
    context = _bind_execution(
        native, state["facts"], observations, ReproductionClock(receipt["clocks"])
    )
    error, packets = None, ()
    with _policies(receipt["policies"]), replay_combat_inputs(
        _strict_tape(observations)
    ):
        try:
            packets = tuple(native.end_server_turn(state["actor_id"], state["turn_id"]))
        except InputReplayMismatch:
            raise
        except Exception as failure:
            error = _error(failure)
        context.assert_complete()
    after = encode_state(dict(runtime=native, packets=packets))
    if (
        after_state_projection(after) != after_state_projection(receipt["after"])
        or error != receipt["error"]
    ):
        raise UnsupportedNPCPublication("Private server end-turn did not reproduce")
    return native, packets, state["facts"]


def replay_npc_publication(receipt):
    """Recompute the chosen attack, then call the real internal Registry API."""
    from .combat_npc_reproduction import (
        replay_npc_receipt,
        sdk_identity,
        _sdk_modules,
        after_state_projection,
        after_comparison,
        _difference_paths,
    )
    from .combat_reproduction import (
        source_identity,
        catalog_identity,
        ReproductionClock,
    )
    from .combat_shared import Transition
    from .combat_shared_incident_capture import suppress_shared_incidents

    if (
        type(receipt) is not dict
        or receipt.get("schema") != SCHEMA
        or receipt.get("incomplete") != []
    ):
        raise UnsupportedNPCPublication("Incomplete NPC publication evidence")
    if (
        receipt["identity"]["source"] != source_identity()
        or receipt["identity"]["catalog"] != catalog_identity()
    ):
        raise UnsupportedNPCPublication("Publication source or catalog changed")
    if receipt["sdk_source"] is not None and receipt["sdk_source"] != sdk_identity(
        _sdk_modules()[2]
    ):
        raise UnsupportedNPCPublication("Publication SDK source changed")
    request = decode_state(receipt["request"])
    observations = decode_state(receipt["observations"])
    clock = ReproductionClock(receipt["clocks"])
    fields = {row["field"] for row in receipt["before"]["graph"]["services"]}
    restored = restore_shared_state(
        receipt["before"],
        decode_state(receipt["lease_observations"]),
        bind_runtime=lambda runtime, shared: _restore_shared_bindings(
            runtime, shared, fields
        ),
    )
    registry, shared, lease_tape = restored
    context = None
    if request["recipe"] == CHOSEN:
        private = receipt["private_commit"]
        if private is None or private["after"] != receipt["prepared"]:
            raise UnsupportedNPCPublication(
                "Private native transition provenance differs"
            )
        result = replay_npc_receipt(private, return_runtime=True)
        if not result["matches"] or result["error"] is not None:
            raise UnsupportedNPCPublication("Linked chosen action did not reproduce")
        native = result["runtime"]
        # The inner oracle callbacks and NativeStats are already real, trusted
        # reconstructions. Only ready/local providers need the outer facts tape.
        state = decode_state(private["before"])
        facts = dict(providers=state["providers"], native=None, stats_inputs=None)
        for name in ("turn_start_provider", "turn_end_provider", "stats_serializer"):
            facts["providers"][name] = None
        context = _bind_execution(native, facts, observations, clock, keep_native=True)
        fresh = Transition(native.fight, native, tuple(result["packets"]))

        def operation(candidate, runtime):
            return fresh

    elif request["recipe"] == FALLBACK:
        if receipt["private_commit"] is not None:
            private = receipt["private_commit"]
            if private["after"] != receipt["prepared"]:
                raise UnsupportedNPCPublication(
                    "Prepared server end-turn provenance differs"
                )
            native, packets, facts = _replay_private_barrier(private)
            outer_facts = deepcopy(facts)
            for name in (
                "turn_start_provider",
                "turn_end_provider",
                "stats_serializer",
            ):
                outer_facts["providers"][name] = None
            outer_facts["stats_inputs"] = None
            context = _bind_execution(
                native, outer_facts, observations, clock, keep_native=True
            )
            fresh = Transition(native.fight, native, packets)

            def operation(candidate, runtime):
                return fresh

        else:
            facts = decode_state(receipt["fallback"])
            context = _bind_execution(shared.runtime, facts, observations, clock)

            def operation(candidate, runtime):
                return Transition(
                    candidate,
                    runtime,
                    tuple(
                        runtime.end_server_turn(request["actor_id"], request["turn_id"])
                    ),
                )

    else:
        raise UnsupportedNPCPublication("Unknown server publication recipe")
    error, value, transition = None, None, None
    native_transition = registry._transition

    def observed_transition(result, candidate, runtime):
        nonlocal transition
        candidate, runtime, packets = native_transition(result, candidate, runtime)
        # Match the live hook after packet validation. A rejecting validator
        # has no accepted transition to observe, even when the private attack
        # itself executed successfully before publication was attempted.
        transition = encode_state(dict(runtime=runtime, packets=packets))
        return candidate, runtime, packets

    token = _REPLAY.set(True)
    try:
        from unittest.mock import patch

        with _policies(
            receipt["policies"]
        ), suppress_shared_incidents(), replay_combat_inputs(
            _strict_tape(observations)
        ), patch.object(
            registry, "_transition", side_effect=observed_transition
        ):
            try:
                value = registry.execute_server(
                    shared.fight.id,
                    request["actor_id"],
                    operation,
                    expected_sequence=request["expected_sequence"],
                )
            except InputReplayMismatch:
                raise
            except Exception as failure:
                error = _error(failure)
            context.assert_complete()
            lease_tape.assert_consumed()
    finally:
        _REPLAY.reset(token)
    after = capture_shared_state(shared, registry=registry)
    return_matches = (
        type(value) is type(receipt["return_value"])
        and value == receipt["return_value"]
    )
    matches = (
        after_state_projection(after) == after_state_projection(receipt["after"])
        and error == receipt["error"]
        and return_matches
        and after_state_projection(transition)
        == after_state_projection(receipt["transition"])
        and receipt["return_recorded"] == (error is None)
    )
    comparison = dict(
        after=after_comparison(receipt["after"]["graph"], after["graph"]),
        transition_matches=after_state_projection(transition)
        == after_state_projection(receipt["transition"]),
        transition_differences=_difference_paths(
            after_state_projection(receipt["transition"]),
            after_state_projection(transition),
        ),
        error_matches=error == receipt["error"],
        return_matches=return_matches,
        return_recorded_matches=receipt["return_recorded"] == (error is None),
    )
    if source_identity() != receipt["identity"]["source"]:
        raise UnsupportedNPCPublication(
            "Publication sources changed during reproduction"
        )
    return dict(
        matches=matches,
        after=after,
        error=error,
        return_value=value,
        return_recorded=error is None,
        transition=transition,
        comparison=comparison,
        dispatch_qualified=False,
        boundary="registry_execute_server_mailboxes_after_shared_postprocessing",
    )
