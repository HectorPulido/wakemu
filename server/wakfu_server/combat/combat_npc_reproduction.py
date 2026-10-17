"""Passive chosen-action NPC receipts and a fixed offline native SDK recipe.

No search, Store, HTTP, callbacks from payloads, or live state restoration.
Unknown providers remain evidence, never accredited execution authority.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import inspect
import logging
import math
import os
from pathlib import Path
import threading
import uuid
import weakref

from .combat_reproduction_state import (
    SCHEMA as STATE_SCHEMA,
    encode_state as _encode_state,
    decode_state,
)
from .combat_input_observation import (
    InputReplayMismatch,
    observe_combat_inputs,
    replay_combat_inputs,
)

SCHEMA = "wakemu-combat-npc-incident-v1"
RECIPE = "native-oracle-chosen-action-v1"
ENVIRONMENT = {"WAKFU_NATIVE_AREA_CALLBACKS": "1", "WAKFU_NATIVE_GRANTED_CAST": "0"}
_PROVIDER_FIELDS = (
    "stats_serializer",
    "runtime_stats_serializer",
    "turn_start_provider",
    "turn_end_provider",
    "expiration_runtime_factory",
    "clock",
)
_REPLAY = ContextVar("npc_reproduction_replay", default=False)
_CORRELATIONS = weakref.WeakKeyDictionary()
_CORRELATION_LOCK = threading.Lock()
LOGGER = logging.getLogger(__name__)


def encode_state(value):
    return _encode_state(value, preserve_scalars=True)


def scalar_value_graph(graph):
    """Post-action comparison projection: remove only str/bytes identity nodes.

    Mutable/container/domain aliases, attribute and event ordering, service
    presence and all byte values remain represented. This is not a checkpoint
    decoder and must never replace the exact pre-action source graph.
    """
    nodes = graph["nodes"]
    retained = [
        index
        for index, node in enumerate(nodes)
        if node["kind"] not in ("str", "bytes")
    ]
    indices = {old: new for new, old in enumerate(retained)}

    def project(value):
        if type(value) is dict:
            if set(value) == {"ref"}:
                node = nodes[value["ref"]]
                if node["kind"] == "str":
                    return node["value"]
                if node["kind"] == "bytes":
                    return {"bytes": node["value"]}
                return {"ref": indices[value["ref"]]}
            return {key: project(item) for key, item in value.items()}
        if type(value) is list:
            return [project(item) for item in value]
        return value

    return dict(
        schema=graph["schema"],
        root=project(graph["root"]),
        nodes=[project(nodes[index]) for index in retained],
        services=[
            dict(node=indices[row["node"]], field=row["field"])
            for row in graph["services"]
        ],
    )


def after_state_projection(value):
    """Compare completed execution data without immutable scalar identities.

    Native execution introduces interned literal keys that cannot share the
    original interpreter's scalar identities after JSON restoration. Their
    values are compared exactly. All domain/container identities and ordering,
    services and bytes remain exact. Never use this as a source checkpoint or
    for captured private-commit/prepared-transition provenance linkage.
    Shared-state envelopes and absent transitions are supported for the CLI.
    """
    if type(value) is dict:
        if value.get("schema") == STATE_SCHEMA:
            return scalar_value_graph(value)
        return {key: after_state_projection(item) for key, item in value.items()}
    if type(value) is list:
        return [after_state_projection(item) for item in value]
    return value


def _difference_paths(expected, actual, limit=12):
    pending, differences = [("state", expected, actual)], []
    while pending and len(differences) < limit:
        path, left, right = pending.pop()
        if type(left) is not type(right):
            differences.append(
                dict(
                    path=path,
                    kind="type",
                    expected_type=type(left).__name__,
                    actual_type=type(right).__name__,
                )
            )
        elif type(left) is dict:
            if set(left) != set(right):
                differences.append(dict(path=path, kind="mapping_fields"))
            for key in reversed(list(left)):
                if key in right:
                    pending.append((path + "." + key, left[key], right[key]))
        elif type(left) is list:
            if len(left) != len(right):
                differences.append(
                    dict(
                        path=path,
                        kind="length",
                        expected_length=len(left),
                        actual_length=len(right),
                    )
                )
            for index in range(min(len(left), len(right)) - 1, -1, -1):
                pending.append(
                    (path + "[" + str(index) + "]", left[index], right[index])
                )
        elif left != right:
            differences.append(
                dict(
                    path=path,
                    kind="value",
                    expected_type=type(left).__name__,
                    actual_type=type(right).__name__,
                )
            )
    return differences


def after_comparison(expected, actual):
    diagnostic = dict(
        raw_matches=expected == actual,
        scalar_value_matches=scalar_value_graph(expected) == scalar_value_graph(actual),
        raw_differences=_difference_paths(expected, actual),
        scalar_value_differences=_difference_paths(
            scalar_value_graph(expected), scalar_value_graph(actual)
        ),
    )
    try:
        default_expected = _encode_state(decode_state(expected))
        default_actual = _encode_state(decode_state(actual))
        diagnostic["default_value_matches"] = default_expected == default_actual
        diagnostic["default_value_differences"] = _difference_paths(
            default_expected, default_actual
        )
    except Exception as error:
        diagnostic["default_normalization_error"] = type(error).__name__
    return diagnostic


class UnsupportedNPCReproduction(InputReplayMismatch):
    """Incomplete authority is an infrastructure failure, never a cast result."""


def publication_correlations(runtime):
    """Bounded out-of-band IDs; never changes native fingerprints or guards."""
    with _CORRELATION_LOCK:
        return tuple(_CORRELATIONS.get(runtime, ()))


def sdk_identity(directory):
    directory = Path(directory).resolve()
    files = {
        path.relative_to(directory)
        .as_posix(): hashlib.sha256(path.read_bytes())
        .hexdigest()
        for path in sorted(directory.rglob("*.py"))
        if not path.is_symlink()
    }
    if not files:
        raise UnsupportedNPCReproduction("Native SDK source is unavailable")
    from .combat_reproduction import digest

    return {"files": files, "sha256": digest(files)}


def _provider(provider):
    return (
        None
        if provider is None
        else {
            "module": getattr(provider, "__module__", type(provider).__module__),
            "qualname": getattr(provider, "__qualname__", type(provider).__qualname__),
        }
    )


def _error(error):
    return (
        None
        if error is None
        else {
            "type": type(error).__module__ + "." + type(error).__name__,
            "message": str(error),
        }
    )


def _native_stats_inputs(serializer):
    if type(serializer).__name__ != "NativeStats" or not type(
        serializer
    ).__module__.endswith(".native.native_stats"):
        return None
    return {
        name: deepcopy(getattr(serializer, name))
        for name in ("characters", "monsters", "fight_id", "registrations", "map_id")
    }


def _routine(provider, identity):
    """Trusted callback with its observed inert fingerprint descriptor."""

    def restored(*args, **kwargs):
        return provider(*args, **kwargs)

    restored.__module__ = identity["module"]
    restored.__qualname__ = identity["qualname"]
    return restored


def _rail_inputs(runtime):
    from .combat_ordinary_authority import (
        OrdinaryActorAuthority,
        _immutable_property_catalog,
    )
    from .combat_summon import RegisteredSummonAuthority
    from .combat_npc_spellbook import ordinary_npc_spellbook

    if not hasattr(runtime.fight, "native_rail_movement_authority"):
        return None
    authority = runtime.fight.native_rail_movement_authority
    registered = type(authority) is RegisteredSummonAuthority
    ordinary = authority.ordinary if registered else authority
    if (
        type(ordinary) is not OrdinaryActorAuthority
        or ordinary.catalog is not _immutable_property_catalog()
        or (
            ordinary.npc_spellbook is not None
            and ordinary.npc_spellbook is not ordinary_npc_spellbook
        )
    ):
        raise UnsupportedNPCReproduction("Unqualified rail actor authority")
    return dict(
        registered=registered,
        npc_spellbook=ordinary.npc_spellbook is not None,
        inputs={
            name: getattr(ordinary, name)
            for name in (
                "characters",
                "monsters",
                "decks",
                "excluded_decks",
                "deck_caps",
                "deck_blobs",
            )
        },
    )


def _restore_rail(runtime, facts):
    if facts is None:
        if hasattr(runtime.fight, "native_rail_movement_authority"):
            del runtime.fight.native_rail_movement_authority
        return
    from .combat_ordinary_authority import OrdinaryActorAuthority
    from .combat_summon import RegisteredSummonAuthority
    from .combat_npc_spellbook import ordinary_npc_spellbook

    if (
        set(facts) != {"registered", "npc_spellbook", "inputs"}
        or type(facts["registered"]) is not bool
        or type(facts["npc_spellbook"]) is not bool
    ):
        raise UnsupportedNPCReproduction("Invalid rail actor authority facts")
    ordinary = OrdinaryActorAuthority(
        **facts["inputs"],
        npc_spellbook=ordinary_npc_spellbook if facts["npc_spellbook"] else None
    )
    runtime.fight.native_rail_movement_authority = (
        RegisteredSummonAuthority(ordinary) if facts["registered"] else ordinary
    )


def _sdk_modules():
    # Imports are selected by trusted code, never by a receipt's module names.
    directory = Path(__file__).resolve().parents[2] / "ai-service"
    path = directory / "world_loader.py"
    spec = importlib.util.spec_from_file_location(
        "_wakemu_npc_reproduction_loader", path
    )
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    entry = loader.load_entry(directory)
    suffix = ".bridge.world_entry"
    if not entry.__module__.endswith(suffix):
        raise UnsupportedNPCReproduction("Unexpected trusted SDK entry namespace")
    package = entry.__module__[: -len(suffix)]
    return (
        importlib.import_module(package + ".native.native_oracle"),
        importlib.import_module(package + ".native.native_stats"),
        directory,
    )


class NPCCommitCapture:
    def __init__(self, oracle, action, serializer):
        from .combat_incident_capture import _identity
        from .combat_reproduction import capture_clocks

        self.oracle = oracle
        self.incident_id = uuid.uuid4().hex
        self.delivery = ()
        self.incomplete = []
        self.identity = deepcopy(_identity())
        self.clocks = capture_clocks()
        self.sdk_source = sdk_identity(Path(inspect.getfile(type(oracle))).parents[2])
        providers = {
            name: _provider(getattr(oracle.runtime, name, None))
            for name in _PROVIDER_FIELDS
        }
        aliases, seen = {}, {}
        for name in _PROVIDER_FIELDS:
            provider = getattr(oracle.runtime, name, None)
            if provider is not None:
                aliases[name] = seen.setdefault(id(provider), name)
        runtime_stats_inputs = _native_stats_inputs(
            getattr(oracle.runtime, "stats_serializer", None)
        )
        try:
            rail_inputs = _rail_inputs(oracle.runtime)
        except UnsupportedNPCReproduction:
            rail_inputs = None
            self.incomplete.append("unqualified_rail_actor_authority")
        if providers["clock"] not in (
            None,
            {"module": "time", "qualname": "monotonic"},
        ):
            self.incomplete.append("unqualified_provider:clock")
        # Start/end callbacks are replaced by commit, preserving presence only.
        # Other custom providers cannot be synthesized from their names.
        callback_identities = {
            name: providers[name]
            for name in ("runtime_stats_serializer", "expiration_runtime_factory")
            if providers[name] is not None
        }
        if providers["stats_serializer"] is not None and runtime_stats_inputs is None:
            callback_identities["stats_serializer"] = providers["stats_serializer"]
        if callback_identities:
            from .combat_live_reproduction import LiveReplayContext

            contract = object.__new__(LiveReplayContext)
            contract.identities = callback_identities
            try:
                contract._validate_providers()
            except InputReplayMismatch:
                self.incomplete.append("unqualified_runtime_providers")
        if oracle.outcome_features_provider is not None:
            self.incomplete.append("custom_outcome_features_provider")
        stats = _native_stats_inputs(serializer)
        if stats is None:
            self.incomplete.append("unqualified_commit_serializer")
        flags = deepcopy(oracle.flags)
        if set(flags) - {
            "native_area_callbacks",
            "native_start_events",
            "native_environment",
        }:
            self.incomplete.append("unknown_native_flags")
            flags = {
                key: value
                for key, value in flags.items()
                if key
                in {
                    "native_area_callbacks",
                    "native_start_events",
                    "native_environment",
                }
            }
        environment = flags.get("native_environment", {})
        if type(environment) is not dict:
            self.incomplete.append("invalid_native_environment")
            environment = {}
        if set(environment) - set(ENVIRONMENT):
            # Unknown values can be secrets. Preserve neither names nor values.
            self.incomplete.append("unknown_native_environment_entries")
        if "native_environment" in flags:
            flags["native_environment"] = {
                key: value
                for key, value in environment.items()
                if key in ENVIRONMENT and value in ("0", "1")
            }
        if any(
            value not in ("0", "1")
            for key, value in environment.items()
            if key in ENVIRONMENT
        ):
            self.incomplete.append("invalid_native_environment_policy")
        self.policies = {
            key: os.environ.get(key, default) for key, default in ENVIRONMENT.items()
        }
        if any(value not in ("0", "1") for value in self.policies.values()):
            self.incomplete.append("invalid_execution_policy")
            self.policies = {}
        deadline_module = importlib.import_module(
            type(oracle).__module__.rsplit(".", 1)[0] + ".native_deadline"
        )
        active = deadline_module._ACTIVE.get()
        self.deadline_active = active is not None
        self.deadline = (
            None
            if active is None
            else {"absolute": active[0], "clock_identity": _provider(active[1])}
        )
        if active is not None and self.deadline["clock_identity"] != {
            "module": "time",
            "qualname": "monotonic",
        }:
            self.incomplete.append("unqualified_native_deadline_clock")
        authorities = oracle.authorities()
        authorities.pop("outcomeFeaturesProvider", None)
        self.before = encode_state(
            dict(
                runtime=oracle.runtime,
                action=deepcopy(action),
                authorities=authorities,
                flags=flags,
                stats_inputs=stats,
                providers=providers,
                provider_aliases=aliases,
                runtime_stats_inputs=runtime_stats_inputs,
                rail_inputs=rail_inputs,
            )
        )
        with _CORRELATION_LOCK:
            values = list(_CORRELATIONS.get(oracle.runtime, ()))
            _CORRELATIONS[oracle.runtime] = tuple((values + [self.incident_id])[-16:])

    def packets(self, packets):
        if type(packets) not in (tuple, list):
            self.incomplete.append("nonmaterialized_delivery")
        else:
            self.delivery = tuple(packets)

    def receipt(self, observation, error=None):
        observations = observation.snapshot()
        return dict(
            schema=SCHEMA,
            recipe=RECIPE,
            incident_id=self.incident_id,
            correlation_id=self.incident_id,
            identity=self.identity,
            sdk_source=self.sdk_source,
            before=self.before,
            after=encode_state(
                dict(runtime=self.oracle.runtime, packets=self.delivery)
            ),
            observations=encode_state(observations),
            error=_error(error),
            status="accepted" if error is None else "raised",
            policies=self.policies,
            clocks=self.clocks,
            deadline_active=self.deadline_active,
            replay_qualified=False,
            deadline=self.deadline,
            incomplete=self.incomplete + list(observations["incomplete"]),
            delivery_boundary="native_oracle_commit_before_registry_publication",
        )


@contextmanager
def npc_commit_scope(oracle, action, stats_serializer):
    """Observe once; diagnostic failures never change gameplay results."""
    root = os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
    if not root or _REPLAY.get():
        yield None
        return
    try:
        capture = NPCCommitCapture(oracle, action, stats_serializer)
    except Exception as failure:
        LOGGER.warning(
            "combat_npc_capture_setup_failed type=%s", type(failure).__name__
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
                    from .combat_npc_publication import remember_private_commit

                    remember_private_commit(oracle.runtime, receipt)
                if (
                    error is not None
                    or os.environ.get("WAKFU_COMBAT_INCIDENT_MODE", "failures") == "all"
                ):
                    from .combat_incident_capture import _enqueue

                    _enqueue(root, receipt)
            except Exception as failure:
                LOGGER.warning(
                    "combat_npc_capture_failed type=%s", type(failure).__name__
                )


def replay_npc_receipt(receipt, *, return_runtime=False):
    """One real commit on an isolated graph; no decision request or Store read."""
    from unittest.mock import patch
    from .combat_reproduction import source_identity, catalog_identity

    if (
        type(receipt) is not dict
        or receipt.get("schema") != SCHEMA
        or receipt.get("recipe") != RECIPE
        or receipt.get("incomplete") != []
    ):
        raise UnsupportedNPCReproduction("Incomplete or unsupported chosen NPC receipt")
    identity = receipt["identity"]
    if (
        identity["source"] != source_identity()
        or identity["catalog"] != catalog_identity()
    ):
        raise UnsupportedNPCReproduction("Native engine source or catalog changed")
    oracle_module, stats_module, directory = _sdk_modules()
    if receipt["sdk_source"] != sdk_identity(directory):
        raise UnsupportedNPCReproduction("Native SDK source changed")
    state = decode_state(receipt["before"])
    runtime, authorities, providers = (
        state["runtime"],
        state["authorities"],
        state["providers"],
    )
    if set(state["flags"]) - {
        "native_start_events",
        "native_area_callbacks",
        "native_environment",
    }:
        raise UnsupportedNPCReproduction("Unknown native execution flags")
    oracle = oracle_module.NativeOracle(
        runtime,
        characters=authorities["characters"],
        monsters=authorities["monsters"],
        decks=authorities["decks"],
        excluded_decks=authorities["excludedDecks"],
        viewer_id=authorities["viewerId"],
        flags=state["flags"],
    )
    # The constructor validates the snapshots, then copies them defensively.
    # Reuse this isolated graph's captured owners to preserve aliases between
    # oracle authorities and the already installed pure actor service.
    for field, key in (
        ("characters", "characters"),
        ("monsters", "monsters"),
        ("decks", "decks"),
        ("excluded_decks", "excludedDecks"),
    ):
        setattr(oracle, field, authorities[key])
    oracle.flags = state["flags"]
    serializer = stats_module.NativeStats(**state["stats_inputs"])
    from .combat_reproduction import ReproductionClock

    restored_clock = ReproductionClock(receipt["clocks"])
    clock = _routine(restored_clock, providers["clock"])
    observations = decode_state(receipt["observations"])
    from .combat_live_reproduction import prepare_live_context

    live_identities = {
        name: providers[name]
        for name in ("runtime_stats_serializer", "expiration_runtime_factory")
        if providers[name] is not None
    }
    if (
        providers["stats_serializer"] is not None
        and state["runtime_stats_inputs"] is None
    ):
        live_identities["stats_serializer"] = providers["stats_serializer"]
    context = prepare_live_context(
        runtime,
        None,
        {
            "live_provider_identity": live_identities,
            "native_events": state["flags"].get("native_start_events", True),
            "area_callbacks": state["flags"].get("native_area_callbacks", False),
            "map_id": state["stats_inputs"]["map_id"],
        },
        clock,
        observations,
    )
    implementations = {
        "clock": clock,
        "turn_start_provider": oracle.live_start_boundary,
        "turn_end_provider": oracle.live_end_boundary,
        "runtime_stats_serializer": context.serialize_runtime,
        "expiration_runtime_factory": context._factory,
        "stats_serializer": (
            stats_module.NativeStats(**state["runtime_stats_inputs"])
            if state["runtime_stats_inputs"] is not None
            else context.serialize_runtime
        ),
    }
    restored = {}
    for name in _PROVIDER_FIELDS:
        if providers[name] is None:
            setattr(runtime, name, None)
            continue
        alias = state["provider_aliases"].get(name)
        if alias not in _PROVIDER_FIELDS or providers[alias] != providers[name]:
            raise UnsupportedNPCReproduction("Invalid captured provider alias")
        if alias not in restored:
            implementation = implementations[alias]
            restored[alias] = (
                implementation
                if alias == "stats_serializer"
                and state["runtime_stats_inputs"] is not None
                else _routine(implementation, providers[alias])
            )
        setattr(runtime, name, restored[alias])
    _restore_rail(runtime, state["rail_inputs"])
    # Catalog reads are preserved as evidence and independently source-pinned.
    # Only ordered RNG/clock events are inputs owned by this tape; snapshot
    # authorities above replace no runtime provider observations.
    observations = deepcopy(observations)
    observations["events"] = [
        row for row in observations["events"] if row["kind"] in ("rng", "clock")
    ]
    for index, row in enumerate(observations["events"], 1):
        row["sequence"] = index
    policies = receipt["policies"]
    if set(policies) != set(ENVIRONMENT) or any(
        v not in ("0", "1") for v in policies.values()
    ):
        raise UnsupportedNPCReproduction("Invalid native execution policies")
    packets, error = (), None
    token = _REPLAY.set(True)
    deadline_module = importlib.import_module(
        oracle_module.__package__ + ".native_deadline"
    )
    deadline = receipt.get("deadline")
    if (
        receipt.get("deadline_active") != (deadline is not None)
        or deadline is not None
        and (
            type(deadline) is not dict
            or set(deadline) != {"absolute", "clock_identity"}
            or type(deadline["absolute"]) not in (int, float)
            or not math.isfinite(deadline["absolute"])
            or deadline["clock_identity"] != {"module": "time", "qualname": "monotonic"}
        )
    ):
        _REPLAY.reset(token)
        raise UnsupportedNPCReproduction("Invalid captured native deadline")
    deadline_token = deadline_module._ACTIVE.set(
        None if deadline is None else (deadline["absolute"], clock)
    )
    try:
        with patch.dict(os.environ, policies), replay_combat_inputs(observations):
            try:
                packets = tuple(
                    oracle.commit(state["action"], stats_serializer=serializer)
                )
            except InputReplayMismatch:
                raise
            except Exception as failure:
                error = _error(failure)
            context.assert_complete()
    finally:
        deadline_module._ACTIVE.reset(deadline_token)
        _REPLAY.reset(token)
    after = encode_state(dict(runtime=runtime, packets=packets))
    # Provider code is reconstructed; compare data and required service fields.
    comparison = after_comparison(receipt["after"], after)
    matches = comparison["scalar_value_matches"] and error == receipt["error"]
    if (
        sdk_identity(directory) != receipt["sdk_source"]
        or source_identity() != identity["source"]
    ):
        raise UnsupportedNPCReproduction("Native sources changed during reproduction")
    result = dict(
        matches=matches,
        after=after,
        error=error,
        packets=packets,
        comparison=comparison,
        boundary="native_oracle_commit_before_registry_publication",
    )
    if return_runtime:
        result["runtime"] = runtime
    return result
