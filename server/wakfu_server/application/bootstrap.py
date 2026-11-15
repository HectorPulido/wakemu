"""Local Python dispatcher/world prototype, seeded from the user's own capture."""

import base64
import sys
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import json
import itertools
import ipaddress
import math
import random
from pathlib import Path
import secrets
import signal
import socket
import ssl
import struct
import threading
import os
import subprocess
import time
import uuid
import weakref

from wakfu_server.performance_profiler import PROFILER

SERVER_BOOT_ID = uuid.uuid4().hex
from wakfu_server.spatial_native import NativeSpatial, configure_spatial

SPATIAL = NativeSpatial(SERVER_BOOT_ID)
configure_spatial(SPATIAL)
from wakfu_server.request_diagnostics import (
    RequestTrace,
    current_request,
    request_context,
    state_summary,
    movement_summary,
    redact,
    exception_frames,
    safe_snapshot,
)
from protocol_codec import Reader, decode_body
from wakfu_server.store import Store
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.api import serve_api
from wakfu_server import wire
from wakfu_server.world import World
from wakfu_server.movement import Movement
from wakfu_server.creation import create as create_character_request
from wakfu_server.creation import select_created as select_created_character
from wakfu_server import builds
from wakfu_server import (
    transports,
    native_transports,
    transport_discovery,
    world_static,
)
from wakfu_server import social
from wakfu_server.social_contacts import SocialContacts
from wakfu_server.social_dispatch import SocialDispatcher
from wakfu_server.shutdown import Connections

CONNECTIONS = Connections()
STOPPING = threading.Event()
from wakfu_server.live_console import LiveConsole

TEST_CONSOLE = LiveConsole()
from wakfu_server import world_clock
from wakfu_server import health, health_store
from wakfu_server.guild_haven_world import world_identity as native_item_world_identity
from wakfu_server import dungeon_transition_delivery, dungeon_hydration
from wakfu_server.world_scene_sync import (
    SceneSync,
    snapshot_ids,
    refresh_snapshots,
)

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent if ROOT.name == "server" else ROOT
RUNTIME = Path(
    os.environ.get("WAKFU_RUNTIME", PROJECT_ROOT / ".local-state/wakemu/world")
)
RUNTIME.mkdir(parents=True, exist_ok=True)
(RUNTIME / "logs").mkdir(exist_ok=True)
LOCK = threading.Lock()
STORE = Store(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
)
STORE.database.acquire_runtime_lock()
from wakfu_server.bootstrap_capture import (
    load as load_bootstrap_capture,
    DEFAULT_KEY as BOOTSTRAP_CAPTURE_KEY,
)

with STORE.connection() as _startup_db:
    FRAMES = load_bootstrap_capture(
        _startup_db,
        os.environ.get("WAKFU_BOOTSTRAP_CAPTURE_KEY", BOOTSTRAP_CAPTURE_KEY),
        expected_source_sha256=os.environ.get("WAKFU_BOOTSTRAP_SOURCE_SHA256"),
    )
    DUNGEON_TRANSITION_OUTBOX_AVAILABLE = _startup_db.execute(
        "SELECT to_regclass('dungeon_transition_outbox') IS NOT NULL AS available"
    ).fetchone()["available"]
    DUNGEON_ROOM_RUNTIME_AVAILABLE = _startup_db.execute(
        "SELECT to_regclass('dungeon_room_runs') IS NOT NULL AND "
        "to_regclass('dungeon_room_spawn_receipts') IS NOT NULL AND EXISTS("
        "SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('dungeon_room_encounters') "
        "AND pg_get_constraintdef(oid) LIKE '%aborted%') AS available"
    ).fetchone()["available"]
# Public installation templates have independent synthetic layout authority.
# A legacy private bootstrap has no metadata and retains its existing adapter.
if FRAMES and "synthetic_template" in FRAMES[0]:
    wire.register_synthetic_bootstrap(FRAMES[0]["synthetic_template"])

from wakfu_server import dungeon_instances

dungeon_instances.load_runtime_routes(STORE)
SOCIAL_CONTACTS = SocialContacts(STORE)
SOCIAL_ACTIONS = SocialDispatcher(SOCIAL_CONTACTS)
from wakfu_server.monster_collect import Harvests

HARVESTS = Harvests(STORE)
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting_location import owned_character as owned_planting_character
from wakfu_server.haven_bag_garden import active_character as active_garden_character

ECOLOGY_MODE = os.environ.get("WAKFU_ECOLOGY_MODE", "external")
if ECOLOGY_MODE == "inline":
    raise ValueError(
        "Inline ecology has been retired; use WAKFU_ECOLOGY_MODE=external "
        "with the Rust ecology service, or explicitly select disabled"
    )
if ECOLOGY_MODE not in ("external", "disabled"):
    raise ValueError("Invalid ecology execution mode")
ECOLOGY_BRIDGE = None
OPEN_PLANTING = os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1"
from wakfu_server.planting_bonus_publisher import Publisher as PlantingBonusPublisher

NATIVE_PLANTING_BONUS = (
    not OPEN_PLANTING and os.environ.get("WAKFU_NATIVE_PLANTING_BONUS", "0") == "1"
)
COMBAT_WIRE_TRACE = os.environ.get("WAKFU_COMBAT_WIRE_TRACE", "0") == "1"
REQUEST_STATE_DETAIL = os.environ.get("WAKFU_REQUEST_STATE_DETAIL", "0") == "1"
PLANTING_BONUSES = PlantingBonusPublisher(STORE)
PLANTINGS = Plantings(
    STORE,
    open_test_policy=OPEN_PLANTING,
    location_context=lambda stored: owned_planting_character(
        stored, WORLD, POSITIONS, store=STORE
    ),
    growth_seconds=float(os.environ.get("WAKFU_PLANT_GROWTH_SECONDS", "30")),
)
TRANSPORT_DISCOVERIES = transport_discovery.Discoveries(STORE)
ALL_ZAAPS = os.environ.get("WAKFU_ALL_ZAAPS", "1") == "1"
ALL_DRAGOS = os.environ.get("WAKFU_ALL_DRAGOS", "1") == "1"


from .position_persistence import PositionPersistence
from .travel_policy import TravelPolicy

_position_persistence = PositionPersistence(sys.modules[__name__])
_travel_policy = TravelPolicy(sys.modules[__name__])
known_transports = _travel_policy.known_transports


CHECKPOINTS = Checkpoints(STORE)
CHECKPOINTS.recover_interrupted()
from wakfu_server.rift_runtime import (
    reconcile_interrupted as reconcile_interrupted_rifts,
)

with STORE.connection() as rift_recovery_db:
    reconcile_interrupted_rifts(rift_recovery_db)
LIVE = {}
LOCAL_WORLD_ACTIONS = itertools.count(1)
from wakfu_server.position_redis import create as create_positions

position_lease_active = _position_persistence.position_lease_active


POSITIONS, POSITION_RECOVERY = create_positions(
    STORE,
    native=SPATIAL,
    lease_active=position_lease_active,
    url=os.environ.get("WAKFU_REDIS_URL"),
    namespace="wakfu:positions:postgres:v1",
)
POSITIONS.observer = lambda details: record(
    event="position_checkpoint_stage", **details
)


from wakfu_server.checkpoint_watchdog import CheckpointWatchdog

CHECKPOINT_WATCHDOG = CheckpointWatchdog(
    RUNTIME / "logs/checkpoint-slow-stacks.log", timeout=5.0
)


flush_positions = PROFILER.profile("persistence.position_checkpoint")(
    _position_persistence.flush_positions
)


from wakfu_server.manual_checkpoint import ManualCheckpoint

MANUAL_CHECKPOINT = ManualCheckpoint(flush_positions)


CLOCK_OFFSET_MS = world_clock.configured_offset_ms()
COMBAT_TEST = os.environ.get("WAKFU_ENABLE_COMBAT_TEST") == "1"
COMBAT_TEST_WP = (
    int(os.environ["WAKFU_COMBAT_TEST_WP"])
    if os.environ.get("WAKFU_COMBAT_TEST_WP", "").strip()
    else None
)
from wakfu_server.breed_resources import live_wp

COMBAT_TEST_CRITICAL_BRANCH = os.environ.get("WAKFU_COMBAT_CRITICAL_BRANCH", "auto")
if COMBAT_TEST_CRITICAL_BRANCH not in ("auto", "normal", "critical"):
    raise ValueError("WAKFU_COMBAT_CRITICAL_BRANCH must be auto, normal or critical")
if COMBAT_TEST:
    from wakfu_server.monsters import owned_instance

    group_size = int(os.environ.get("WAKFU_COMBAT_TEST_GROUP_SIZE", "1"))
    if group_size not in (1, 2):
        raise ValueError("Verified local test group size must be 1 or 2")
    TEST_MONSTERS = tuple(
        owned_instance(5525, 1, -200 - i, map_id=1134, x=-7, y=-7 + i, z=-1)
        for i in range(group_size)
    )
    TEST_MONSTER = TEST_MONSTERS[0]
    TEST_MONSTERS_BY_ID = {monster["id"]: monster for monster in TEST_MONSTERS}
    from wakfu_server.combat_group_store import PersistentGroups

    COMBAT_GROUPS = PersistentGroups(STORE, recover=True)
    if DUNGEON_ROOM_RUNTIME_AVAILABLE:
        from wakfu_server.dungeon_fight_binding import reconcile_aborted_encounters

        with STORE.connection() as dungeon_recovery_db:
            reconcile_aborted_encounters(dungeon_recovery_db)
    TEST_GROUP_KEY = COMBAT_GROUPS.register_seed(1134, 0, 200, TEST_MONSTERS)
    from wakfu_server.combat_session_adapter import CombatSessionAdapter

    COMBAT_SESSIONS = CombatSessionAdapter(
        STORE,
        player_appearance=lambda source: (
            12608,
            wire.spawn_player(PLAYER_TEMPLATE, source),
        ),
    )
    from wakfu_server.combat_spectators import ObserverSession, SpectatorRegistry
    from wakfu_server.combat_external_markers import ExternalFightMarkers

    def spectator_location_current(session):
        with STORE.connection() as db:
            row = db.execute(
                "SELECT c.map_id,c.instance_id FROM sessions s "
                "JOIN characters c ON c.account_id=s.account_id "
                "AND c.id=s.character_id WHERE s.account_id=%s "
                "AND s.generation=%s AND s.character_id=%s "
                "AND s.expires_at>%s AND c.deleted_at IS NULL",
                (
                    session.account_id,
                    session.generation,
                    session.character_id,
                    STORE.now(),
                ),
            ).fetchone()
        return row is not None and (row["map_id"], row["instance_id"]) == (
            session.map_id,
            session.instance_id,
        )

    SPECTATORS = SpectatorRegistry(
        lambda session: STORE.current_character_session(
            session.account_id, session.generation, session.character_id
        ),
        live_location=spectator_location_current,
    )
    EXTERNAL_FIGHT_MARKERS = ExternalFightMarkers()
CHARACTER = decode_body("out", 23664, base64.b64decode(FRAMES[44]["body_base64"]))


from .protocol_bootstrap import ProtocolBootstrap

_protocol_bootstrap = ProtocolBootstrap(sys.modules[__name__])
pack_text = _protocol_bootstrap.pack_text


send_shop_authentication = _protocol_bootstrap.send_shop_authentication


realms_local = _protocol_bootstrap.realms_local


fixture = _protocol_bootstrap.fixture


REALMS = realms_local(fixture(453))


character_list_local = _protocol_bootstrap.character_list_local


CHARACTERS = character_list_local(fixture(23548))


player_template = _protocol_bootstrap.player_template


PLAYER_TEMPLATE = player_template()


owned_hero_template = _protocol_bootstrap.owned_hero_template


OWNED_HERO_TEMPLATE = owned_hero_template()


from .transport import AbortedNativeReturn


from .transport import written_fight_id


from .transport import Connection as _Connection


class Connection(_Connection):
    def __init__(self, socket):
        super().__init__(socket, runtime=sys.modules[__name__])


from wakfu_server.async_diagnostic_log import AsyncDiagnosticLog

DIAGNOSTIC_LOG = AsyncDiagnosticLog(RUNTIME / "logs/game-server.jsonl")


from .diagnostics import Diagnostics

_diagnostics = Diagnostics(sys.modules[__name__])
write_records = _diagnostics.write_records


record = _diagnostics.record


from wakfu_server.checkpoint_worker import CheckpointWorker

CHECKPOINT_WRITER = CheckpointWorker(
    CHECKPOINTS,
    failed=lambda fight_id, error: record(
        event="combat_checkpoint_failed",
        fight_id=fight_id,
        reason=redact(str(error)),
    ),
)


from .network_delivery import NetworkDelivery

_network_delivery = NetworkDelivery(sys.modules[__name__])
receive = _network_delivery.receive


record_combat_wire_effect = _network_delivery.record_combat_wire_effect


publish_item_spell_updates = _network_delivery.publish_item_spell_updates


send = _network_delivery.send


send_batch = _network_delivery.send_batch


from wakfu_server.mount_publication import snapshot as mount_snapshot


from .world_publication import WorldPublication

_world_publication = WorldPublication(sys.modules[__name__])
consumable_state_packets = _world_publication.consumable_state_packets


world_state_packets = _world_publication.world_state_packets


rich_inventory_packet = _world_publication.rich_inventory_packet


from wakfu_server.haven_bag_exterior import ExteriorBags

HAVEN_BAG_EXTERIORS = ExteriorBags()

WORLD = World(
    lambda character: wire.spawn_player(PLAYER_TEMPLATE, character),
    wire.remove_player,
    lambda peer, opcode, body: send(peer, "world", opcode, body),
    native=SPATIAL,
    deliver_batch=lambda peer, packets: send_batch(peer, "world", packets),
    state_packets=world_state_packets,
    # The owner receives regional replacements from send_planting_context.
    # Peer actor creation still replays that actor's complete retained state.
    own_state_packets=lambda character: world_state_packets(
        character, include_territory=False, reset_riding=True
    ),
    refresh_state_packets=consumable_state_packets,
    delivery_failure=lambda peer, opcode, error: record(
        event="world_delivery_failed_before_shutdown",
        target_connection_id=getattr(peer, "trace_id", None),
        opcode=opcode,
        error=type(error).__name__,
        errno=error.errno,
    ),
)

from wakfu_server.objectives.environmental_presence import (
    configure as configure_environmental_presence,
)

configure_environmental_presence(WORLD)

from wakfu_server.territory_bonus_updates import RegionalBonusUpdates

REGIONAL_BONUSES = RegionalBonusUpdates(STORE, WORLD)

from wakfu_server.ecology_admin_jobs import (
    COMMANDS as ASYNC_ECOLOGY_COMMANDS,
    EcologyAdminCancelled,
    EcologyAdminJobs,
)


from .ecology_publication import EcologyPublication

_ecology_publication = EcologyPublication(sys.modules[__name__])
ecology_admin_coordination = contextmanager(
    _ecology_publication.ecology_admin_coordination
)


publish_ecology_admin_outcome = _ecology_publication.publish_ecology_admin_outcome


validate_ecology_admin_job = _ecology_publication.validate_ecology_admin_job


ECOLOGY_ADMIN_JOBS = EcologyAdminJobs(
    STORE,
    COMBAT_GROUPS if COMBAT_TEST else None,
    players=WORLD.ecology_snapshot,
    coordination=ecology_admin_coordination,
    publish=publish_ecology_admin_outcome,
    validate_actor=validate_ecology_admin_job,
)


submit_ecology_admin_command = _ecology_publication.submit_ecology_admin_command


from wakfu_server.party_dispatch import Parties
from wakfu_server.chat_channels import Channels
from wakfu_server.exchange_dispatch import Exchanges

PARTIES = Parties(STORE, WORLD)
CHANNELS = Channels(STORE, WORLD)
EXCHANGES = Exchanges(STORE, WORLD)
BOTS_BRIDGE = None


from .social_publication import SocialPublication

_social_publication = SocialPublication(sys.modules[__name__])
publish_bot_chat = _social_publication.publish_bot_chat


deliver_bot_whisper = _social_publication.deliver_bot_whisper


from wakfu_server.guild_dispatch import (
    Guilds,
    REQUEST_OPCODES as GUILD_REQUEST_OPCODES,
)

guild_local_entity = _social_publication.guild_local_entity


guild_company_packet = _social_publication.guild_company_packet


GUILDS = Guilds(
    STORE,
    WORLD,
    guild_local_entity,
    remote_publish=lambda character, packet: WORLD.emit_location_batch(
        character["map_id"],
        character["instance_id"],
        (packet,),
        exclude_character_id=character["id"],
    ),
    company_packet=guild_company_packet,
)


refresh_guild = _social_publication.refresh_guild


refresh_party = _social_publication.refresh_party


territory_weather_region_changed = _ecology_publication.territory_weather_region_changed


send_native_planting_bonus = _ecology_publication.send_native_planting_bonus


send_planting_context = _ecology_publication.send_planting_context


CORPSE_SCENES = weakref.WeakKeyDictionary()
CORPSE_SCENES_LOCK = threading.RLock()


monster_corpse_snapshot = _world_publication.monster_corpse_snapshot


join_world = PROFILER.profile("world.join")(_world_publication.join_world)


owned_scene_spawn_group = _world_publication.owned_scene_spawn_group


publish_available_group = _world_publication.publish_available_group


release_groups = _world_publication.release_groups


reconcile_closed_rift_login = _world_publication.reconcile_closed_rift_login


acknowledge_rift_login_bootstrap = _world_publication.acknowledge_rift_login_bootstrap


is_dungeon_run = _world_publication.is_dungeon_run


owned_native_bootstrap = PROFILER.profile("world.bootstrap")(
    _world_publication.owned_native_bootstrap
)


owned_haven_leave = _world_publication.owned_haven_leave


native_current_xp_rate = _world_publication.native_current_xp_rate


replay = _world_publication.replay


combat_group_for_target = _world_publication.combat_group_for_target


harvest_target = _world_publication.harvest_target


def session(raw, peer, service, context):
    from .session import Session
    import sys

    return Session(sys.modules[__name__], raw, peer, service, context).run()


def listen(port, service, context):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((os.environ.get("WAKFU_BIND_HOST", "127.0.0.1"), port))
        listener.listen(4)
        record(event="listening", service=service, address=f"127.0.0.1:{port}")
        print(f"Python {service}: TLS on 127.0.0.1:{port}", flush=True)
        while True:
            connection, peer = listener.accept()
            threading.Thread(
                target=session,
                args=(connection, peer, service, context),
                name="wakfu-client-session",
                daemon=True,
            ).start()


def expire_developer_test_actors():
    """Expire temporary developer actors independently of autonomous ecology."""
    last_expiry = 0.0
    while not STOPPING.wait(1):
        if time.monotonic() - last_expiry < 10:
            continue
        last_expiry = time.monotonic()
        try:
            from wakfu_server.item_test_spawns import expire as expire_test_actors

            for delivery in expire_test_actors(STORE, COMBAT_GROUPS):
                WORLD.emit_location(
                    delivery["map_id"], delivery["instance_id"], *delivery["packet"]
                )
        except Exception as error:
            record(event="developer_test_actor_expiry_failed", reason=str(error))


def refresh_player_parties():
    while not STOPPING.wait(5):
        with PROFILER.span("background.refresh_player_parties"):
            try:
                result = PARTIES.refresh_online()
                if result["deferred"]:
                    record(
                        event="party_refresh_deferred",
                        parties=result["deferred"][:16],
                        deferred_count=len(result["deferred"]),
                        refreshed=result["refreshed"],
                    )
            except Exception as error:
                record(event="party_refresh_failed", reason=str(error))


def refresh_player_guilds():
    from wakfu_server.guild_progression import tick

    while not STOPPING.wait(5):
        with PROFILER.span("background.refresh_player_guilds"):
            try:
                tick(STORE, limit=16)
            except Exception as error:
                record(event="guild_progression_tick_failed", reason=str(error))
            # Retry committed publications even when this clock batch fails.
            try:
                GUILDS.drain_pending(limit=64)
            except Exception as error:
                record(event="guild_publication_retry_failed", reason=str(error))


def refresh_player_exchanges():
    from wakfu_server.player_exchanges import expire

    while not STOPPING.wait(1):
        with PROFILER.span("background.refresh_player_exchanges"):
            try:
                expire(STORE)
                EXCHANGES.drain()
            except Exception as error:
                record(event="exchange_refresh_failed", reason=str(error))


def main():
    global ECOLOGY_BRIDGE, BOTS_BRIDGE
    intergame_server = None
    intergame_thread = None
    if os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE") == "1":
        try:
            import runpy

            probe = runpy.run_path(str(ROOT / "tools" / "registry_execute_cprofile.py"))
            if probe["install_from_environment"](runtime_root=RUNTIME):
                record(event="registry_execute_cprofile_armed")
        except Exception as error:
            try:
                record(
                    event="registry_execute_cprofile_setup_failed",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
    if os.environ.get("WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE") == "1":
        try:
            import runpy

            probe = runpy.run_path(
                str(ROOT / "tools" / "registry_execute_allocation_trace.py")
            )
            if probe["install_from_environment"](runtime_root=RUNTIME):
                record(event="registry_execute_allocation_trace_armed")
        except Exception as error:
            try:
                record(
                    event="registry_execute_allocation_trace_setup_failed",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
    if ECOLOGY_MODE == "external":
        from wakfu_server.ecology.world_bridge import EcologyWorldBridge
        from wakfu_server.ecology.runtime import configure_domains
        from wakfu_server.ecology.client import EcologyClient

        token = Path(os.environ["WAKFU_ECOLOGY_TOKEN_FILE"]).read_text().strip()
        ECOLOGY_BRIDGE = configure_domains(
            EcologyWorldBridge(
                store=STORE,
                world=WORLD,
                groups=COMBAT_GROUPS,
                harvests=HARVESTS,
                plantings=PLANTINGS,
                token=token,
                mode=ECOLOGY_MODE,
                record=record,
                combat_sessions=COMBAT_SESSIONS if COMBAT_TEST else None,
                ecology_client=EcologyClient(
                    os.environ.get("WAKFU_ECOLOGY_URL", "http://ecology:8093"),
                    token,
                    timeout=2.0,
                ),
            ),
            regional_bonuses=REGIONAL_BONUSES,
        )
        from wakfu_server.ecology_planting_intents import EcologyPlantingIntents

        PLANTINGS.ecology_intents = EcologyPlantingIntents(STORE, ECOLOGY_BRIDGE.epoch)
        record(event="ecology_external_ready", world_epoch=ECOLOGY_BRIDGE.epoch)
    if COMBAT_TEST:
        from wakfu_server.combat_module_loading import preload_combat_modules
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

        started = time.monotonic()
        startup_prewarm = globals().pop("_COMBAT_STARTUP_PREWARM", None)
        if startup_prewarm is None:
            catalog_info = dict(
                **preload_combat_modules(), **prewarm_runtime_catalogs()
            )
            prewarm_elapsed_ms = 0.0
        else:
            catalog_info = startup_prewarm["details"]
            prewarm_elapsed_ms = startup_prewarm["elapsed_ms"]
        # Import the World-owned bridge at startup so optional WakIA workers
        # initialize outside an actor turn.
        from wakfu_server.wakia_bridge.wakfu_ai.bridge import backend_selection

        record(
            event="combat_catalogs_ready",
            elapsed_ms=round(
                (time.monotonic() - started) * 1000 + prewarm_elapsed_ms, 3
            ),
            **catalog_info,
        )
    record(
        event="position_backend_ready",
        backend="redis" if POSITION_RECOVERY is not None else "memory",
        recovery=POSITION_RECOVERY,
    )

    def stop(signum, frame):
        try:
            flush_positions()
        except Exception as error:
            record(event="shutdown_position_flush_failed", reason=str(error))
            return  # Keep running so pending authoritative positions can retry.
        STOPPING.set()
        results = CONNECTIONS.drain()
        record(
            event="server_shutdown",
            connections=len(results),
            notices_failed=sum(
                result["notice_error"] is not None for result in results
            ),
        )
        deadline = time.monotonic() + 6
        for worker in threading.enumerate():
            if worker.name == "wakfu-client-session":
                worker.join(max(0, deadline - time.monotonic()))
        try:
            flush_positions()  # Catch a move already being handled at signal time.
        except Exception as error:
            record(event="shutdown_position_flush_failed", reason=str(error))
            return
        if any(
            worker.name == "wakfu-client-session" and worker.is_alive()
            for worker in threading.enumerate()
        ):
            record(event="shutdown_waiting_for_session_cleanup")
            return
        if not ECOLOGY_ADMIN_JOBS.close(timeout=3.0):
            record(event="shutdown_waiting_for_ecology_admin_cleanup")
            return
        if intergame_server is not None:
            if intergame_thread is not None and intergame_thread.is_alive():
                intergame_server.shutdown()
            intergame_server.connections.close_all()
            intergame_server.server_close()
        STORE.close()
        DIAGNOSTIC_LOG.close(timeout=1.0)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    from wakfu_server.territory_weather import initialize_local_baselines

    weather_baselines = initialize_local_baselines(STORE)
    record(event="territory_weather_baselines_initialized", **weather_baselines)
    from wakfu_server.performance_monitor import start_monitor

    start_monitor(PROFILER, RUNTIME / "logs/profiles/performance-latest.json", STOPPING)
    from wakfu_server.global_tasks import GlobalTasks, SlowSaveAnnouncements
    from wakfu_server.position_checkpoint_worker import PositionCheckpointWorker

    callbacks = {"positions_flush": flush_positions}
    global_tasks = GlobalTasks(callbacks, observer=SlowSaveAnnouncements(WORLD))
    threading.Thread(
        target=refresh_player_parties, name="wakfu-player-parties", daemon=True
    ).start()
    threading.Thread(
        target=refresh_player_guilds, name="wakfu-player-guilds", daemon=True
    ).start()
    threading.Thread(
        target=refresh_player_exchanges, name="wakfu-player-exchanges", daemon=True
    ).start()
    position_worker = PositionCheckpointWorker(
        STORE,
        POSITIONS,
        STOPPING,
        record=record,
        checkpoint=lambda **budget: flush_positions(background_budget=budget),
    )
    record(event="position_checkpoint_worker_started", **position_worker.policy)
    threading.Thread(
        target=position_worker.run, name="wakfu-position-flusher", daemon=True
    ).start()
    if COMBAT_TEST:
        threading.Thread(
            target=expire_developer_test_actors,
            name="wakfu-developer-test-actor-expiry",
            daemon=True,
        ).start()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(RUNTIME / "server.crt", RUNTIME / "server.key")
    from wakfu_server.intergame_domain import Intergame
    from wakfu_server.intergame_transport import make_server as make_intergame_server

    intergame_server = make_intergame_server(
        Intergame(STORE),
        context,
        host=os.environ.get("WAKFU_BIND_HOST", "127.0.0.1"),
        port=16337,
    )
    intergame_thread = threading.Thread(
        target=intergame_server.serve_forever,
        name="wakfu-intergame-listener",
        daemon=True,
    )
    intergame_thread.start()
    record(event="listening", service="intergame", port=16337)
    from wakfu_server.combat_admin_recovery import CombatAdminRecovery

    if os.environ.get("WAKFU_BOTS_TOKEN_FILE"):
        from wakfu_server.bots.bootstrap import configure

        BOTS_BRIDGE = configure(
            store=STORE,
            world=WORLD,
            exchanges=EXCHANGES,
            positions=POSITIONS,
            token=Path(os.environ["WAKFU_BOTS_TOKEN_FILE"]).read_text().strip(),
            say=lambda generation, character, text: WORLD.broadcast(
                generation, character["id"], 674, wire.chat(character, text)
            ),
            whisper=deliver_bot_whisper,
            stopping=STOPPING,
            record=record,
        )

    threading.Thread(
        target=serve_api,
        args=(STORE, os.environ.get("WAKFU_BIND_HOST", "127.0.0.1"), 18081),
        kwargs={
            "live_console": (
                TEST_CONSOLE
                if os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
                else None
            ),
            "global_tasks": global_tasks,
            "ecology_bridge": ECOLOGY_BRIDGE,
            "bots_bridge": BOTS_BRIDGE,
            "combat_recovery": (
                CombatAdminRecovery(
                    STORE,
                    COMBAT_SESSIONS.registry,
                    POSITIONS,
                    groups=COMBAT_GROUPS,
                    checkpoint_writer=CHECKPOINT_WRITER,
                )
                if COMBAT_TEST
                else None
            ),
        },
        daemon=True,
    ).start()
    threading.Thread(target=listen, args=(15556, "world", context), daemon=True).start()
    listen(15558, "dispatcher", context)
