"""One opt-in receipt for the complete locked Registry execute/ACK boundary.

Actual operation inputs, lease verdicts and mailbox publication are observed;
no lease call is added, no callback is replaced, and no socket is opened here.
Bootstrap history, dispatch and provider equivalence remain explicit unknowns.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
import uuid

from .combat_reproduction_state import encode_state, decode_state
from .combat_shared_reproduction import capture_shared_state, lease_result

LOGGER = logging.getLogger(__name__)
SCHEMA = "wakemu-shared-combat-incident-v1"
_active = ContextVar("shared_combat_incident", default=None)
_suppressed = ContextVar("shared_combat_incident_suppressed", default=False)
MAX_LEASES = 512
MAX_OPERATIONS = 8


def current_shared_incident():
    return _active.get()


def shared_incidents_suppressed():
    return _suppressed.get()


@contextmanager
def suppress_shared_incidents():
    """Trusted offline replay cannot emit new receipts or nest observers."""
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


class SharedIncidentCapture:
    def __init__(self, shared, registry, request):
        self.shared, self.registry = shared, registry
        self.before = self.after = self.identity = self.request = None
        self.clocks = self.policies = None
        self.provider_identity = {}
        self.preceding_delivery_history = None
        self.bootstrap_available = self.delivery_history_continuous = False
        self.delivery_correlation = None
        self.operations = []
        self.operation_packets = ()
        self.lease_rows = []
        self.return_value = None
        self.return_recorded = False
        self.incomplete = [
            "Socket dispatch following this operation requires correlated delivery evidence",
            "Runtime providers require a trusted replay qualification",
        ]
        try:
            from .combat_delivery_observation import delivery_history

            self.preceding_delivery_history = delivery_history(shared)
            if self.preceding_delivery_history is not None:
                history = decode_state(self.preceding_delivery_history)
                streams = history["streams"]
                self.bootstrap_available = bool(streams) and all(
                    not stream["bootstrap_missing"] for stream in streams
                )
                self.delivery_history_continuous = self.bootstrap_available and all(
                    not stream["history_gap"] for stream in streams
                )
                self.delivery_correlation = dict(
                    process_boot_id=history["process_boot_id"],
                    fight_id=shared.fight.id,
                    before_sequence=shared.sequence,
                )
        except Exception as failure:
            self._missing(
                "Preceding delivery history unavailable: " + type(failure).__name__
            )
        try:
            for field in (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_start_provider",
                "turn_end_provider",
                "expiration_runtime_factory",
                "clock",
            ):
                provider = getattr(shared.runtime, field, None)
                if provider is not None:
                    self.provider_identity[field] = {
                        "module": getattr(
                            provider, "__module__", type(provider).__module__
                        ),
                        "qualname": getattr(
                            provider, "__qualname__", type(provider).__qualname__
                        ),
                    }
        except Exception as failure:
            self._missing(
                "Original provider identity capture failed: " + type(failure).__name__
            )
        try:
            from .combat_reproduction import capture_clocks, POLICY_DEFAULTS

            self.clocks = capture_clocks()
            self.policies = {
                name: os.environ.get(name, default)
                for name, default in POLICY_DEFAULTS.items()
            }
        except Exception as failure:
            self._missing("Clock/policy capture failed: " + type(failure).__name__)
        try:
            from .combat_incident_capture import _identity

            self.identity = _identity()
        except Exception as failure:
            self._missing("Identity capture failed: " + type(failure).__name__)
        try:
            self.request = encode_state(request)
        except Exception as failure:
            self._missing("Request capture failed: " + type(failure).__name__)
        try:
            self.before = capture_shared_state(shared, registry=registry)
        except Exception as failure:
            self._missing(
                "Before shared-state capture failed: " + type(failure).__name__
            )

    def _missing(self, reason):
        if reason not in self.incomplete and len(self.incomplete) < 32:
            self.incomplete.append(reason)

    def attach(
        self, runtime, action, inputs, *, session=None, bootstrap=(), recipients=()
    ):
        """Freeze inner operation evidence without opening a nested receipt."""
        try:
            if len(self.operations) >= MAX_OPERATIONS:
                self._missing("Operation evidence limit exceeded")
                return
            providers = {}
            for field in (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_start_provider",
                "turn_end_provider",
                "expiration_runtime_factory",
                "clock",
            ):
                provider = getattr(runtime, field, None)
                if provider is not None:
                    providers[field] = {
                        "module": getattr(
                            provider, "__module__", type(provider).__module__
                        ),
                        "qualname": getattr(
                            provider, "__qualname__", type(provider).__qualname__
                        ),
                    }
            self.operations.append(
                encode_state(
                    {
                        "action": action,
                        "inputs": inputs,
                        "session": session,
                        "bootstrap": tuple(bootstrap),
                        "recipients": tuple(recipients),
                        "provider_identity": providers,
                    }
                )
            )
        except Exception as failure:
            self._missing(
                "Operation evidence capture failed: " + type(failure).__name__
            )

    def packets(self, packets):
        try:
            if type(packets) not in (tuple, list):
                self._missing("Operation packets were not a materialized batch")
                return
            self.operation_packets = tuple(packets)
        except Exception as failure:
            self._missing("Operation packet capture failed: " + type(failure).__name__)

    def lease(self, session, *, result=None, error=None):
        try:
            if len(self.lease_rows) >= MAX_LEASES:
                self._missing("Lease observation limit exceeded")
                return
            self.lease_rows.append(lease_result(session, result=result, error=error))
        except Exception as failure:
            self._missing("Lease observation failed: " + type(failure).__name__)

    def result(self, value):
        try:
            # The native Registry APIs return int sequence / bool release only.
            if type(value) not in (int, bool):
                self._missing("Unexpected Registry return type")
                return
            self.return_value, self.return_recorded = value, True
        except Exception as failure:
            self._missing("Return observation failed: " + type(failure).__name__)

    def finish(self, observation, error, root):
        try:
            self.after = capture_shared_state(self.shared, registry=self.registry)
        except Exception as failure:
            self._missing(
                "After shared-state capture failed: " + type(failure).__name__
            )
        observed = observation.snapshot()
        if error is None and not self.return_recorded:
            self._missing("Registry return value was not observed")
        receipt = {
            "schema": SCHEMA,
            "incident_id": uuid.uuid4().hex,
            "identity": self.identity,
            "identity_boundary": "first_enabled_capture_in_this_process",
            "provider_identity": self.provider_identity,
            "clocks": self.clocks,
            "policies": self.policies,
            "request": self.request,
            "before": self.before,
            "after": self.after,
            "operations": self.operations,
            "operation_evidence_available": bool(self.operations),
            "preceding_delivery_history": self.preceding_delivery_history,
            "delivery_history_continuous": self.delivery_history_continuous,
            "delivery_correlation": self.delivery_correlation,
            "operation_packets": encode_state(self.operation_packets),
            "lease_observations": encode_state(self.lease_rows),
            "observations": encode_state(observed),
            "return_value": self.return_value,
            "return_recorded": self.return_recorded,
            "error": None
            if error is None
            else {
                "type": type(error).__module__ + "." + type(error).__name__,
                "message": str(error),
            },
            "status": "returned" if error is None else "raised",
            "replay_qualified": False,
            "incomplete": self.incomplete + list(observed.get("incomplete", ())),
            "delivery_boundary": "registry_mailboxes_after_shared_postprocessing",
            "bootstrap_available": self.bootstrap_available,
            "dispatch_observed": False,
        }
        from .combat_incident_capture import _enqueue

        _enqueue(root, receipt)


def observe_shared_lease(session, *, result=None, error=None):
    capture = _active.get()
    if capture is None:
        return
    try:
        capture.lease(session, result=result, error=error)
    except Exception:
        # Fail open even if a diagnostic implementation or test sink is broken.
        pass


@contextmanager
def shared_incident_scope(shared, registry, request):
    """Called under shared.lock before membership validation/ACK mutation."""
    root = os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
    if not root or _suppressed.get():
        yield None
        return
    # Nested entry is not a separate receipt or observation stream.
    if _active.get() is not None:
        yield _active.get()
        return
    try:
        from .combat_input_observation import observe_combat_inputs

        capture = SharedIncidentCapture(shared, registry, request)
        scope = observe_combat_inputs()
        observation = scope.__enter__()
        token = _active.set(capture)
    except Exception as failure:
        LOGGER.warning(
            "shared_combat_incident_setup_failed type=%s", type(failure).__name__
        )
        yield None
        return
    error = None
    try:
        yield capture
    except BaseException as failure:
        error = failure
        raise
    finally:
        _active.reset(token)
        try:
            scope.__exit__(
                type(error) if error is not None else None,
                error,
                error.__traceback__ if error is not None else None,
            )
        except Exception as failure:
            LOGGER.warning(
                "shared_combat_incident_observer_failed type=%s", type(failure).__name__
            )
        if (
            error is not None
            or os.environ.get("WAKFU_COMBAT_INCIDENT_MODE", "failures") == "all"
        ):
            try:
                capture.finish(observation, error, root)
            except Exception as failure:
                LOGGER.warning(
                    "shared_combat_incident_capture_failed type=%s",
                    type(failure).__name__,
                )
