"""Capture and replay one isolated combat action with exact observable results.

This offline diagnostic API never restores a live session or persists gameplay.
Catalogs must be captured/restored before importing engine code. Source changes
are explicit comparison inputs rather than silently compatible snapshots.
"""
from contextlib import ExitStack, contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from unittest.mock import patch

from .combat_reproduction_state import encode_state, decode_state, MAX_BYTES

SCHEMA = "wakemu-combat-reproduction-v1"
POLICY_DEFAULTS = {
    "WAKFU_NATIVE_AREA_CALLBACKS": "1",
    "WAKFU_NATIVE_GRANTED_CAST": "0",
}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def source_identity():
    """Pin engine sources and Python without service configuration or credentials."""
    server = Path(__file__).resolve().parents[2]
    paths = sorted(
        path
        for path in (server / "wakfu_server").rglob("*")
        if path.is_file() and path.suffix in (".py", ".json")
    )
    paths.extend(path for path in (server / "protocol_codec.py",) if path.is_file())
    files = {}
    for path in paths:
        if path.is_symlink() or "__pycache__" in path.parts:
            continue
        files[path.relative_to(server).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    python = {
        "implementation": sys.implementation.name,
        "version": list(sys.version_info[:3]),
    }
    return {
        "files": files,
        "python": python,
        "sha256": digest({"files": files, "python": python}),
    }


def capture_clocks():
    return {"wall_time_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns()}


def catalog_identity():
    from wakfu_server import native_catalog

    return {
        "revision": native_catalog.release(),
        "inventory_sha256": digest(native_catalog.document_hashes()),
    }


class ReproductionClock:
    def __init__(self, observations):
        if not isinstance(observations, dict) or set(observations) != {
            "wall_time_ns",
            "monotonic_ns",
        }:
            raise ValueError("Explicit wall and monotonic observations required")
        if any(type(value) is not int or value < 0 for value in observations.values()):
            raise ValueError("Invalid reproduction clock observation")
        self.observations = dict(observations)

    def __call__(self):
        return self.observations["monotonic_ns"] / 1_000_000_000


def _validate_policies(policies):
    if not isinstance(policies, dict) or set(policies) != set(POLICY_DEFAULTS):
        raise ValueError("Incomplete reproduction policy manifest")
    if any(value not in ("0", "1") for value in policies.values()):
        raise ValueError("Invalid reproduction policy value")


@contextmanager
def controlled_environment(clocks, policies):
    """Process-local offline boundary; do not install on a live server thread."""
    clock = ReproductionClock(clocks)
    _validate_policies(policies)
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, policies))
        stack.enter_context(
            patch("time.time", lambda: clocks["wall_time_ns"] / 1_000_000_000)
        )
        stack.enter_context(patch("time.time_ns", lambda: clocks["wall_time_ns"]))
        stack.enter_context(patch("time.monotonic", clock))
        stack.enter_context(patch("time.monotonic_ns", lambda: clocks["monotonic_ns"]))
        yield clock


def capture_request(
    runtime,
    action,
    inputs,
    rng,
    *,
    clocks=None,
    session=None,
    bootstrap=(),
    recipients=(),
    policies=None,
):
    """Capture before execution, including pending presentation and authority.

    ``session`` is explicit plain session/barrier evidence, never a Store,
    socket, lock or callback. Exact identity values are private diagnostic data.
    The trusted authority recipe is required when executing the capsule.
    """
    if not isinstance(rng, random.Random):
        raise ValueError("An owned Random instance is required")
    if policies is None:
        policies = {
            name: os.environ.get(name, default)
            for name, default in POLICY_DEFAULTS.items()
        }
    clocks = capture_clocks() if clocks is None else clocks
    # Live capture only reads facts. Global clock/environment overrides belong
    # exclusively to the isolated replay process, never a server request thread.
    ReproductionClock(clocks)
    _validate_policies(policies)
    graph = encode_state(
        {
            "runtime": runtime,
            "action": action,
            "inputs": inputs,
            "rng_state": rng.getstate(),
            "session": session,
            "bootstrap": tuple(bootstrap),
            "recipients": tuple(recipients),
        }
    )
    sources = source_identity()
    return {
        "schema": SCHEMA,
        "source": sources,
        "catalog": {
            **catalog_identity(),
            "bundle_sha256": None,
        },
        "clocks": dict(clocks),
        "policies": dict(policies),
        "before": graph,
        "expected": None,
        "boundary": "isolated-runtime-action-not-live-session-recovery",
    }


def _validate_case(case):
    if not isinstance(case, dict) or case.get("schema") != SCHEMA:
        raise ValueError("Unsupported combat reproduction schema")
    if set(case) != {
        "schema",
        "source",
        "catalog",
        "clocks",
        "policies",
        "before",
        "expected",
        "boundary",
    }:
        raise ValueError("Unexpected combat reproduction fields")
    if case["boundary"] != "isolated-runtime-action-not-live-session-recovery":
        raise ValueError("Unsupported combat reproduction boundary")
    if len(_json(case).encode()) > MAX_BYTES:
        raise ValueError("Combat reproduction exceeds size bound")
    source = case["source"]
    if not isinstance(source, dict) or set(source) not in (
        {"files", "sha256"},
        {"files", "python", "sha256"},
    ):
        raise ValueError("Invalid reproduction source manifest")
    # Legacy manifests remain readable. Their missing interpreter evidence
    # makes strict comparison fail against a current identity; drift must be
    # explicitly requested rather than silently claiming compatibility.
    identity = source["files"]
    if "python" in source:
        python = source["python"]
        if (
            type(python) is not dict
            or set(python) != {"implementation", "version"}
            or type(python["implementation"]) is not str
            or not python["implementation"]
            or type(python["version"]) is not list
            or len(python["version"]) != 3
            or any(type(value) is not int or value < 0 for value in python["version"])
        ):
            raise ValueError("Invalid reproduction interpreter identity")
        identity = {"files": source["files"], "python": python}
    if digest(identity) != source["sha256"]:
        raise ValueError("Invalid reproduction source manifest")
    catalog = case["catalog"]
    if not isinstance(catalog, dict) or set(catalog) != {
        "revision",
        "inventory_sha256",
        "bundle_sha256",
    }:
        raise ValueError("Missing reproduction catalog identity")
    if not isinstance(catalog["revision"], str) or not catalog["revision"]:
        raise ValueError("Invalid reproduction catalog revision")
    for field in ("inventory_sha256", "bundle_sha256"):
        value = catalog[field]
        if value is None and field == "bundle_sha256":
            continue
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ValueError("Invalid reproduction catalog digest")


def bind_catalog_bundle(case, root):
    """Seal this case to its exported catalog metadata and blob identities."""
    path = Path(root) / "catalog.json"
    raw = path.read_bytes()
    manifest = json.loads(raw)
    identity = {
        "revision": manifest["revision"],
        "inventory_sha256": digest(manifest["published_hashes"]),
    }
    if identity != {key: case["catalog"][key] for key in identity}:
        raise ValueError("Exported catalog differs from captured catalog")
    case["catalog"]["bundle_sha256"] = hashlib.sha256(raw).hexdigest()
    return case


def verify_catalog_bundle(case, root):
    expected = case["catalog"]["bundle_sha256"]
    if expected is None:
        raise ValueError("Reproduction is not bound to an exported catalog")
    if (
        hashlib.sha256((Path(root) / "catalog.json").read_bytes()).hexdigest()
        != expected
    ):
        raise ValueError("Reproduction catalog bundle was replaced or modified")


def execute_case(case, *, allow_source_drift=False, observations=None):
    """Always execute on a new private graph, including rejection reproductions."""
    _validate_case(case)
    current_source = source_identity()
    source_matches = current_source == case["source"]
    if not source_matches and not allow_source_drift:
        raise ValueError("Combat sources differ; use explicit source comparison mode")
    if catalog_identity() != {
        key: case["catalog"][key] for key in ("revision", "inventory_sha256")
    }:
        raise ValueError("Active replay catalog differs from captured catalog")
    from .combat_reproduction_actions import execute, prepare_context
    from .combat_reproduction_catalog import MissingReproductionCatalog
    from .combat_input_observation import InputReplayMismatch, replay_combat_inputs

    with controlled_environment(case["clocks"], case["policies"]) as clock:
        state = decode_state(case["before"])
        if set(state) != {
            "runtime",
            "action",
            "inputs",
            "rng_state",
            "session",
            "bootstrap",
            "recipients",
        }:
            raise ValueError("Incomplete captured action context")
        rng = random.Random()
        rng.setstate(state["rng_state"])
        runtime = state["runtime"]
        runtime.clock = clock
        before_runtime = encode_state(runtime)
        before_rng = rng.getstate()
        event_start = len(runtime.fight.events)
        prepared_context = prepare_context(
            runtime, state["action"], state["inputs"], rng, clock
        )
        trace = []
        from .combat_diagnostics import combat_diagnostic_scope

        input_replay = None
        try:
            # Binding diagnostic providers is deliberately outside the input
            # tape: it is not part of the recorded gameplay operation.
            tape = (
                nullcontext()
                if observations is None
                else replay_combat_inputs(observations)
            )
            with tape as input_replay, combat_diagnostic_scope(
                lambda **row: trace.append(row)
            ):
                result = execute(
                    runtime,
                    state["action"],
                    state["inputs"],
                    rng,
                    clock,
                    prepared_context=prepared_context,
                )
        except (MissingReproductionCatalog, InputReplayMismatch):
            raise
        except Exception as error:
            status = "rejected" if isinstance(error, ValueError) else "execution_error"
            outcome = {
                "status": status,
                "error": {
                    "type": type(error).__module__ + "." + type(error).__name__,
                    "message": str(error),
                },
                "packets": (),
                "plan": None,
                "outcomes": (),
            }
        else:
            outcome = {
                "status": "accepted",
                "error": None,
                "packets": tuple(result["packets"]),
                "plan": result.get("plan"),
                "outcomes": result.get("outcomes", ()),
            }
        # Diagnostics timing is observational, not part of deterministic output.
        outcome.update(
            runtime=runtime,
            events=tuple(runtime.fight.events[event_start:]),
            rng_state=rng.getstate(),
            session=state["session"],
            bootstrap=state["bootstrap"],
            recipients=state["recipients"],
            rollback={
                "runtime_unchanged": {
                    key: value
                    for key, value in encode_state(runtime).items()
                    if key != "services"
                }
                == {
                    key: value
                    for key, value in before_runtime.items()
                    if key != "services"
                },
                "rng_unchanged": rng.getstate() == before_rng,
            },
        )
        if input_replay is not None:
            outcome["observed_rng_streams"] = tuple(
                {
                    "stream_id": identity,
                    "initial_state": observations["rng_streams"][identity][
                        "initial_state"
                    ],
                    "final_state": stream.getstate(),
                }
                for identity, stream in sorted(input_replay.streams.items())
            )
            outcome["input_replay"] = {
                "ownership_known": input_replay.ownership_known,
                "ownership_unknown": input_replay.ownership_unknown,
            }
            # The legacy fallback RNG is not authority when the input tape
            # supplies per-binding streams. Report those streams explicitly.
            outcome["rng_state"] = None
            outcome["rollback"]["rng_unchanged"] = None
        encoded = encode_state(outcome)
    if source_identity() != current_source:
        raise ValueError("Combat sources changed during reproduction")
    return {
        "result": encoded,
        "sha256": digest(encoded),
        "source_matches": source_matches,
        "source_sha256": current_source["sha256"],
        "catalog_matches": True,
        "catalog_revision": case["catalog"]["revision"],
        "trace": trace,
        "status": outcome["status"],
    }


def record_expectation(case, result):
    """Record observed behavior, including failures, without accrediting it."""
    case["expected"] = {"result": result["result"], "sha256": result["sha256"]}
    return case


def compare_expectation(case, result):
    expected = case["expected"]
    if expected is None:
        return {"has_expectation": False, "matches": None}
    if (
        not isinstance(expected, dict)
        or set(expected) != {"result", "sha256"}
        or digest(expected["result"]) != expected["sha256"]
    ):
        raise ValueError("Invalid captured expectation digest")
    differences = []

    def compare(left, right, path="result"):
        if len(differences) >= 20:
            return
        if type(left) is not type(right):
            differences.append(path + ": type differs")
        elif isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                if key not in left or key not in right:
                    differences.append(path + "." + str(key) + ": field missing")
                else:
                    compare(left[key], right[key], path + "." + str(key))
        elif isinstance(left, list):
            if len(left) != len(right):
                differences.append(path + ": length differs")
            for index, (a, b) in enumerate(zip(left, right)):
                compare(a, b, path + "[" + str(index) + "]")
        elif left != right:
            differences.append(path + ": value differs")

    compare(expected["result"], result["result"])
    return {
        "has_expectation": True,
        "matches": expected["sha256"] == result["sha256"],
        "differences": differences,
    }


def write_case(path, case):
    _validate_case(case)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _json(case).encode()
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_case(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Combat reproduction exceeds size bound")
    case = json.loads(path.read_bytes())
    _validate_case(case)
    return case
