"""Explicit worker envelopes for tests of World's retained planting authority.

Probability and growth candidates are fixture inputs. This module does not
choose species, calculate eligibility/probability, or scan for due resources.
The optional ``mature`` adapter asks the real Rust planner for due candidates.
"""

import atexit
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from datetime import date, datetime

from wakfu_server import planting


def prepare(
    store,
    account,
    generation,
    character,
    body,
    *,
    authorize_cell,
    probability=1.0,
    duration_ms=None,
    item_reference=None,
    open_test_policy=None,
):
    """Build the worker envelope from explicit probability and owned seed ID."""
    request = planting.decode(body)
    with store.connection() as db:
        if item_reference is None:
            item = db.execute(
                "SELECT reference FROM inventory_items WHERE uid=%s AND character_id=%s",
                (request["item_uid"], character["id"]),
            ).fetchone()
            if item is None:
                raise ValueError("Seed fixture is not owned")
            item_reference = item["reference"]
        if duration_ms is None:
            row = db.execute(
                "SELECT value FROM settings WHERE name='planting_duration_ms'"
            ).fetchone()
            duration_ms = None if row is None else row["value"]
    seed = planting.SEEDS.get(item_reference)
    if seed is None:
        raise ValueError("Seed fixture lacks a native planting action")
    definition = planting.RESOURCES[seed["resource_reference"]]
    z = authorize_cell(character, request, seed, definition)
    return dict(
        character=dict(character),
        request=request,
        seed=seed,
        definition=definition,
        z=z,
        probability=probability,
        duration_ms=duration_ms,
    )


def begin_prepared(
    runtime,
    account,
    generation,
    character,
    body,
    authorize_cell,
    *,
    probability=1.0,
    duration_ms=None,
    item_reference=None,
):
    prepared = prepare(
        runtime.store,
        account,
        generation,
        character,
        body,
        authorize_cell=authorize_cell,
        probability=probability,
        duration_ms=duration_ms,
        item_reference=item_reference,
    )
    return runtime.begin_prepared(
        account, generation, character, body, prepared, authorize_cell
    )


def grow_prepared(
    runtime, groups, candidates, *, prepared_members=None, publish, random_draw=None
):
    """Commit explicit candidates and publish through the real World outbox."""
    options = {} if random_draw is None else {"random_draw": random_draw}
    runtime.apply_growth_candidates(
        candidates, prepared_members=prepared_members, **options
    )
    return runtime.publish_growth(groups, publish=publish)


_PROBE = None
_PROBE_LOCK = threading.Lock()


def _close_probe():
    if _PROBE is not None and _PROBE.poll() is None:
        _PROBE.stdin.close()
        try:
            _PROBE.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _PROBE.terminate()
            _PROBE.wait(timeout=2)


atexit.register(_close_probe)


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    raise TypeError(f"Unsupported fixture JSON value: {type(value).__name__}")


def _rust(request):
    global _PROBE
    with _PROBE_LOCK:
        if _PROBE is None or _PROBE.poll() is not None:
            binary = os.environ.get("WAKFU_ECOLOGY_NATIVE_PROBE_BIN") or os.environ.get(
                "WAKFU_ECOLOGY_NATIVE_PROBE"
            )
            if not binary:
                binary = str(
                    Path(__file__).resolve().parents[1]
                    / "rust-services/target/debug/ecology-native-probe"
                )
            if not Path(binary).is_file():
                raise RuntimeError(
                    "Build ecology-native-probe or set WAKFU_ECOLOGY_NATIVE_PROBE"
                )
            _PROBE = subprocess.Popen(
                [binary],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
            )
        _PROBE.stdin.write(
            json.dumps(request, separators=(",", ":"), default=_json_default) + "\n"
        )
        _PROBE.stdin.flush()
        raw = _PROBE.stdout.readline()
        if not raw:
            raise RuntimeError("Rust planting fixture probe exited")
        result = json.loads(raw)
        if "error" in result:
            raise ValueError(result["error"])
        return result["result"]


def mature(runtime, groups, *, publish, random_draw=None, players=()):
    """Run actual Rust growth policy against this case's isolated read-only DB."""
    snapshot = dict(
        world_epoch="fixture:"
        + hashlib.sha256(runtime.store.database_url.encode()).hexdigest(),
        now_ms=int(runtime.store.clock() * 1000),
        planning_tick=0,
        growth_seconds=runtime.growth_seconds,
        players=list(players),
        skip_interactive=True,
    )
    proposals = _rust(
        dict(
            operation="prepare_growth",
            test_database_url=runtime.store.database_url,
            snapshot=snapshot,
            limit=64,
        )
    )
    candidates, members = [], {}
    for proposal in proposals:
        rows = (
            proposal.get("resources", [])
            if proposal["kind"] == "resource_growth_bulk"
            else [proposal]
        )
        for row in rows:
            if row["kind"] != "resource_growth":
                continue
            resource = row["expected"]
            transition = row.get("transition")
            candidates.append(
                (
                    resource,
                    planting.RESOURCES[resource["resource_reference"]],
                    None if transition is None else tuple(transition),
                )
            )
            if row.get("member") is not None:
                members[resource["resource_uid"]] = row["member"]
    return grow_prepared(
        runtime,
        groups,
        candidates,
        prepared_members=members,
        publish=publish,
        random_draw=random_draw,
    )


def prepare_intents(store, snapshot, *, limit=4):
    """Ask the native intent planner; reuse Inventory's authority when required."""
    snapshot = dict(snapshot)
    if not snapshot.get("open_planting", True) or any(
        player.get("map_id") == 9 for player in snapshot.get("players", ())
    ):
        from wakfu_server.planting_equipment_projection import pending_projection

        snapshot["planting_equipment"] = pending_projection(
            store,
            snapshot["world_epoch"],
            snapshot["started_at_ms"],
            gardens_only=snapshot.get("open_planting", True),
        )
    return _rust(
        dict(
            operation="prepare_intents",
            test_database_url=store.database_url,
            snapshot=snapshot,
            limit=limit,
        )
    )
