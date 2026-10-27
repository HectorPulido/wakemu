"""Explicit AI routing, pinned to the native runtime for an entire actor turn."""
import json
import os
from pathlib import Path
import tempfile

CONFIG_PATH = Path("/data/ai-backend.json")
BACKENDS = ("current", "jondo")


def endpoint_for(backend):
    if backend == "current":
        return "tcp://ai:8090"
    if backend == "jondo":
        return "tcp://ai-jondo:8091"
    raise ValueError("Unknown AI backend: " + repr(backend))


def read_config(path=CONFIG_PATH):
    try:
        with open(path, "rb") as source:
            raw = source.read(4097)
    except FileNotFoundError:
        return dict(version=1, backend="current")
    if len(raw) > 4096:
        raise ValueError("AI backend configuration exceeds its size limit")
    config = json.loads(raw)
    if (
        not isinstance(config, dict)
        or set(config) != {"version", "backend"}
        or type(config["version"]) is not int
        or config["version"] != 1
        or config["backend"] not in BACKENDS
    ):
        raise ValueError("Invalid AI backend configuration")
    return config


def write_config(path, backend):
    """Atomically publish validated routing; the CLI verifies reachability first."""
    endpoint_for(backend)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, mode="wb", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(dict(version=1, backend=backend)) + "\n").encode())
            # Routing contains no secrets and must be readable by World's UID.
            os.fchmod(stream.fileno(), 0o644)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _identity(runtime):
    fight = runtime.fight
    if fight.phase != "active" or fight.current is None:
        raise ValueError("AI routing requires an active actor turn")
    identity = [fight.id, fight.current.id, fight.turn_id]
    if any(type(value) is not int for value in identity):
        raise ValueError("Invalid native AI routing identity")
    return identity


def pin_backend(runtime, *, config_path=CONFIG_PATH):
    """Read routing once per native (fight, actor, turn), before preparation.

    Plain runtime metadata survives Registry deepcopy/adoption and reconnects.
    A configuration change never redirects another action of the pinned turn.
    """
    identity = _identity(runtime)
    pin = getattr(runtime, "native_ai_backend_pin", None)
    if pin is not None:
        if (
            not isinstance(pin, dict)
            or set(pin) != {"version", "identity", "backend", "endpoint"}
            or type(pin["version"]) is not int
            or pin["version"] != 1
            or not isinstance(pin["identity"], list)
            or len(pin["identity"]) != 3
            or any(type(value) is not int for value in pin["identity"])
            or pin["backend"] not in BACKENDS
            or pin["endpoint"] != endpoint_for(pin["backend"])
        ):
            raise ValueError("Invalid pinned AI backend")
        if pin["identity"] == identity:
            return dict(pin, identity=list(identity))
    config = read_config(config_path)
    pin = dict(
        version=1,
        identity=identity,
        backend=config["backend"],
        endpoint=endpoint_for(config["backend"]),
    )
    runtime.native_ai_backend_pin = pin
    return dict(pin, identity=list(identity))


def pinned_endpoint(runtime, *, expected_backend):
    """Adapters may consume only the backend already chosen by the dispatcher."""
    pin = getattr(runtime, "native_ai_backend_pin", None)
    if not isinstance(pin, dict) or pin.get("identity") != _identity(runtime):
        raise ValueError("AI backend was not pinned before native preparation")
    pin = pin_backend(runtime)
    if pin["backend"] != expected_backend:
        raise ValueError("AI adapter differs from the pinned backend")
    return pin["endpoint"]
