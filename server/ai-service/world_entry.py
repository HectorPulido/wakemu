"""Complete native SDK entry point loaded by the final stable world shim."""
import os
from pathlib import Path
import threading
import tempfile

if __package__:
    from .native_store import load_authorities
    from .native_profiles import encounter_profiles
    from .native_turn import run_turn
    from .native_stats import NativeStats
    from .native_actor_source import registered_source
    from .world_bridge import CompleteContextExporter, ContextTransport
else:
    from native_store import load_authorities
    from native_profiles import encounter_profiles
    from native_turn import run_turn
    from native_stats import NativeStats
    from native_actor_source import registered_source
    from world_bridge import CompleteContextExporter, ContextTransport

_EXPORTERS = {}
_EXPORTER_LOCK = threading.Lock()


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
        if __package__:
            from .world_host import execute
        else:
            from world_host import execute
        yield from execute(runtime, world_context, run_npc_turn)
        return
    if session is not None:
        if shared_adapter is None:
            raise ValueError("Shared native AI requires its encounter coordinator")
        if __package__:
            from .world_shared import run_shared_turn
        else:
            from world_shared import run_shared_turn
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
    # The preparation phase must fail as a turn outcome, not disconnect the
    # owning game session before the turn driver can apply its fallback.
    from psycopg import Error as DatabaseError

    try:
        yield from _run_npc_turn(
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
        )
        yield [], diagnostic
        fight = runtime.fight
        if (
            fight.phase == "active"
            and fight.current is not None
            and not fight.current.controlled
            and runtime.awaiting_ack is None
            and not runtime.pending
        ):
            yield runtime.end_server_turn(fight.current.id, fight.turn_id), diagnostic


def _run_npc_turn(runtime, *, store, viewer_character, monsters, stats_serializer):
    viewer_id = viewer_character["id"]
    authorities = load_authorities(runtime, store, monsters, viewer_id=viewer_id)
    profiles = encounter_profiles(runtime, store, authorities["monsters"])
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
    flags = dict(
        native_area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "0") == "1",
        native_start_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
        native_environment={
            key: value
            for key, value in os.environ.items()
            if key.startswith("WAKFU_NATIVE_")
        },
    )
    url = os.environ.get("WAKFU_AI_URL", "http://ai:8090")
    transport = ContextTransport(url)
    serializer = NativeStats(
        characters=authorities["characters"],
        monsters=authorities["monsters"],
        fight_id=runtime.fight.id,
        registrations=authorities["registrations"],
    )
    yield from run_turn(
        runtime,
        characters=authorities["characters"],
        monsters=authorities["monsters"],
        decks=authorities["decks"],
        excluded_decks=authorities["excluded_decks"],
        viewer_id=viewer_id,
        flags=flags,
        transport=transport,
        exporter=native_exporter(),
        policy=profile["policy"],
        policy_version=profile["identity"],
        stats_serializer=serializer,
        budget_seconds=turn_ms / 1000,
    )
