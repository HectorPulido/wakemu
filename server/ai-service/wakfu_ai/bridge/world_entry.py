"""Complete native SDK entry point loaded by the final stable world shim."""
from ..native.native_control import effective_server_controlled
import os
from copy import deepcopy
from pathlib import Path
import threading
import tempfile
import time

from ..native.native_deadline import bounded, check

from ..native.native_store import load_authorities
from ..native.native_profiles import encounter_profiles
from ..native.native_turn import run_turn
from ..native.native_stats import NativeStats
from ..native.native_actor_source import registered_source
from .world_bridge import CompleteContextExporter
from ..transport.endpoint import DEFAULT_ENDPOINT, tcp_address

_EXPORTERS = {}
_EXPORTER_LOCK = threading.Lock()


def context_transport(url=DEFAULT_ENDPOINT, *, first_turn=False, timeout=None):
    """Use the persistent TCP channel for every native query and context."""
    from ..transport.framed_context import FramedContextTransport

    host, port = tcp_address(url)
    return FramedContextTransport(
        host, port, timeout=(20 if first_turn else 10) if timeout is None else timeout
    )


def native_exporter():
    import wakfu_server
    from wakfu_server.paths import DATA_ROOT

    engine = Path(wakfu_server.__file__).resolve().parent
    server = engine.parent
    key = str(server), str(DATA_ROOT)
    with _EXPORTER_LOCK:
        if key not in _EXPORTERS:
            # No source file whitelist: future server/SDK files are available
            # without another outside-world integration change. Duplicate
            # bytes share their content hash and are never uploaded twice.
            _EXPORTERS[key] = CompleteContextExporter(
                {"catalog": DATA_ROOT, "engine": engine, "server": server},
                cache_root=Path(tempfile.gettempdir())
                / "wakfu-ai-native-catalog-cache",
            )
        return _EXPORTERS[key]


def run_npc_turn(
    runtime,
    *,
    store=None,
    viewer_character=None,
    monsters=None,
    stats_serializer=None,
    shared_adapter=None,
    session=None,
    world_context=None
):
    """Receive complete live dependencies once; return native FIFO deliveries."""
    if world_context is not None:
        from .world_host import execute

        yield from execute(runtime, world_context, run_npc_turn)
        return
    if session is not None:
        if shared_adapter is None:
            raise ValueError("Shared native AI requires its encounter coordinator")
        from .world_shared import run_shared_turn

        yield from run_shared_turn(
            runtime,
            shared_adapter,
            session,
            lambda candidate: run_npc_turn(
                candidate,
                store=store,
                viewer_character=viewer_character,
                monsters=monsters,
                stats_serializer=stats_serializer,
            ),
        )
        return
    if runtime.awaiting_ack is not None or runtime.pending:
        return
    from wakfu_server.combat_automatic_npc_turn import requires_automatic_npc_turn_end

    if requires_automatic_npc_turn_end(runtime.fight, runtime.fight.current):
        yield runtime.end_automatic_npc_turn(
            runtime.fight.current.id, runtime.fight.turn_id
        ), dict(
            action={"type": "end_turn"},
            reason="ordinary_root_without_action_controller",
        )
        return
    # The preparation phase must fail as a turn outcome, not disconnect the
    # owning game session before the turn driver can apply its fallback.
    from psycopg import Error as DatabaseError

    bridge_started = time.monotonic()
    try:
        from .backend_selection import pin_backend

        backend = pin_backend(runtime)
        runner = _run_npc_turn
        if backend["backend"] == "jondo":
            from .jondo_entry import run_npc_turn as runner
        yield from runner(
            runtime,
            store=store,
            viewer_character=viewer_character,
            monsters=monsters,
            stats_serializer=stats_serializer,
        )
    except (ValueError, TypeError, OSError, DatabaseError) as error:
        diagnostic = dict(
            action={"type": "end_turn"},
            reason="complete_native_bridge_rejected",
            detail=str(error),
            error=type(error).__name__,
            stage="bridge_preparation",
            bridgeElapsedMs=(time.monotonic() - bridge_started) * 1000,
        )
        yield [], diagnostic
        fight = runtime.fight
        if (
            fight.phase == "active"
            and fight.current is not None
            and effective_server_controlled(fight, fight.current)
            and runtime.awaiting_ack is None
            and not runtime.pending
        ):
            yield runtime.end_server_turn(fight.current.id, fight.turn_id), diagnostic


def _run_npc_turn(runtime, *, store, viewer_character, monsters, stats_serializer):
    started = min(
        time.monotonic(),
        getattr(runtime, "native_ai_preparation_started_at", time.monotonic()),
    )
    # The first actual turn of each actor includes cold authority/catalog work.
    # Actor-local turn count also covers monsters introduced by later rift waves;
    # resuming the same turn must not consume or renew this allowance.
    first_turn = getattr(runtime.fight.current, "turn_count", None) == 1
    allowance_seconds = 20 if first_turn else 10
    # Preparation consumes the same allowance as planning and transport.
    with bounded(started + allowance_seconds):
        yield from _prepare_npc_turn(
            runtime,
            store=store,
            viewer_character=viewer_character,
            monsters=monsters,
            stats_serializer=stats_serializer,
            started=started,
        )


def _prepare_npc_turn(
    runtime, *, store, viewer_character, monsters, stats_serializer, started
):
    viewer_id = viewer_character["id"]
    stage_started = time.monotonic()
    authorities = load_authorities(runtime, store, monsters, viewer_id=viewer_id)
    preparation_ms = {"authorities": (time.monotonic() - stage_started) * 1000}
    check()
    stage_started = time.monotonic()
    profiles = encounter_profiles(runtime, store, authorities["monsters"])
    preparation_ms["profiles"] = (time.monotonic() - stage_started) * 1000
    check()
    current = runtime.fight.current
    descriptor = (
        authorities["monsters"].get(current.id) if current is not None else None
    )
    if current is not None and current.id in authorities["registrations"]:
        descriptor = registered_source(
            current, authorities["registrations"][current.id]
        )
    profile = profiles.get(
        descriptor["ref"] if descriptor is not None else None, profiles[None]
    )
    turn_ms = profile["policy"].get("limits", {}).get("turnMs", 10000)
    if type(turn_ms) is not int or not 1 <= turn_ms <= 60000:
        raise ValueError("Invalid complete native turn deadline")
    first_turn = getattr(current, "turn_count", None) == 1
    if first_turn:
        turn_ms = max(turn_ms, 20000)
    flags = dict(
        native_area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "0") == "1",
        native_start_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
        native_environment={
            key: value
            for key, value in os.environ.items()
            if key.startswith("WAKFU_NATIVE_")
        },
    )
    url = os.environ.get("WAKFU_AI_URL", DEFAULT_ENDPOINT)
    # The transport still clips each request to the original absolute deadline.
    # Its normal ten-second socket cap must not truncate first-turn cold work.
    transport = context_transport(url, first_turn=first_turn)
    try:
        with bounded(started + turn_ms / 1000):
            stage_started = time.monotonic()
            serializer = NativeStats(
                characters=authorities["characters"],
                monsters=authorities["monsters"],
                fight_id=runtime.fight.id,
                registrations=authorities["registrations"],
                map_id=viewer_character["map_id"],
            )
            preparation_ms["stats"] = (time.monotonic() - stage_started) * 1000
            stage_started = time.monotonic()
            exporter = native_exporter()
            preparation_ms["exporter"] = (time.monotonic() - stage_started) * 1000
            check()
            for delivery in run_turn(
                runtime,
                characters=authorities["characters"],
                monsters=authorities["monsters"],
                decks=authorities["decks"],
                excluded_decks=authorities["excluded_decks"],
                viewer_id=viewer_id,
                flags=flags,
                transport=transport,
                exporter=exporter,
                policy=profile["policy"],
                policy_version=profile["identity"],
                stats_serializer=serializer,
                budget_seconds=turn_ms / 1000,
            ):
                if (
                    isinstance(delivery, tuple)
                    and len(delivery) == 2
                    and isinstance(delivery[1], dict)
                ):
                    packets, diagnostic = delivery
                    diagnostic = dict(
                        diagnostic,
                        preparationElapsedMs=dict(preparation_ms),
                        bridgeElapsedMs=(time.monotonic() - started) * 1000,
                        transportMetrics=deepcopy(getattr(transport, "metrics", {})),
                    )
                    yield packets, diagnostic
                else:
                    yield delivery
    finally:
        close = getattr(transport, "close", None)
        if callable(close):
            close()
