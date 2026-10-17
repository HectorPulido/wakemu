"""Opt-in private receipts from actual actions, without replaying live gameplay.

Receipts preserve evidence; an unqualified provider or missing input is never
promoted to a successful deterministic reproduction. Only immutable encoded
data crosses the bounded writer queue. Diagnostics cannot replace game errors.
"""
from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
from queue import Queue, Full
import threading
import uuid

from .combat_reproduction_state import encode_state, MAX_BYTES

LOGGER = logging.getLogger(__name__)
SCHEMA = "wakemu-combat-incident-v1"
MAX_FILES = 128
MAX_DIRECTORY_BYTES = 256 * 1024 * 1024
_QUEUE = Queue(maxsize=2)
_WORKER_LOCK = threading.Lock()
_WORKER = None
_IDENTITY_LOCK = threading.Lock()
_IDENTITY = None


def incident_enabled():
    return bool(os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"))


def _identity():
    global _IDENTITY
    with _IDENTITY_LOCK:
        if _IDENTITY is None:
            from .combat_reproduction import source_identity, catalog_identity

            dispatcher = Path(__file__).resolve().parents[2] / "local_game_server.py"
            _IDENTITY = {
                "source": source_identity(),
                "catalog": catalog_identity(),
                "dispatcher_sha256": hashlib.sha256(
                    dispatcher.read_bytes()
                ).hexdigest(),
            }
        return _IDENTITY


def _persist(root, incident_id, raw):
    root = Path(root)
    if root.is_symlink():
        raise ValueError("Incident destination must not be a symlink")
    # Canonicalize system aliases such as macOS /var -> /private/var.
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.stat().st_mode & 0o077:
        raise ValueError("Incident destination must be private")
    files = list(root.glob("*.json"))
    if (
        len(files) >= MAX_FILES
        or sum(path.stat().st_size for path in files) + len(raw) > MAX_DIRECTORY_BYTES
    ):
        raise ValueError("Incident retention quota reached")
    path = root / (incident_id + ".json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _writer():
    while True:
        root, incident_id, raw = _QUEUE.get()
        try:
            _persist(root, incident_id, raw)
        except Exception as error:
            LOGGER.warning(
                "combat_incident_write_failed id=%s type=%s",
                incident_id,
                type(error).__name__,
            )
        finally:
            _QUEUE.task_done()


def _enqueue(root, receipt):
    global _WORKER
    raw = json.dumps(receipt, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("Incident receipt exceeds size bound")
    with _WORKER_LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(
                target=_writer, name="combat-incident-writer", daemon=True
            )
            _WORKER.start()
    try:
        _QUEUE.put_nowait((root, receipt["incident_id"], raw))
    except Full:
        LOGGER.warning("combat_incident_dropped reason=queue_full")


class IncidentCapture:
    def __init__(self, runtime, action, inputs, session, bootstrap, recipients):
        self.runtime = runtime
        self.delivery = ()
        self.incomplete = [
            "Live providers and shared delivery require replay qualification"
        ]
        self.before = None
        self.identity = None
        self.providers = {}
        self.clocks = None
        self.policies = None
        try:
            from .combat_reproduction import capture_clocks, POLICY_DEFAULTS

            self.clocks = capture_clocks()
            self.policies = {
                name: os.environ.get(name, default)
                for name, default in POLICY_DEFAULTS.items()
            }
            self.identity = _identity()
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
                    self.providers[field] = {
                        "module": getattr(
                            provider, "__module__", type(provider).__module__
                        ),
                        "qualname": getattr(
                            provider, "__qualname__", type(provider).__qualname__
                        ),
                    }
            self.before = encode_state(
                {
                    "runtime": runtime,
                    "action": action,
                    "inputs": inputs,
                    "session": session,
                    "bootstrap": tuple(bootstrap),
                    "recipients": tuple(recipients),
                }
            )
        except Exception as error:
            self.incomplete.append(
                "Before-state capture failed: " + type(error).__name__
            )

    def packets(self, packets):
        # Never consume a gameplay iterator or mutate its delivery.
        if type(packets) not in (tuple, list):
            self.incomplete.append("Delivery was not a materialized packet batch")
            return
        self.delivery = tuple(packets)

    def finish(self, observation, error, root):
        after = None
        try:
            after = encode_state({"runtime": self.runtime, "packets": self.delivery})
        except Exception as failure:
            self.incomplete.append(
                "After-state capture failed: " + type(failure).__name__
            )
        observations = observation.snapshot()
        receipt = {
            "schema": SCHEMA,
            "incident_id": uuid.uuid4().hex,
            "identity": self.identity,
            "identity_boundary": "first_enabled_capture_in_this_process",
            "provider_identity": self.providers,
            "clocks": self.clocks,
            "policies": self.policies,
            "before": self.before,
            "after": after,
            "observations": encode_state(observations),
            "error": None
            if error is None
            else {
                "type": type(error).__module__ + "." + type(error).__name__,
                "message": str(error),
            },
            "status": "accepted" if error is None else "raised",
            "replay_qualified": False,
            "incomplete": self.incomplete + list(observations.get("incomplete", ())),
            "delivery_boundary": "operation_packets_before_shared_postprocessing",
        }
        _enqueue(root, receipt)


@contextmanager
def incident_scope(
    runtime, action, inputs, *, session=None, bootstrap=(), recipients=()
):
    """Observe real execution; save failures, or all actions in explicit all mode.

    Call under the same action lock as gameplay. Capturing the original graph
    before execution also supports paths which mutate their runtime on failure.
    Writing is asynchronous and may drop receipts at the documented quotas.
    """
    root = os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
    if not root:
        yield None
        return
    try:
        from .combat_input_observation import observe_combat_inputs

        capture = IncidentCapture(
            runtime, action, inputs, session, bootstrap, recipients
        )
        scope = observe_combat_inputs()
        observation = scope.__enter__()
    except Exception as failure:
        LOGGER.warning("combat_incident_setup_failed type=%s", type(failure).__name__)
        yield None
        return
    error = None
    try:
        yield capture
    except BaseException as failure:
        error = failure
        raise
    finally:
        try:
            scope.__exit__(
                type(error) if error is not None else None,
                error,
                error.__traceback__ if error is not None else None,
            )
        except Exception as failure:
            LOGGER.warning(
                "combat_incident_observer_failed type=%s", type(failure).__name__
            )
        if (
            error is not None
            or os.environ.get("WAKFU_COMBAT_INCIDENT_MODE", "failures") == "all"
        ):
            try:
                capture.finish(observation, error, root)
            except Exception as failure:
                LOGGER.warning(
                    "combat_incident_capture_failed type=%s", type(failure).__name__
                )
