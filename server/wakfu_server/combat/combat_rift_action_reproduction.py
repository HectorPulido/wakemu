"""Isolated diagnostic recipe for one private Rift player end-turn operation.

This does not replay Registry publication, Rift accepted-action hooks, checkpoint
SQL, ACK fanout, or a wave transition. No capture hook is installed by this module.
Encode before/after outside the measured operation and never install replay on a
live World thread. Incomplete evidence is a diagnostic failure, not gameplay.
"""
from contextlib import contextmanager
from types import MethodType
import time
import os
import hashlib

from .combat_input_observation import (
    InputReplayMismatch,
    observe_combat_inputs,
    replay_combat_inputs,
)
from .combat_reproduction_state import encode_state, decode_state
from .combat_rift_provider_recipe import capture_providers, restore_providers

SCHEMA = "wakemu-private-rift-end-turn-v2"
COMPARISON_POLICY = "native-graph-except-str-interning-v1"
_STATS = ("stats_serializer", "runtime_stats_serializer")
_FIELDS = _STATS + (
    "turn_start_provider",
    "turn_end_provider",
    "expiration_runtime_factory",
    "clock",
)


class RiftReplayError(InputReplayMismatch):
    pass


def _graph(value):
    return encode_state(value, preserve_scalars=True)


def _qualified(runtime, action):
    from .combat_runtime_messages import RuntimeMessages
    from .combat_state import Fight
    from .combat_retained_gc_authority import capture_native_callbacks

    if (
        type(runtime) is not RuntimeMessages
        or type(runtime.fight) is not Fight
        or getattr(runtime.fight, "rift_wave_state", None) is None
        or type(action) is not dict
        or set(action) != {"type", "owner_id", "actor_id", "turn_id"}
        or action["type"] != "end_turn"
        or any(
            type(action[key]) is not int for key in ("owner_id", "actor_id", "turn_id")
        )
    ):
        raise RiftReplayError("Unsupported private Rift operation")
    callback = runtime.end_turn
    if (
        type(callback) is not MethodType
        or callback.__self__ is not runtime
        or callback.__func__ is not RuntimeMessages.end_turn
        or capture_native_callbacks(runtime) is None
    ):
        raise RiftReplayError("Missing native private-delivery callback proof")
    if runtime.clock is not time.monotonic:
        raise RiftReplayError("Unsupported native runtime clock")


def _stats_payload(runtime, *, sdk_source=None):
    from .combat_npc_reproduction import _sdk_modules

    _, stats_module, _ = _sdk_modules(runtime, sdk_source=sdk_source)
    provider = runtime.stats_serializer
    if (
        type(provider) is not stats_module.NativeStats
        or runtime.runtime_stats_serializer is not provider
    ):
        raise RiftReplayError(
            "This recipe requires the actual shared NativeStats owner"
        )
    attrs = vars(provider)
    if set(attrs) != {"characters", "monsters", "fight_id", "registrations", "map_id"}:
        raise RiftReplayError("Unsupported native statistics extension")
    for name, original in stats_module._GC_STATS_METHODS.items():
        if getattr(type(provider), name) is not original or name in attrs:
            raise RiftReplayError("Native statistics implementation differs")
    return {"fields": dict(attrs)}


def _binding_aliases(runtime):
    seen = {}
    return {
        field: (
            None
            if getattr(runtime, field) is None
            else seen.setdefault(id(getattr(runtime, field)), field)
        )
        for field in _FIELDS
    }


def _rail_payload(runtime):
    from .combat_npc_reproduction import _rail_inputs
    from .combat_summon import RegisteredSummonAuthority

    authority = getattr(runtime.fight, "native_rail_movement_authority", None)
    if authority is not None:
        if type(authority) is RegisteredSummonAuthority:
            if set(vars(authority)) != {"ordinary"}:
                raise RiftReplayError("Extended registered rail authority")
            authority = authority.ordinary
        if set(vars(authority)) != {
            "characters",
            "monsters",
            "decks",
            "excluded_decks",
            "deck_caps",
            "deck_blobs",
            "catalog",
            "npc_spellbook",
        }:
            raise RiftReplayError("Extended ordinary rail authority")
    return _rail_inputs(runtime)


def _restore_rail_aliases(runtime, facts):
    from .combat_npc_reproduction import _restore_rail
    from .combat_summon import RegisteredSummonAuthority

    _restore_rail(runtime, facts)
    if facts is not None:
        authority = runtime.fight.native_rail_movement_authority
        if type(authority) is RegisteredSummonAuthority:
            authority = authority.ordinary
        # The validated constructor defensively copies these two mappings.
        # Restore the captured graph's owners after validation, before execution.
        for key, value in facts["inputs"].items():
            setattr(authority, key, value)
    _rail_payload(runtime)


def _payload(runtime, action):
    _qualified(runtime, action)
    return {
        "runtime": runtime,
        "action": action,
        "providers": capture_providers(runtime),
        "stats": _stats_payload(runtime),
        "aliases": _binding_aliases(runtime),
        "rail": _rail_payload(runtime),
        "native_callback_proof": True,
    }


def _owned_scope(runtime):
    from .combat_native_action_ids import _OWNED_DELIVERY
    from .combat_runtime_messages import RuntimeMessages

    scope = _OWNED_DELIVERY.get()
    if (
        type(scope) is not tuple
        or len(scope) != 2
        or scope[0] is not runtime
        or scope[1] is not RuntimeMessages.end_turn
    ):
        raise RiftReplayError("Capture is not inside the actual owned end-turn scope")


def capture_before(runtime, action):
    """Call inside the real private scope, before the measured boundary."""
    _owned_scope(runtime)
    from .combat_reproduction import source_identity, catalog_identity
    from .combat_npc_reproduction import _sdk_modules, sdk_identity

    _, _, directory = _sdk_modules(runtime)
    from .combat_npc_reproduction import ENVIRONMENT

    return {
        "schema": SCHEMA,
        "scope": "private-end-turn-before-publication",
        "comparison_policy": COMPARISON_POLICY,
        "policies": {
            key: os.environ.get(key, default) for key, default in ENVIRONMENT.items()
        },
        "identity": {
            "source": source_identity(),
            "catalog": catalog_identity(),
            "sdk": sdk_identity(directory),
        },
        "before": _graph(_payload(runtime, action)),
    }


def finish_capture(receipt, runtime, packets, observation, *, action):
    """Call after timing, retaining all Fight fields including Rift state."""
    before = decode_state(receipt["before"])
    if action != before["action"]:
        raise RiftReplayError("Captured action changed")
    if getattr(observation, "_rift_operation_runtime", None) is not runtime:
        raise RiftReplayError("Missing observed private-delivery scope")
    # Verify wave identity/value without deleting or projecting any Rift fields.
    before_wave = before["runtime"].fight.rift_wave_state
    if before_wave != runtime.fight.rift_wave_state:
        raise RiftReplayError("Wave transition is outside this operation recipe")
    result = dict(receipt)
    result["owned_delivery"] = True
    result["after"] = _graph({"payload": _payload(runtime, action), "packets": packets})
    result["observations"] = _graph(observation.snapshot())
    return result


@contextmanager
def observe_operation(runtime):
    """Observe only inside the real caller-owned private delivery scope."""
    _owned_scope(runtime)
    with observe_combat_inputs(limit=20000, max_value_bytes=16_000_000) as tape:
        tape._rift_operation_runtime = runtime
        yield tape


def _restore_stats(runtime, payload, *, sdk_source=None):
    from .combat_npc_reproduction import _sdk_modules

    _, stats_module, _ = _sdk_modules(runtime, sdk_source=sdk_source)
    provider = stats_module.NativeStats(**payload["fields"])
    provider.__dict__.update(payload["fields"])
    runtime.stats_serializer = runtime.runtime_stats_serializer = provider
    _stats_payload(runtime, sdk_source=sdk_source)


@contextmanager
def _verified_catalog_reads(expected_identity):
    """Verify actual cold-read bytes; cache/backend telemetry is not gameplay input.

    Offline replay only. A loaded source uses the already pinned release and full
    path/SHA inventory; actual misses additionally prove the returned raw bytes.
    The original observer still records every read without changing its schema.
    """
    from unittest.mock import patch
    from wakfu_server import native_catalog
    from .combat_reproduction import digest

    inventory = native_catalog.document_hashes()
    if (
        native_catalog.release() != expected_identity["revision"]
        or digest(inventory) != expected_identity["inventory_sha256"]
    ):
        raise RiftReplayError("Published catalog inventory differs")
    original = native_catalog._observe_read
    verified = {}

    def observe_read(name, source, raw, started, **stages):
        checksum = hashlib.sha256(raw).hexdigest()
        if inventory.get(name) != checksum:
            raise RiftReplayError("Actual catalog bytes differ from pinned inventory")
        verified[name] = checksum
        return original(name, source, raw, started, **stages)

    try:
        with patch.object(native_catalog, "_observe_read", observe_read):
            yield inventory, verified
    finally:
        # Break the local self-module closure cycle promptly after replay.
        observe_read = None


def _semantic_evidence(rows, inventory, revision):
    evidence = []
    for row in rows:
        if row["kind"] == "catalog" and row["label"] == "exists":
            if (
                type(row.get("path")) is not str
                or row.get("revision") != revision
                or type(row.get("value")) is not bool
                or row["value"] is not (row["path"] in inventory)
                or row.get("collection") is not None
                or row.get("record_key") is not None
            ):
                raise RiftReplayError("Catalog existence differs from pinned inventory")
            continue
        if row["kind"] == "catalog" and row["label"] == "read":
            value = row.get("value")
            if (
                row.get("path") not in inventory
                or type(value) is not dict
                or set(value) != {"size", "source"}
                or type(value["size"]) is not int
                or value["size"] < 0
                or value["source"] not in ("redis", "postgres")
                or any(
                    row.get(key) is not None
                    for key in ("revision", "collection", "record_key")
                )
            ):
                raise RiftReplayError("Unknown catalog read telemetry")
            continue
        if row["kind"] in ("authority", "catalog", "fact"):
            evidence.append(
                {key: value for key, value in row.items() if key != "sequence"}
            )
    return evidence


def replay(receipt):
    """Run one isolated native end-turn; native graph/packets under the declared string-interning policy."""
    from .combat_reproduction import source_identity, catalog_identity
    from .combat_npc_reproduction import _sdk_modules, sdk_identity
    from .combat_retained_gc_authority import _NativeCallbacks
    from .combat_native_action_ids import owned_native_delivery
    from .combat_runtime_messages import RuntimeMessages

    if (
        type(receipt) is not dict
        or receipt.get("schema") != SCHEMA
        or receipt.get("scope") != "private-end-turn-before-publication"
        or receipt.get("owned_delivery") is not True
        or receipt.get("comparison_policy") != COMPARISON_POLICY
    ):
        raise RiftReplayError("Unsupported Rift reproduction receipt")
    _, _, directory = _sdk_modules(sdk_source=receipt["identity"]["sdk"])
    identity = {
        "source": source_identity(),
        "catalog": catalog_identity(),
        "sdk": sdk_identity(directory),
    }
    if receipt["identity"] != identity:
        raise RiftReplayError("Replay source/catalog/SDK differs")
    from .combat_npc_reproduction import ENVIRONMENT

    if receipt["policies"] != {
        key: os.environ.get(key, default) for key, default in ENVIRONMENT.items()
    }:
        raise RiftReplayError("Native execution policy differs")
    state = decode_state(receipt["before"])
    runtime, action = state["runtime"], state["action"]
    observations = decode_state(receipt["observations"])
    if state["native_callback_proof"] is not True:
        raise RiftReplayError("Missing captured native callback provenance")
    runtime.clock = time.monotonic
    _restore_stats(runtime, state["stats"], sdk_source=receipt["identity"]["sdk"])
    restore_providers(
        runtime, state["providers"], sdk_source=receipt["identity"]["sdk"]
    )
    _restore_rail_aliases(runtime, state["rail"])
    if _binding_aliases(runtime) != state["aliases"]:
        raise RiftReplayError("Reconstructed callback aliases differ")
    # Issued only after every captured provider has passed the fixed recipe.
    from importlib import import_module

    oracle_module, _, _ = _sdk_modules(runtime, sdk_source=receipt["identity"]["sdk"])
    authority = import_module(oracle_module.__package__ + ".native_callback_authority")
    authority.renew_native_callbacks(runtime, _NativeCallbacks(()))
    _qualified(runtime, action)
    with _verified_catalog_reads(receipt["identity"]["catalog"]) as (
        inventory,
        verified,
    ):
        with owned_native_delivery(runtime, RuntimeMessages.end_turn):
            with observe_operation(runtime) as actual_inputs, replay_combat_inputs(
                observations
            ) as tape:
                packets = runtime.end_turn(
                    action["owner_id"], action["actor_id"], action["turn_id"]
                )
    if not tape.ownership_known:
        raise RiftReplayError("Unknown replay RNG ownership")
    # Exact source/fact/record values remain mandatory. A cache miss/transport
    # choice is telemetry, and each actual miss was verified above by raw SHA.
    expected = _semantic_evidence(
        observations["events"], inventory, identity["catalog"]["revision"]
    )
    actual = _semantic_evidence(
        actual_inputs.snapshot()["events"], inventory, identity["catalog"]["revision"]
    )
    if expected != actual:
        raise RiftReplayError("Recomputed source/catalog evidence differs")
    after = _graph({"payload": _payload(runtime, action), "packets": packets})
    from .combat_reproduction_graph_compare import compare_graphs

    if not compare_graphs(after, receipt["after"]):
        raise RiftReplayError("Exact after-state or packet graph differs")
    return {
        "matched": True,
        "scope": receipt["scope"],
        "packet_count": len(packets),
        "comparison_policy": COMPARISON_POLICY,
        "verified_cold_catalog_reads": len(verified),
    }
