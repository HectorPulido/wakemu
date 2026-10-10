"""Local Python dispatcher/world prototype, seeded from the user's own capture."""
import base64
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
from wakfu_server.request_diagnostics import (
    RequestTrace,
    current_request,
    request_context,
    state_summary,
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
from wakfu_server.maps import dungeon_transition_delivery, dungeon_hydration
from wakfu_server.maps.world_scene_sync import (
    SceneSync,
    snapshot_ids,
    refresh_snapshots,
)

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent if ROOT.name == "server" else ROOT
RUNTIME = Path(os.environ.get("WAKFU_RUNTIME", PROJECT_ROOT / ".runtime/local"))
RUNTIME.mkdir(parents=True, exist_ok=True)
(RUNTIME / "logs").mkdir(exist_ok=True)
SOURCE = Path(
    os.environ.get(
        "WAKFU_CAPTURE_PATH",
        PROJECT_ROOT
        / ".runtime/captures/2026-10-03T03-40-46.413625Z-fe2520f4/decoded/frames.jsonl",
    )
)
FRAMES = [json.loads(line) for line in SOURCE.read_text().splitlines()]
LOCK = threading.Lock()
STORE = Store(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
)
STORE.database.acquire_runtime_lock()
with STORE.connection() as _startup_db:
    DUNGEON_TRANSITION_OUTBOX_AVAILABLE = _startup_db.execute(
        "SELECT to_regclass('dungeon_transition_outbox') IS NOT NULL AS available"
    ).fetchone()["available"]
    DUNGEON_ROOM_RUNTIME_AVAILABLE = _startup_db.execute(
        "SELECT to_regclass('dungeon_room_runs') IS NOT NULL AND "
        "to_regclass('dungeon_room_spawn_receipts') IS NOT NULL AND EXISTS("
        "SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('dungeon_room_encounters') "
        "AND pg_get_constraintdef(oid) LIKE '%aborted%') AS available"
    ).fetchone()["available"]
from wakfu_server import dungeon_instances

dungeon_instances.load_runtime_routes(STORE)
SOCIAL_CONTACTS = SocialContacts(STORE)
SOCIAL_ACTIONS = SocialDispatcher(SOCIAL_CONTACTS)
from wakfu_server.monster_collect import Harvests

HARVESTS = Harvests(STORE)
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting_probability import resolver as planting_probability_resolver
from wakfu_server.planting_bonus import current as current_planting_bonus
from wakfu_server.haven_bag_garden import active_character as active_garden_character

OPEN_PLANTING = os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1"
PLANTINGS = Plantings(
    STORE,
    open_test_policy=OPEN_PLANTING,
    location_context=lambda stored: active_garden_character(stored, WORLD.snapshot()),
    growth_seconds=float(os.environ.get("WAKFU_PLANT_GROWTH_SECONDS", "30")),
    probability_context=planting_probability_resolver(
        STORE, profession_bonus=current_planting_bonus, open_test_policy=OPEN_PLANTING
    ),
)
TRANSPORT_DISCOVERIES = transport_discovery.Discoveries(STORE)
ALL_ZAAPS = os.environ.get("WAKFU_ALL_ZAAPS", "1") == "1"
ALL_DRAGOS = os.environ.get("WAKFU_ALL_DRAGOS", "1") == "1"


def known_transports(account_id):
    return transport_discovery.local_policy(
        TRANSPORT_DISCOVERIES.known(account_id),
        all_zaaps=ALL_ZAAPS,
        all_dragos=ALL_DRAGOS,
    )


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


def position_lease_active(account_id, generation, character_id):
    with LOCK:
        live = LIVE.get(account_id)
        return live is not None and live[0] == generation


POSITIONS, POSITION_RECOVERY = create_positions(
    STORE,
    lease_active=position_lease_active,
    url=os.environ.get("WAKFU_REDIS_URL"),
    namespace="wakfu:positions:postgres:v1",
)
POSITIONS.observer = lambda details: record(
    event="position_checkpoint_stage", **details
)
POSITION_FLUSH_SECONDS = float(os.environ.get("WAKFU_POSITION_FLUSH_SECONDS", "2"))
if not 0.1 <= POSITION_FLUSH_SECONDS <= 30:
    raise ValueError("WAKFU_POSITION_FLUSH_SECONDS must be between 0.1 and 30")


from wakfu_server.checkpoint_watchdog import CheckpointWatchdog

CHECKPOINT_WATCHDOG = CheckpointWatchdog(
    RUNTIME / "logs/checkpoint-slow-stacks.log", timeout=5.0
)


@PROFILER.profile("persistence.position_checkpoint")
def flush_positions(**scope):
    started = time.monotonic()
    try:
        with CHECKPOINT_WATCHDOG.watch():
            count = POSITIONS.flush(**scope)
    except Exception as error:
        record(
            event="position_batch_timing",
            status="failed",
            elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            account_id=scope.get("account_id"),
            error_type=type(error).__name__,
        )
        raise
    record(
        event="position_batch_timing",
        status="completed",
        characters=count,
        elapsed_ms=round((time.monotonic() - started) * 1000, 3),
        account_id=scope.get("account_id"),
    )
    with POSITIONS.lock:
        evictions = tuple(POSITIONS.evictions)
        POSITIONS.evictions.clear()
    for account, generation, character_id in evictions:
        record(
            event="position_buffer_stale_evicted",
            account_id=account,
            actor_id=character_id,
        )
    if count:
        record(event="position_batch_flushed", characters=count)
    return count


from wakfu_server.manual_checkpoint import ManualCheckpoint

MANUAL_CHECKPOINT = ManualCheckpoint(flush_positions)


def flush_position_batches():
    while not STOPPING.wait(POSITION_FLUSH_SECONDS):
        try:
            flush_positions()
        except Exception as error:
            record(event="position_batch_flush_failed", reason=str(error))


CLOCK_OFFSET_MS = int(os.environ.get("WAKFU_CLOCK_OFFSET_SECONDS", "0")) * 1000
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
        from wakfu_server.maps.dungeon_fight_binding import reconcile_aborted_encounters

        with STORE.connection() as dungeon_recovery_db:
            reconcile_aborted_encounters(dungeon_recovery_db)
    TEST_GROUP_KEY = COMBAT_GROUPS.register_seed(1134, 0, 200, TEST_MONSTERS)
    from wakfu_server.combat_session_adapter import CombatSessionAdapter

    COMBAT_SESSIONS = CombatSessionAdapter(STORE)
    from wakfu_server.combat_spectators import ObserverSession, SpectatorRegistry
    from wakfu_server.combat.combat_external_markers import ExternalFightMarkers

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


def pack_text(value, width="I"):
    data = value.encode()
    return struct.pack(">" + width, len(data)) + data


def realms_local(body):
    """Keep realm metadata and advertise the configured emulator endpoint."""
    address = ipaddress.IPv4Address(os.environ.get("WAKFU_ADVERTISE_HOST", "127.0.0.1"))
    port = int(os.environ.get("WAKFU_ADVERTISE_WORLD_PORT", "15556"))
    if address.is_unspecified or address.is_multicast or not 1 <= port <= 65535:
        raise ValueError("Invalid advertised game endpoint")
    host = str(address)
    r = Reader(body)
    realms = []
    for _ in range(r.number("i")):
        start = r.pos
        realm_id = r.number("i")
        if r.number("B"):
            r.take(4)
        r.text("B")
        for _ in range(r.number("B")):
            r.take(1)
            r.text("B")
        r.take(4)
        if r.number("B"):
            r.take(4)
        host_start = r.pos
        r.text("I")
        for _ in range(r.number("i")):
            r.take(4)
        host_end = r.pos
        r.take(1 + 4 + 1 + 4 + 1)
        if realm_id == 10:
            realm = (
                body[start:host_start]
                + pack_text(host)
                + struct.pack(">ii", 1, port)
                + body[host_end : r.pos]
            )
            realms.append(realm)
    configs = []
    for _ in range(r.number("i")):
        start = r.pos
        realm_id = r.number("i")
        r.take(r.number("i"))
        r.take(r.number("i"))
        r.take(1)
        if realm_id == 10:
            configs.append(body[start : r.pos])
    flags = r.take(1)
    r.finish()
    assert len(realms) == len(configs) == 1
    result = (
        struct.pack(">i", 1) + realms[0] + struct.pack(">i", 1) + configs[0] + flags
    )
    assert b"ankama" not in result and host.encode() in result
    return result


def fixture(opcode):
    return base64.b64decode(
        next(
            frame["body_base64"]
            for frame in FRAMES
            if frame["direction"] == "in" and frame["opcode"] == opcode
        )
    )


REALMS = realms_local(fixture(453))


def character_list_local(body):
    r = Reader(body)
    characters = [r.take(r.number("I")) for _ in range(r.number("B"))]
    pekebu = [blob for blob in characters if b"Pekebu" in blob]
    assert len(pekebu) == 1
    return b"\x01" + struct.pack(">I", len(pekebu[0])) + pekebu[0] + body[r.pos :]


CHARACTERS = character_list_local(fixture(23548))


def player_template():
    r = Reader(fixture(12608))
    r.take(1)
    for _ in range(r.number("B")):
        actor_type, actor_id = r.number("B"), r.number("q")
        blob = r.take(r.number("H"))
        if actor_type == 0 and actor_id == wire.TEMPLATE_CHARACTER:
            return blob
    raise ValueError("Missing player appearance template")


PLAYER_TEMPLATE = player_template()


class Connection:
    """Serialize frames sent by the receiver and other players' workers."""

    def __init__(self, socket):
        self.socket = socket
        self.write_lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def sendall(self, data):
        with PROFILER.span("network.send_lock"):
            self.write_lock.acquire()
        try:
            with PROFILER.span("network.send"):
                self.socket.sendall(data)
        finally:
            self.write_lock.release()


from wakfu_server.async_diagnostic_log import AsyncDiagnosticLog

DIAGNOSTIC_LOG = AsyncDiagnosticLog(RUNTIME / "logs/game-server.jsonl")


def write_records(rows):
    # Rows have already passed through redact(). Filesystem writes happen on a
    # dedicated bounded queue, independent of LIVE ownership and game threads.
    DIAGNOSTIC_LOG.enqueue(rows)


def record(**fields):
    active = current_request()
    event = fields.get("event", "")
    if active is not None and (
        event.endswith("_rejected") or event.endswith("_failed")
    ):
        active.rejection(event, fields.get("reason", fields.get("detail", "")))
        fields["state_at_rejection"] = safe_snapshot(active.snapshot)
    row = redact(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "server_boot_id": SERVER_BOOT_ID,
            "server_pid": os.getpid(),
            **request_context(),
            **fields,
        }
    )
    if active is not None and not active.closed:
        active.append(row)
        if event == "unexpected_request_exception":
            active.flush()
    else:
        write_records([row])


from wakfu_server.checkpoint_worker import CheckpointWorker

CHECKPOINT_WRITER = CheckpointWorker(
    CHECKPOINTS,
    failed=lambda fight_id, error: record(
        event="combat_checkpoint_failed",
        fight_id=fight_id,
        reason=redact(str(error)),
    ),
)


def receive(connection, count, on_idle=None):
    data = bytearray()
    while len(data) < count:
        try:
            chunk = connection.recv(count - len(data))
        except socket.timeout:
            if on_idle is None or not on_idle():
                raise ValueError("Session expired or replaced")
            continue
        if not chunk:
            raise EOFError()
        data.extend(chunk)
    return bytes(data)


def send(connection, service, opcode, body):
    connection.sendall(struct.pack(">IH", 6 + len(body), opcode) + body)
    record(
        service=service,
        direction="out",
        opcode=opcode,
        bytes=len(body),
        target_connection_id=getattr(connection, "trace_id", None),
    )


def send_batch(connection, service, packets):
    packets = tuple(packets)
    if not packets:
        return
    frames = []
    for opcode, body in packets:
        if type(opcode) is not int or not 0 <= opcode <= 0xFFFF:
            raise ValueError("Invalid pushed packet opcode")
        if not isinstance(body, bytes) or len(body) > 327670 - 6:
            raise ValueError("Invalid pushed packet body")
        frames.append(struct.pack(">IH", 6 + len(body), opcode) + body)
    # Connection.sendall holds one write lock for the entire ordered batch.
    connection.sendall(b"".join(frames))
    for opcode, body in packets:
        record(
            service=service,
            direction="out",
            opcode=opcode,
            bytes=len(body),
            target_connection_id=getattr(connection, "trace_id", None),
        )


from wakfu_server.mount_publication import snapshot as mount_snapshot


def world_state_packets(character):
    from wakfu_server.personal_ecology import snapshot as ecology_snapshot

    from wakfu_server.characters.emotes import retained as emote_snapshot

    return (*mount_snapshot(character), *ecology_snapshot(character), *emote_snapshot(character))


def rich_inventory_packet(character):
    """Build the selected character's independent ProtoItem UID registry."""
    from wakfu_server.inventory_items import equipment_inventory

    return equipment_inventory(character)


from wakfu_server.haven_bag_exterior import ExteriorBags

HAVEN_BAG_EXTERIORS = ExteriorBags()

WORLD = World(
    lambda character: wire.spawn_player(PLAYER_TEMPLATE, character),
    wire.remove_player,
    lambda peer, opcode, body: send(peer, "world", opcode, body),
    deliver_batch=lambda peer, packets: send_batch(peer, "world", packets),
    state_packets=world_state_packets,
    delivery_failure=lambda peer, opcode, error: record(
        event="world_delivery_failed_before_shutdown",
        target_connection_id=getattr(peer, "trace_id", None),
        opcode=opcode,
        error=type(error).__name__,
        errno=error.errno,
    ),
)

from wakfu_server.party_dispatch import Parties
from wakfu_server.chat_channels import Channels
from wakfu_server.exchange_dispatch import Exchanges

PARTIES = Parties(STORE, WORLD)
CHANNELS = Channels(STORE, WORLD)
EXCHANGES = Exchanges(STORE, WORLD)


def refresh_party(generation, character):
    """Social publication failures must not disconnect a playable character."""
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout

    try:
        PARTIES.refresh(character["account_id"], generation, character["id"])
    except (ValueError, DatabaseError, PoolTimeout) as error:
        record(
            event="party_refresh_failed", actor_id=character["id"], reason=str(error)
        )


def territory_weather_region_changed(map_id, old_position, new_position):
    """Return whether an accepted walk entered a different known region."""
    from wakfu_server.territory_cells import region_at

    try:
        previous = region_at(map_id, old_position["x"], old_position["y"])
    except (KeyError, ValueError):
        previous = None
    try:
        current = region_at(map_id, new_position["x"], new_position["y"])
    except (KeyError, ValueError):
        return False
    return current != previous


def send_planting_context(connection, character, *, include_weather=True):
    from wakfu_server.ecology_context import packet as ecology_packet
    from wakfu_server.territory_weather_forecast import packet_for_territory
    from wakfu_server.territory_weather import context as weather_context

    try:
        packet = ecology_packet(STORE, character, open_test_policy=OPEN_PLANTING)
        send(connection, "world", *packet)
    except ValueError as error:
        record(
            event="planting_context_unavailable",
            actor_id=character["id"],
            map_id=character["map_id"],
            reason=str(error),
        )
    if not include_weather:
        return
    try:
        weather = weather_context(
            STORE, character, x=character["x"], y=character["y"], z=character["z"]
        )
    except ValueError as error:
        record(
            event="territory_weather_unavailable",
            actor_id=character["id"],
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            reason=str(error),
        )
        return
    send(connection, "world", 13948, weather["native_payload"])
    try:
        forecast = packet_for_territory(
            STORE,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            region_id=weather["region_id"],
        )
    except ValueError as error:
        record(
            event="territory_weather_forecast_unavailable",
            actor_id=character["id"],
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            reason=str(error),
        )
        return
    send(connection, "world", 13895, forecast)


CORPSE_SCENES = weakref.WeakKeyDictionary()
CORPSE_SCENES_LOCK = threading.RLock()


def monster_corpse_snapshot(map_id, instance_id, *, peer=None, peers=()):
    """Reconcile only corpses delivered to these retained connection scenes."""
    from wakfu_server.monster_corpses import reconcile

    # Preserve identities while the socket temporarily leaves WORLD for a
    # fight/spectator view. A new socket has no historical removal backlog.
    with CORPSE_SCENES_LOCK:
        known = CORPSE_SCENES.get(peer, ()) if peer is not None else ()
        with STORE.connection() as db:
            packets, active = reconcile(db, map_id, instance_id, known)
        if peer is not None:
            CORPSE_SCENES[peer] = active
        for recipient in peers:
            # Exploration peers receive scheduler removals directly. Their
            # complete current-map replay supersedes previous tracked IDs.
            CORPSE_SCENES[recipient] = active
        return packets


@PROFILER.profile("world.join")
def join_world(generation, connection, character):
    from wakfu_server.profession_store import ensure_learned

    profession = ensure_learned(
        STORE,
        character["account_id"],
        generation,
        character["id"],
        (64, 71, 72, 73, 74, 75),
    )
    for packet in profession["packets"]:
        send(connection, "world", *packet)
    for packet in HAVEN_BAG_EXTERIORS.snapshots(character):
        send(connection, "world", *packet)
    send_planting_context(connection, character)
    for packet in PLANTINGS.snapshots(character["map_id"], character["instance_id"]):
        send(connection, "world", *packet)
    if not COMBAT_TEST:
        WORLD.join(generation, connection, character)
        refresh_party(generation, character)
        return
    from wakfu_server.combat_monster_world import spawn_group

    # Snapshot and publishes use the same lock as group claims.
    with COMBAT_GROUPS.lock:
        WORLD.join(generation, connection, character)
        for packet in monster_corpse_snapshot(
            character["map_id"], character["instance_id"], peer=connection
        ):
            send(connection, "world", *packet)
        for group in COMBAT_GROUPS.available(
            character["map_id"], character["instance_id"]
        ):
            send(
                connection,
                "world",
                12608,
                spawn_group(group["members"], group_id=group["key"][2]),
            )
    for packet in HARVESTS.availability_snapshot(
        character["map_id"], character["instance_id"]
    ):
        send(connection, "world", *packet)
    for packet in EXTERNAL_FIGHT_MARKERS.world_snapshots(
        character["map_id"],
        character["instance_id"],
        exclude_character_id=character["id"],
    ):
        send(connection, "world", *packet)
    refresh_party(generation, character)


def release_groups(generation):
    if not COMBAT_TEST or generation is None:
        return
    if COMBAT_SESSIONS.registry.lease_generation_active(generation):
        return
    from wakfu_server.combat_monster_world import spawn_group

    with COMBAT_GROUPS.lock:
        for group in COMBAT_GROUPS.release_session(generation):
            map_id, instance_id, group_id = group["key"]
            WORLD.emit_location(
                map_id,
                instance_id,
                12608,
                spawn_group(group["members"], group_id=group_id),
            )
            for packet in HARVESTS.availability_for(
                map_id, instance_id, [m["id"] for m in group["members"]]
            ):
                WORLD.emit_location(map_id, instance_id, *packet)


def is_dungeon_run(instance_id):
    if (
        not DUNGEON_ROOM_RUNTIME_AVAILABLE
        or type(instance_id) is not int
        or instance_id <= 0
    ):
        return False
    with STORE.connection() as db:
        return db.execute(
            "SELECT EXISTS(SELECT 1 FROM dungeon_instances WHERE instance_id=%s AND status='active') AS present",
            (instance_id,),
        ).fetchone()["present"]


@PROFILER.profile("world.bootstrap")
def owned_native_bootstrap(character, **options):
    if is_dungeon_run(character.get("instance_id", 0)):
        from wakfu_server.maps import dungeon_context

        with STORE.connection() as db:
            fighting = db.execute(
                "SELECT EXISTS(SELECT 1 FROM combat_fights f JOIN dungeon_room_encounters e "
                "ON e.fight_id=f.id WHERE e.instance_id=%s AND e.status='active' "
                "AND f.status IN ('placement','active')) AS fighting",
                (character["instance_id"],),
            ).fetchone()["fighting"]
        options["dungeon_context"] = dungeon_context.for_instance(
            STORE, character["instance_id"], fight_in_progress=fighting
        )
    messages = native_transports.bootstrap(character, **options)
    if not is_dungeon_run(character.get("instance_id", 0)):
        return messages
    from wakfu_server import dungeon_object_states, dungeon_runtime, generic_transports

    with STORE.connection() as db:
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, character["instance_id"]
        )
        progress = db.execute(
            "SELECT current_room, status FROM dungeon_room_runs WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
    if progress is None:
        raise ValueError("Dungeon bootstrap has no committed room progress")
    from wakfu_server.maps import dungeon_physical_doors

    if dungeon_physical_doors.enabled(configuration["topology"]):
        return tuple(messages) + dungeon_physical_doors.packets(
            configuration["topology"],
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            unlocked_room=progress["current_room"],
            completed=progress["status"] == "completed",
        )
    sources = [
        row
        for row in generic_transports._CATALOG
        if row["map_id"] == character["map_id"]
    ]
    return tuple(messages) + dungeon_object_states.packets(
        configuration["topology"],
        sources,
        map_id=character["map_id"],
        instance_id=character["instance_id"],
        unlocked_room=progress["current_room"],
        completed=progress["status"] == "completed",
    )


def owned_haven_leave(body, character):
    from wakfu_server.haven_bag import leave_messages

    messages = leave_messages(body, character)
    if not is_dungeon_run(character.get("instance_id", 0)):
        return messages
    context_packet = next(
        payload
        for message_id, payload in owned_native_bootstrap(character)
        if message_id == 13974
    )
    return tuple(
        (message_id, context_packet if message_id == 13974 else payload)
        for message_id, payload in messages
    )


def replay(connection, start, end, account_id, character=None, *, generation=None):
    account_characters = None
    if character is not None:
        from wakfu_server.combat_drop_delivery import temporary_section

        with STORE.connection() as db:
            STORE.lock_character(db, account_id, generation, character["id"])
            character = {
                **character,
                "temporary_inventory_section": temporary_section(db, character["id"]),
            }

    def owned_characters():
        nonlocal account_characters
        if account_characters is None:
            account_characters = STORE.characters(account_id)
        return account_characters

    for frame in FRAMES[start:end]:
        if frame["direction"] == "in":
            if frame["opcode"] in (12789, 13948):
                # Ecology comes from the current native region and our own
                # population; weather is published from exact territory state.
                # Never apply a captured region's climate to another region.
                continue
            if (
                character is not None
                and character["map_id"] != 1134
                and frame["opcode"]
                in {
                    12318,
                    12549,
                    12608,
                    12789,
                    13369,
                    13411,
                    13664,
                    13753,
                    13877,
                    13984,
                }
            ):
                # These fixture packets belong to the original1134 map. A
                # verified destination bootstrap supplies its own world data.
                continue
            if (
                frame["opcode"] == 13974
                and character is not None
                and is_dungeon_run(character.get("instance_id", 0))
            ):
                for message_id, payload in owned_native_bootstrap(character):
                    if message_id == 13974:
                        send(connection, "world", message_id, payload)
                continue
            original = base64.b64decode(frame["body_base64"])
            if frame["opcode"] == 630 and generation is not None:
                for social_packet in SOCIAL_ACTIONS.bootstrap(account_id, generation):
                    send(connection, "world", *social_packet)
                continue
            if frame["opcode"] == 23082 and character is not None:
                from wakfu_server.builds import capacity_message

                send(connection, "world", *capacity_message(character))
            if frame["opcode"] in (12722, 13369):
                from wakfu_server.gifts import empty_message

                send(
                    connection, "world", frame["opcode"], empty_message(frame["opcode"])
                )
                continue
            if frame["opcode"] == 23354:
                send(
                    connection,
                    "world",
                    23354,
                    world_clock.packet(offset_ms=CLOCK_OFFSET_MS),
                )
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 4):
                from wakfu_server.characters.exploration_secrets import (
                    account_packet as exploration_account_packet,
                )

                with STORE.connection() as db:
                    secret_packet = exploration_account_packet(db)
                send(connection, "world", *secret_packet)
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 10):
                from wakfu_server.characters.emotes import (
                    packet as emote_account_packet,
                )

                send(connection, "world", *emote_account_packet(STORE, account_id))
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 11):
                from wakfu_server.haven_bag_furniture_knowledge import (
                    packet as furniture_account_packet,
                )

                send(connection, "world", *furniture_account_packet(STORE, account_id))
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 12):
                message_id, message_body = transport_discovery.account_packet(
                    known_transports(account_id)
                )
                send(connection, "world", message_id, message_body)
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 13):
                from wakfu_server.tutorials import payload as tutorial_payload

                send(
                    connection,
                    "world",
                    13873,
                    struct.pack(">II", 1, 13) + tutorial_payload(STORE, account_id),
                )
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 14):
                from wakfu_server.profession_store import account_packet

                with STORE.connection() as db:
                    craft_packet = account_packet(db, account_id)
                send(connection, "world", *craft_packet)
                continue
            owned = (
                owned_characters()
                if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 2, 0)
                else None
            )
            social_body = social.adapt(
                frame["opcode"],
                original,
                account_id,
                character,
                owned,
                cosmetic_record=(
                    STORE.cosmetic_record(account_id)
                    if frame["opcode"] == 13873
                    and original[:8]
                    in (
                        struct.pack(">II", 1, 8),
                        struct.pack(">II", 1, 9),
                        struct.pack(">II", 2, 8),
                    )
                    else None
                ),
            )
            if social_body is not None:
                send(connection, "world", frame["opcode"], social_body)
                continue
            if frame["opcode"] == 13078 and character is None:
                # Account equipment inventories precede character selection.
                # Only seed owned characters from the known Pekebu inventory.
                if struct.unpack(">q", original[:8])[0] == wire.TEMPLATE_CHARACTER:
                    for owned in owned_characters():
                        send(
                            connection,
                            "world",
                            13078,
                            wire.adapt(13078, original, account_id, owned),
                        )
                continue
            if frame["opcode"] == 23548:
                body = wire.character_list(CHARACTERS, account_id, owned_characters())
            elif frame["opcode"] == 12393:
                body = wire.attribute_sheets(original, owned_characters())
            elif frame["opcode"] == 12608:
                body = wire.without_captured_players(original)
            elif frame["opcode"] == 13664:
                body = wire.without_captured_haven_bags(original)
                send(
                    connection,
                    "world",
                    13082,
                    wire.remove_captured_haven_bags(original),
                )
            else:
                body = wire.adapt(
                    frame["opcode"],
                    original,
                    account_id,
                    character,
                    kamas=STORE.account_kamas(account_id),
                )
            send(connection, "world", frame["opcode"], body)


def combat_group_for_target(registry, character, target):
    """Select the authoritative available roster in the actor's map instance."""
    candidates = [
        group
        for group in registry.available(character["map_id"], character["instance_id"])
        if any(member["id"] == target for member in group["members"])
    ]
    if len(candidates) != 1:
        raise ValueError("No unique available combat group for this target")
    group = candidates[0]
    if (
        group["key"][:2] != (character["map_id"], character["instance_id"])
        or not group["members"]
        or any(
            member["map_id"] != character["map_id"]
            or member.get("instance_id", 0) != character["instance_id"]
            for member in group["members"]
        )
    ):
        raise ValueError("Combat group has a foreign map or instance")
    return group


def harvest_target(character, target):
    try:
        group = combat_group_for_target(COMBAT_GROUPS, character, target)
    except ValueError:
        from wakfu_server.monster_corpses import resolve_target

        with STORE.connection() as db:
            return resolve_target(db, character, target)
    member = next(m for m in group["members"] if m["id"] == target)
    return dict(member, instance_id=group["key"][1])


def session(raw, peer, service, context):
    selected = loaded = False
    scene_sync = SceneSync()
    static_sync_pending = False
    static_sync_attempts = 0
    static_sync_due = time.monotonic() + 0.75
    world_snapshot_pending = False
    world_snapshot_due = time.monotonic() + 0.75
    world_snapshot_identity = None
    account_id = generation = character = None
    bag_session = None
    chest_opening = None
    fight = None
    combat_session = None
    spectator_session = None
    spectator_fight_id = None
    spectator_terminal_pending = None
    pve_withdrawal_pending = None
    active_request = None
    connection_trace_id = uuid.uuid4().hex
    fight_messages = None
    fight_started_at = None
    group_lease = None
    # Each session binds its own claimed roster; globals only register defaults.
    TEST_MONSTERS = ()
    TEST_MONSTERS_BY_ID = {}
    TEST_GROUP_KEY = None
    checkpoint_local_shared = None
    checkpoint_revision = checkpoint_id = None
    checkpoint_terminal = False
    connected_at = time.monotonic()
    last_chat = 0
    last_health_tick = 0
    last_session_renewal = 0
    last_dungeon_transition_poll = 0.0
    last_dungeon_transition_report = None
    from wakfu_server.placement_deadline import Deadline

    @PROFILER.profile("world.static_sync")
    def sync_static_world(*, force=False, validated=False):
        nonlocal static_sync_pending, static_sync_attempts, static_sync_due
        if (
            character is None
            or fight is not None
            or (not static_sync_pending and not force)
        ):
            return
        if not force and time.monotonic() < static_sync_due:
            return
        if (
            account_id is None
            or generation is None
            or not STORE.current_session(account_id, generation)
        ):
            return
        if character["map_id"] != 9:
            for message_body in world_static.snapshots(character["map_id"]):
                send(connection, service, 13984, message_body)
            # The asset baseline also belongs to private dungeon scenes. Replay
            # its dynamic state first, then restore the run-owned door policy;
            # native default states must never reopen progression exits.
            if is_dungeon_run(character.get("instance_id", 0)):
                for message_id, message_body in owned_native_bootstrap(character):
                    if message_id == 12344:
                        send(connection, service, message_id, message_body)
        elif (
            bag_session is not None
            and bag_session.is_owner
            and bag_session.owns(character)
        ):
            from wakfu_server.haven_chest_wire import scene_packet as chest_scene_packet

            for chest_object in world_static.objects(9):
                if chest_object["type"] == "AccountChest":
                    send(connection, service, *chest_scene_packet(chest_object["id"]))
        if validated:
            static_sync_pending = False
            static_sync_attempts = 0
        elif not force:
            # Only a due timer consumes the retry budget or moves its deadline.
            # Movement, interaction and 14689 can request an immediate resend
            # without starving the scheduled map-load retries.
            static_sync_attempts += 1
            static_sync_pending = static_sync_attempts < 3
            static_sync_due = time.monotonic() + 0.75
        record(
            event="static_map_state_synchronized",
            actor_id=character["id"],
            map_id=character["map_id"],
            instance_id=character.get("instance_id", 0),
            forced=force,
            validated=validated,
        )

    @PROFILER.profile("world.scene_sync")
    def sync_scene_world():
        """Hydrate newly loaded native scene partitions after local travel."""
        if (
            not loaded
            or character is None
            or fight is not None
            or spectator_session is not None
        ):
            return
        if character["map_id"] == 9:
            return
        packets = scene_sync.poll(
            character["map_id"], character.get("instance_id", 0), time.monotonic()
        )
        if not packets:
            return
        # csV/cgN shifts the native interactive registry independently of the
        # terrain camera. Raw assets must be registered before state hydration.
        send(
            connection,
            service,
            12318,
            struct.pack(">ii", character["x"], character["y"]),
        )
        for payload in packets:
            send(connection, service, 13984, payload)
            # Native duplicate attachment retains an existing instance. Apply
            # the authoritative state directly to that retained instance too.
            for state in refresh_snapshots(payload):
                send(connection, service, 12344, state)
        if is_dungeon_run(character.get("instance_id", 0)):
            for message_id, payload in owned_native_bootstrap(character):
                if message_id == 12344:
                    send(connection, service, message_id, payload)
        record(
            event="scene_objects_synchronized",
            actor_id=character["id"],
            map_id=character["map_id"],
            instance_id=character.get("instance_id", 0),
            packets=len(packets),
            bytes=sum(map(len, packets)),
            object_ids=snapshot_ids(packets),
        )

    @PROFILER.profile("world.snapshot")
    def send_loaded_world_snapshot():
        """Rebuild the current loaded map for this peer after scene transitions."""
        if character is None or not loaded or account_id is None or generation is None:
            raise ValueError("Loaded world session is required")
        if fight is not None or combat_session is not None:
            raise ValueError("Cannot rebuild an exploration snapshot during combat")
        if character.get("map_id") == 9:
            raise ValueError("Private haven-bag maps do not use world replay")
        if not STORE.current_session(account_id, generation):
            raise ValueError("World snapshot session is stale")
        if not WORLD.resynchronize(generation, connection, character):
            raise ValueError("Player snapshot delivery failed")
        for packet in HAVEN_BAG_EXTERIORS.snapshots(character):
            send(connection, service, *packet)
        # This is a complete current-map snapshot, so it also validates the
        # static-object load. Do not leave the independent retry timer armed
        # to resend the same 13984 packets after the world replay.
        sync_static_world(force=True, validated=True)
        send_planting_context(connection, character)
        for packet in PLANTINGS.snapshots(
            character["map_id"], character.get("instance_id", 0)
        ):
            send(connection, service, *packet)
        if COMBAT_TEST:
            from wakfu_server.combat_monster_world import spawn_group
            from wakfu_server.combat.combat_world_group_cleanup import defeated_snapshot

            with COMBAT_GROUPS.lock:
                with STORE.connection() as db:
                    for packet in defeated_snapshot(
                        db, character["map_id"], character.get("instance_id", 0)
                    ):
                        send(connection, service, *packet)
                for packet in monster_corpse_snapshot(
                    character["map_id"],
                    character.get("instance_id", 0),
                    peer=connection,
                ):
                    send(connection, service, *packet)
                groups = COMBAT_GROUPS.available(
                    character["map_id"], character.get("instance_id", 0)
                )
                for group in groups:
                    send(
                        connection,
                        service,
                        12608,
                        spawn_group(group["members"], group_id=group["key"][2]),
                    )
        for packet in HARVESTS.availability_snapshot(
            character["map_id"], character.get("instance_id", 0)
        ):
            send(connection, service, *packet)
        if COMBAT_TEST:
            for packet in EXTERNAL_FIGHT_MARKERS.world_snapshots(
                character["map_id"],
                character.get("instance_id", 0),
                exclude_character_id=character["id"],
            ):
                send(connection, service, *packet)

    def sync_loaded_world_snapshot(*, force=False):
        nonlocal world_snapshot_pending
        if not world_snapshot_pending or not loaded or character is None:
            return False
        if fight is not None or combat_session is not None:
            return False
        if character.get("map_id") == 9:
            # Each haven bag is a private instance; the normal join already
            # supplied its scoped state and must not trigger public replay.
            world_snapshot_pending = False
            return False
        identity = (
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )
        if identity != world_snapshot_identity:
            world_snapshot_pending = False
            return False
        if not force and time.monotonic() < world_snapshot_due:
            return False
        try:
            send_loaded_world_snapshot()
        except ValueError as error:
            record(
                event="world_snapshot_resynchronization_failed",
                actor_id=character["id"],
                reason=str(error),
            )
            world_snapshot_pending = False
            return False
        world_snapshot_pending = False
        record(
            event="world_snapshot_resynchronized",
            actor_id=character["id"],
            map_id=character["map_id"],
            instance_id=character.get("instance_id", 0),
            trigger="ready" if force else "fallback",
        )
        return True

    def refresh_owned_world_after_spectating():
        """Restore the loaded observer's current world snapshot after 12154."""
        if character is None or account_id is None or generation is None:
            raise ValueError("Loaded observer session is required")
        send_loaded_world_snapshot()
        nonlocal world_snapshot_pending
        world_snapshot_pending = False

    def mark_static_sync_pending(*, world_ready=False):
        nonlocal static_sync_pending, static_sync_attempts, static_sync_due
        nonlocal world_snapshot_pending, world_snapshot_due, world_snapshot_identity
        scene_sync.arm(
            character["map_id"],
            character.get("instance_id", 0),
            [character],
            time.monotonic(),
        )
        static_sync_pending = True
        static_sync_attempts = 0
        static_sync_due = time.monotonic() + 0.75
        world_snapshot_pending = not world_ready and character.get("map_id") != 9
        world_snapshot_due = static_sync_due
        world_snapshot_identity = (
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )

    def deliver_rift_transition():
        nonlocal character, position, movement_state
        if not loaded or character is None or account_id is None or generation is None:
            return False
        if fight is not None or combat_session is not None:
            return False
        from wakfu_server import rift_transition_delivery

        destination = rift_transition_delivery.pending(
            account_id, generation, character["id"]
        )
        if destination is None:
            return False
        if not STORE.current_character_session(account_id, generation, character["id"]):
            raise ValueError("Rift transition belongs to a replaced session")
        saved = STORE.character(account_id, character["id"])
        if any(
            saved[key] != destination[key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Committed rift destination changed before hydration")
        cancel_crafting()
        WORLD.leave(character["id"], generation)
        character = saved
        POSITIONS.attach(account_id, generation, character)
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        for packet in owned_native_bootstrap(character):
            send(connection, service, *packet)
        join_world(generation, connection, character)
        mark_static_sync_pending()
        rift_transition_delivery.acknowledge(
            account_id, generation, character["id"], destination
        )
        record(event="rift_map_transition", actor_id=character["id"], **destination)
        return True

    def prepare_rift_start(body):
        if character is None or not (1 << 58) < character.get("instance_id", 0) < (
            1 << 59
        ):
            return None
        from wakfu_server import rift_entry_adapter

        try:
            with STORE.connection() as db:
                run = rift_entry_adapter.authorize_start(
                    db,
                    STORE,
                    account_id,
                    generation,
                    character["id"],
                    body,
                    source_allowed=lambda actor, source: (
                        actor["map_id"] == source["map_id"]
                        and max(
                            abs(actor["x"] - source["x"]), abs(actor["y"] - source["y"])
                        )
                        <= 3
                        and abs(actor["z"] - source["z"]) <= 2
                    ),
                )
                if run is not None:
                    from wakfu_server import rift_transition_delivery

                    members = db.execute(
                        "SELECT c.id,c.account_id,s.generation FROM characters c "
                        "JOIN sessions s ON s.account_id=c.account_id WHERE c.id=ANY(%s)",
                        (run["members"],),
                    ).fetchall()
                    if any(
                        rift_transition_delivery.pending(
                            row["account_id"], row["generation"], row["id"]
                        )
                        is not None
                        for row in members
                    ):
                        raise ValueError(
                            "Wait for every frozen rift member to load the interior"
                        )
            if run is not None:
                with WORLD.lock:
                    for row in members:
                        visible = WORLD.players.get(row["id"])
                        if (
                            visible is None
                            or visible[0] != row["generation"]
                            or WORLD.location(visible[2])
                            != (character["map_id"], run["instance_id"])
                        ):
                            raise ValueError(
                                "Every frozen rift member must finish loading the interior"
                            )
            return run
        except ValueError as error:
            record(
                event="rift_start_rejected", actor_id=character["id"], reason=str(error)
            )
            return None

    def checkpoint_accepted_rift(shared, candidate, runtime, packets):
        from wakfu_server.rift_dispatch_combat import finish_accepted_action

        prepared = finish_accepted_action(
            candidate,
            runtime,
            packets,
            initialize_actor=lambda current, actor, monster: (),
        )
        owners = [
            owner
            for owner in shared.participants.values()
            if STORE.current_character_session(
                owner.account_id, owner.generation, owner.character_id
            )
        ]
        if not owners:
            raise ValueError("Rift checkpoint requires a current participant lease")
        owner = min(owners, key=lambda entry: entry.character_id)
        shared.checkpoint_revision = CHECKPOINTS.save(
            owner.account_id,
            owner.generation,
            prepared.fight,
            expected_revision=shared.checkpoint_revision,
            runtime=prepared.runtime,
        )
        return prepared

    @PROFILER.profile("dungeon.transition")
    def deliver_dungeon_transitions(*, before_action=False):
        """Poll this worker's durable transition without crossing combat/context.

        Prepare the authoritative destination and pinned context before any
        runtime mutation. Acknowledge only after complete bootstrap delivery.
        """
        nonlocal last_dungeon_transition_poll, last_dungeon_transition_report
        if (
            not DUNGEON_TRANSITION_OUTBOX_AVAILABLE
            or not selected
            or not loaded
            or character is None
            or account_id is None
            or generation is None
        ):
            return None
        if fight is not None or combat_session is not None:
            return {"state": "deferred_combat", "pending_event_ids": ()}
        now = time.monotonic()
        if not before_action and now - last_dungeon_transition_poll < 1.0:
            return None
        last_dungeon_transition_poll = now
        if DUNGEON_ROOM_RUNTIME_AVAILABLE and is_dungeon_run(
            character.get("instance_id", 0)
        ):
            from wakfu_server import (
                dungeon_auto_transition,
                dungeon_auto_exit,
                dungeon_runtime,
            )

            with STORE.connection() as db:
                pending = db.execute(
                    "SELECT e.fight_id,COALESCE((e.result->>'completed')::boolean,false) AS completed "
                    "FROM dungeon_room_encounters e "
                    "JOIN dungeon_room_runs r ON r.instance_id=e.instance_id "
                    "WHERE e.instance_id=%s AND e.status='victory' "
                    "AND e.result_revision=r.revision "
                    "AND e.result->>'physical_publication_revision' IS NULL "
                    "AND ((e.result->>'auto_transition_revision' IS NULL "
                    "AND NOT COALESCE((e.result->>'completed')::boolean,false)) "
                    "OR (e.result->>'auto_exit_revision' IS NULL "
                    "AND COALESCE((e.result->>'completed')::boolean,false))) "
                    "ORDER BY e.fight_id DESC LIMIT 1",
                    (character["instance_id"],),
                ).fetchone()
                if pending is not None:
                    _, configuration = dungeon_runtime.configuration_for_instance(
                        db, character["instance_id"]
                    )
            if pending is not None:
                from wakfu_server.maps import dungeon_physical_doors

                if dungeon_physical_doors.enabled(configuration["topology"]):
                    # Room progress is committed by settlement; publish without moving players.
                    from wakfu_server.combat_monster_world import spawn_group

                    with COMBAT_GROUPS.lock:
                        physical_groups = tuple(
                            COMBAT_GROUPS.available(
                                character["map_id"], character["instance_id"]
                            )
                        )
                    with STORE.connection() as db:
                        progress = db.execute(
                            "SELECT current_room,status,revision FROM dungeon_room_runs "
                            "WHERE instance_id=%s FOR UPDATE",
                            (character["instance_id"],),
                        ).fetchone()
                        physical_packets = dungeon_physical_doors.packets(
                            configuration["topology"],
                            map_id=character["map_id"],
                            instance_id=character["instance_id"],
                            unlocked_room=progress["current_room"],
                            completed=progress["status"] == "completed",
                        )
                        for packet in physical_packets:
                            WORLD.emit_location(
                                character["map_id"], character["instance_id"], *packet
                            )
                        for group in physical_groups:
                            WORLD.emit_location(
                                character["map_id"],
                                character["instance_id"],
                                12608,
                                spawn_group(group["members"], group_id=group["key"][2]),
                            )
                        db.execute(
                            "UPDATE dungeon_room_encounters SET result=result || "
                            "jsonb_build_object('physical_publication_revision',%s) "
                            "WHERE instance_id=%s AND fight_id=%s AND result_revision=%s",
                            (
                                progress["revision"],
                                character["instance_id"],
                                pending["fight_id"],
                                progress["revision"],
                            ),
                        )
                    return {"state": "physical_room_published", "pending_event_ids": ()}
                transition = (
                    dungeon_auto_exit.complete
                    if pending.get("completed")
                    else dungeon_auto_transition.advance
                )
                transition(
                    STORE,
                    character["instance_id"],
                    pending["fight_id"],
                    topology=configuration["topology"],
                    in_fight=lambda character_id: COMBAT_SESSIONS.lookup_character(
                        character_id
                    )
                    is not None,
                )

        def current_location():
            return {
                key: character.get(key, 0)
                for key in ("map_id", "instance_id", "x", "y", "z")
            }

        def bootstrap_dungeon_event(event):
            nonlocal character, position, movement_state
            plan = dungeon_hydration.prepare_transition(
                STORE, account_id, generation, character["id"], event
            )
            cancel_crafting()
            WORLD.leave(character["id"], generation)
            character = plan.character
            POSITIONS.attach(account_id, generation, character)
            position = {key: character[key] for key in ("x", "y", "z")}
            movement_state = Movement(position)
            for message_id, message_body in plan.packets:
                send(connection, service, message_id, message_body)
            join_world(generation, connection, character)
            mark_static_sync_pending()
            return True

        result = dungeon_transition_delivery.deliver_pending_transitions(
            STORE,
            account_id,
            generation,
            character["id"],
            worker_generation=generation,
            current_location=current_location,
            in_fight=lambda: fight is not None or combat_session is not None,
            bootstrap=bootstrap_dungeon_event,
        )
        report_key = (
            result["state"],
            tuple(result["pending_event_ids"]),
        )
        if result["state"] != "idle" and report_key != last_dungeon_transition_report:
            record(
                event="dungeon_transition_deferred",
                actor_id=character["id"],
                state=result["state"],
                pending_event_ids=list(result["pending_event_ids"]),
                reason=(
                    "destination bootstrap did not complete"
                    if result["state"] == "bootstrap_incomplete"
                    else None
                ),
            )
        last_dungeon_transition_report = report_key
        return result

    placement_deadline = Deadline()
    position = {"x": -12, "y": -8, "z": -1}
    console_session = None
    flora_ticket = None

    def cancel_flora():
        nonlocal flora_ticket
        if flora_ticket is not None:
            from wakfu_server.resource_collect import cancel

            cancel(STORE, flora_ticket)
            flora_ticket = None

    def cancel_crafting():
        if account_id is None or generation is None or character is None:
            return
        from wakfu_server.crafting import current as current_crafting
        from wakfu_server.crafting import cancel as cancel_crafting_occupation

        occupation = current_crafting(STORE, account_id, generation, character["id"])
        if occupation is not None:
            cancel_crafting_occupation(
                STORE,
                account_id,
                generation,
                character["id"],
                occupation["token"],
                occupation["version"],
                b"\x03\x00\x08",
            )

    @PROFILER.profile("inventory.mount_publish")
    def publish_mount_equipment(previous, current):
        # Build transactions already reconcile riding when the equipped UID
        # changes. Publish that committed state only outside combat.
        if fight is not None:
            return
        from wakfu_server.mount_publication import equipment_changes

        for packet in equipment_changes(PLAYER_TEMPLATE, previous, current):
            WORLD.update(generation, current, *packet)

    @PROFILER.profile("combat.checkpoint")
    def checkpoint_fight(status=None):
        nonlocal checkpoint_revision, checkpoint_id, checkpoint_terminal, checkpoint_local_shared
        if fight is None:
            return
        if checkpoint_id != fight.id:
            checkpoint_id = fight.id
            checkpoint_revision = None
            checkpoint_terminal = False
        if checkpoint_terminal:
            return
        checkpoint_started = time.monotonic()
        captured_checkpoint_id = fight.id

        def checkpoint_trace(stage, **details):
            details.setdefault("fight_id", captured_checkpoint_id)
            record(
                event="persistence_stage",
                domain="fight_checkpoint",
                stage=stage,
                **details,
            )

        try:
            if combat_session is not None:
                shared_checkpoint = COMBAT_SESSIONS.registry.lookup(fight.id)
            else:
                from types import SimpleNamespace

                if (
                    checkpoint_local_shared is None
                    or checkpoint_local_shared.fight.id != fight.id
                ):
                    checkpoint_local_shared = SimpleNamespace(
                        fight=fight,
                        runtime=fight_messages,
                        lock=threading.RLock(),
                        checkpoint_revision=checkpoint_revision,
                        checkpoint_terminal=False,
                    )
                shared_checkpoint = checkpoint_local_shared
            if (
                shared_checkpoint.checkpoint_terminal
                or CHECKPOINT_WRITER.terminal_pending(fight.id)
            ):
                return
            if combat_session is not None:
                # Deliver committed owner and spectator batches before copying a checkpoint.
                # Runtime.pending remains gated by the native turn ACK boundary.
                drain_shared_combat()
            record(
                event="persistence_stage",
                domain="fight_checkpoint",
                stage="save_started",
                fight_id=fight.id,
            )
            if getattr(fight, "rift_wave_state", None) is not None:
                with shared_checkpoint.lock:
                    shared_checkpoint.checkpoint_revision = CHECKPOINTS.save(
                        account_id,
                        generation,
                        shared_checkpoint.fight,
                        expected_revision=shared_checkpoint.checkpoint_revision,
                        runtime=shared_checkpoint.runtime,
                        trace=checkpoint_trace,
                    )
                    if status is not None:
                        shared_checkpoint.checkpoint_revision = CHECKPOINTS.end(
                            account_id,
                            generation,
                            fight.id,
                            expected_revision=shared_checkpoint.checkpoint_revision,
                            status=status,
                            trace=checkpoint_trace,
                        )
                        shared_checkpoint.checkpoint_terminal = True
                return
            queued = CHECKPOINT_WRITER.submit(
                shared_checkpoint,
                account_id,
                generation,
                status=status,
                trace=checkpoint_trace,
            )
            record(
                event="combat_checkpoint_queued",
                fight_id=fight.id,
                sequence=queued["sequence"],
                terminal=queued["terminal"],
            )
            record(
                event="combat_checkpoint_timing",
                fight_id=fight.id,
                elapsed_ms=round((time.monotonic() - checkpoint_started) * 1000, 3),
            )
        except ValueError as error:
            # A replaced login cannot overwrite the current generation's state.
            record(
                event="combat_checkpoint_rejected", fight_id=fight.id, reason=str(error)
            )

    @PROFILER.profile("combat.settlement")
    def complete_test_fight():
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_lifecycle import prepare_finish

        if combat_session is not None:
            from wakfu_server.combat_lifecycle import prepare_finish_shared
            from wakfu_server.monster_removal_ecology import (
                finish as finish_world_group,
            )
            from wakfu_server.storage import combat_reward_context, reward_policy
            from wakfu_server import combat_drops, combat_drop_delivery
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.inventory_items import equipment_inventory

            shared = refresh_shared_combat()
            if shared is None:
                raise ValueError("Shared fight registry entry is unavailable")
            owner_characters, _ = COMBAT_SESSIONS.player_sources(fight)
            from wakfu_server.combat.combat_terminal_metadata import (
                owner_characters_for_finish,
                registered_summon_actor_ids,
                registered_summon_metadata,
            )

            owner_characters = owner_characters_for_finish(
                STORE, shared, fight, owner_characters
            )
            summon_actor_ids = registered_summon_actor_ids(fight)
            if getattr(shared, "is_duel", False):
                from wakfu_server.combat_results import finish_messages
                from wakfu_server.friendly_duels import settle as settle_duel

                duel_metadata = {
                    actor.id: dict(
                        kind="player",
                        account_id=actor.owner_id,
                        name=owner_characters[actor.id]["name"],
                        breed=owner_characters[actor.id]["breed"],
                        is_male=owner_characters[actor.id]["sex"] == 0,
                    )
                    for actor in fight.actors.values()
                    if actor.controlled and actor.id not in summon_actor_ids
                }
                duel_metadata.update(registered_summon_metadata(fight))

                def prepare_duel_packets(current_shared):
                    reason = getattr(current_shared, "duel_finish_reason", "defeat")
                    disconnected_id = getattr(
                        current_shared, "duel_disconnected_character_id", None
                    )
                    settle_duel(
                        STORE,
                        combat_session.account_id,
                        combat_session.generation,
                        combat_session.character_id,
                        current_shared.fight,
                        reason=reason,
                        disconnected_character_id=disconnected_id,
                    )
                    batches = {}
                    for owner, participant in current_shared.participants.items():
                        packets = finish_messages(
                            current_shared.runtime,
                            duel_metadata,
                            duration_ms=int(
                                (time.monotonic() - fight_started_at) * 1000
                            ),
                            fight_instance_id=current_shared.fight.id,
                            initiator_id=participant.character_id,
                        )
                        packets.append(
                            (13420, struct.pack(">i", current_shared.fight.id))
                        )
                        batches[owner] = tuple(packets)
                    return batches

                COMBAT_SESSIONS.settle_finished(
                    combat_session, fight.id, prepare_duel_packets
                )
                refresh_shared_combat()
                drain_shared_combat()
                checkpoint_fight("ended")
                character.update(STORE.character(account_id, character["id"]))
                record(
                    event="friendly_duel_finished",
                    actor_id=combat_session.character_id,
                    fight_id=fight.id,
                    winner=fight.winner,
                    reason=getattr(shared, "duel_finish_reason", "defeat"),
                )
                return
            metadata = {
                actor.id: dict(
                    kind="player",
                    account_id=actor.owner_id,
                    name=owner_characters[actor.id]["name"],
                    breed=owner_characters[actor.id]["breed"],
                    is_male=owner_characters[actor.id]["sex"] == 0,
                )
                for actor in fight.actors.values()
                if actor.controlled and actor.id not in summon_actor_ids
            }
            metadata.update(registered_summon_metadata(fight))
            metadata.update(
                {
                    monster_id: dict(kind="monster", ref=monster["ref"])
                    for monster_id, monster in TEST_MONSTERS_BY_ID.items()
                }
            )
            frozen_contexts = {}

            def settle_rift_rewards(db):
                from wakfu_server import rift_runtime
                from wakfu_server.maps import rift_rewards

                eligible = tuple(
                    actor.id
                    for actor in fight.actors.values()
                    if actor.id in owner_characters
                    and actor.team == fight.winner
                    and not getattr(actor, "pve_withdrawn", False)
                )
                return rift_runtime.settle(
                    db,
                    fight.rift_wave_state["instance_id"],
                    fight.id,
                    outcome=(
                        "closed"
                        if fight.rift_wave_state.get("outcome") == "capacity_exhausted"
                        else "won"
                        if fight.winner == 0
                        else "lost"
                        if fight.winner == 1
                        else "closed"
                    ),
                    turn=fight.native_timeline_round,
                    apply_rewards=lambda reward_db, run, result: rift_rewards.apply(
                        reward_db,
                        run,
                        result,
                        store=STORE,
                        eligible_character_ids=eligible,
                    ),
                )

            def shared_policy(db, member, source):
                if getattr(fight, "rift_wave_state", None) is not None:
                    from wakfu_server.combat_rewards import Policy

                    # Loot receipts must exist before per-member native reports are built.
                    settle_rift_rewards(db)
                    return Policy(xp=0, kamas=0)
                context, drop_context = combat_reward_context.settlement_contexts(
                    db, fight, source, TEST_MONSTERS
                )
                frozen_contexts[member["character_id"]] = (context, drop_context)
                return reward_policy.resolve(
                    STORE,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=member["character_id"],
                    fight_id=fight.id,
                    context=context,
                ).policy

            def shared_loot(db, member, reward):
                if getattr(fight, "rift_wave_state", None) is not None:
                    from wakfu_server.maps import rift_rewards

                    settle_rift_rewards(db)
                    return rift_rewards.delivery(
                        db,
                        STORE,
                        fight.rift_wave_state["instance_id"],
                        member["character_id"],
                    )
                actor = fight.actors[member["character_id"]]
                frozen = frozen_contexts.get(member["character_id"])
                if frozen is None:
                    raise ValueError("Shared loot has no pre-award context snapshot")
                _, drop_context = frozen
                batch = combat_drops.resolve(
                    STORE,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=member["character_id"],
                    fight_id=fight.id,
                    monsters=[
                        {"actor_id": monster["id"], "reference": monster["ref"]}
                        for monster in TEST_MONSTERS
                    ],
                    prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                    can_loot=True,
                    fight_context=drop_context,
                )
                combat_drop_delivery.apply(STORE, db, batch)
                saved = STORE.character(
                    member["account_id"], member["character_id"], db
                )
                return {
                    "loots": combat_drops.report_loots(batch),
                    "packets": [
                        synchronization(saved),
                        equipment_inventory(saved),
                        combat_drop_delivery.temporary_update(
                            db, member["character_id"]
                        ),
                    ],
                }

            def shared_group_settlement(db, owner_account, owner_character, defeated):
                if getattr(fight, "rift_wave_state", None) is not None:
                    settle_rift_rewards(db)
                    return {"applied": True, "packets": []}
                if group_lease is None:
                    return {"applied": True, "packets": []}
                outcome = finish_world_group(
                    STORE,
                    COMBAT_GROUPS,
                    group_lease,
                    character_id=owner_character,
                    defeated=defeated,
                    db=db,
                )
                if outcome["applied"] and defeated:
                    from wakfu_server.monster_corpses import retain

                    retain(db, fight, TEST_MONSTERS)
                if (
                    outcome["applied"]
                    and DUNGEON_ROOM_RUNTIME_AVAILABLE
                    and group_lease[0][1] > 0
                ):
                    from wakfu_server.maps import dungeon_progression, dungeon_runtime
                    from wakfu_server.combat_terrain import map_geometry

                    room_result = dungeon_progression.settle_encounter(db, fight)
                    if room_result is not None:
                        dungeon_runtime.ensure_current_room(
                            db,
                            COMBAT_GROUPS,
                            room_result["instance_id"],
                            map_geometry(group_lease[0][0]),
                        )
                return outcome

            def prepare_shared_packets(current_shared):
                return prepare_finish_shared(
                    STORE,
                    combat_session.account_id,
                    combat_session.generation,
                    combat_session.character_id,
                    current_shared.runtime,
                    metadata,
                    duration_ms=int((time.monotonic() - fight_started_at) * 1000),
                    fight_instance_id=fight.id,
                    policy_resolver=shared_policy,
                    loot_resolver=shared_loot,
                    expected_accounts=set(current_shared.participants),
                    trace=lambda stage, **fields: record(
                        event="persistence_stage",
                        domain="fight_settlement",
                        stage=stage,
                        **fields,
                    ),
                    group_settlement=(
                        shared_group_settlement
                        if group_lease is not None
                        or getattr(fight, "rift_wave_state", None) is not None
                        else None
                    ),
                )

            if group_lease is None:
                COMBAT_SESSIONS.settle_finished(
                    combat_session, fight.id, prepare_shared_packets
                )
            else:
                settlement_lock_started = time.monotonic()
                record(
                    event="persistence_stage",
                    domain="fight_settlement",
                    stage="group_lock_wait",
                    fight_id=fight.id,
                )
                with COMBAT_GROUPS.lock:
                    record(
                        event="persistence_stage",
                        domain="fight_settlement",
                        stage="group_lock_acquired",
                        fight_id=fight.id,
                        elapsed_ms=round(
                            (time.monotonic() - settlement_lock_started) * 1000, 3
                        ),
                    )
                    COMBAT_SESSIONS.settle_finished(
                        combat_session, fight.id, prepare_shared_packets
                    )
            refresh_shared_combat()
            drain_shared_combat()
            checkpoint_fight("ended")
            character.update(STORE.character(account_id, character["id"]))
            record(
                event="combat_shared_finished",
                actor_id=combat_session.character_id,
                fight_id=fight.id,
                participants=len(shared.participants),
                winner=fight.winner,
            )
            return

        for actor in fight.actors.values():
            if actor.hp == 0 and actor.id not in getattr(
                fight_messages, "_reported_deaths", set()
            ):
                for message_id, payload in fight_messages.prepare_delivery(
                    death_messages(fight_messages, actor.id)
                ):
                    send(connection, service, message_id, payload)
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account_id,
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            ),
        }
        metadata.update(
            {m["id"]: dict(kind="monster", ref=m["ref"]) for m in TEST_MONSTERS}
        )
        from wakfu_server.monster_removal_ecology import finish as finish_world_group
        from wakfu_server.storage import combat_reward_context, reward_policy

        def resolve_fight_reward(db):
            context = combat_reward_context.build_context(
                fight, character, TEST_MONSTERS
            )
            return reward_policy.resolve(
                STORE,
                db,
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                context=context,
            ).policy

        def resolve_fight_loot(db, reward):
            from wakfu_server import combat_drops, combat_drop_delivery
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.inventory_items import equipment_inventory

            actor = fight.actors[character["id"]]
            batch = combat_drops.resolve(
                STORE,
                db,
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                monsters=[
                    {"actor_id": m["id"], "reference": m["ref"]} for m in TEST_MONSTERS
                ],
                prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                can_loot=True,
                fight_context=combat_reward_context.build_drop_context(
                    fight, character, TEST_MONSTERS
                ),
            )
            combat_drop_delivery.apply(STORE, db, batch)
            saved = STORE.character(account_id, character["id"], db)
            return {
                "loots": combat_drops.report_loots(batch),
                "packets": [
                    synchronization(saved),
                    (13078, equipment_inventory(saved)),
                    combat_drop_delivery.temporary_update(db, character["id"]),
                ],
            }

        def settle_individual_group(db, lease, defeated):
            outcome = finish_world_group(
                STORE,
                COMBAT_GROUPS,
                lease,
                character_id=character["id"],
                defeated=defeated,
                db=db,
            )
            if outcome["applied"] and defeated:
                from wakfu_server.monster_corpses import retain

                retain(db, fight, TEST_MONSTERS)
            return outcome

        with COMBAT_GROUPS.lock:
            result = prepare_finish(
                STORE,
                account_id,
                generation,
                character,
                fight_messages,
                metadata,
                duration_ms=int((time.monotonic() - fight_started_at) * 1000),
                fight_instance_id=fight.id,
                policy_resolver=resolve_fight_reward,
                loot_resolver=resolve_fight_loot,
                groups=COMBAT_GROUPS,
                group_lease=group_lease,
                group_settlement=settle_individual_group,
            )
        # A terminal checkpoint must not precede the reward transaction.
        checkpoint_fight("ended")
        character.update(
            {
                key: result["character"][key]
                for key in (
                    "xp",
                    "kamas",
                    "level",
                    "hp",
                    "max_hp",
                    "hp_damage",
                    "health_dead",
                    "ecology_value",
                    "ecology_revision",
                    "captured_roster",
                )
            }
        )
        if result["reward"] is not None:
            # Update the existing wallet model, including an already-open UI.
            # Bootstrap wallet packets alone replace rather than refresh it.
            send(
                connection,
                service,
                12753,
                wire.account_kamas_update(character["kamas"]),
            )
        for message_id, payload in fight_messages.prepare_delivery(result["packets"]):
            send(connection, service, message_id, payload)
        if result["reward"] is not None:
            record(
                event="combat_reward_committed",
                actor_id=character["id"],
                fight_id=fight.id,
                xp=result["reward"]["xp"],
                kamas=result["reward"]["kamas"],
                awarded=result["reward"]["awarded"],
            )
        send(connection, service, *fight_messages._flush())
        record(event="combat_finished", fight_id=fight.id, winner=fight.winner)

    def area_boundary_provider(preview, **boundary):
        from wakfu_server.combat_server_spell import prepare_server_turn_start
        from wakfu_server.spells import default_deck

        if combat_session is not None:
            characters, decks = COMBAT_SESSIONS.player_sources(preview)
            source = characters.get(
                boundary.get("actor_id"), next(iter(characters.values()))
            )
            deck = decks[source["id"]]
        else:
            source = character
            stored = character.get("builds", {}).get(0, {}).get("deck")
            deck = bytes.fromhex(stored) if stored else default_deck(character)
        return prepare_server_turn_start(
            source,
            TEST_MONSTERS_BY_ID,
            preview,
            deck,
            player_characters=characters if combat_session is not None else None,
            deck_blobs=decks if combat_session is not None else None,
            native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1",
            **boundary,
        )

    def area_movement_provider(preview, **boundary):
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.spells import default_deck

        if combat_session is not None:
            characters, decks = COMBAT_SESSIONS.player_sources(preview)
            source = characters.get(
                boundary.get("actor_id"), next(iter(characters.values()))
            )
            deck = decks[source["id"]]
        else:
            source = character
            stored = character.get("builds", {}).get(0, {}).get("deck")
            deck = bytes.fromhex(stored) if stored else default_deck(character)
        return prepare_area_movement(
            source,
            TEST_MONSTERS_BY_ID,
            preview,
            deck,
            player_characters=characters if combat_session is not None else None,
            deck_blobs=decks if combat_session is not None else None,
            **boundary,
        )

    def pass_test_monster_turn():
        if combat_session is None or fight is None:
            return run_test_monster_turn()
        from wakfu_server.combat_turn_guard import run_shared_npc_attempt

        shared = COMBAT_SESSIONS.registry.lookup(fight.id)
        return run_shared_npc_attempt(
            shared,
            run_test_monster_turn,
            lambda identity, error: record(
                event="combat_npc_turn_retry_pending",
                fight_id=shared.fight.id,
                actor_id=identity[0],
                turn_id=identity[1],
                exception_type=type(error).__name__,
                reason=redact(str(error)),
                retry_delay_seconds=2,
            ),
        )

    @PROFILER.profile("combat.ai_turn")
    def run_test_monster_turn():
        import hashlib
        import pathlib
        import sys
        import types

        directory = pathlib.Path(
            os.environ.get(
                "WAKFU_AI_SDK_DIR",
                str(pathlib.Path(__file__).resolve().parent / "ai-service"),
            )
        )
        path = directory / "world_loader.py"
        source = path.read_bytes()
        name = "_wakfu_world_ai_loader_" + hashlib.sha256(source).hexdigest()
        loader = sys.modules.get(name)
        if loader is None:
            candidate = types.ModuleType(name)
            candidate.__file__ = str(path)
            exec(compile(source, str(path), "exec"), candidate.__dict__)
            loader = sys.modules.setdefault(name, candidate)
        entry = loader.load_entry(directory)
        scopes = []
        frame = sys._getframe(1)
        try:
            while frame is not None:
                if frame.f_globals is globals():
                    scopes.append(dict(frame.f_locals))
                frame = frame.f_back
        finally:
            del frame
        for _ in entry(
            fight_messages, world_context=dict(globals=globals(), scopes=scopes)
        ):
            pass

    @PROFILER.profile("admin.command")
    def execute_test_command(text, *, authorized_by=None):
        nonlocal character, position, movement_state
        from wakfu_server.test_console import execute, parse_target
        from wakfu_server.command_permissions import (
            authorize_command,
            canonical_command,
            is_admin,
        )

        failure = None
        try:
            issuer = account_id if authorized_by is None else authorized_by
            authorize_command(STORE, issuer, text)
            text, target = parse_target(text)
            command = canonical_command(text.split()[0])
            if command == "!perfil":
                from wakfu_server.performance_commands import execute_profile_command

                if not is_admin(STORE, issuer):
                    raise PermissionError(
                        "Solo un administrador puede consultar perfiles"
                    )
                answer = execute_profile_command(
                    PROFILER, text, RUNTIME / "logs/profiles"
                )
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
            if command == "!checkpoint":
                from wakfu_server.manual_checkpoint import checkpoint_message

                args = text.split()[1:]
                if len(args) > 1:
                    raise ValueError("Uso: !checkpoint [recibo]")
                if args:
                    checkpoint_result = MANUAL_CHECKPOINT.status(args[0])
                else:
                    recipient = dict(character, name="Consola local")
                    recipient_id, recipient_generation = character["id"], generation
                    checkpoint_result = MANUAL_CHECKPOINT.request(
                        requester=(recipient_id, recipient_generation),
                        notify=lambda completed: WORLD.send_to(
                            recipient_id,
                            recipient_generation,
                            674,
                            wire.chat(recipient, checkpoint_message(completed)),
                        ),
                    )
                answer = checkpoint_message(checkpoint_result)
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer, "checkpoint": checkpoint_result}
            if target is not None:
                if not is_admin(STORE, issuer):
                    raise PermissionError(
                        "Solo un administrador puede modificar otro personaje"
                    )
                identity = WORLD.live_identity(name=target)
                if identity is None:
                    raise ValueError("El personaje de destino debe estar conectado")
                target_generation, target_character = identity
                if target_character["id"] != character["id"]:
                    # The target's owner thread must execute with its own closure.
                    receipt = TEST_CONSOLE.submit(
                        target_character["id"],
                        text,
                        requester_account_id=issuer,
                        authorize=lambda: authorize_command(STORE, issuer, text),
                        delegated_by=issuer,
                        expected_generation=target_generation,
                    )
                    answer = f"Comando enviado a {target_character['name']}; recibo {receipt['handle']}"
                    send(
                        connection,
                        service,
                        674,
                        wire.chat(dict(character, name="Consola local"), answer),
                    )
                    return {"message": answer, "handle": receipt["handle"]}
            if command == "!resultado":
                args = text.split()[1:]
                if len(args) != 1:
                    raise ValueError("Uso: !resultado recibo")
                receipt = TEST_CONSOLE.poll(args[0])
                if receipt.get("requester_account_id") != issuer and not is_admin(
                    STORE, issuer
                ):
                    raise PermissionError("El recibo pertenece a otra cuenta")
                answer = str(
                    receipt.get("error")
                    or receipt.get("result", {}).get("message")
                    or receipt["status"]
                )
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
            if command in ("!buscar", "!search", "!ids"):
                import shlex
                from wakfu_server.command_search import search

                args = shlex.split(text)[1:]
                kind, page = "all", 1
                if args and args[0].lower() in ("item", "items", "mob", "mobs"):
                    kind = args.pop(0).lower()
                if "--pagina" in args:
                    index = args.index("--pagina")
                    if index != len(args) - 2:
                        raise ValueError("Uso: !buscar [item|mob] nombre [--pagina 2]")
                    page = int(args[index + 1])
                    args = args[:index]
                found = search(" ".join(args), kind=kind, page=page)
                for line in found["message"].splitlines():
                    send(
                        connection,
                        service,
                        674,
                        wire.chat(dict(character, name="Consola local"), line),
                    )
                return {"message": found["message"]}
            if (
                command in ("!tp", "!mob", "!item", "!equip", "!unequip", "!nivel")
                and fight is not None
            ):
                raise ValueError(
                    "Termina el combate antes de modificar el mundo o el inventario."
                )
            if command in ("!tp", "!mob") and bag_session is not None:
                raise ValueError(
                    "Sal del combate o del merkasaco antes de usar este comando."
                )
            flush_positions(
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
            )
            result = execute(
                STORE,
                COMBAT_GROUPS if COMBAT_TEST else None,
                account_id,
                generation,
                character,
                text,
                authorized_by=issuer,
            )
            if result["action"] == "tp":
                cancel_crafting()
                WORLD.leave(character["id"], generation)
                character = result["character"]
                POSITIONS.attach(account_id, generation, character)
                position = {key: character[key] for key in ("x", "y", "z")}
                movement_state = Movement(position)
                for message_id, message_body in owned_native_bootstrap(character):
                    send(connection, service, message_id, message_body)
                join_world(generation, connection, character)
                mark_static_sync_pending()
            else:
                character = (
                    bag_session.refresh(character, result["character"])
                    if bag_session is not None and bag_session.owns(character)
                    else result["character"]
                )
                for message_id, message_body in result["packets"]:
                    send(connection, service, message_id, message_body)
                for message_id, message_body in result.get("world_packets", []):
                    WORLD.emit_location(
                        character["map_id"],
                        character["instance_id"],
                        message_id,
                        message_body,
                    )
            answer = result["message"]
            record(
                event="test_console_command",
                actor_id=character["id"],
                command=command,
                outcome="ok",
            )
        except (ValueError, PermissionError) as error:
            failure = error
            answer = str(error)
            record(
                event="test_console_command",
                actor_id=character["id"],
                command=text.split()[0],
                outcome="rejected",
                reason=answer,
            )
        send(
            connection,
            service,
            674,
            wire.chat(dict(character, name="Consola local"), answer),
        )
        if failure is not None:
            raise failure
        summary = {"message": answer}
        if "item" in result:
            summary["item"] = {
                key: result["item"][key]
                for key in ("uid", "reference", "quantity", "container", "slot")
            }
        if "group_key" in result:
            summary["group_key"] = list(result["group_key"])
            summary["actor_ids"] = [member["id"] for member in result["members"]]
        return summary

    def current_combat_stats(actor, state=None):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        current_fight = fight if state is None else state
        if actor.id in getattr(current_fight, "native_summon_registrations", {}):
            from wakfu_server.combat_summon_stats import registered_summon_stats

            return registered_summon_stats(actor, current_fight, character["map_id"])
        if getattr(actor, "native_summon_source", None) is not None:
            raise ValueError("Summon stats require current native registration")
        if actor.effect_stats is not None:
            if (
                actor.effect_maxima is None
                or 4 not in actor.effect_stats
                or 4 not in actor.effect_maxima
            ):
                raise ValueError("Missing authoritative combat WP snapshot")
            wp_current = actor.effect_stats[4]
            wp_maximum = actor.effect_maxima[4]
        else:
            raise ValueError("Missing authoritative combat WP snapshot")
        if actor.controlled:
            source = (
                STORE.character(actor.owner_id, actor.id) if COMBAT_TEST else character
            )
            return actual_actor_stats(
                source,
                actor,
                fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
            )
        return actual_monster_actor_stats(
            TEST_MONSTERS_BY_ID[actor.id],
            actor,
            fight.id,
            wp_current=wp_current,
            wp_maximum=wp_maximum,
            direction=3,
        )

    @PROFILER.profile("combat.refresh")
    def refresh_shared_combat():
        nonlocal fight, fight_messages, group_lease, TEST_MONSTERS, TEST_MONSTERS_BY_ID
        if combat_session is None or fight is None:
            return None
        shared = COMBAT_SESSIONS.registry.lookup(fight.id)
        fight = shared.fight
        fight_messages = shared.runtime
        group_lease = getattr(shared, "group_lease", group_lease)
        context = shared.join_context or {}
        monsters = getattr(fight, "rift_monsters", context.get("monsters"))
        if monsters is not None:
            if getattr(fight, "rift_wave_state", None) is not None:
                context["monsters"] = monsters
            TEST_MONSTERS_BY_ID = monsters
            TEST_MONSTERS = tuple(monsters.values())
        return shared

    def publish_external_marker(shared):
        """Publish public-world marker deltas, never to fight participants."""
        if not COMBAT_TEST or shared is None or getattr(shared, "is_duel", False):
            return
        fight = getattr(shared, "fight", None)
        if fight is None:
            return
        previous_location = EXTERNAL_FIGHT_MARKERS.location(fight.id)
        if fight.phase == "finished":
            committed_abandon = (
                getattr(getattr(shared, "runtime", None), "abandon_owner", None)
                is not None
                and fight.winner is None
            )
            # A lethal action can drain before the group tombstone commits.
            # Keep the marker until settlement so terminal world removal is
            # derived from durable state rather than an uncommitted preview.
            # Abandonment commits its own durable abort before setting
            # abandon_owner; it deliberately has no reward settlement.
            if not getattr(shared, "settlement_ready", False) and not committed_abandon:
                return
            packet = EXTERNAL_FIGHT_MARKERS.remove(fight.id)
        else:
            packet = EXTERNAL_FIGHT_MARKERS.update(shared)
        if packet is None:
            return
        if packet[0] == 12238 and previous_location is not None:
            map_id, instance_id = previous_location
        else:
            map_id, instance_id = shared.map_id, shared.instance_id
        participant_sessions = frozenset(
            (session.character_id, session.generation)
            for session in getattr(shared, "participants", {}).values()
        )
        observer_sessions = frozenset(
            (session.character_id, session.generation)
            for session in SPECTATORS.sessions(fight.id)
        )
        try:
            # The native marker resolves its NPC leader in the world actor
            # registry. A claimed group is absent from available() snapshots.
            # Publish its authoritative descriptor before announcing the fight.
            if packet[0] == 13753:
                actor_packet = EXTERNAL_FIGHT_MARKERS.actor_packet(fight.id)
                if actor_packet is None:
                    raise ValueError("External fight marker lacks its NPC snapshot")
                packets = (actor_packet, packet)
            else:
                packets = (packet,)
            # Live markers only enqueue an already-owned actor/marker batch;
            # they neither inspect nor modify world groups. Do not wait behind
            # unrelated ecology transactions. Terminal snapshots still require
            # the group fence through their final ordered publication.
            from contextlib import nullcontext

            marker_fence = (
                COMBAT_GROUPS.lock if fight.phase == "finished" else nullcontext()
            )
            with marker_fence:
                if (
                    fight.phase == "finished"
                    and getattr(shared, "settlement_ready", False)
                    and getattr(shared, "group_lease", None)
                ):
                    from wakfu_server.combat.combat_world_group_cleanup import (
                        defeated_snapshot,
                    )

                    with STORE.connection() as db:
                        packets += defeated_snapshot(
                            db, map_id, instance_id, lease=shared.group_lease
                        )
                    with WORLD.lock:
                        corpse_peers = tuple(
                            peer
                            for session_generation, peer, owner in WORLD.players.values()
                            if (owner["map_id"], owner.get("instance_id", 0))
                            == (map_id, instance_id)
                            and (owner["id"], session_generation)
                            not in participant_sessions | observer_sessions
                        )
                    packets += monster_corpse_snapshot(
                        map_id, instance_id, peers=corpse_peers
                    )
                delivered_recipients = WORLD.emit_location_batch(
                    map_id,
                    instance_id,
                    packets,
                    exclude_sessions=participant_sessions | observer_sessions,
                )
            record(
                event="combat_external_marker_published",
                fight_id=fight.id,
                map_id=map_id,
                instance_id=instance_id,
                opcode=packet[0],
                delivered_recipients=delivered_recipients,
            )
        except (KeyError, TypeError, ValueError) as error:
            record(
                event="combat_external_marker_publish_failed",
                fight_id=fight.id,
                reason=str(error),
            )

    @PROFILER.profile("combat.event_delivery")
    def drain_shared_combat():
        if combat_session is None or fight is None:
            return

        delivered_batches = {}

        def deliver(owner, batches):
            for batch in batches:
                delivered_batches.setdefault(batch.sequence, []).append(batch.packets)
            packets = tuple(packet for batch in batches for packet in batch.packets)
            if not packets:
                return
            if (
                owner.account_id == combat_session.account_id
                and owner.generation == combat_session.generation
                and owner.character_id == combat_session.character_id
            ):
                send_batch(connection, service, packets)
            else:
                WORLD.send_batch_to(owner.character_id, owner.generation, packets)

        COMBAT_SESSIONS.dispatch_connected(fight.id, deliver)
        shared = COMBAT_SESSIONS.registry.lookup(fight.id)
        publish_external_marker(shared)
        if delivered_batches:
            from wakfu_server.combat_spectator_events import public_combat_events

            publish_spectator_state(
                shared,
                tuple(
                    packet
                    for sequence in sorted(delivered_batches)
                    for packet in public_combat_events(delivered_batches[sequence])
                ),
            )

    def spectator_session_for_current_character():
        if account_id is None or generation is None or character is None:
            raise ValueError("A loaded character session is required")
        return ObserverSession(
            account_id,
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )

    def spectator_snapshot(shared):
        from wakfu_server.combat_spectator_snapshot import current_snapshot

        owner_session = spectator_session_for_current_character()
        deadline_ms = None
        if shared.fight.phase == "active":
            deadline = getattr(shared.runtime, "turn_deadline", None)
            if deadline is None:
                raise ValueError("Active fight has no current native turn deadline")
            deadline_ms = int(
                time.time() * 1000 + max(0.0, deadline - time.monotonic()) * 1000
            )
        packets = current_snapshot(
            shared.fight,
            shared,
            actor_payload=lambda current_fight, actor: COMBAT_SESSIONS.actor_payload(
                current_fight, actor, owner_session
            ),
            deadline_ms=deadline_ms,
        )
        if getattr(shared.fight, "rift_wave_state", None) is not None:
            from wakfu_server.rift_combat_adapter import world_snapshot

            return tuple(world_snapshot(shared.fight)) + tuple(packets)
        return packets

    def spectator_waiting_for_ack(shared):
        runtime = getattr(shared, "runtime", None)
        awaiting = getattr(runtime, "awaiting_ack", None)
        return (
            shared.fight.phase == "active"
            and awaiting is not None
            and getattr(runtime, "turn_deadline", None) is None
            and getattr(getattr(shared, "ack", None), "turn", None) == awaiting
        )

    @PROFILER.profile("combat.spectator_publish")
    def publish_spectator_state(shared, event_packets=()):
        """Publish current state plus only the shared batches after its cursor."""
        if not COMBAT_TEST or shared is None or getattr(shared, "is_duel", False):
            return
        try:
            if shared.fight.phase == "finished" and not getattr(
                shared, "settlement_ready", False
            ):
                # Preserve lethal action/death delivery, but do not let the
                # client return before the durable NPC tombstone is committed.
                current = SPECTATORS.fights.get(shared.fight.id)
                pending_events = tuple(
                    packet for packet in event_packets if packet[0] != 12238
                )
                if current is not None and pending_events:
                    SPECTATORS.publish_events(
                        shared.fight.id,
                        revision=max(shared.sequence, current.revision + 1),
                        event_packets=pending_events,
                    )
                return
            if shared.fight.phase == "finished":
                from copy import copy
                from wakfu_server.combat_results import terminal_event
                from wakfu_server.combat_spectator_events import terminal_batch

                event_packets = terminal_batch(
                    event_packets,
                    fight_id=shared.fight.id,
                    fallback_packet=lambda: terminal_event(copy(shared.runtime)),
                )
            participants = tuple(
                ObserverSession(
                    entry.account_id,
                    entry.character_id,
                    entry.generation,
                    entry.map_id,
                    entry.instance_id,
                )
                for entry in shared.participants.values()
            )
            current = SPECTATORS.fights.get(shared.fight.id)
            if spectator_waiting_for_ack(shared):
                if current is not None and event_packets:
                    SPECTATORS.publish_events(
                        shared.fight.id,
                        revision=max(shared.sequence, current.revision + 1),
                        event_packets=event_packets,
                    )
                return
            if current is None:
                if shared.fight.phase == "finished":
                    return
                packets = spectator_snapshot(shared)
                SPECTATORS.publish_fight(
                    shared.fight.id,
                    map_id=shared.map_id,
                    instance_id=shared.instance_id,
                    participant_sessions=participants,
                    revision=max(1, shared.sequence),
                    snapshot_packets=packets,
                    visible=not getattr(shared, "is_duel", False),
                )
            elif shared.fight.phase == "finished":
                revision = max(shared.sequence, current.revision + 1)
                observers = SPECTATORS.publish_terminal(
                    shared.fight.id,
                    revision=revision,
                    event_packets=event_packets,
                )
            else:
                try:
                    packets = spectator_snapshot(shared)
                except (KeyError, TypeError, ValueError):
                    # Existing observers already own a native bootstrap. A
                    # rejected replacement must not discard their committed
                    # action stream or admit newcomers at a stale snapshot.
                    SPECTATORS.invalidate_snapshot(shared.fight.id)
                    if event_packets:
                        SPECTATORS.publish_events(
                            shared.fight.id,
                            revision=max(shared.sequence, current.revision + 1),
                            event_packets=event_packets,
                        )
                    raise
                SPECTATORS.publish_update(
                    shared.fight.id,
                    revision=max(shared.sequence, current.revision + 1),
                    snapshot_packets=packets,
                    event_packets=event_packets,
                )
        except (KeyError, TypeError, ValueError) as error:
            record(
                event="combat_spectator_snapshot_rejected",
                fight_id=getattr(getattr(shared, "fight", None), "id", None),
                reason=str(error),
            )

    def resume_settled_shared_combat():
        nonlocal combat_session, fight, fight_messages, group_lease
        nonlocal TEST_MONSTERS, TEST_MONSTERS_BY_ID, TEST_GROUP_KEY
        nonlocal checkpoint_id, checkpoint_revision, checkpoint_terminal
        if (
            not COMBAT_TEST
            or character is None
            or combat_session is not None
            or fight is not None
        ):
            return False
        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is not None and getattr(shared, "is_duel", False):
            if not shared.settlement_ready or account_id in shared.returned:
                return False
            fight_id = shared.fight.id
            session_entry = COMBAT_SESSIONS.session(account_id, generation, character)
            try:
                shared = COMBAT_SESSIONS.takeover_settled(session_entry, fight_id)
            except ValueError as error:
                record(
                    event="combat_settlement_takeover_rejected",
                    actor_id=character["id"],
                    fight_id=fight_id,
                    reason=str(error),
                )
                return False
            combat_session = session_entry
            fight = shared.fight
            fight_messages = shared.runtime
            group_lease = getattr(shared, "group_lease", None)
            context = shared.join_context or {}
            TEST_MONSTERS_BY_ID = context.get("monsters", {})
            TEST_MONSTERS = tuple(TEST_MONSTERS_BY_ID.values())
            TEST_GROUP_KEY = context.get("group_key")
            checkpoint = CHECKPOINTS.read(account_id, fight_id)
            checkpoint_id = fight_id
            checkpoint_revision = checkpoint["revision"]
            checkpoint_terminal = True
            drain_shared_combat()
            record(
                event="combat_settlement_taken_over",
                actor_id=character["id"],
                fight_id=fight_id,
            )
            return True
        if shared is not None and (
            not shared.settlement_ready or account_id in shared.returned
        ):
            return False
        session_entry = COMBAT_SESSIONS.session(account_id, generation, character)
        try:
            recovered = COMBAT_SESSIONS.recover_settled_world(
                session_entry,
                character,
                wp=COMBAT_TEST_WP,
            )
        except ValueError as error:
            record(
                event="combat_settled_world_recovery_rejected",
                actor_id=character["id"],
                fight_id=None if shared is None else shared.fight.id,
                reason=str(error),
            )
            return False
        if recovered is None:
            return False
        character.update(recovered["character"])
        for message_id, payload in recovered["packets"]:
            send(connection, service, message_id, payload)
        group_lease = None
        record(
            event="combat_settled_world_recovered",
            actor_id=character["id"],
            fight_id=recovered["fight_id"],
            health_applied=recovered["applied"],
            native_fight_attached=False,
        )
        return True

    def adopt_shared_duel():
        """Attach a loaded owner to its existing shared combat FSM/outbox."""
        nonlocal combat_session, fight, fight_messages, group_lease
        nonlocal TEST_MONSTERS, TEST_MONSTERS_BY_ID, TEST_GROUP_KEY
        nonlocal fight_started_at, checkpoint_id, checkpoint_revision
        nonlocal checkpoint_terminal
        if (
            not COMBAT_TEST
            or not loaded
            or character is None
            or combat_session is not None
            or fight is not None
        ):
            return False
        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is None:
            return False
        owner = shared.participants.get(account_id)
        if owner is None or owner.character_id != character["id"]:
            return False
        # A participant who has completed native12925 is back in the world
        # even while the other owner is still viewing the settled result.
        # Never let an idle/reconnect callback reattach that returned socket.
        if account_id in shared.returned or account_id in shared.withdrawals:
            return False
        if owner.generation != generation:
            if shared.settlement_ready:
                return resume_settled_shared_combat()
            from wakfu_server.combat_shared import Session
            from wakfu_server.fight_store import takeover_participant

            replacement = Session(
                account_id,
                character["id"],
                generation,
                shared.map_id,
                shared.instance_id,
            )

            # The worker publishes its revision under shared.lock. Drain before
            # Registry.takeover acquires that lock, never from its callback.
            if not CHECKPOINT_WRITER.flush_fight(shared.fight.id, timeout=10):
                raise ValueError("Checkpoint takeover drain timed out")

            def persist_takeover(previous):
                CHECKPOINT_WRITER.takeover_writer(
                    shared.fight.id,
                    account_id,
                    previous.generation,
                    generation,
                    persist=lambda: takeover_participant(
                        STORE,
                        account_id,
                        generation,
                        character["id"],
                        fight_id=shared.fight.id,
                        previous_generation=previous.generation,
                    ),
                )

            COMBAT_SESSIONS.registry.takeover(
                shared.fight.id,
                replacement,
                lambda current_fight, current_shared, current_session: (
                    ()
                    if current_fight.phase == "finished"
                    else COMBAT_SESSIONS.owned_reconnect_bootstrap(
                        current_fight, current_shared, current_session
                    )
                ),
                persist_takeover=persist_takeover,
                recover_disconnected=True,
            )
            shared = COMBAT_SESSIONS.registry.lookup(shared.fight.id)
            owner = replacement
        if owner.generation != generation:
            return False
        combat_session = owner
        fight = shared.fight
        fight_messages = shared.runtime
        group_lease = shared.group_lease
        context = shared.join_context or {}
        TEST_MONSTERS_BY_ID = context.get("monsters", {})
        TEST_MONSTERS = tuple(TEST_MONSTERS_BY_ID.values())
        TEST_GROUP_KEY = context.get("group_key")
        fight_started_at = context.get("fight_started_at", time.monotonic())
        placement_deadline.start(
            fight.id,
            context.get("duration_ms"),
            fight_started_at,
        )
        try:
            checkpoint = CHECKPOINTS.read(account_id, fight.id)
        except ValueError:
            checkpoint = None
        checkpoint_id = fight.id
        checkpoint_revision = None if checkpoint is None else checkpoint["revision"]
        checkpoint_terminal = False
        # Another peer can adopt/checkpoint this shared duel concurrently.
        # Seed once; a delayed SQL read on this socket must not roll back a
        # newer fight-wide revision observed by another socket.
        checkpoint_revision = shared.seed_checkpoint_revision(checkpoint_revision)
        drain_shared_combat()
        if checkpoint is None:
            checkpoint_fight()
        record(
            event="shared_combat_owner_attached",
            actor_id=character["id"],
            fight_id=fight.id,
        )
        return True

    def apply_readiness(ready):
        nonlocal fight, fight_messages
        if fight is None or fight.phase != "placement":
            return False
        from wakfu_server.combat_actor import actor_effects
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.spells import default_deck

        if combat_session is not None:
            from wakfu_server.fight_store import activate

            shared = refresh_shared_combat()

            def ready_operation(candidate, runtime):
                prepared = COMBAT_SESSIONS.ready_transition(
                    combat_session,
                    candidate,
                    runtime,
                    ready,
                    shared.join_context["monsters"],
                    previous_native_action_id=(
                        0 if runtime is None else runtime.native_action_id
                    ),
                    fight_start=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
                    area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
                    == "1",
                )
                if candidate.phase == "placement" and prepared.fight.phase == "active":
                    activate(
                        STORE,
                        combat_session.account_id,
                        combat_session.generation,
                        combat_session.character_id,
                        candidate.id,
                    )
                return prepared

            COMBAT_SESSIONS.execute(
                combat_session,
                fight.id,
                character["id"],
                ready_operation,
                require_turn=False,
            )
            refresh_shared_combat()
            drain_shared_combat()
            checkpoint_fight()
            if fight.phase == "finished":
                complete_test_fight()
            else:
                pass_test_monster_turn()
            return True

        stored_deck = character.get("builds", {}).get(0, {}).get("deck")
        deck = bytes.fromhex(stored_deck) if stored_deck else default_deck(character)
        candidate, candidate_messages, packets = prepare_ready(
            fight,
            account_id,
            ready,
            initialize=lambda preview, action_id: prepare_server_initialization(
                character,
                TEST_MONSTERS_BY_ID,
                preview,
                account_id,
                deck,
                action_id=action_id,
                fight_start=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            ),
            stats_serializer=current_combat_stats,
            runtime_stats_serializer=current_combat_stats,
            effects_serializer=actor_effects,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                TEST_MONSTERS_BY_ID,
                deck,
                action_id=action_id,
                critical=False,
            )[0],
            turn_start_provider=area_boundary_provider
            if (
                os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
                or os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1"
            )
            else None,
            previous_native_action_id=(
                fight_messages.native_action_id if fight_messages is not None else 0
            ),
            turn_end_provider=(
                lambda preview, **boundary: prepare_server_turn_end(
                    character,
                    TEST_MONSTERS_BY_ID,
                    preview,
                    deck,
                    **boundary,
                )
            )
            if os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1"
            else None,
        )
        if candidate_messages is None:
            fight = candidate
            return False
        from wakfu_server.fight_store import activate

        activate(STORE, account_id, generation, character["id"], candidate.id)
        fight = candidate
        fight_messages = candidate_messages
        for message_id, payload in packets:
            send(connection, service, message_id, payload)
        record(
            event="combat_test_active",
            actor_id=character["id"],
            fight_id=fight.id,
        )
        if fight.phase == "finished":
            complete_test_fight()
        else:
            pass_test_monster_turn()
        return True

    @PROFILER.profile("session.idle")
    def idle():
        if STOPPING.is_set():
            return False
        nonlocal last_health_tick, last_session_renewal, console_session
        nonlocal spectator_session, spectator_fight_id
        nonlocal spectator_terminal_pending
        if account_id is not None:
            now = time.monotonic()
            renew = now - last_session_renewal >= 10
            health_started = time.monotonic()
            session_health = STORE.session_health(account_id, generation, renew=renew)
            health_elapsed_ms = (time.monotonic() - health_started) * 1000
            if not session_health["valid"] or health_elapsed_ms >= 1000:
                record(
                    event="session_failure"
                    if not session_health["valid"]
                    else "session_renewal_slow",
                    account_id=account_id,
                    actor_id=None if character is None else character["id"],
                    fight_id=None if fight is None else fight.id,
                    turn_id=None if fight is None else fight.turn_id,
                    renewal_requested=renew,
                    health_elapsed_ms=round(health_elapsed_ms, 3),
                    last_successful_renewal_age_seconds=None
                    if last_session_renewal == 0
                    else round(now - last_session_renewal, 3),
                    **session_health,
                )
            if not session_health["valid"]:
                return False
            if renew:
                last_session_renewal = time.monotonic()
            deliver_rift_transition()
            if combat_session is None:
                try:
                    adopt_shared_duel()
                except (ValueError, KeyError) as error:
                    record(
                        event="friendly_duel_attach_rejected",
                        actor_id=None if character is None else character["id"],
                        reason=str(error),
                    )
            if combat_session is not None:
                refresh_shared_combat()
                drain_shared_combat()
                if fight is not None and fight.phase == "finished":
                    try:
                        shared_state = COMBAT_SESSIONS.registry.lookup(fight.id)
                        if (
                            getattr(shared_state, "is_duel", False)
                            and not shared_state.settlement_ready
                        ):
                            complete_test_fight()
                    except ValueError as error:
                        record(
                            event="friendly_duel_settlement_retry",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            reason=str(error),
                        )
            deliver_rift_transition()
            deliver_dungeon_transitions()
            if not sync_loaded_world_snapshot():
                sync_static_world()
            sync_scene_world()
            if spectator_session is not None and spectator_fight_id is not None:
                try:
                    if character is None or (
                        character["map_id"],
                        character.get("instance_id", 0),
                    ) != (spectator_session.map_id, spectator_session.instance_id):
                        SPECTATORS.disconnect(spectator_session)
                        record(
                            event="combat_spectator_left_location",
                            actor_id=spectator_session.character_id,
                            fight_id=spectator_fight_id,
                        )
                        spectator_session = None
                        spectator_fight_id = None
                        return True
                    for delivery in SPECTATORS.poll(spectator_session):
                        for message_id, payload in delivery.packets:
                            send(connection, service, message_id, payload)
                            if message_id == 12238:
                                from wakfu_server.combat_spectator_events import (
                                    is_normal_finish_packet,
                                )

                                if is_normal_finish_packet(
                                    (message_id, payload), spectator_fight_id
                                ):
                                    from wakfu_server.combat_spectators import (
                                        TerminalAck,
                                    )

                                    spectator_terminal_pending = TerminalAck(
                                        spectator_session, spectator_fight_id
                                    )
                    if SPECTATORS.observing(spectator_session) is None:
                        record(
                            event="combat_spectator_subscription_closed",
                            actor_id=spectator_session.character_id,
                            fight_id=spectator_fight_id,
                        )
                        spectator_session = None
                        spectator_fight_id = None
                except ValueError as error:
                    SPECTATORS.disconnect(spectator_session)
                    record(
                        event="combat_spectator_lease_expired",
                        actor_id=spectator_session.character_id,
                        fight_id=spectator_fight_id,
                        reason=str(error),
                    )
                    return False
            if time.monotonic() - now >= 10:
                record(
                    event="session_idle_slow",
                    account_id=account_id,
                    actor_id=None if character is None else character["id"],
                    fight_id=None if fight is None else fight.id,
                    elapsed_ms=round((time.monotonic() - now) * 1000, 3),
                )
            for map_id, instance_id, packet in HARVESTS.due_availability(
                blocking=False
            ):
                WORLD.emit_location(map_id, instance_id, *packet)
            if placement_deadline.take_expired(fight, now):
                try:
                    apply_readiness(True)
                    checkpoint_fight()
                    record(
                        event="combat_placement_expired",
                        fight_id=fight.id,
                        actor_id=character["id"],
                    )
                except ValueError as error:
                    record(
                        event="combat_placement_expiry_rejected",
                        fight_id=fight.id,
                        actor_id=character["id"],
                        reason=str(error),
                    )
            if fight_messages is not None and fight is not None:
                if combat_session is not None:
                    # A failed Ready/ACK callback can leave an unpublished NPC
                    # action pending. Any remaining owner may retry it; the AI
                    # bridge claims the actual shared actor/turn under its lock.
                    if (
                        fight.phase == "active"
                        and fight.current is not None
                        and not fight.current.controlled
                        and fight_messages.awaiting_ack is None
                        and not fight_messages.pending
                    ):
                        pass_test_monster_turn()
                        refresh_shared_combat()
                        drain_shared_combat()
                    expired, expiry_error = COMBAT_SESSIONS.expire_current_turn(
                        fight.id,
                        combat_session,
                        now_ms=int(time.time() * 1000),
                    )
                    if expired:
                        refresh_shared_combat()
                        drain_shared_combat()
                        checkpoint_fight()
                        record(
                            event=(
                                "combat_turn_expiry_recovered"
                                if expiry_error is not None
                                else "combat_turn_expired"
                            ),
                            fight_id=fight.id,
                            actor_id=character["id"],
                        )
                        if fight.phase == "finished":
                            complete_test_fight()
                else:
                    (
                        expired_packets,
                        expiry_error,
                    ) = fight_messages.expire_current_or_recover(
                        account_id, now_ms=int(time.time() * 1000)
                    )
                    if expiry_error is not None:
                        record(
                            event="combat_turn_expiry_rejected",
                            fight_id=fight.id,
                            actor_id=character["id"],
                            reason=expiry_error,
                        )
                    for message_id, payload in expired_packets:
                        send(connection, service, message_id, payload)
                    if expired_packets:
                        checkpoint_fight()
                        record(
                            event="combat_turn_expiry_recovered"
                            if expiry_error is not None
                            else "combat_turn_expired",
                            fight_id=fight.id,
                            actor_id=character["id"],
                        )
                    if fight.phase == "finished":
                        complete_test_fight()
            if (
                loaded
                and character is not None
                and fight is None
                and combat_session is None
                and time.monotonic() - last_health_tick >= 1
            ):
                last_health_tick = time.monotonic()
                saved = health_store.tick(
                    STORE, account_id, generation, character["id"], character["hp"]
                )
                if saved["hp"] != character["hp"]:
                    previous_hp = character["hp"]
                    character.update(hp=saved["hp"], max_hp=saved["max_hp"])
                    WORLD.update(
                        generation,
                        character,
                        12436,
                        health.packet(
                            character["id"],
                            character["hp"],
                            0 if character["hp"] == 0 else 1,
                        ),
                    )
                    record(
                        event="health_regenerated",
                        actor_id=character["id"],
                        previous_hp=previous_hp,
                        hp=character["hp"],
                        max_hp=character["max_hp"],
                    )
            if (
                loaded
                and character is not None
                and os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
            ):
                current_console = (character["id"], generation)
                if console_session != current_console:
                    if console_session is not None:
                        TEST_CONSOLE.unregister(*console_session)
                    TEST_CONSOLE.register(
                        character["id"],
                        generation,
                        name=character["name"],
                        account_id=account_id,
                    )
                    console_session = current_console
                TEST_CONSOLE.drain(character["id"], generation, execute_test_command)
            return True
        return time.monotonic() - connected_at < 30

    try:
        raw.settimeout(1)
        with context.wrap_socket(raw, server_side=True) as connection:
            connection = Connection(connection)
            connection.trace_id = connection_trace_id
            if not CONNECTIONS.register(
                connection, lambda opcode, body: send(connection, service, opcode, body)
            ):
                return
            record(
                event="tls_connected",
                connection_id=connection_trace_id,
                service=service,
                peer=peer,
                tls=connection.version(),
            )
            while not STOPPING.is_set():
                if active_request is not None:
                    active_request.finish()
                    active_request = None
                if not idle():
                    raise ValueError("Session expired or replaced")
                length = struct.unpack(">I", receive(connection, 4, idle))[0]
                if not 7 <= length <= 327670:
                    raise ValueError("Invalid frame size")
                frame = receive(connection, length - 4, idle)
                route, opcode = struct.unpack(">BH", frame[:3])
                body = frame[3:]
                request_received_at = time.monotonic()
                from wakfu_server.combat_diagnostics import combat_diagnostic_scope

                active_request = RequestTrace(
                    sink=record,
                    opcode=opcode,
                    service=service,
                    connection_id=connection_trace_id,
                    snapshot=lambda: state_summary(character, fight, fight_messages),
                    effect_scope=combat_diagnostic_scope(record)
                    if fight is not None or opcode in (13130, 12523, 13260)
                    else None,
                    flush=write_records,
                )
                record(
                    service=service,
                    direction="in",
                    opcode=opcode,
                    route=route,
                    bytes=len(body),
                )
                if loaded:
                    # A frozen rift party must hydrate its committed asset map
                    # before adopting a placement already registered by its leader.
                    deliver_rift_transition()
                # The accepted challenger can receive its placement batch on
                # WORLD before its own idle callback runs. Bind that socket to
                # the shared duel before dispatching an immediate readiness or
                # action packet; otherwise the first 12523 can be rejected as
                # having no fight handler even though the client saw placement.
                if (
                    COMBAT_TEST
                    and loaded
                    and character is not None
                    and combat_session is None
                    and fight is None
                ):
                    try:
                        adopt_shared_duel()
                    except (ValueError, KeyError) as error:
                        record(
                            event="friendly_duel_attach_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                if combat_session is not None and fight is not None:
                    refresh_shared_combat()
                if loaded:
                    deliver_rift_transition()
                    deliver_dungeon_transitions(before_action=True)
                if chest_opening is not None and (
                    fight is not None
                    or spectator_session is not None
                    or bag_session is None
                    or not bag_session.is_owner
                    or not bag_session.owns(character)
                    or opcode == 13331
                ):
                    chest_opening = None
                # All transactional actions/DB refreshes see the last approved
                # outside-world position; own-bag moves remain session-only.
                if character is not None and opcode != 13331:
                    flush_positions(
                        account_id=account_id,
                        generation=generation,
                        character_id=character["id"],
                    )
                if flora_ticket is not None and opcode in (
                    13331,
                    13686,
                    12296,
                    13578,
                    12247,
                    13130,
                    13220,
                    13481,
                ):
                    cancel_flora()
                if character is not None and opcode in (13686, 12296, 13578, 12247):
                    HARVESTS.cancel(character["id"], generation=generation)
                    PLANTINGS.cancel(character["id"], generation)
                if fight is not None and opcode in (
                    13686,
                    12296,
                    13578,
                    12247,
                    13331,
                    12772,
                    13434,
                    12580,
                    13210,
                    13826,
                    12870,
                    12363,
                ):
                    if opcode == 12772:
                        # The client edits builds optimistically. Restore the
                        # prior sheet while preserving combat resources; a
                        # silent discard looks like a lost save on reconnect.
                        try:
                            packets = builds.blocked_save_messages(character, body)
                        except (ValueError, UnicodeError) as error:
                            record(
                                event="build_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                        else:
                            for message_id, message_body in packets:
                                send(connection, service, message_id, message_body)
                            record(
                                event="build_rejected",
                                actor_id=character["id"],
                                reason="Build editing is unavailable during combat",
                            )
                    record(
                        event="combat_world_action_rejected",
                        actor_id=character["id"],
                        opcode=opcode,
                        reason="World action is unavailable during combat",
                    )
                    continue
                # 14689 is an auxiliary request, not a mandatory world-ready
                # acknowledgement. A cached map after character switching can
                # omit it; the first world action must still join the session.
                if (
                    selected
                    and not loaded
                    and opcode
                    in (
                        14689,
                        13331,
                        12366,
                        13578,
                        12772,
                        12296,
                        13686,
                        12870,
                        13220,
                        13481,
                        1156,
                        1031,
                        1074,
                        1066,
                        13074,
                        13224,
                        13188,
                        13831,
                        13140,
                        12997,
                        13037,
                        12203,
                        12781,
                        13406,
                        12027,
                        13113,
                        784,
                        657,
                        672,
                        799,
                        12449,
                        12787,
                        13993,
                        12294,
                    )
                ):
                    loaded = True
                    destination_route = transports.for_map(character["map_id"])
                    if destination_route:
                        for message_id, message_body in transports.bootstrap(
                            character, destination_route
                        ):
                            send(connection, service, message_id, message_body)
                    elif character["map_id"] != 1134:
                        for message_id, message_body in owned_native_bootstrap(
                            character
                        ):
                            send(connection, service, message_id, message_body)
                    else:
                        replay(
                            connection,
                            119,
                            131,
                            account_id,
                            character,
                            generation=generation,
                        )
                    join_world(generation, connection, character)
                    resume_settled_shared_combat()
                    # Bootstrap can arrive before the client finishes loading its
                    # scene. Initial login needs the same complete post-load replay
                    # as map transitions, even when no movement request follows.
                    mark_static_sync_pending()
                    send(
                        connection,
                        service,
                        12436,
                        health.packet(
                            character["id"],
                            character["hp"],
                            0 if character["hp"] == 0 else 1,
                        ),
                    )
                    record(event="world_bootstrap_sent", position=position)
                if (
                    loaded
                    and world_snapshot_pending
                    and opcode
                    in (
                        13331,
                        12366,
                        13578,
                        12772,
                        12296,
                        13686,
                        12870,
                        13220,
                        13481,
                        1156,
                        1031,
                        1074,
                        1066,
                        13074,
                        13224,
                        13188,
                        13831,
                        13140,
                        12997,
                        13037,
                        12203,
                        12781,
                        13406,
                        12027,
                        13113,
                        784,
                        657,
                        672,
                        799,
                        12449,
                        12787,
                        13993,
                        12294,
                    )
                ):
                    sync_loaded_world_snapshot(force=True)
                rift_start_run = None
                if opcode == 33:
                    send(connection, service, 23, b"\x01" + body)
                    send(connection, service, 309, struct.pack(">I", 12345))
                elif opcode == 574:
                    send(
                        connection,
                        service,
                        400,
                        struct.pack(">q", 123456789)
                        + (RUNTIME / "public-key.der").read_bytes(),
                    )
                elif service == "dispatcher":
                    if opcode == 584:
                        r = Reader(body)
                        encrypted = r.take(r.number("I"))
                        r.finish()
                        result = subprocess.run(
                            [
                                "openssl",
                                "pkeyutl",
                                "-decrypt",
                                "-inkey",
                                str(RUNTIME / "server.key"),
                                "-pkeyopt",
                                "rsa_padding_mode:pkcs1",
                            ],
                            input=encrypted,
                            capture_output=True,
                            timeout=5,
                        )
                        if result.returncode:
                            raise ValueError("Invalid RSA authentication")
                        r = Reader(result.stdout)
                        if r.number("q") != 123456789:
                            raise ValueError("Invalid challenge")
                        token = r.text("B")
                        r.finish()
                        access = STORE.token(token, "game", consume=True)
                        account_id = access["account_id"]
                        # Hold the buffer across takeover so the old worker
                        # cannot enqueue another move between flush and CAS.
                        with POSITIONS.account_barrier(account_id):
                            flush_positions(account_id=account_id)
                            generation = STORE.begin_session(account_id)
                            with LOCK:
                                previous = LIVE.pop(account_id, None)
                        if previous:
                            record(
                                event="session_replaced_before_shutdown",
                                account_id=account_id,
                                target_connection_id=getattr(
                                    previous[1], "trace_id", None
                                ),
                                replacement_connection_id=connection_trace_id,
                            )
                            try:
                                previous[1].shutdown(socket.SHUT_RDWR)
                            except OSError:
                                pass
                        send(
                            connection,
                            service,
                            472,
                            wire.adapt(472, fixture(472), account_id),
                        )
                        record(event="account_authenticated", account_id=account_id)
                    elif opcode == 402:
                        if account_id is None:
                            raise ValueError("Authentication required")
                        send(connection, service, 453, REALMS)
                    elif opcode == 575:
                        request = decode_body("out", opcode, body)
                        if request["server_id"] != 10:
                            raise ValueError("Unknown local realm")
                        if account_id is None:
                            raise ValueError("Authentication required")
                        ticket = STORE.issue_token(
                            account_id, "ticket", generation=generation, realm_id=10
                        )
                        send(connection, service, 466, b"\x00" + pack_text(ticket))
                elif opcode == 426:
                    request = decode_body("out", opcode, body)
                    access = STORE.token(request["ticket"], "ticket", consume=True)
                    account_id, generation = access["account_id"], access["generation"]
                    if access["realm_id"] != 10 or not STORE.current_session(
                        account_id, generation
                    ):
                        raise ValueError("Invalid local ticket session")
                    with LOCK:
                        LIVE[account_id] = (generation, connection)
                    replay(connection, 24, 44, account_id, generation=generation)
                    send(
                        connection,
                        service,
                        13873,
                        wire.account_kamas(STORE.account_kamas(account_id)),
                    )
                elif opcode == 13488:
                    if account_id is None or body != b"\x00":
                        raise ValueError("Invalid character selection request")
                    spectator_terminal_pending = None
                    if combat_session is not None and fight is not None:
                        shared_selection = refresh_shared_combat()
                        if (
                            not getattr(shared_selection, "is_duel", False)
                            and len(
                                set(shared_selection.participants)
                                - set(shared_selection.withdrawals)
                            )
                            > 1
                        ):
                            pve_withdrawal_pending = COMBAT_SESSIONS.withdraw_pve(
                                combat_session, character, b""
                            )
                            character.update(pve_withdrawal_pending["character"])
                            fight = fight_messages = None
                            combat_session = group_lease = None
                        elif (
                            not getattr(shared_selection, "is_duel", False)
                            and not shared_selection.settlement_ready
                        ):
                            from wakfu_server.combat_abandon import (
                                prepare as prepare_selection_abandon,
                                placement_runtime as selection_abandon_runtime,
                                return_to_world as return_selection_abandon,
                            )

                            with shared_selection.lock:
                                selection_runtime = selection_abandon_runtime(
                                    fight, shared_selection.runtime
                                )
                                abandoned_selection = prepare_selection_abandon(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    selection_runtime,
                                    b"",
                                )
                                shared_selection.runtime = selection_runtime
                                character.update(abandoned_selection["character"])
                                return_selection_abandon(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    selection_runtime,
                                    struct.pack(">iB", fight.id, 1),
                                    wp=COMBAT_TEST_WP,
                                )
                            publish_external_marker(shared_selection)
                            publish_spectator_state(
                                shared_selection, abandoned_selection["packets"]
                            )
                            if not COMBAT_SESSIONS.registry.retire_abandoned_single_owner(
                                fight.id, combat_session
                            ):
                                raise ValueError(
                                    "Selector PvE abandon was not safely retired"
                                )
                            if shared_selection.group_lease is not None:
                                COMBAT_GROUPS.finish(
                                    shared_selection.group_lease, defeated=False
                                )
                            fight = fight_messages = None
                            combat_session = group_lease = None
                    if pve_withdrawal_pending is not None:
                        recovered = COMBAT_SESSIONS.recover_withdrawn_pve(
                            COMBAT_SESSIONS.session(account_id, generation, character)
                        )
                        if recovered is not None:
                            character.update(recovered)
                        pve_withdrawal_pending = None
                    from wakfu_server.combat_health import persist_aborted_fight

                    checkpoint_fight(
                        "ended"
                        if fight is not None and fight.phase == "finished"
                        else "aborted"
                    )
                    persist_aborted_fight(
                        STORE, account_id, generation, character, fight
                    )
                    if not COMBAT_SESSIONS.registry.lease_generation_active(generation):
                        release_groups(generation)
                    group_lease = None
                    fight = fight_messages = None
                    if character is not None:
                        POSITIONS.release(account_id, generation, character["id"])
                    STORE.clear_character(account_id, generation)
                    if character is not None:
                        exterior = HAVEN_BAG_EXTERIORS.discard(
                            generation, character["id"]
                        )
                        if exterior is not None:
                            outside, packet = exterior
                            WORLD.emit_location(
                                outside["map_id"], outside["instance_id"], *packet
                            )
                        WORLD.leave(character["id"], generation)
                    selected = loaded = False
                    character = None
                    movement_state = None
                    bag_session = None
                    replay(connection, 31, 44, account_id, generation=generation)
                    send(
                        connection,
                        service,
                        13873,
                        wire.account_kamas(STORE.account_kamas(account_id)),
                    )
                    record(
                        event="returned_to_character_selection", account_id=account_id
                    )
                elif opcode == 22296:
                    if account_id is None or selected:
                        raise ValueError(
                            "Authentication required or character already selected"
                        )
                    status, created = create_character_request(
                        STORE, account_id, generation, body
                    )
                    send(connection, service, 22025, bytes([status]))
                    if created is not None:
                        send(
                            connection,
                            service,
                            13078,
                            wire.adapt(13078, fixture(13078), account_id, created),
                        )
                        send(
                            connection,
                            service,
                            12393,
                            wire.attribute_sheets(
                                fixture(12393), STORE.characters(account_id)
                            ),
                        )
                        send(
                            connection,
                            service,
                            23548,
                            wire.character_list(
                                CHARACTERS, account_id, STORE.characters(account_id)
                            ),
                        )
                        record(
                            event="character_created",
                            account_id=account_id,
                            character_id=created["id"],
                            breed=created["breed"],
                        )
                        # Official creation selects the new character server-side;
                        # it sends 23082/bootstrap without waiting for 23664.
                        character = STORE.select_character(
                            account_id, generation, created["id"]
                        )
                        character = health_store.initialize(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            coefficient=1,
                        )
                        POSITIONS.attach(account_id, generation, character)
                        position = {k: character[k] for k in ("x", "y", "z")}
                        movement_state = Movement(position)
                        selected = True
                        replay(
                            connection,
                            45,
                            114,
                            account_id,
                            character,
                            generation=generation,
                        )
                        send(connection, service, *rich_inventory_packet(character))
                        from wakfu_server.inventory_uids import initialize_pool

                        message_id, message_body = initialize_pool(
                            STORE, account_id, generation, character["id"]
                        )["packet"]
                        send(connection, service, message_id, message_body)
                        record(
                            event="character_selected_after_creation",
                            account_id=account_id,
                            character_id=character["id"],
                        )
                elif opcode == 22870:
                    # cDN from the native character selector is a single i64
                    # character ID. Deletion is permitted only before selection.
                    character_id = None
                    deleted = False
                    if account_id is None:
                        error = ValueError("Authentication required")
                    elif selected:
                        error = ValueError(
                            "Return to character selection before deletion"
                        )
                    else:
                        try:
                            request = decode_body("out", opcode, body)
                            character_id = request["character_id"]
                            with PARTIES._guard(character_id):
                                result = STORE.delete_character(
                                    account_id, generation, character_id
                                )
                                deleted = True
                                try:
                                    PARTIES.publish_character_deletion(
                                        result["party_change"]
                                    )
                                except Exception as failure:
                                    record(
                                        event="character_deletion_party_publish_failed",
                                        character_id=character_id,
                                        reason=str(failure),
                                    )
                        except (ValueError, UnicodeError) as failure:
                            error = failure
                    if not deleted:
                        record(
                            event="character_deletion_rejected",
                            account_id=account_id,
                            reason=str(error),
                        )
                    else:
                        record(
                            event="character_deleted",
                            account_id=account_id,
                            character_id=character_id,
                        )
                    if account_id is not None and not selected:
                        owned = STORE.characters(account_id)
                        send(
                            connection,
                            service,
                            12393,
                            wire.attribute_sheets(fixture(12393), owned),
                        )
                        send(
                            connection,
                            service,
                            23548,
                            wire.character_list(CHARACTERS, account_id, owned),
                        )
                elif opcode == 23664:
                    request = decode_body("out", opcode, body)
                    if account_id is None or selected:
                        raise ValueError(
                            "Authentication required or character already selected"
                        )
                    character = STORE.select_character(
                        account_id, generation, request["character_id"]
                    )
                    if is_dungeon_run(character.get("instance_id", 0)):
                        from wakfu_server.maps import dungeon_recovery, dungeon_runtime
                        from wakfu_server.combat_terrain import map_geometry

                        dungeon_recovery.resume_member(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            character["instance_id"],
                        )
                        with STORE.connection() as dungeon_db:
                            dungeon_runtime.ensure_current_room(
                                dungeon_db,
                                COMBAT_GROUPS,
                                character["instance_id"],
                                map_geometry(character["map_id"]),
                            )
                    if request["character_name"] != character["name"]:
                        raise ValueError("Character name mismatch")
                    reconnect_session = COMBAT_SESSIONS.session(
                        account_id, generation, character
                    )
                    live_reconnect = COMBAT_SESSIONS.live_reconnect_available(
                        reconnect_session
                    )
                    reconciliation = (
                        None
                        if live_reconnect
                        else COMBAT_SESSIONS.reconcile_disconnected_pve(
                            reconnect_session, groups=COMBAT_GROUPS
                        )
                    )
                    if reconciliation is not None:
                        orphan = reconciliation["shared"]
                        # Durable health/abort committed before registry removal.
                        # Refresh before regeneration, position attachment and
                        # world bootstrap; never initialize from stale login HP.
                        character = STORE.character(account_id, character["id"])
                        with orphan.lock:
                            orphan.fight.phase = "finished"
                            orphan.fight.winner = None
                        publish_external_marker(orphan)
                        record(
                            event="shared_pve_reconnect_reconciled",
                            actor_id=character["id"],
                            fight_id=orphan.fight.id,
                            registry_retired=True,
                            durable_abort=True,
                        )
                    recovered = COMBAT_SESSIONS.recover_withdrawn_pve(
                        COMBAT_SESSIONS.session(account_id, generation, character)
                    )
                    if recovered is not None:
                        character.update(recovered)
                    character = health_store.initialize(
                        STORE,
                        account_id,
                        generation,
                        character["id"],
                        coefficient=0 if live_reconnect else 1,
                    )
                    POSITIONS.attach(account_id, generation, character)
                    position = {k: character[k] for k in ("x", "y", "z")}
                    movement_state = Movement(position)
                    selected = True
                    replay(
                        connection,
                        45,
                        114,
                        account_id,
                        character,
                        generation=generation,
                    )
                    send(connection, service, *rich_inventory_packet(character))
                    from wakfu_server.inventory_uids import initialize_pool

                    message_id, message_body = initialize_pool(
                        STORE, account_id, generation, character["id"]
                    )["packet"]
                    send(connection, service, message_id, message_body)
                    record(
                        event="character_selected",
                        account_id=account_id,
                        character_id=character["id"],
                        name=character["name"],
                    )
                elif opcode == 12767 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.mount_feeding_dispatch import (
                        prepare as prepare_mount_feeding,
                        publish_result as publish_mount_feeding,
                    )
                    from wakfu_server.inventory_move import (
                        reload_inventory,
                        synchronization,
                    )
                    from wakfu_server.ecology_feedback import information

                    try:
                        result = prepare_mount_feeding(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            in_fight=fight is not None,
                        )
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        send_batch(
                            connection,
                            service,
                            [
                                synchronization(character),
                                rich_inventory_packet(character),
                            ],
                        )
                        send(connection, service, *information(str(error)))
                        record(
                            event="mount_food_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    except (DatabaseError, PoolTimeout) as error:
                        send(
                            connection,
                            service,
                            *information(
                                "La alimentación está temporalmente indisponible."
                            ),
                        )
                        record(
                            event="mount_food_unavailable",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                    else:
                        # This is deliberately outside the domain-error catch:
                        # publication happens after commit. Any send/encoding
                        # failure must disconnect so the next bootstrap repairs
                        # the client's inventory without replaying additive deltas.
                        publish_mount_feeding(
                            result,
                            lambda packets: send_batch(connection, service, packets),
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        if result["applied"]:
                            # PET attaches the actor observer to the refreshed
                            # rich item model. XP itself belongs to ProtoPet.
                            WORLD.update(
                                generation,
                                character,
                                *wire.refresh_player(PLAYER_TEMPLATE, character),
                            )
                            from wakfu_server.combat_lifecycle import (
                                outside_progression,
                            )

                            send(connection, service, *outside_progression(character))
                            for packet in mount_snapshot(character):
                                send(connection, service, *packet)
                        record(
                            event="mount_food_fed",
                            actor_id=character["id"],
                            applied=result["applied"],
                            replayed=result["replayed"],
                            xp_delta=result["xp_delta"],
                            health_delta=result["health_delta"],
                        )
                elif opcode in (12634, 13928) and loaded:
                    from wakfu_server.mount_state import toggle
                    from wakfu_server.mount_codec import ride_result, dismounted

                    if body:
                        send(connection, service, *ride_result(character["id"], 7))
                        record(
                            event="mount_request_rejected",
                            actor_id=character["id"],
                            reason="Mount requests require an empty body",
                        )
                        continue
                    wants_mount = opcode == 12634
                    if fight is not None or bag_session is not None:
                        send(connection, service, *ride_result(character["id"], 3))
                        continue
                    if wants_mount:
                        cancel_flora()
                        PLANTINGS.cancel(character["id"], generation)
                        HARVESTS.cancel(character["id"], generation=generation)
                    try:
                        code, saved = toggle(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            mounted=wants_mount,
                            in_fight=False,
                            location_allowed=True,
                            occupation_cancelable=True,
                        )
                    except ValueError as error:
                        send(connection, service, *ride_result(character["id"], 7))
                        record(
                            event="mount_request_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        continue
                    character = saved
                    if code:
                        send(connection, service, *ride_result(character["id"], code))
                    else:
                        packet = (
                            ride_result(character["id"], 0)
                            if wants_mount
                            else dismounted(character["id"])
                        )
                        WORLD.update(generation, character, *packet)
                    record(
                        event="mount_toggle",
                        actor_id=character["id"],
                        requested_mounted=wants_mount,
                        result=code,
                    )
                elif opcode in (12231, 13382) and loaded:
                    from wakfu_server.crafting import begin as begin_crafting
                    from wakfu_server.items.craft_station import (
                        native_catalog as craft_catalog,
                        resolve_current as resolve_craft_station,
                    )
                    from wakfu_server.items.craft_wire import request as craft_request
                    from wakfu_server.items.craft_wire import (
                        occupation_request as craft_occupation_request,
                    )
                    from wakfu_server.items.craft_wire import result as craft_result

                    try:
                        if fight is not None:
                            raise ValueError(
                                "Crafting is unavailable in this session state"
                            )
                        if (
                            character["id"] in PLANTINGS.pending
                            or character["id"] in HARVESTS.pending
                        ):
                            raise ValueError(
                                "Finish or cancel the current occupation first"
                            )
                        request = (
                            craft_request(opcode, body)
                            if opcode == 12231
                            else craft_occupation_request(body)
                        )
                        station = resolve_craft_station(character, request["table_id"])
                        result = begin_crafting(
                            STORE,
                            craft_catalog(),
                            account_id,
                            generation,
                            character["id"],
                            opcode,
                            body,
                            station=station,
                            # Character-level CRAFT_SPEED is not persisted in
                            # the world snapshot yet; zero is the explicit
                            # local baseline, while the recipe timer still
                            # uses the native percentage formula.
                            craft_speed_modifier=0,
                            location_resolver=(
                                lambda saved: bag_session.refresh(character, saved)
                            )
                            if bag_session is not None
                            else None,
                        )
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        record(
                            event="craft_occupation_started",
                            actor_id=character["id"],
                            table_uid=request["table_id"],
                            recipe_id=request["recipe_id"],
                            request_opcode=opcode,
                            duration_ms=result["duration_ms"],
                            duplicate=result["duplicate"],
                        )
                    except ValueError as error:
                        message = str(error)
                        status = (
                            7
                            if "reachable" in message or "current map" in message
                            else 8
                            if "not allowed" in message or "table" in message
                            else 9
                            if "criterion" in message or "flags" in message
                            else 10
                            if "ingredient" in message or "batch" in message
                            else 3
                            if "Unknown native crafting recipe" in message
                            else 1
                        )
                        try:
                            send(connection, service, *craft_result(status, 0, 0))
                        except ValueError:
                            pass
                        record(
                            event="craft_occupation_rejected",
                            actor_id=character["id"],
                            reason=message,
                            native_status=status,
                        )
                elif (
                    opcode == 13429
                    and loaded
                    and len(body) == 3
                    and struct.unpack(">h", body[1:])[0] == 8
                ):
                    from wakfu_server.crafting import (
                        cancel as cancel_crafting_occupation,
                        complete as complete_crafting,
                        current as current_crafting,
                        completion_target as craft_completion_target,
                    )
                    from wakfu_server.items.craft_station import (
                        native_catalog as craft_catalog,
                        resolve_current as resolve_craft_station,
                    )
                    from wakfu_server.items.craft_wire import result as craft_result

                    try:
                        if fight is not None:
                            raise ValueError(
                                "Crafting is unavailable in this session state"
                            )
                        occupation = (
                            craft_completion_target(
                                STORE, account_id, generation, character["id"]
                            )
                            if body[0] == 2
                            else current_crafting(
                                STORE, account_id, generation, character["id"]
                            )
                        )
                        if occupation is None:
                            raise ValueError("Crafting occupation is no longer active")
                        if body[0] == 3:
                            cancel_crafting_occupation(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                occupation["token"],
                                occupation["version"],
                                body,
                            )
                            record(
                                event="craft_occupation_canceled",
                                actor_id=character["id"],
                                recipe_id=occupation["recipe_id"],
                            )
                            continue
                        station = (
                            None
                            if occupation.get("state") == "completed"
                            else resolve_craft_station(
                                character, occupation["table_uid"]
                            )
                        )
                        result = complete_crafting(
                            STORE,
                            craft_catalog(),
                            account_id,
                            generation,
                            character["id"],
                            occupation["token"],
                            occupation["version"],
                            body,
                            station=station,
                            location_resolver=(
                                lambda saved: bag_session.refresh(character, saved)
                            )
                            if bag_session is not None
                            else None,
                        )
                        if result["replay"]:
                            from wakfu_server.inventory_move import synchronization
                            from wakfu_server.inventory_items import equipment_inventory
                            from wakfu_server.profession_store import account_packet

                            saved = STORE.character(account_id, character["id"])
                            send(connection, service, *synchronization(saved))
                            send(connection, service, *equipment_inventory(saved))
                            with STORE.connection() as db:
                                progress_packet = account_packet(db, account_id)
                            send(connection, service, *progress_packet)
                        else:
                            for message_id, message_body in result["packets"]:
                                send(connection, service, message_id, message_body)
                        saved = STORE.character(account_id, character["id"])
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        record(
                            event="craft_occupation_completed",
                            actor_id=character["id"],
                            recipe_id=occupation["recipe_id"],
                            applied_xp=result.get("applied_xp", 0),
                            replay=result["replay"],
                        )
                    except ValueError as error:
                        message = str(error)
                        status = (
                            12
                            if "before its duration" in message
                            else 7
                            if "reachable" in message or "current map" in message
                            else 10
                            if "ingredient" in message
                            else 1
                        )
                        try:
                            send(connection, service, *craft_result(status, 0, 0))
                        except ValueError:
                            pass
                        record(
                            event="craft_occupation_rejected",
                            actor_id=character["id"],
                            reason=message,
                            native_status=status,
                        )
                elif opcode == 12995 and loaded:
                    from wakfu_server.resource_collect import (
                        prepare,
                        reserve,
                        start_packet,
                    )
                    from wakfu_server.combat_terrain import map_geometry

                    try:
                        if fight is not None:
                            raise ValueError("Sal del combate para recolectar")
                        cancel_flora()

                        def reachable_flora(current, resource):
                            if current["map_id"] == 9:
                                from wakfu_server.haven_bag_garden import reachable

                                return reachable(current, resource)
                            source = tuple(current[k] for k in ("x", "y", "z"))
                            destination = tuple(resource[k] for k in ("x", "y", "z"))
                            return any(
                                tuple(a) == source and tuple(b) == destination
                                for a, b in map_geometry(current["map_id"])["edges"]
                            )

                        prepared = prepare(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            reachable=reachable_flora,
                            location_context=lambda stored: active_garden_character(
                                stored, WORLD.snapshot()
                            ),
                        )
                        PLANTINGS.cancel(character["id"], generation)
                        HARVESTS.cancel(character["id"], generation=generation)
                        flora_ticket = reserve(
                            STORE,
                            account_id,
                            generation,
                            prepared,
                            location_context=lambda stored: active_garden_character(
                                stored, WORLD.snapshot()
                            ),
                        )
                        WORLD.emit_location(
                            prepared["character"]["map_id"],
                            prepared["character"]["instance_id"],
                            *start_packet(
                                prepared["character"],
                                prepared["resource"],
                                prepared["rule"],
                            ),
                        )
                        record(
                            event="resource_harvest_started",
                            actor_id=character["id"],
                            resource_uid=flora_ticket["resource_uid"],
                            action_id=flora_ticket["action_id"],
                        )
                    except ValueError as error:
                        cancel_flora()
                        record(
                            event="resource_harvest_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif (
                    opcode == 13429
                    and loaded
                    and len(body) == 3
                    and struct.unpack(">Bh", body)[1] == 3
                ):
                    from wakfu_server.resource_collect import (
                        complete,
                        acknowledge_publication,
                    )

                    if flora_ticket is None:
                        continue
                    try:
                        if fight is not None:
                            raise ValueError(
                                "La cosecha requiere estar fuera del combate"
                            )
                        with PLANTINGS.publisher_lock:
                            result = complete(
                                STORE,
                                flora_ticket,
                                body,
                                location_context=lambda stored: active_garden_character(
                                    stored, WORLD.snapshot()
                                ),
                            )
                            for message_id, payload in result["world_packets"]:
                                WORLD.emit_location(
                                    result["map_id"],
                                    result["instance_id"],
                                    message_id,
                                    payload,
                                )
                            acknowledge_publication(STORE, result)
                        flora_ticket = None
                        if result["applied"]:
                            saved = STORE.character(account_id, character["id"])
                            character = (
                                bag_session.refresh(character, saved)
                                if bag_session is not None
                                else saved
                            )
                        for message_id, payload in result["packets"]:
                            if message_id == 13574:
                                WORLD.update(
                                    generation,
                                    character,
                                    message_id,
                                    payload,
                                    include_sender=False,
                                )
                            send(connection, service, message_id, payload)
                        record(
                            event="resource_harvest_completed",
                            actor_id=character["id"],
                            applied=result["applied"],
                            ecology=result.get("outcome", {})
                            .get("ecology", {})
                            .get("reason"),
                        )
                    except ValueError as error:
                        cancel_flora()
                        record(
                            event="resource_harvest_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif opcode == 13220 and loaded and len(body) == 12:
                    from wakfu_server.cosmetic_learning import (
                        learn_item,
                    )

                    try:
                        if fight is not None:
                            raise ValueError(
                                "Item learning is unavailable during combat"
                            )
                        result = learn_item(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        record(
                            event="item_learned",
                            actor_id=character["id"],
                        )
                    except ValueError as error:
                        record(
                            event="item_learning_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif opcode == 13220 and loaded:
                    from wakfu_server.planting_cells import authorize
                    from wakfu_server.combat_terrain import map_geometry

                    try:
                        if fight is not None:
                            raise ValueError("Sal del combate para plantar")

                        def authorize_planting(current, request, seed, resource):
                            if current["map_id"] == 9:
                                from wakfu_server.haven_bag_garden import (
                                    authorize as authorize_garden,
                                )

                                z = authorize_garden(
                                    STORE, current, request, seed, resource
                                )
                                for player in WORLD.snapshot():
                                    if (
                                        player["map_id"],
                                        player["instance_id"],
                                        player["x"],
                                        player["y"],
                                    ) == (
                                        9,
                                        current["instance_id"],
                                        request["x"],
                                        request["y"],
                                    ):
                                        raise ValueError(
                                            "Hay un personaje en esa casilla"
                                        )
                                return z
                            z = authorize(
                                STORE,
                                current,
                                request,
                                seed,
                                resource,
                                open_test_policy=OPEN_PLANTING,
                            )
                            source = tuple(current[k] for k in ("x", "y", "z"))
                            destination = (request["x"], request["y"], z)
                            if not any(
                                tuple(a) == source and tuple(b) == destination
                                for a, b in map_geometry(current["map_id"])["edges"]
                            ):
                                raise ValueError("Acércate a la casilla para plantar")
                            for player in WORLD.snapshot():
                                if (player["map_id"], player["instance_id"]) == (
                                    current["map_id"],
                                    current["instance_id"],
                                ) and tuple(
                                    player[k] for k in ("x", "y", "z")
                                ) == destination:
                                    raise ValueError("Hay un personaje en esa casilla")
                            if COMBAT_TEST:
                                for group in COMBAT_GROUPS.snapshot():
                                    if group["key"][:2] == (
                                        current["map_id"],
                                        current["instance_id"],
                                    ) and group["status"] in ("available", "fighting"):
                                        if any(
                                            tuple(m[k] for k in ("x", "y", "z"))
                                            == destination
                                            for m in group["members"]
                                        ):
                                            raise ValueError(
                                                "Hay un monstruo en esa casilla"
                                            )
                            return z

                        with COMBAT_GROUPS.lock:
                            HARVESTS.cancel(character["id"], generation=generation)
                            packet = PLANTINGS.begin(
                                account_id,
                                generation,
                                character,
                                body,
                                authorize_planting,
                            )
                        WORLD.emit_location(
                            character["map_id"], character["instance_id"], *packet
                        )
                        record(event="planting_started", actor_id=character["id"])
                    except ValueError as error:
                        record(
                            event="planting_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif opcode == 13481 and loaded and COMBAT_TEST:
                    PLANTINGS.cancel(character["id"], generation)
                    from wakfu_server.monster_collect import (
                        decode_request,
                        action,
                        Regenerating,
                        availability_packet,
                    )
                    from wakfu_server.profession_store import level as profession_level
                    from wakfu_server.combat_terrain import map_geometry

                    try:
                        if fight is not None or bag_session is not None:
                            raise ValueError(
                                "La recolección requiere estar fuera del combate y del merkasaco"
                            )
                        request = decode_request(body)
                        with COMBAT_GROUPS.lock:
                            monster = harvest_target(character, request["monster_id"])
                            rule = action(monster["ref"], request["action_id"])
                            source = tuple(character[k] for k in ("x", "y", "z"))
                            target = tuple(monster[k] for k in ("x", "y", "z"))
                            reachable = any(
                                tuple(a) == source and tuple(b) == target
                                for a, b in map_geometry(character["map_id"])["edges"]
                            )
                            packet = HARVESTS.begin(
                                account_id,
                                generation,
                                character["id"],
                                body,
                                monster,
                                profession_level=profession_level(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    rule["profession_id"],
                                ),
                                reachable=reachable,
                            )
                        send(connection, service, *packet)
                        record(
                            event="monster_harvest_started",
                            actor_id=character["id"],
                            monster_id=monster["id"],
                            action_id=rule["action_id"],
                        )
                    except Regenerating as error:
                        send(
                            connection,
                            service,
                            *availability_packet(
                                error.monster_id,
                                error.action_id,
                                False,
                            ),
                        )
                        record(
                            event="monster_harvest_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                            monster_id=error.monster_id,
                            action_id=error.action_id,
                        )
                    except ValueError as error:
                        record(
                            event="monster_harvest_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif (
                    opcode == 13429
                    and loaded
                    and COMBAT_TEST
                    and len(body) == 3
                    and struct.unpack(">Bh", body)[0] in (2, 3)
                    and struct.unpack(">h", body[1:])[0] in (2, 6)
                ):
                    from wakfu_server.profession_store import level as profession_level
                    from wakfu_server.inventory_items import equipment_inventory

                    try:
                        if len(body) == 3 and struct.unpack(">Bh", body)[1] == 2:
                            with COMBAT_GROUPS.lock:
                                result = PLANTINGS.complete(
                                    account_id, generation, character, body
                                )
                            for message_id, payload in result["packets"]:
                                if message_id == 13135:
                                    WORLD.emit_location(
                                        character["map_id"],
                                        character["instance_id"],
                                        message_id,
                                        payload,
                                    )
                                else:
                                    if message_id == 13574:
                                        WORLD.update(
                                            generation,
                                            result["character"],
                                            message_id,
                                            payload,
                                            include_sender=False,
                                        )
                                    send(connection, service, message_id, payload)
                            if result["applied"]:
                                saved = STORE.character(account_id, character["id"])
                                character = (
                                    bag_session.refresh(character, saved)
                                    if bag_session is not None
                                    else saved
                                )
                                send_planting_context(connection, character)
                            record(
                                event="planting_completed",
                                actor_id=character["id"],
                                applied=result["applied"],
                                success=result.get("success"),
                                probability=result.get("probability"),
                                ecology=result.get("ecology", {}).get("reason"),
                            )
                            continue
                        with COMBAT_GROUPS.lock, HARVESTS.lock:
                            ticket = HARVESTS.pending.get(character["id"])
                            if ticket is None:
                                continue
                            monster = harvest_target(character, ticket["monster_id"])
                            result = HARVESTS.complete(
                                account_id,
                                generation,
                                character["id"],
                                body,
                                monster=monster,
                                profession_level=profession_level(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    ticket["rule"]["profession_id"],
                                ),
                            )
                        if result["applied"] and result.get("availability") is not None:
                            map_id, instance_id, packet = result["availability"]
                            WORLD.emit_location(map_id, instance_id, *packet)
                        for message_id, payload in result["packets"]:
                            send(connection, service, message_id, payload)
                        if result["applied"]:
                            character = STORE.character(account_id, character["id"])
                            send(connection, service, *equipment_inventory(character))
                        record(
                            event="monster_harvest_completed",
                            actor_id=character["id"],
                            applied=result["applied"],
                        )
                    except ValueError as error:
                        PLANTINGS.cancel(character["id"], generation)
                        HARVESTS.cancel(character["id"], generation=generation)
                        record(
                            event="monster_harvest_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif opcode == 12117 and loaded:
                    from wakfu_server.combat.friendly_duel_wire import cancellation

                    try:
                        if (
                            not COMBAT_TEST
                            or fight is not None
                            or bag_session is not None
                            or spectator_session is not None
                        ):
                            raise ValueError(
                                "Duel invitations are unavailable in this session"
                            )
                        from wakfu_server.combat.friendly_duel_wire import (
                            decode_challenge,
                        )
                        from wakfu_server.friendly_duels import (
                            cancel_undelivered_invitation,
                            invite_challenge,
                        )

                        request = decode_challenge(body)
                        identity = WORLD.live_identity(
                            character_id=request["target_character_id"]
                        )
                        if identity is None:
                            raise ValueError("Duel target is offline")
                        target_generation, target_character = identity
                        challenger_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        target_session = COMBAT_SESSIONS.session(
                            target_character["account_id"],
                            target_generation,
                            target_character,
                        )
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        flush_positions(
                            account_id=target_character["account_id"],
                            generation=target_generation,
                            character_id=target_character["id"],
                        )
                        result = invite_challenge(
                            STORE, challenger_session, target_session, body
                        )
                        if not WORLD.send_to(
                            target_character["id"],
                            target_generation,
                            *result["packet"],
                        ):
                            cancel_undelivered_invitation(
                                STORE,
                                account_id,
                                character["id"],
                                result["invitation_id"],
                            )
                            send(connection, service, *cancellation(6))
                        record(
                            event="friendly_duel_invitation",
                            actor_id=character["id"],
                            target_id=target_character["id"],
                            delivered=bool(result),
                        )
                    except ValueError as error:
                        record(
                            event="friendly_duel_invitation_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(connection, service, *cancellation(7))
                elif opcode == 13520 and loaded:
                    from wakfu_server.combat.friendly_duel_wire import cancellation

                    try:
                        if (
                            not COMBAT_TEST
                            or fight is not None
                            or bag_session is not None
                        ):
                            raise ValueError(
                                "Duel answer is unavailable in this session"
                            )
                        from wakfu_server.combat.friendly_duel_runtime import (
                            prepare_and_register,
                        )
                        from wakfu_server.friendly_duels import (
                            answer_challenge,
                            flush_answer_positions,
                        )

                        # Checkpoint only these duel owners, never the world.
                        flush_answer_positions(
                            STORE,
                            COMBAT_SESSIONS.session(account_id, generation, character),
                            body,
                            flush_positions,
                        )

                        def prepare_duel(db, fight_id, invitation, challenger, target):
                            prepared = prepare_and_register(
                                STORE,
                                COMBAT_SESSIONS,
                                db,
                                fight_id,
                                invitation,
                                challenger,
                                target,
                                auto_locked=bool(invitation["auto_lock"]),
                            )
                            rollback = prepared.pop("rollback")
                            return prepared, rollback

                        result = answer_challenge(
                            STORE,
                            COMBAT_SESSIONS.session(account_id, generation, character),
                            body,
                            prepare_duel=prepare_duel,
                        )
                        if result.get("accepted"):
                            adopt_shared_duel()
                            drain_shared_combat()
                            checkpoint_fight()
                            record(
                                event="friendly_duel_accepted",
                                actor_id=character["id"],
                                fight_id=result["fight_id"],
                            )
                        else:
                            send(connection, service, *result["packet"])
                            if result.get("notify_character_id") is not None:
                                WORLD.send_to(
                                    result["notify_character_id"],
                                    result["notify_generation"],
                                    *result["packet"],
                                )
                            record(
                                event="friendly_duel_declined_or_stale",
                                actor_id=character["id"],
                                fight_id=result.get("fight_id"),
                            )
                    except ValueError as error:
                        record(
                            event="friendly_duel_answer_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(connection, service, *cancellation(6))
                elif opcode == 13241 and loaded and COMBAT_TEST:
                    from wakfu_server.combat_multiplayer_wire import decode_join

                    try:
                        if fight is not None or bag_session is not None:
                            raise ValueError("Already in a fight or inventory session")
                        request = decode_join(body)
                        fight_id = COMBAT_SESSIONS.registry.resolve_join_target(
                            request["target_id"]
                        )
                        shared = COMBAT_SESSIONS.registry.lookup(fight_id)
                        context = shared.join_context
                        if not isinstance(context, dict):
                            raise ValueError(
                                "Placement bootstrap context is unavailable"
                            )
                        target = shared.fight.actors.get(request["target_id"])
                        if target is None:
                            raise ValueError("Join target disappeared")
                        combat_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        joined_actor = COMBAT_SESSIONS.player_actor(
                            combat_session, team=target.team
                        )
                        shared = COMBAT_SESSIONS.join(
                            combat_session,
                            body,
                            joined_actor,
                            expected_fight_id=fight_id,
                        )
                        fight = shared.fight
                        fight_messages = shared.runtime
                        group_lease = getattr(shared, "group_lease", None)
                        TEST_MONSTERS_BY_ID = context["monsters"]
                        TEST_MONSTERS = tuple(TEST_MONSTERS_BY_ID.values())
                        TEST_GROUP_KEY = context["group_key"]
                        fight_started_at = context["fight_started_at"]
                        placement_deadline.start(
                            fight.id,
                            context["duration_ms"],
                            fight_started_at,
                        )
                        checkpoint_fight()
                        drain_shared_combat()
                        record(
                            event="combat_test_joined",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            target_id=request["target_id"],
                        )
                    except ValueError as error:
                        combat_session = None
                        record(
                            event="combat_test_join_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"), str(error)
                            ),
                        )
                elif opcode == 13413 and loaded and COMBAT_TEST:
                    from wakfu_server.combat.combat_spectator_wire import (
                        decode_spectator_request,
                    )

                    try:
                        if fight is not None or combat_session is not None:
                            raise ValueError(
                                "Combat participants cannot observe another fight"
                            )
                        if bag_session is not None:
                            raise ValueError("Close the inventory session first")
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        character = STORE.character(account_id, character["id"])
                        fight_id = decode_spectator_request(body)
                        shared = COMBAT_SESSIONS.registry.lookup(fight_id)
                        observer = spectator_session_for_current_character()
                        if (observer.map_id, observer.instance_id) != (
                            shared.map_id,
                            shared.instance_id,
                        ):
                            raise ValueError("Fight is outside this map instance")
                        if spectator_waiting_for_ack(shared):
                            SPECTATORS.defer_enter(
                                observer,
                                fight_id,
                                authorize=lambda _session, _fight_id: True,
                            )
                            spectator_session = observer
                            spectator_fight_id = fight_id
                            # Close the check/register race: if the last ACK
                            # arrived just before defer_enter, this publishes
                            # the current snapshot and materializes the request.
                            publish_spectator_state(shared)
                            record(
                                event="combat_spectator_entry_deferred",
                                actor_id=character["id"],
                                fight_id=fight_id,
                                revision=shared.sequence,
                            )
                            continue
                        if (
                            shared.fight.phase == "active"
                            and getattr(shared.runtime, "turn_deadline", None) is None
                        ):
                            raise ValueError(
                                "Fight has no current native action deadline"
                            )
                        publish_spectator_state(shared)
                        delivery = SPECTATORS.enter(
                            observer,
                            fight_id,
                            authorize=lambda _session, _fight_id: True,
                        )
                        spectator_session = observer
                        spectator_fight_id = fight_id
                        for message_id, message_body in delivery.packets:
                            send(connection, service, message_id, message_body)
                        record(
                            event="combat_spectator_entered",
                            actor_id=character["id"],
                            fight_id=fight_id,
                            revision=delivery.revision,
                        )
                    except (KeyError, ValueError) as error:
                        record(
                            event="combat_spectator_entry_rejected",
                            actor_id=None if character is None else character["id"],
                            reason=str(error),
                        )
                        if character is not None:
                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"), str(error)
                                ),
                            )
                elif opcode == 12154 and loaded and COMBAT_TEST:
                    from wakfu_server.combat.combat_spectator_wire import (
                        decode_spectator_request,
                    )

                    try:
                        # Native bvU clears spectator mode and restores the
                        # world before sending cpg/12154; this is a no-ACK
                        # server cleanup notification, not a new world bootstrap.
                        fight_id = decode_spectator_request(body)
                        observer = spectator_session_for_current_character()
                        left = SPECTATORS.leave(observer, fight_id)
                        spectator_session = None
                        spectator_fight_id = None
                        terminal_return = False
                        if (
                            spectator_terminal_pending is not None
                            and spectator_terminal_pending.fight_id == fight_id
                        ):
                            if spectator_terminal_pending.session != observer:
                                raise ValueError(
                                    "Spectator terminal return belongs to another lease"
                                )
                            terminal_return = True
                            spectator_terminal_pending = None
                        if left or terminal_return:
                            refresh_owned_world_after_spectating()
                        record(
                            event="combat_spectator_left",
                            actor_id=character["id"],
                            fight_id=fight_id,
                            world_refreshed=left or terminal_return,
                        )
                    except (KeyError, ValueError) as error:
                        record(
                            event="combat_spectator_leave_rejected",
                            actor_id=None if character is None else character["id"],
                            reason=str(error),
                        )
                elif (
                    loaded
                    and COMBAT_TEST
                    and (
                        opcode == 13130
                        or (
                            opcode == 12870
                            and (rift_start_run := prepare_rift_start(body)) is not None
                        )
                    )
                ):
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    from wakfu_server.combat_bootstrap import create_placement
                    from wakfu_server.combat_terrain import local_arena

                    if rift_start_run is None:
                        target, x, y, z, auto_lock = struct.unpack(">qiihB", body)
                    else:
                        target = x = y = z = auto_lock = None
                    if (
                        fight is not None
                        or bag_session is not None
                        or spectator_session is not None
                    ):
                        record(
                            event="combat_test_attack_rejected",
                            actor_id=character["id"],
                            reason="Fight or inventory session is already active",
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                "No puedes iniciar otro combate con una sesión de combate o inventario activa.",
                            ),
                        )
                        continue
                    durable_fight_id = None
                    entry_stage_started = time.monotonic()
                    entry_stage_cpu = time.thread_time()

                    def entry_stage(stage):
                        nonlocal entry_stage_started, entry_stage_cpu
                        now, cpu = time.monotonic(), time.thread_time()
                        record(
                            event="combat_entry_stage",
                            stage=stage,
                            fight_id=durable_fight_id,
                            map_id=character["map_id"],
                            elapsed_ms=round((now - entry_stage_started) * 1000, 3),
                            thread_cpu_ms=round((cpu - entry_stage_cpu) * 1000, 3),
                        )
                        entry_stage_started, entry_stage_cpu = now, cpu

                    try:
                        if rift_start_run is None:
                            with COMBAT_GROUPS.lock:
                                selected_group = combat_group_for_target(
                                    COMBAT_GROUPS, character, target
                                )
                        else:
                            from wakfu_server.rift_dispatch_lifecycle import (
                                initial_members,
                            )
                            from wakfu_server.combat_terrain import map_geometry

                            with STORE.connection() as rift_db:
                                members = initial_members(
                                    rift_db,
                                    rift_start_run,
                                    map_geometry(character["map_id"]),
                                    (character["x"], character["y"], character["z"]),
                                )
                            selected_group = {
                                "key": (
                                    character["map_id"],
                                    character["instance_id"],
                                    rift_start_run["instance_id"],
                                ),
                                "members": members,
                            }
                        TEST_GROUP_KEY = selected_group["key"]
                        TEST_MONSTERS = tuple(selected_group["members"])
                        TEST_MONSTERS_BY_ID = {m["id"]: m for m in TEST_MONSTERS}
                        entry_stage("group_selected")
                        arena = local_arena(
                            character["map_id"],
                            character["id"],
                            (character["x"], character["y"], character["z"]),
                            [(m["x"], m["y"], m["z"]) for m in TEST_MONSTERS],
                        )
                        entry_stage("arena_selected")
                        from wakfu_server import territory_bonuses

                        with STORE.connection() as territory_db:
                            character = territory_bonuses.attach_character(
                                territory_db, character
                            )
                        from wakfu_server.equipment_stats import combat_resources

                        resources = combat_resources(character, wp=COMBAT_TEST_WP)
                        entry_stage("resources_built")
                        from wakfu_server.fight_store import (
                            create as create_fight_identity,
                        )

                        from wakfu_server.placement_deadline import duration

                        placement_duration = duration(STORE)
                        terrain_instance_id = secrets.randbelow(2**60) + 1
                        dungeon_binding = None
                        if (
                            rift_start_run is None
                            and DUNGEON_ROOM_RUNTIME_AVAILABLE
                            and is_dungeon_run(character.get("instance_id", 0))
                        ):
                            from wakfu_server.maps.dungeon_fight_binding import (
                                bind_room_group,
                            )

                            dungeon_binding = lambda db, fight_id: bind_room_group(
                                db,
                                TEST_GROUP_KEY,
                                character["id"],
                                fight_id,
                                player_team=0,
                            )
                        durable_fight_id = create_fight_identity(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            on_created=dungeon_binding,
                        )
                        from wakfu_server.combat_placement_policy import (
                            freeze as freeze_placement,
                        )

                        arena = freeze_placement(
                            STORE,
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                            fight_id=durable_fight_id,
                            map_id=character["map_id"],
                            instance_id=character["instance_id"],
                            selected_arena=arena,
                            seeds={
                                0: [(character["x"], character["y"], character["z"])],
                                1: [(m["x"], m["y"], m["z"]) for m in TEST_MONSTERS],
                            },
                        )
                        entry_stage("durable_placement_frozen")
                        candidate, packets = create_placement(
                            character,
                            TEST_MONSTERS,
                            arena,
                            fight_id=durable_fight_id,
                            player_ap=resources["ap"],
                            player_mp=resources["mp"],
                            player_wp=resources["wp"],
                            player_initiative=resources["initiative"],
                            terrain_effect_id=46,
                            terrain_instance_id=terrain_instance_id,
                            duration_ms=placement_duration,
                        )
                        entry_stage("placement_created")
                        from wakfu_server.combat_actor_snapshot import (
                            initialize_fight_snapshots,
                        )

                        initialization_warnings = []
                        initialize_fight_snapshots(
                            candidate,
                            characters={character["id"]: character},
                            monsters=TEST_MONSTERS_BY_ID,
                            wp_resources={
                                character["id"]: (resources["wp"], resources["wp"]),
                                **{
                                    m["id"]: (m["wp"], m.get("max_wp", m["wp"]))
                                    for m in TEST_MONSTERS
                                },
                            },
                            running_effects={
                                identity: () for identity in candidate.actors
                            },
                            initial_effect_uid=1,
                            dev_skip_unsupported=os.environ.get(
                                "WAKFU_DEV_SKIP_UNSUPPORTED_INITIALIZATION", "0"
                            )
                            == "1",
                            initialization_warnings=initialization_warnings,
                        )
                        entry_stage("actor_snapshots_initialized")
                        from wakfu_server.combat_forced_terrain import prewarm_map

                        warm_started = time.monotonic()
                        warm_thread_cpu = time.thread_time()
                        warm_process_cpu = time.process_time()
                        forced_terrain_loaded = prewarm_map(character["map_id"])
                        record(
                            event="combat_forced_terrain_ready",
                            fight_id=candidate.id,
                            map_id=character["map_id"],
                            available=forced_terrain_loaded,
                            thread_cpu_ms=round(
                                (time.thread_time() - warm_thread_cpu) * 1000, 3
                            ),
                            process_cpu_ms=round(
                                (time.process_time() - warm_process_cpu) * 1000, 3
                            ),
                            elapsed_ms=round(
                                (time.monotonic() - warm_started) * 1000, 3
                            ),
                        )
                        # Match the directions published by placement actor serializers.
                        for participant in candidate.actors.values():
                            participant.direction = 0 if participant.controlled else 3
                        from wakfu_server.combat_monster_world import remove_message

                        if rift_start_run is None:
                            with COMBAT_GROUPS.lock:
                                group_lease, members = COMBAT_GROUPS.claim(
                                    TEST_GROUP_KEY, generation, candidate.id
                                )
                                WORLD.emit_location(
                                    TEST_GROUP_KEY[0],
                                    TEST_GROUP_KEY[1],
                                    *remove_message([m["id"] for m in members]),
                                    exclude_generation=generation,
                                )
                        else:
                            group_lease = None
                            from wakfu_server.rift_dispatch_lifecycle import (
                                reserve_actor_ids,
                            )

                            with STORE.connection() as rift_db:
                                reserved_ids = reserve_actor_ids(rift_db, 128)
                            candidate.rift_wave_state = {
                                "instance_id": rift_start_run["instance_id"],
                                "world_group_id": candidate.id,
                                "wave": rift_start_run["wave"],
                                "turn_budget": rift_start_run["policy"]["turn_budget"],
                                "wave_actor_ids": [
                                    monster["id"] for monster in TEST_MONSTERS
                                ],
                                "wave_species_refs": [
                                    monster["ref"] for monster in TEST_MONSTERS
                                ],
                                "catalog": rift_start_run["catalog"],
                                "policy": rift_start_run["policy"],
                                "seed": rift_start_run["seed"],
                                "actor_id_pool": list(reserved_ids),
                            }
                            candidate.rift_monsters = dict(TEST_MONSTERS_BY_ID)
                        saved = health_store.sync(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            character["hp"],
                            character["hp"],
                            coefficient=0,
                        )
                        character.update(hp=saved["hp"], max_hp=saved["max_hp"])
                        fight_started_at = time.monotonic()
                        combat_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        COMBAT_SESSIONS.register(
                            combat_session,
                            candidate,
                            runtime=None,
                            group_lease=group_lease,
                            join_context={
                                **(
                                    {"rift_accepted_action": checkpoint_accepted_rift}
                                    if rift_start_run is not None
                                    else {}
                                ),
                                "arena": arena,
                                "terrain_effect_id": 46,
                                "terrain_instance_id": terrain_instance_id,
                                "leaders": {
                                    0: character["id"],
                                    1: TEST_MONSTERS[0]["id"],
                                },
                                "duration_ms": placement_duration,
                                "monsters": TEST_MONSTERS_BY_ID,
                                "group_key": TEST_GROUP_KEY,
                                "fight_started_at": fight_started_at,
                                "world_marker_cells": (
                                    (character["x"], character["y"]),
                                ),
                                "world_marker_origin": (
                                    character["x"],
                                    character["y"],
                                    character["z"],
                                ),
                            },
                        )
                        if rift_start_run is not None:
                            from wakfu_server import rift_runtime
                            from wakfu_server.combat_monster_world import spawn_group

                            shared_rift = COMBAT_SESSIONS.registry.lookup(candidate.id)
                            with COMBAT_SESSIONS.registry.lock, shared_rift.lock:
                                with STORE.connection() as rift_db:
                                    party_rows = rift_db.execute(
                                        "SELECT c.id,c.account_id,s.generation FROM characters c "
                                        "JOIN sessions s ON s.account_id=c.account_id "
                                        "WHERE c.id=ANY(%s) AND s.character_id=c.id AND s.expires_at>%s "
                                        "ORDER BY c.id",
                                        (rift_start_run["members"], STORE.now()),
                                    ).fetchall()
                                if {row["id"] for row in party_rows} != set(
                                    rift_start_run["members"]
                                ):
                                    raise ValueError(
                                        "Frozen rift party has a stale selected session"
                                    )
                                for member in party_rows:
                                    if member["id"] == character["id"]:
                                        continue
                                    member_character = STORE.character(
                                        member["account_id"], member["id"]
                                    )
                                    member_session = COMBAT_SESSIONS.session(
                                        member["account_id"],
                                        member["generation"],
                                        member_character,
                                    )
                                    COMBAT_SESSIONS.join(
                                        member_session,
                                        struct.pack(">qB", character["id"], 0),
                                        COMBAT_SESSIONS.player_actor(
                                            member_session, team=0
                                        ),
                                        expected_fight_id=candidate.id,
                                    )
                                candidate = shared_rift.fight
                                with STORE.connection() as rift_db:
                                    rift_runtime.start(
                                        rift_db,
                                        rift_start_run["instance_id"],
                                        character["id"],
                                        candidate.id,
                                    )
                                    rift_runtime.bind_wave(
                                        rift_db,
                                        rift_start_run["instance_id"],
                                        rift_start_run["wave"],
                                        [
                                            (monster["id"], monster["ref"])
                                            for monster in TEST_MONSTERS
                                        ],
                                    )
                                send(
                                    connection,
                                    service,
                                    12608,
                                    spawn_group(TEST_MONSTERS, group_id=candidate.id),
                                )
                        fight = candidate
                        publish_external_marker(
                            COMBAT_SESSIONS.registry.lookup(candidate.id)
                        )
                        placement_deadline.start(
                            fight.id, placement_duration, fight_started_at
                        )
                        send(
                            connection,
                            service,
                            12436,
                            health.packet(character["id"], character["hp"], 0),
                        )
                        for m in TEST_MONSTERS:
                            send(
                                connection,
                                service,
                                13249,
                                struct.pack(">qiih", m["id"], m["x"], m["y"], m["z"]),
                            )
                        for message_id, payload in packets:
                            send(connection, service, message_id, payload)
                        from wakfu_server.combat_initialization_policy import (
                            warning_text,
                        )

                        for warning in initialization_warnings:
                            record(
                                event="combat_initialization_effect_skipped",
                                fight_id=fight.id,
                                development_fallback=True,
                                **warning,
                            )
                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"),
                                    warning_text(warning),
                                ),
                            )
                        record(
                            event="combat_test_placement_started",
                            actor_id=character["id"],
                            fight_id=fight.id,
                        )
                    except ValueError as error:
                        if fight is None:
                            combat_session = None
                        if fight is None and group_lease is not None:
                            release_groups(generation)
                            group_lease = None
                        if fight is None and durable_fight_id is not None:
                            from wakfu_server.fight_store import abort
                            from wakfu_server.maps.dungeon_fight_binding import (
                                abort_room_encounter,
                            )

                            abort(
                                STORE,
                                account_id,
                                character["id"],
                                durable_fight_id,
                                on_aborted=(
                                    abort_room_encounter
                                    if DUNGEON_ROOM_RUNTIME_AVAILABLE
                                    and rift_start_run is None
                                    else None
                                ),
                            )
                            if rift_start_run is not None:
                                COMBAT_SESSIONS.registry.retire_unpublished_rift(
                                    durable_fight_id
                                )
                        record(
                            event="combat_test_attack_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                    except Exception:
                        # Durable identity may exist before bootstrap produces a Fight.
                        if fight is None:
                            combat_session = None
                        if fight is None and group_lease is not None:
                            release_groups(generation)
                            group_lease = None
                        if fight is None and durable_fight_id is not None:
                            from wakfu_server.fight_store import abort
                            from wakfu_server.maps.dungeon_fight_binding import (
                                abort_room_encounter,
                            )

                            abort(
                                STORE,
                                account_id,
                                character["id"],
                                durable_fight_id,
                                on_aborted=(
                                    abort_room_encounter
                                    if DUNGEON_ROOM_RUNTIME_AVAILABLE
                                    and rift_start_run is None
                                    else None
                                ),
                            )
                            if rift_start_run is not None:
                                COMBAT_SESSIONS.registry.retire_unpublished_rift(
                                    durable_fight_id
                                )
                        raise
                elif opcode == 12806 and fight is not None:
                    from wakfu_server.combat_bootstrap import placement_positions

                    actor_id, x, y, z = struct.unpack(">qiih", body)
                    try:
                        if combat_session is not None:
                            from wakfu_server.combat_shared import Transition

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                actor_id,
                                lambda candidate, runtime: (
                                    candidate.place(account_id, actor_id, (x, y, z)),
                                    Transition(
                                        candidate,
                                        runtime,
                                        ((13652, placement_positions(candidate)),),
                                    ),
                                )[1],
                                require_turn=False,
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                        else:
                            fight.place(account_id, actor_id, (x, y, z))
                            send(
                                connection,
                                service,
                                13652,
                                placement_positions(fight),
                            )
                    except ValueError as error:
                        record(
                            event="combat_test_placement_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                elif opcode == 12523 and fight is not None:
                    try:
                        if len(body) != 1 or body[0] not in (0, 1):
                            raise ValueError("Invalid placement readiness")
                        apply_readiness(bool(body[0]))
                    except ValueError as error:
                        record(
                            event="combat_test_ready_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                elif opcode == 13260 and fight_messages is not None:
                    from wakfu_server.combat_cast import decode_cast
                    from wakfu_server.combat_execute import execute_adjacent_cast
                    from wakfu_server.combat_wire import actor_state
                    from wakfu_server.combat_death import death_messages
                    from wakfu_server.combat_results import finish_messages
                    from wakfu_server.spells import default_deck

                    cast_request = {}
                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition
                        from wakfu_server.combat_cast import decode_cast
                        from wakfu_server.combat_server_spell import (
                            prepare_server_spell,
                        )
                        from wakfu_server.combat_spell_commit import (
                            commit_spell_transaction,
                        )
                        from wakfu_server.combat_los import authoritative_visible
                        from wakfu_server.combat_death import death_messages

                        try:
                            cast_request = decode_cast(body)
                            shared = refresh_shared_combat()
                            if shared.runtime is None:
                                raise ValueError("Fight is not ready for actions")
                            if shared.runtime.awaiting_ack is not None:
                                raise ValueError("Previous turn is not synchronized")
                            action_results = {}

                            def shared_cast(candidate, runtime):
                                characters, decks = COMBAT_SESSIONS.player_sources(
                                    candidate
                                )
                                from wakfu_server.combat_cast_delivery_source import (
                                    connected_cast_source,
                                )

                                source, owner_deck = connected_cast_source(
                                    characters,
                                    decks,
                                    character["id"],
                                    combat_session.account_id,
                                )
                                transaction = prepare_server_spell(
                                    body,
                                    source,
                                    TEST_MONSTERS_BY_ID,
                                    candidate,
                                    combat_session.account_id,
                                    owner_deck,
                                    action_id=runtime.action_id + 1,
                                    critical=None
                                    if COMBAT_TEST_CRITICAL_BRANCH == "auto"
                                    else COMBAT_TEST_CRITICAL_BRANCH == "critical",
                                    line_of_sight=lambda origin, target, state: authoritative_visible(
                                        source["map_id"],
                                        origin,
                                        target,
                                        state,
                                        blocking_footprints={
                                            actor.id: {actor.position[:2]}
                                            for actor in state.actors.values()
                                            if actor.hp > 0
                                        },
                                    ),
                                    player_characters=characters,
                                    deck_blobs=decks,
                                )
                                delivery = commit_spell_transaction(
                                    runtime,
                                    transaction,
                                    stats_serializer=lambda actor, state: current_combat_stats(
                                        actor, state
                                    ),
                                    diagnostic=lambda **details: record(
                                        event="combat_commit_stage", **details
                                    ),
                                )
                                packets = list(delivery)
                                for event in transaction.events:
                                    if event["kind"] == "death":
                                        packets.extend(
                                            runtime.prepare_delivery(
                                                death_messages(
                                                    runtime, event["actor_id"]
                                                )
                                            )
                                        )
                                action_results["transaction"] = transaction
                                action_results["delivery"] = delivery
                                return Transition(
                                    transaction.fight, runtime, tuple(packets)
                                )

                            prepare_started = time.monotonic()
                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                cast_request["actor_id"],
                                shared_cast,
                            )
                            prepare_finished = time.monotonic()
                            refresh_shared_combat()
                            drain_shared_combat()
                            transaction = action_results["transaction"]
                            delivery = action_results["delivery"]
                            checkpoint_fight()
                            record(
                                event="combat_cast",
                                native_actions=getattr(delivery, "native_actions", ()),
                                dispatch_ms=round(
                                    (prepare_started - request_received_at) * 1000, 3
                                ),
                                prepare_ms=round(
                                    (prepare_finished - prepare_started) * 1000, 3
                                ),
                                actor_id=transaction.plan["actor_id"],
                                spell_id=transaction.plan["spell_id"],
                                cast_diagnostics=transaction.plan.get(
                                    "cast_diagnostics"
                                ),
                                native_casting_selection=transaction.plan.get(
                                    "native_casting_selection"
                                ),
                                native_casting_flags=transaction.plan.get(
                                    "native_casting_flags"
                                ),
                                native_casting_diagnostic=transaction.plan.get(
                                    "native_casting_diagnostic"
                                ),
                                critical_decision=transaction.plan.get(
                                    "critical_decision"
                                ),
                                costs=transaction.plan["costs"],
                                outcomes=transaction.outcomes,
                            )
                            if fight.phase == "finished":
                                complete_test_fight()
                        except ValueError as error:
                            record(
                                event="combat_cast_rejected",
                                actor_id=cast_request.get("actor_id"),
                                spell_uid=cast_request.get("spell_uid"),
                                target=cast_request.get("target"),
                                cast_diagnostics=getattr(
                                    error, "cast_diagnostics", None
                                ),
                                native_casting_result=getattr(
                                    error, "native_casting_result", None
                                ),
                                native_casting_diagnostic=getattr(
                                    error, "native_casting_diagnostic", None
                                ),
                                cast_validation_code=getattr(
                                    error, "cast_validation_code", None
                                ),
                                reason=str(error),
                            )
                            from wakfu_server.combat_initialization_policy import (
                                safe_rejection_text,
                            )

                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"),
                                    safe_rejection_text(error),
                                ),
                            )
                        continue
                    try:
                        cast_request = decode_cast(body)
                        if fight_messages.awaiting_ack is not None:
                            raise ValueError("Previous turn is not synchronized")
                        deck_hex = character["builds"].get(0, {}).get("deck")
                        from wakfu_server.combat_server_spell import (
                            prepare_server_spell,
                        )
                        from wakfu_server.combat_spell_commit import (
                            commit_spell_transaction,
                        )
                        from wakfu_server.combat_los import authoritative_visible

                        cast_prepare_started = time.monotonic()
                        transaction = prepare_server_spell(
                            body,
                            character,
                            TEST_MONSTERS_BY_ID,
                            fight,
                            account_id,
                            bytes.fromhex(deck_hex)
                            if deck_hex
                            else default_deck(character),
                            action_id=fight_messages.action_id + 1,
                            critical=None
                            if COMBAT_TEST_CRITICAL_BRANCH == "auto"
                            else COMBAT_TEST_CRITICAL_BRANCH == "critical",
                            line_of_sight=lambda source, target, state: authoritative_visible(
                                character["map_id"],
                                source,
                                target,
                                state,
                                blocking_footprints={
                                    a.id: {a.position[:2]}
                                    for a in state.actors.values()
                                    if a.hp > 0
                                },
                            ),
                        )
                        cast_prepare_finished = time.monotonic()
                        packets = commit_spell_transaction(
                            fight_messages,
                            transaction,
                            stats_serializer=lambda actor, state: current_combat_stats(
                                actor, state
                            ),
                            diagnostic=lambda **details: record(
                                event="combat_commit_stage", **details
                            ),
                        )
                        cast_commit_finished = time.monotonic()
                        fight = transaction.fight
                        for message_id, payload in packets:
                            send(connection, service, message_id, payload)
                        record(
                            event="combat_cast",
                            native_actions=packets.native_actions,
                            dispatch_ms=round(
                                (cast_prepare_started - request_received_at) * 1000, 3
                            ),
                            prepare_ms=round(
                                (cast_prepare_finished - cast_prepare_started) * 1000, 3
                            ),
                            commit_ms=round(
                                (cast_commit_finished - cast_prepare_finished) * 1000, 3
                            ),
                            send_ms=round(
                                (time.monotonic() - cast_commit_finished) * 1000, 3
                            ),
                            actor_id=character["id"],
                            spell_id=transaction.plan["spell_id"],
                            cast_diagnostics=transaction.plan.get("cast_diagnostics"),
                            native_casting_selection=transaction.plan.get(
                                "native_casting_selection"
                            ),
                            native_casting_flags=transaction.plan.get(
                                "native_casting_flags"
                            ),
                            native_casting_diagnostic=transaction.plan.get(
                                "native_casting_diagnostic"
                            ),
                            critical_decision=transaction.plan.get("critical_decision"),
                            costs=transaction.plan["costs"],
                            resources_before={
                                "ap": transaction.source_state["actors"][
                                    str(transaction.plan["actor_id"])
                                ]["ap"],
                                "mp": transaction.source_state["actors"][
                                    str(transaction.plan["actor_id"])
                                ]["mp"],
                                "wp": transaction.source_state["actors"][
                                    str(transaction.plan["actor_id"])
                                ]["effect_stats"].get("4"),
                            },
                            resources_after={
                                "ap": fight.actors[transaction.plan["actor_id"]].ap,
                                "mp": fight.actors[transaction.plan["actor_id"]].mp,
                                "wp": fight.actors[
                                    transaction.plan["actor_id"]
                                ].effect_stats.get(4),
                            },
                            outcomes=transaction.outcomes,
                        )
                        result = {"events": transaction.events}
                        for event in result["events"]:
                            if event["kind"] == "death":
                                for (
                                    message_id,
                                    payload,
                                ) in fight_messages.prepare_delivery(
                                    death_messages(fight_messages, event["actor_id"])
                                ):
                                    send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                    except ValueError as error:
                        record(
                            event="combat_cast_rejected",
                            actor_id=character["id"],
                            spell_uid=cast_request.get("spell_uid"),
                            target=cast_request.get("target"),
                            cast_diagnostics=getattr(error, "cast_diagnostics", None),
                            native_casting_result=getattr(
                                error, "native_casting_result", None
                            ),
                            native_casting_diagnostic=getattr(
                                error, "native_casting_diagnostic", None
                            ),
                            cast_validation_code=getattr(
                                error, "cast_validation_code", None
                            ),
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                elif opcode == 12889 and fight_messages is not None:
                    from wakfu_server.combat_melee import prepare_server_unarmed
                    from wakfu_server.combat_wire import actor_state
                    from wakfu_server.combat_death import death_messages
                    from wakfu_server.combat_weapon import (
                        decode_request,
                        prepare_server_weapon,
                    )

                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition
                        from wakfu_server.combat_spell_commit import (
                            commit_spell_transaction,
                        )
                        from wakfu_server.combat_los import authoritative_visible
                        from wakfu_server.combat_death import death_messages
                        from wakfu_server.spells import default_deck

                        try:
                            request = decode_request(body)
                            action_results = {}

                            def shared_weapon(candidate, runtime):
                                if runtime.awaiting_ack is not None:
                                    raise ValueError(
                                        "Previous turn is not synchronized"
                                    )
                                characters, decks = COMBAT_SESSIONS.player_sources(
                                    candidate
                                )
                                actor_id = request["actor_id"]
                                source = characters.get(actor_id)
                                if source is None:
                                    raise ValueError(
                                        "Weapon actor has no owner snapshot"
                                    )
                                if request["item_uid"] == -1:
                                    from wakfu_server.equipment import validate_sheet
                                    from wakfu_server.combat_melee import (
                                        prepare_server_unarmed,
                                    )

                                    selected = source["builds"].get(
                                        source.get("active_build_index", 0), {}
                                    )
                                    if any(
                                        row["slot"] == 15
                                        for row in validate_sheet(
                                            source,
                                            bytes.fromhex(
                                                selected.get("equipment", "")
                                            ),
                                        )
                                    ):
                                        raise ValueError(
                                            "Unarmed action requires the owned weapon slot to be empty"
                                        )
                                    wp_current, wp_maximum = live_wp(
                                        candidate, actor_id
                                    )
                                    transaction = prepare_server_unarmed(
                                        body,
                                        source,
                                        TEST_MONSTERS_BY_ID,
                                        candidate,
                                        combat_session.account_id,
                                        unarmed=True,
                                        wp_current=wp_current,
                                        wp_maximum=wp_maximum,
                                        action_id=runtime.action_id + 1,
                                        effect_uid=secrets.randbelow(2**60) + 1,
                                        critical_chance=0,
                                        caster_running_effects=(),
                                        target_running_effects=(),
                                        caster_bonuses={},
                                        target_bonuses={},
                                        mitigate=lambda damage, element, source, target, state: damage,
                                        player_characters=characters,
                                        deck_blobs=decks,
                                    )
                                else:
                                    transaction = prepare_server_weapon(
                                        body,
                                        source,
                                        TEST_MONSTERS_BY_ID,
                                        candidate,
                                        combat_session.account_id,
                                        decks[actor_id],
                                        action_id=runtime.action_id + 1,
                                        critical=None
                                        if COMBAT_TEST_CRITICAL_BRANCH == "auto"
                                        else COMBAT_TEST_CRITICAL_BRANCH == "critical",
                                        line_of_sight=lambda origin, target, state: authoritative_visible(
                                            source["map_id"],
                                            origin,
                                            target,
                                            state,
                                            blocking_footprints={
                                                actor.id: {actor.position[:2]}
                                                for actor in state.actors.values()
                                                if actor.hp > 0
                                            },
                                        ),
                                        player_characters=characters,
                                        deck_blobs=decks,
                                    )
                                delivery = commit_spell_transaction(
                                    runtime,
                                    transaction,
                                    stats_serializer=lambda actor, state: current_combat_stats(
                                        actor, state
                                    ),
                                    diagnostic=lambda **details: record(
                                        event="combat_commit_stage", **details
                                    ),
                                )
                                packets = list(delivery)
                                for event in transaction.events:
                                    if event["kind"] == "death":
                                        packets.extend(
                                            runtime.prepare_delivery(
                                                death_messages(
                                                    runtime, event["actor_id"]
                                                )
                                            )
                                        )
                                action_results["transaction"] = transaction
                                action_results["delivery"] = delivery
                                return Transition(
                                    transaction.fight, runtime, tuple(packets)
                                )

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                request["actor_id"],
                                shared_weapon,
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                            checkpoint_fight()
                            transaction = action_results["transaction"]
                            record(
                                event="combat_melee",
                                native_actions=getattr(
                                    action_results["delivery"], "native_actions", ()
                                ),
                                actor_id=request["actor_id"],
                                outcomes=transaction.outcomes,
                            )
                            if fight.phase == "finished":
                                complete_test_fight()
                        except ValueError as error:
                            record(
                                event="combat_melee_rejected",
                                actor_id=character["id"],
                                item_uid=request.get("item_uid")
                                if "request" in locals()
                                else None,
                                reason=str(error),
                            )
                            from wakfu_server.combat_initialization_policy import (
                                safe_rejection_text,
                            )

                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"),
                                    safe_rejection_text(error),
                                ),
                            )
                        continue

                    try:
                        if fight_messages.awaiting_ack is not None:
                            raise ValueError("Previous turn is not synchronized")
                        from wakfu_server.combat_spell_commit import (
                            commit_spell_transaction,
                        )
                        from wakfu_server.combat_los import authoritative_visible
                        from wakfu_server.spells import default_deck

                        request = decode_request(body)
                        record(event="combat_weapon_request", **request)
                        if request["item_uid"] == -1:
                            from wakfu_server.equipment import validate_sheet

                            selected = character["builds"].get(
                                character.get("active_build_index", 0), {}
                            )
                            if any(
                                row["slot"] == 15
                                for row in validate_sheet(
                                    character,
                                    bytes.fromhex(selected.get("equipment", "")),
                                )
                            ):
                                raise ValueError(
                                    "Unarmed action requires the owned weapon slot to be empty"
                                )
                            unarmed_prepare_started = time.monotonic()
                            transaction = prepare_server_unarmed(
                                body,
                                character,
                                TEST_MONSTERS_BY_ID,
                                fight,
                                account_id,
                                unarmed=True,
                                wp_current=live_wp(fight, character["id"])[0],
                                wp_maximum=live_wp(fight, character["id"])[1],
                                action_id=fight_messages.action_id + 1,
                                effect_uid=secrets.randbelow(2**60) + 1,
                                critical_chance=0,
                                caster_running_effects=(),
                                target_running_effects=(),
                                caster_bonuses={},
                                target_bonuses={},
                                mitigate=lambda damage, element, source, target, state: damage,
                            )
                            unarmed_prepare_finished = time.monotonic()
                            packets = commit_spell_transaction(
                                fight_messages,
                                transaction,
                                stats_serializer=lambda actor, state: current_combat_stats(
                                    actor, state
                                ),
                                diagnostic=lambda **details: record(
                                    event="combat_commit_stage", **details
                                ),
                            )
                            unarmed_commit_finished = time.monotonic()
                            fight = transaction.fight
                            for message_id, payload in packets:
                                send(connection, service, message_id, payload)
                                if message_id in (13509, 12613):
                                    (
                                        delivered_fight,
                                        delivered_action,
                                    ) = struct.unpack_from(">ii", payload)
                                    record(
                                        event="combat_melee_delivery",
                                        fight_id=delivered_fight,
                                        action_id=delivered_action,
                                        opcode=message_id,
                                        actor_id=character["id"],
                                        item_uid=request["item_uid"],
                                        target=request["target"],
                                    )
                            result = {"events": transaction.events, "damage": None}
                            record(
                                event="combat_unarmed",
                                actor_id=character["id"],
                                costs=transaction.plan["costs"],
                                prepare_ms=round(
                                    (unarmed_prepare_finished - unarmed_prepare_started)
                                    * 1000,
                                    3,
                                ),
                                commit_ms=round(
                                    (unarmed_commit_finished - unarmed_prepare_finished)
                                    * 1000,
                                    3,
                                ),
                                send_ms=round(
                                    (time.monotonic() - unarmed_commit_finished) * 1000,
                                    3,
                                ),
                            )
                        else:
                            deck_hex = character["builds"].get(0, {}).get("deck")
                            weapon_prepare_started = time.monotonic()
                            transaction = prepare_server_weapon(
                                body,
                                character,
                                TEST_MONSTERS_BY_ID,
                                fight,
                                account_id,
                                bytes.fromhex(deck_hex)
                                if deck_hex
                                else default_deck(character),
                                action_id=fight_messages.action_id + 1,
                                critical=None
                                if COMBAT_TEST_CRITICAL_BRANCH == "auto"
                                else COMBAT_TEST_CRITICAL_BRANCH == "critical",
                                line_of_sight=lambda source, target, state: authoritative_visible(
                                    character["map_id"],
                                    source,
                                    target,
                                    state,
                                    blocking_footprints={
                                        a.id: {a.position[:2]}
                                        for a in state.actors.values()
                                        if a.hp > 0
                                    },
                                ),
                            )
                            weapon_prepare_finished = time.monotonic()
                            packets = commit_spell_transaction(
                                fight_messages,
                                transaction,
                                stats_serializer=lambda actor, state: current_combat_stats(
                                    actor, state
                                ),
                                diagnostic=lambda **details: record(
                                    event="combat_commit_stage", **details
                                ),
                            )
                            weapon_commit_finished = time.monotonic()
                            fight = transaction.fight
                            for message_id, payload in packets:
                                send(connection, service, message_id, payload)
                            result = {"events": transaction.events, "damage": None}
                            record(
                                event="combat_weapon",
                                actor_id=character["id"],
                                item_uid=request["item_uid"],
                                slot=request["slot"],
                                target=request["target"],
                                item_reference=transaction.plan["item_reference"],
                                item_level=transaction.plan["evaluation_level"],
                                critical_decision=transaction.plan.get(
                                    "critical_decision"
                                ),
                                costs=transaction.plan["costs"],
                                prepare_ms=round(
                                    (weapon_prepare_finished - weapon_prepare_started)
                                    * 1000,
                                    3,
                                ),
                                commit_ms=round(
                                    (weapon_commit_finished - weapon_prepare_finished)
                                    * 1000,
                                    3,
                                ),
                                send_ms=round(
                                    (time.monotonic() - weapon_commit_finished) * 1000,
                                    3,
                                ),
                                outcomes=transaction.outcomes,
                            )
                        record(
                            event="combat_melee",
                            native_actions=packets.native_actions,
                            actor_id=character["id"],
                            damage=result["damage"],
                        )
                        for event in result["events"]:
                            if event["kind"] == "death":
                                for (
                                    message_id,
                                    payload,
                                ) in fight_messages.prepare_delivery(
                                    death_messages(fight_messages, event["actor_id"])
                                ):
                                    send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                    except ValueError as error:
                        try:
                            rejected_weapon = decode_request(body)
                        except ValueError:
                            rejected_weapon = {}
                        record(
                            event="combat_melee_rejected",
                            item_uid=rejected_weapon.get("item_uid"),
                            slot=rejected_weapon.get("slot"),
                            target=rejected_weapon.get("target"),
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                elif opcode == 13952 and loaded:
                    from wakfu_server.combat_abandon import (
                        prepare as prepare_abandon,
                        placement_runtime,
                    )

                    try:
                        if combat_session is not None:
                            if body != b"":
                                raise ValueError("Invalid native abandon request")
                            shared = refresh_shared_combat()
                            if shared.fight.phase == "finished":
                                # Retry the original terminal settlement;
                                # a finished victory must not become defeat.
                                complete_test_fight()
                            elif getattr(shared, "is_duel", False):
                                if not COMBAT_SESSIONS.registry.forfeit_duel(
                                    combat_session, reason="defeat"
                                ):
                                    raise ValueError(
                                        "Friendly duel can no longer be forfeited"
                                    )
                                refresh_shared_combat()
                                complete_test_fight()
                                record(
                                    event="friendly_duel_forfeited",
                                    actor_id=character["id"],
                                    fight_id=fight.id,
                                )
                            else:
                                active_owners = set(shared.participants) - set(
                                    shared.withdrawals
                                )
                                if len(active_owners) > 1:
                                    pve_withdrawal_pending = (
                                        COMBAT_SESSIONS.withdraw_pve(
                                            combat_session, character, body
                                        )
                                    )
                                    character.update(
                                        pve_withdrawal_pending["character"]
                                    )
                                    for packet in pve_withdrawal_pending[
                                        "withdrawal"
                                    ].private_packets:
                                        send(connection, service, *packet)
                                    record(
                                        event="shared_pve_member_withdrawn",
                                        actor_id=character["id"],
                                        fight_id=fight.id,
                                    )
                                    # Private native continuation is independent of the live
                                    # encounter. This socket must not tick, abort or release it.
                                    fight = fight_messages = None
                                    combat_session = group_lease = None
                                    loaded = False
                                    continue
                                abandon_messages = placement_runtime(
                                    fight, shared.runtime
                                )
                                with shared.lock:
                                    # Snapshot/readiness/turn transitions share
                                    # this lock; publish abandon only after its
                                    # HP and terminal state are committed.
                                    abandoned = prepare_abandon(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        abandon_messages,
                                        body,
                                    )
                                    fight_messages = shared.runtime = abandon_messages
                                    character.update(abandoned["character"])
                                    if abandoned["applied"]:
                                        checkpoint_fight("aborted")
                                for (
                                    message_id,
                                    payload,
                                ) in fight_messages.prepare_delivery(
                                    abandoned["packets"]
                                ):
                                    send(connection, service, message_id, payload)
                                publish_external_marker(shared)
                                publish_spectator_state(shared, abandoned["packets"])
                                record(
                                    event="shared_pve_abandoned_waiting_return",
                                    actor_id=character["id"],
                                    fight_id=fight.id,
                                    applied=abandoned["applied"],
                                )
                            continue
                        abandon_messages = placement_runtime(fight, fight_messages)
                        abandoned = prepare_abandon(
                            STORE,
                            account_id,
                            generation,
                            character,
                            abandon_messages,
                            body,
                        )
                        fight_messages = abandon_messages
                        character.update(abandoned["character"])
                        if abandoned["applied"]:
                            checkpoint_fight("aborted")
                        for message_id, payload in fight_messages.prepare_delivery(
                            abandoned["packets"]
                        ):
                            send(connection, service, message_id, payload)
                        record(
                            event="combat_abandoned_waiting_return",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            applied=abandoned["applied"],
                        )
                    except ValueError as error:
                        record(
                            event="combat_abandon_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                elif opcode == 12925 and pve_withdrawal_pending is not None:
                    try:
                        pending = pve_withdrawal_pending
                        owner = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        returned = COMBAT_SESSIONS.return_withdrawn_pve(
                            owner,
                            pending["withdrawal"].fight.id,
                            character,
                            body,
                            wp=COMBAT_TEST_WP,
                            pending=pending,
                        )
                        character.update(returned["character"])
                        for packet in returned["packets"]:
                            send(connection, service, *packet)
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        WORLD.leave(character["id"], generation)
                        for packet in owned_native_bootstrap(character):
                            send(connection, service, *packet)
                        join_world(generation, connection, character)
                        loaded = True
                        mark_static_sync_pending()
                        pve_withdrawal_pending = None
                        record(
                            event="shared_pve_withdrawal_returned",
                            actor_id=character["id"],
                            fight_id=pending["withdrawal"].fight.id,
                        )
                    except ValueError as error:
                        record(
                            event="shared_pve_withdrawal_return_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif (
                    opcode == 12925
                    and loaded
                    and spectator_terminal_pending is not None
                ):
                    try:
                        pending_ack = spectator_terminal_pending
                        current_observer = spectator_session_for_current_character()
                        if not STORE.current_session(account_id, generation) or (
                            current_observer != pending_ack.session
                            or fight is not None
                            or combat_session is not None
                        ):
                            raise ValueError(
                                "Spectator terminal ACK has a stale session"
                            )
                        pending_ack.validate(current_observer, body)
                        refresh_owned_world_after_spectating()
                        spectator_terminal_pending = None
                        record(
                            event="combat_spectator_terminal_returned",
                            actor_id=character["id"],
                            fight_id=pending_ack.fight_id,
                            native_return_ack=True,
                            world_refreshed=True,
                        )
                    except ValueError as error:
                        record(
                            event="combat_spectator_terminal_return_rejected",
                            actor_id=None if character is None else character["id"],
                            fight_id=(
                                spectator_terminal_pending.fight_id
                                if spectator_terminal_pending is not None
                                else None
                            ),
                            reason=str(error),
                        )
                elif opcode == 12925 and fight_messages is not None:
                    from wakfu_server.combat_lifecycle import return_to_world
                    from wakfu_server.combat_death import despawn_monster

                    try:
                        shared_return = combat_session is not None
                        duel_return = False
                        abandoned = (
                            getattr(fight_messages, "abandon_owner", None) is not None
                        )
                        if shared_return:
                            refresh_shared_combat()
                            shared_state = COMBAT_SESSIONS.registry.lookup(fight.id)
                            if abandoned:
                                if (
                                    getattr(shared_state, "is_duel", False)
                                    or len(
                                        set(shared_state.participants)
                                        - set(shared_state.withdrawals)
                                    )
                                    != 1
                                    or shared_state.participants.get(account_id)
                                    != combat_session
                                    or shared_state.settlement_ready
                                ):
                                    raise ValueError(
                                        "Only a single-owner PvE fight can use abandon return"
                                    )
                            elif not shared_state.settlement_ready:
                                raise ValueError(
                                    "Shared fight settlement is not ready for return"
                                )
                        if abandoned:
                            from wakfu_server.combat_abandon import (
                                return_to_world as return_abandon,
                            )

                            if shared_return:
                                with shared_state.lock:
                                    returned = return_abandon(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        fight_messages,
                                        body,
                                        wp=COMBAT_TEST_WP,
                                    )
                            else:
                                returned = return_abandon(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    fight_messages,
                                    body,
                                    wp=COMBAT_TEST_WP,
                                )
                        else:
                            if fight.phase != "finished" or fight.winner not in (0, 1):
                                raise ValueError(
                                    "Normal return requires a resolved fight outcome"
                                )
                            duel_return = bool(
                                shared_return
                                and getattr(shared_state, "is_duel", False)
                            )
                            if duel_return:
                                from wakfu_server.friendly_duels import (
                                    return_packets as duel_return_packets,
                                )

                                returned = duel_return_packets(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    fight,
                                    body,
                                    wp=COMBAT_TEST_WP,
                                )
                            else:
                                returned = return_to_world(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    fight_messages,
                                    body,
                                    wp=COMBAT_TEST_WP,
                                )
                        character.update(returned["character"])
                        for message_id, payload in returned["packets"]:
                            send(connection, service, message_id, payload)
                        if not abandoned and not duel_return:
                            from wakfu_server.combat_death import dead_world_removals

                            for packet in dead_world_removals(
                                fight, [m["id"] for m in TEST_MONSTERS]
                            ):
                                send(connection, service, *packet)
                            record(
                                event="dead_monsters_removed_from_world",
                                fight_id=fight.id,
                                actor_ids=[
                                    m["id"]
                                    for m in TEST_MONSTERS
                                    if fight.actors[m["id"]].hp == 0
                                ],
                            )
                        # This callback follows native aUH cleanup. Restore the
                        # actual owned map, not an inherited fight/report state.
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        WORLD.leave(character["id"], generation)
                        for message_id, payload in owned_native_bootstrap(character):
                            send(connection, service, message_id, payload)
                        from wakfu_server.combat_monster_world import spawn_group

                        if group_lease is not None and (not shared_return or abandoned):
                            with COMBAT_GROUPS.lock:
                                defeated = (
                                    not abandoned
                                    and fight.winner
                                    == fight.actors[character["id"]].team
                                )
                                restored = COMBAT_GROUPS.finish(
                                    group_lease, defeated=defeated
                                )
                                if restored and not defeated:
                                    map_id, instance_id, group_id = group_lease[0]
                                    WORLD.emit_location(
                                        map_id,
                                        instance_id,
                                        12608,
                                        spawn_group(TEST_MONSTERS, group_id=group_id),
                                        exclude_generation=generation,
                                    )
                                    for packet in HARVESTS.availability_for(
                                        map_id,
                                        instance_id,
                                        [m["id"] for m in TEST_MONSTERS],
                                    ):
                                        WORLD.emit_location(
                                            map_id,
                                            instance_id,
                                            *packet,
                                            exclude_generation=generation,
                                        )
                        join_world(generation, connection, character)
                        mark_static_sync_pending()
                        if shared_return and abandoned:
                            if not COMBAT_SESSIONS.registry.retire_abandoned_single_owner(
                                fight.id, combat_session
                            ):
                                raise ValueError(
                                    "Shared PvE abandon was not safely retired"
                                )
                        elif shared_return:
                            # Persist the terminal checkpoint while the shared
                            # registry entry still exists. mark_returned may
                            # retire it when this is the last owner.
                            checkpoint_fight("ended")
                            COMBAT_SESSIONS.mark_returned(combat_session, fight.id)
                            COMBAT_SESSIONS.disconnect(combat_session)
                        else:
                            checkpoint_fight("aborted" if abandoned else "ended")
                        record(
                            event="combat_return_to_world",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            abandoned=abandoned,
                        )
                        group_lease = None
                        fight = fight_messages = None
                        combat_session = None
                    except ValueError as error:
                        record(
                            event="combat_return_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13655 and fight is None and loaded:
                    from wakfu_server.combat_orientation import decode_request
                    from wakfu_server.world_orientation import save as save_orientation

                    try:
                        actor_id, direction = decode_request(body)
                        if actor_id != character["id"]:
                            raise ValueError(
                                "Orientation actor is not the selected character"
                            )
                        POSITIONS.flush(
                            account_id=account_id,
                            generation=generation,
                            character_id=actor_id,
                        )
                        changed = save_orientation(
                            STORE,
                            account_id,
                            generation,
                            actor_id,
                            direction,
                            outside=True,
                        )
                        character = dict(character, direction=changed["direction"])
                        POSITIONS.attach(account_id, generation, character)
                        WORLD.update(generation, character, *changed["packet"])
                        record(
                            event="world_orientation",
                            actor_id=actor_id,
                            direction=direction,
                        )
                    except ValueError as error:
                        record(
                            event="world_orientation_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13655 and fight is not None:
                    from wakfu_server.combat_orientation import apply as orient_actor
                    from wakfu_server.combat_abandon import placement_runtime

                    try:
                        orientation_runtime = placement_runtime(fight, fight_messages)
                        oriented = orient_actor(orientation_runtime, account_id, body)
                        fight_messages = orientation_runtime
                        for message_id, payload in fight_messages.prepare_delivery(
                            oriented["packets"]
                        ):
                            send(connection, service, message_id, payload)
                        checkpoint_fight()
                        # Combat keeps its sequenced action. World observers need
                        # the distinct ctz event and persisted world snapshot.
                        actor_id, _ = struct.unpack(">qB", body)
                        if actor_id == character["id"]:
                            from wakfu_server.world_orientation import (
                                save as save_orientation,
                            )

                            try:
                                POSITIONS.flush(
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=actor_id,
                                )
                                changed = save_orientation(
                                    STORE,
                                    account_id,
                                    generation,
                                    actor_id,
                                    oriented["direction"],
                                )
                                character = dict(
                                    character, direction=changed["direction"]
                                )
                                POSITIONS.attach(account_id, generation, character)
                                WORLD.update(
                                    generation,
                                    character,
                                    *changed["packet"],
                                    include_sender=False,
                                )
                            except ValueError as error:
                                record(
                                    event="world_orientation_rejected",
                                    actor_id=actor_id,
                                    reason=str(error),
                                )
                        record(
                            event="combat_orientation",
                            actor_id=character["id"],
                            direction=oriented["direction"],
                        )
                    except ValueError as error:
                        record(
                            event="combat_orientation_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12161 and fight_messages is not None:
                    from wakfu_server.combat_movement_runtime import apply_client
                    from wakfu_server.combat_actor import actual_actor_stats

                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition

                        try:
                            movement_result = {}

                            def shared_move(candidate, runtime):
                                characters, decks = COMBAT_SESSIONS.player_sources(
                                    candidate
                                )
                                source = characters.get(combat_session.character_id)
                                if source is None:
                                    raise ValueError(
                                        "Movement actor has no owner snapshot"
                                    )
                                packets, event = apply_client(
                                    runtime,
                                    combat_session.account_id,
                                    body,
                                    current_combat_stats,
                                    runtime_stats_serializer=current_combat_stats,
                                    area_provider=area_movement_provider
                                    if os.environ.get(
                                        "WAKFU_NATIVE_AREA_CALLBACKS", "1"
                                    )
                                    == "1"
                                    else None,
                                )
                                packets = runtime.prepare_delivery(packets)
                                movement_result["event"] = event
                                return Transition(candidate, runtime, tuple(packets))

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                combat_session.character_id,
                                shared_move,
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                            checkpoint_fight()
                            record(
                                event="combat_movement",
                                actor_id=combat_session.character_id,
                                movement=movement_result.get("event"),
                            )
                        except ValueError as error:
                            record(
                                event="combat_movement_rejected",
                                actor_id=combat_session.character_id,
                                reason=str(error),
                            )
                        continue

                    try:
                        packets, event = apply_client(
                            fight_messages,
                            account_id,
                            body,
                            current_combat_stats,
                            runtime_stats_serializer=current_combat_stats,
                            area_provider=area_movement_provider
                            if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
                            else None,
                        )
                        packets = fight_messages.prepare_delivery(packets)
                        for message_id, payload in packets:
                            send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                        record(
                            event="combat_movement",
                            actor_id=character["id"],
                            movement=event,
                        )
                    except ValueError as error:
                        record(
                            event="combat_movement_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12403 and fight_messages is not None:
                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition

                        try:
                            actor_id, actor_turn = struct.unpack(">qh", body)

                            def shared_end_turn(candidate, runtime):
                                packets = runtime.end_turn(
                                    combat_session.account_id, actor_id, actor_turn
                                )
                                return Transition(candidate, runtime, tuple(packets))

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                actor_id,
                                shared_end_turn,
                            )
                            refresh_shared_combat()
                            if fight_messages.awaiting_ack is not None:
                                COMBAT_SESSIONS.registry.arm_ack(
                                    fight.id, fight_messages.awaiting_ack
                                )
                            drain_shared_combat()
                            checkpoint_fight()
                            if fight.phase == "finished":
                                complete_test_fight()
                        except ValueError as error:
                            record(
                                event="combat_test_end_turn_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                        continue
                    try:
                        actor_id, actor_turn = struct.unpack(">qh", body)
                        for message_id, payload in fight_messages.end_turn(
                            account_id, actor_id, actor_turn
                        ):
                            send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                    except ValueError as error:
                        record(
                            event="combat_test_end_turn_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        from wakfu_server.combat_initialization_policy import (
                            safe_rejection_text,
                        )

                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                safe_rejection_text(error),
                            ),
                        )
                        # Only an owned, still-active turn may be reannounced.
                        # Stale or foreign requests must not clear another
                        # actor's native synchronization barrier.
                        current = fight.current
                        if (
                            fight.phase == "active"
                            and current is not None
                            and current.controlled
                            and current.owner_id == account_id
                            and fight_messages.awaiting_ack is None
                        ):
                            for message_id, payload in fight_messages.recover(
                                account_id,
                                struct.pack(">i", fight.id),
                                now_ms=int(time.time() * 1000),
                            ):
                                send(connection, service, message_id, payload)
                            record(
                                event="combat_turn_rejection_recovered",
                                fight_id=fight.id,
                                actor_id=current.id,
                            )
                elif opcode == 13332 and fight_messages is not None:
                    try:
                        for message_id, payload in fight_messages.recover(
                            account_id, body, now_ms=int(time.time() * 1000)
                        ):
                            send(connection, service, message_id, payload)
                        record(
                            event="combat_timeline_recovered",
                            actor_id=character["id"],
                            fight_id=fight.id,
                        )
                        # Recovery supersedes the outstanding turn ACK. A
                        # server-controlled actor otherwise has no remaining
                        # packet that can trigger its bounded turn policy.
                        if fight.phase == "finished":
                            complete_test_fight()
                        else:
                            pass_test_monster_turn()
                    except ValueError as error:
                        record(
                            event="combat_recovery_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13510 and fight_messages is not None:
                    if combat_session is not None:
                        try:
                            released = COMBAT_SESSIONS.acknowledge(
                                combat_session,
                                fight.id,
                                body,
                                lambda candidate, runtime, ack_body: runtime.acknowledge_turn(
                                    ack_body
                                ),
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                            if released:
                                checkpoint_fight()
                                if fight.phase == "finished":
                                    complete_test_fight()
                                else:
                                    pass_test_monster_turn()
                        except ValueError as error:
                            record(
                                event="combat_test_turn_ack_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                        continue
                    try:
                        for message_id, payload in fight_messages.acknowledge_turn(
                            body
                        ):
                            send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                        else:
                            pass_test_monster_turn()
                    except ValueError as error:
                        record(
                            event="combat_test_turn_ack_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13571 and loaded:
                    from wakfu_server.characters.captured_roster_selection import select
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    try:
                        selected_record = {}
                        if combat_session is not None:
                            from wakfu_server.combat_shared import Transition

                            def shared_select(candidate, runtime):
                                selected_record.update(
                                    select(
                                        STORE,
                                        account_id,
                                        character,
                                        body,
                                        fight=candidate,
                                    )
                                )
                                return Transition(candidate, runtime, ())

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                combat_session.character_id,
                                shared_select,
                                require_turn=False,
                            )
                            refresh_shared_combat()
                            checkpoint_fight()
                        else:
                            selected_record = select(
                                STORE, account_id, character, body, fight=fight
                            )
                            if fight is not None:
                                checkpoint_fight()
                        character["captured_roster"] = selected_record
                        record(
                            event="symbiot_selection",
                            actor_id=character["id"],
                            slot=selected_record["selected_slot"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        record(
                            event="symbiot_selection_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 14689 and loaded:
                    if not sync_loaded_world_snapshot(force=True):
                        sync_static_world()
                    record(
                        event="transport_objects_initialized",
                        actor_id=character["id"],
                        map_id=character["map_id"],
                    )
                elif opcode == 13787 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.shard_identification import identify
                    from wakfu_server.shard_identification_wire import response
                    from wakfu_server.inventory_move import reload_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None:
                            raise ValueError(
                                "No puedes identificar objetos durante un combate."
                            )
                        result = identify(
                            STORE, account_id, generation, character["id"], body
                        )
                        character = reload_inventory(STORE, account_id, character)
                        send(connection, service, *response(result))
                        if result["cost_kamas"] > 0 and result["status"] == 0:
                            with STORE.connection() as db:
                                balance = db.execute(
                                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                                    (account_id,),
                                ).fetchone()["kamas"]
                            send(connection, service, 12753, struct.pack(">q", balance))
                        record(
                            event="inventory_socket_identification",
                            actor_id=character["id"],
                            uid=result["uid"],
                            status=result["status"],
                            applied=result["applied"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "La identificación está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="inventory_socket_identification_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                elif opcode == 12487 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.element_selection import select as select_elements
                    from wakfu_server.inventory_move import reload_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None:
                            raise ValueError(
                                "No puedes seleccionar elementos durante un combate."
                            )
                        result = select_elements(
                            STORE, account_id, generation, character["id"], body
                        )
                        character = reload_inventory(STORE, account_id, character)
                        send(connection, service, *result["packet"])
                        if result.get("cost_kamas", 0) > 0:
                            send(
                                connection,
                                service,
                                12753,
                                struct.pack(">q", result["wallet_kamas"]),
                            )
                        record(
                            event="inventory_elements_selected",
                            actor_id=character["id"],
                            uid=result["uid"],
                            applied=result["applied"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "La selección de elementos está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="inventory_elements_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                elif opcode in (12365, 13257, 12221, 12364, 13269) and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.socket_enchantment import install_bonus, mutate
                    from wakfu_server.socket_enchantment_wire import (
                        bonus_installation_packets,
                        packets,
                    )
                    from wakfu_server.inventory_move import reload_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None:
                            raise ValueError(
                                "No puedes modificar objetos durante un combate."
                            )
                        if opcode == 13269:
                            result = install_bonus(
                                STORE, account_id, generation, character["id"], body
                            )
                        else:
                            result = mutate(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                opcode,
                                body,
                            )
                        character = reload_inventory(STORE, account_id, character)
                        response_packets = (
                            bonus_installation_packets(character["id"], result)
                            if opcode == 13269
                            else packets(character["id"], result)
                        )
                        for message_id, message_body in response_packets:
                            send(connection, service, message_id, message_body)
                        record(
                            event="inventory_socket_enchantment_changed",
                            actor_id=character["id"],
                            uid=result["uid"],
                            operation=result["operation"],
                            applied=result["applied"],
                            consumed_uid=result.get("consumed_uid"),
                            consumed=result.get("consumed", []),
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "La modificación de ranuras está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="inventory_socket_enchantment_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                elif opcode == 13589 and loaded:
                    from wakfu_server.inventory_uids import replenish

                    message_id, message_body = replenish(
                        STORE, account_id, generation, character["id"], body
                    )["packet"]
                    send(connection, service, message_id, message_body)
                    record(event="inventory_uids_reserved", actor_id=character["id"])
                elif opcode in (12656, 13673) and loaded:
                    from wakfu_server.inventory_bags import equip, remove
                    from wakfu_server.inventory_move import (
                        synchronization,
                        reload_inventory,
                    )

                    try:
                        operation = equip if opcode == 12656 else remove
                        result = operation(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        record(
                            event="inventory_bag_changed",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_bag_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12659 and loaded:
                    from wakfu_server.inventory_consumables import use
                    from wakfu_server.inventory_move import (
                        synchronization,
                        reload_inventory,
                    )

                    try:
                        result = use(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            expected_hp=character["hp"],
                            in_fight=fight is not None,
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        from wakfu_server.inventory_animation import eating

                        for emote in result.get("emotes", ()):
                            action_id = next(LOCAL_WORLD_ACTIONS)
                            animation = eating(
                                actor_id=character["id"],
                                action_id=action_id,
                                effect_uid=(1 << 48) + action_id,
                                effect_id=emote["effect_id"],
                            )
                            WORLD.broadcast(generation, character["id"], *animation)
                        record(
                            event="inventory_food_used",
                            actor_id=character["id"],
                            hp=character["hp"],
                        )
                        from wakfu_server.inventory_items import equipment_inventory

                        send(connection, service, *equipment_inventory(character))
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_food_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode in (13993, 12294) and loaded:
                    from wakfu_server import combat_drop_delivery
                    from wakfu_server.inventory_move import reload_inventory

                    try:
                        action = (
                            combat_drop_delivery.claim
                            if opcode == 13993
                            else combat_drop_delivery.bulk_transfer
                        )
                        result = action(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = (
                            result["character"] if opcode == 13993 else result["source"]
                        )
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        with STORE.connection() as db:
                            packet = combat_drop_delivery.temporary_update(
                                db, character["id"]
                            )
                        send(connection, service, *packet)
                        record(
                            event="combat_loot_claim_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12561 and loaded:
                    from wakfu_server import combat_drop_delivery

                    try:
                        result = combat_drop_delivery.discard(
                            STORE, account_id, generation, character["id"], body
                        )
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        record(
                            event="combat_loot_discarded",
                            actor_id=character["id"],
                            applied=result["applied"],
                        )
                    except ValueError as error:
                        record(
                            event="combat_loot_discard_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13447 and loaded:
                    from wakfu_server.items.temporary_recycling import recycle
                    from wakfu_server.ecology_feedback import information

                    try:
                        result = recycle(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        record(
                            event="temporary_inventory_recycled",
                            actor_id=character["id"],
                            applied=result["applied"],
                        )
                    except ValueError as error:
                        send(connection, service, *information(str(error)))
                        record(
                            event="temporary_inventory_recycling_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12787 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.recycling import recycle
                    from wakfu_server.inventory_move import (
                        synchronization,
                        reload_inventory,
                    )
                    from wakfu_server.inventory_items import equipment_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        result = recycle(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            fight=fight,
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        # Replace both native bags and their rich UID registry.
                        # Do not combine this snapshot with additive grant packets.
                        send(connection, service, *synchronization(character))
                        send(connection, service, *equipment_inventory(character))
                        send(connection, service, *result["packets"][-1])
                        record(
                            event="inventory_recycled",
                            actor_id=character["id"],
                            applied=result["applied"],
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "El reciclado está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="inventory_recycling_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                elif opcode == 12490 and loaded:
                    from wakfu_server.inventory_actions import destroy
                    from wakfu_server.inventory_move import (
                        synchronization,
                        reload_inventory,
                    )

                    try:
                        result = destroy(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        record(
                            event="inventory_item_destroyed", actor_id=character["id"]
                        )
                        from wakfu_server.inventory_items import equipment_inventory

                        send(connection, service, *equipment_inventory(character))
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_destroy_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12804 and loaded:
                    from wakfu_server.inventory_move import (
                        transfer,
                        synchronization,
                        reload_inventory,
                    )

                    try:
                        result = transfer(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        record(event="inventory_item_moved", actor_id=character["id"])
                        from wakfu_server.inventory_items import equipment_inventory

                        send(connection, service, *equipment_inventory(character))
                    except ValueError as error:
                        character = reload_inventory(STORE, account_id, character)
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_move_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13686 and loaded:
                    try:
                        destination_route = native_transports.resolve(
                            character,
                            body,
                            known_ids=known_transports(account_id),
                            waive_criteria=ALL_ZAAPS,
                        )
                        saved = STORE.transition_map(
                            account_id,
                            generation,
                            character["id"],
                            character,
                            destination_route["destination"],
                        )
                    except ValueError as error:
                        record(
                            event="native_transport_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    else:
                        cancel_crafting()
                        WORLD.leave(character["id"], generation)
                        character = saved
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        for message_id, message_body in owned_native_bootstrap(
                            character
                        ):
                            send(connection, service, message_id, message_body)
                        join_world(generation, connection, character)
                        mark_static_sync_pending()
                        record(
                            event="native_map_transition",
                            actor_id=character["id"],
                            source_id=destination_route["source_id"],
                            destination_id=destination_route["destination_id"],
                            map_id=character["map_id"],
                            position=position,
                        )
                elif opcode == 12296 and loaded:
                    from wakfu_server import generic_transports, teleporter_approach

                    generic_route = False
                    try:
                        if (1 << 58) < character.get("instance_id", 0) < (1 << 59):
                            from wakfu_server import rift_exit

                            exited = rift_exit.leave(
                                STORE,
                                POSITIONS,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                source_allowed=teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character["instance_id"],
                                ),
                                fighting=lambda actor_id: COMBAT_SESSIONS.lookup_character(
                                    actor_id
                                )
                                is not None,
                            )
                            if exited is not None:
                                deliver_rift_transition()
                                continue
                        if (
                            DUNGEON_TRANSITION_OUTBOX_AVAILABLE
                            and DUNGEON_ROOM_RUNTIME_AVAILABLE
                        ):
                            from wakfu_server.maps import (
                                dungeon_transport,
                                dungeon_criteria,
                                dungeon_runtime,
                            )
                            from wakfu_server.combat_terrain import map_geometry

                            if is_dungeon_run(character.get("instance_id", 0)):
                                from wakfu_server.maps import (
                                    dungeon_doors,
                                    dungeon_exit,
                                )

                                with STORE.connection() as dungeon_db:
                                    (
                                        _,
                                        dungeon_config,
                                    ) = dungeon_runtime.configuration_for_instance(
                                        dungeon_db, character["instance_id"]
                                    )
                                if (
                                    dungeon_config["topology"].get("policy")
                                    == "local_accessible_anchor_policy"
                                ):
                                    raise ValueError(
                                        "This dungeon uses automatic party travel"
                                    )
                                source_id, destination_id, _, _ = struct.unpack(
                                    ">qiBi", body
                                )
                                source = generic_transports.source(
                                    character["map_id"], source_id
                                )
                                destination = next(
                                    (
                                        row
                                        for row in (source or {}).get(
                                            "destinations", ()
                                        )
                                        if row["destination_id"] == destination_id
                                    ),
                                    None,
                                )
                                if destination is None:
                                    raise ValueError(
                                        "Dungeon teleporter destination is absent"
                                    )
                                approach = teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character["instance_id"],
                                )

                                def dungeon_member_in_fight(actor_id):
                                    if actor_id == character["id"] and (
                                        fight is not None or combat_session is not None
                                    ):
                                        return True
                                    return (
                                        COMBAT_SESSIONS.lookup_character(actor_id)
                                        is not None
                                    )

                                if destination["map_id"] != character["map_id"]:
                                    from wakfu_server.maps import dungeon_physical_doors

                                    if dungeon_physical_doors.enabled(
                                        dungeon_config["topology"]
                                    ):
                                        physical_exit = next(
                                            (
                                                row
                                                for row in dungeon_config["topology"][
                                                    "physical_exit_objects"
                                                ]
                                                if row["source_id"] == source_id
                                            ),
                                            None,
                                        )
                                        with STORE.connection() as exit_db:
                                            exit_progress = exit_db.execute(
                                                "SELECT status FROM dungeon_room_runs WHERE instance_id=%s",
                                                (character["instance_id"],),
                                            ).fetchone()
                                        if physical_exit is None or (
                                            physical_exit["room_order"] != 1
                                            and exit_progress["status"] != "completed"
                                        ):
                                            raise ValueError(
                                                "Physical dungeon exit is locked"
                                            )
                                    dungeon_exit.leave(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        body,
                                        source_allowed=approach,
                                        in_fight=dungeon_member_in_fight,
                                    )
                                else:
                                    dungeon_doors.advance(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        body,
                                        source_allowed=approach,
                                        in_fight=dungeon_member_in_fight,
                                        room_for_position=lambda map_id, x, y, z: dungeon_runtime.room_for_position(
                                            dungeon_config, map_id, x, y, z
                                        ),
                                    )
                                deliver_dungeon_transitions(before_action=True)
                                continue
                            configured_entry = dungeon_transport.resolve_request(
                                character["map_id"], body
                            )
                            if configured_entry is not None:
                                from wakfu_server.maps import (
                                    dungeon_entry_access,
                                )

                                geometry = map_geometry(
                                    configured_entry["route"].start_map_id
                                )
                                dungeon_transport.enter(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    character["map_id"],
                                    body,
                                    criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                                        STORE, criterion, character=actor
                                    ),
                                    source_allowed=teleporter_approach.callback(
                                        movement_state,
                                        map_id=character["map_id"],
                                        instance_id=character.get("instance_id", 0),
                                    ),
                                    resolve_destination=dungeon_runtime.entry_destination,
                                    initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                                        db,
                                        session,
                                        groups=COMBAT_GROUPS,
                                        geometry=geometry,
                                    ),
                                )
                                deliver_dungeon_transitions(before_action=True)
                                continue
                        identity = (
                            struct.unpack_from(">q", body)[0]
                            if len(body) == 17
                            else None
                        )
                        verified_tutorial = any(
                            route["source_map"] == character["map_id"]
                            and route["interactive_element_id"] == identity
                            for route in transports.CATALOG["routes"]
                        )
                        if (
                            not verified_tutorial
                            and identity is not None
                            and generic_transports.source(character["map_id"], identity)
                            is not None
                        ):
                            destination_route = generic_transports.resolve(
                                character,
                                body,
                                source_allowed=teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character.get("instance_id", 0),
                                ),
                            )
                            generic_route = True
                        else:
                            destination_route = transports.resolve(character, body)
                        saved = STORE.transition_map(
                            account_id,
                            generation,
                            character["id"],
                            character,
                            destination_route["destination"],
                        )
                    except ValueError as error:
                        record(
                            event="transport_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            service,
                            13974,
                            (
                                next(
                                    payload
                                    for message_id, payload in owned_native_bootstrap(
                                        character
                                    )
                                    if message_id == 13974
                                )
                                if is_dungeon_run(character.get("instance_id", 0))
                                else wire.adapt(
                                    13974, fixture(13974), account_id, character
                                )
                            ),
                        )
                    else:
                        cancel_crafting()
                        WORLD.leave(character["id"], generation)
                        character = saved
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        messages = (
                            owned_native_bootstrap(
                                character, direction=destination_route["direction"]
                            )
                            if generic_route
                            else transports.bootstrap(character, destination_route)
                        )
                        for message_id, message_body in messages:
                            send(connection, service, message_id, message_body)
                        join_world(generation, connection, character)
                        mark_static_sync_pending()
                        record(
                            event="map_transition",
                            actor_id=character["id"],
                            map_id=character["map_id"],
                            position=position,
                        )
                elif opcode == 12962 and generation:
                    from wakfu_server.tutorials import update as update_tutorials

                    update_tutorials(STORE, account_id, generation, body)
                    record(event="tutorial_state_saved", account_id=account_id)
                elif opcode == 12091 and loaded:
                    from wakfu_server import world_shortcuts

                    try:
                        saved = world_shortcuts.apply(
                            STORE, account_id, generation, character["id"], body
                        )
                    except (ValueError, UnicodeError) as error:
                        record(
                            event="world_shortcuts_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    else:
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        record(event="world_shortcuts_saved", actor_id=character["id"])
                elif opcode == 13169 and loaded:
                    previous_mount_character = character
                    index = character["active_build_index"]
                    try:
                        requested_actor, index = builds.decode_deletion(body)
                        if requested_actor != character["id"]:
                            raise ValueError(
                                "Build deletion belongs to another character"
                            )
                        saved = STORE.delete_build(
                            account_id,
                            generation,
                            character["id"],
                            index,
                            in_fight=fight is not None,
                        )
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                    except (ValueError, UnicodeError) as error:
                        send(
                            connection,
                            service,
                            *builds.deletion_message(
                                character["id"],
                                index,
                                failed=True,
                            ),
                        )
                        record(
                            event="build_deletion_rejected",
                            actor_id=character["id"],
                            build_index=index,
                            reason=str(error),
                        )
                    else:
                        # cEN removes the sheet and releases heroBuildLock first.
                        send(
                            connection,
                            service,
                            *builds.deletion_message(
                                character["id"],
                                index,
                                failed=False,
                            ),
                        )
                        send(connection, service, *builds.selection_message(character))
                        publish_mount_equipment(previous_mount_character, character)
                        from wakfu_server.combat_lifecycle import outside_progression

                        send(
                            connection,
                            service,
                            *outside_progression(character, wp=COMBAT_TEST_WP),
                        )
                        record(
                            event="build_deleted",
                            actor_id=character["id"],
                            build_index=index,
                            active_build_index=character["active_build_index"],
                        )
                elif opcode == 13776 and loaded:
                    previous_mount_character = character
                    try:
                        requested_actor, index = builds.decode_activation(body)
                        if requested_actor != character["id"]:
                            raise ValueError(
                                "Build activation belongs to another character"
                            )
                        saved = STORE.activate_build(
                            account_id,
                            generation,
                            character["id"],
                            index,
                            in_fight=fight is not None,
                        )
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                    except (ValueError, UnicodeError) as error:
                        send(connection, service, *builds.selection_message(character))
                        record(
                            event="build_activation_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    else:
                        send(connection, service, *builds.selection_message(character))
                        publish_mount_equipment(previous_mount_character, character)
                        from wakfu_server.combat_lifecycle import outside_progression

                        send(
                            connection,
                            service,
                            *outside_progression(character, wp=COMBAT_TEST_WP),
                        )
                        record(
                            event="build_activated",
                            actor_id=character["id"],
                            build_index=index,
                            revision=character["build_selection_revision"],
                        )
                elif opcode == 12772 and loaded:
                    previous_mount_character = character
                    request_id, index, blobs = builds.decode(body)
                    if request_id != character["id"]:
                        raise ValueError(
                            "Build character does not belong to this session"
                        )
                    try:
                        record(
                            event="persistence_stage",
                            domain="build",
                            stage="save_started",
                            build_index=index,
                            backend="postgresql",
                        )
                        saved = STORE.save_build(
                            account_id, generation, request_id, index, blobs
                        )
                        record(
                            event="persistence_stage",
                            domain="build",
                            stage="postgresql_committed",
                            build_index=index,
                        )
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                    except (ValueError, UnicodeError) as error:
                        reason = str(error)
                        status = (
                            7
                            if "equipment" in reason.casefold()
                            else 9
                            if "aptitude" in reason.lower()
                            else 8
                            if "spell" in reason.lower() or "deck" in reason.lower()
                            else 2
                        )
                        saved = STORE.character(account_id, request_id)
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        send(connection, service, *builds.capacity_message(character))
                        for message_id, message_body in builds.rejection_messages(
                            character, index, wp=COMBAT_TEST_WP, status=status
                        ):
                            send(connection, service, message_id, message_body)
                        record(
                            event="build_rejected",
                            actor_id=request_id,
                            build_index=index,
                            reason=str(error),
                        )
                    else:
                        send(connection, service, *builds.capacity_message(character))
                        for message_id, message_body in builds.response_messages(
                            character, index, wp=COMBAT_TEST_WP
                        ):
                            send(connection, service, message_id, message_body)
                        publish_mount_equipment(previous_mount_character, character)
                        record(
                            event="build_saved", actor_id=request_id, build_index=index
                        )
                elif opcode == 13578 and loaded:
                    from wakfu_server.haven_bag import (
                        HavenBagSession,
                        entry_result,
                        entry_messages,
                    )

                    if len(body) != 8:
                        raise ValueError("Invalid haven bag entry request")
                    target_id = struct.unpack(">q", body)[0]
                    if character["map_id"] == 9:
                        send(
                            connection,
                            service,
                            13307,
                            entry_result(success=False, own=target_id == 0),
                        )
                        continue
                    if fight is not None:
                        send(connection, service, 13307, entry_result(success=False))
                        continue
                    owner = None
                    if target_id != 0:
                        from wakfu_server.haven_bag_exterior import can_visit

                        try:
                            exterior_owner = HAVEN_BAG_EXTERIORS.resolve(
                                character, target_id
                            )
                            owner = STORE.character(
                                exterior_owner["account_id"], target_id
                            )
                            if not can_visit(character, owner):
                                raise ValueError("Haven Bag access denied")
                        except ValueError as error:
                            send(
                                connection,
                                service,
                                13307,
                                entry_result(success=False, own=False),
                            )
                            record(
                                event="haven_bag_visit_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                            continue
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    cancel_flora()
                    cancel_crafting()
                    if owner is None:
                        packet = HAVEN_BAG_EXTERIORS.publish(generation, character)
                        WORLD.emit_location(
                            character["map_id"], character["instance_id"], *packet
                        )
                    bag_session = HavenBagSession(character, owner=owner)
                    WORLD.leave(character["id"], generation)
                    character = dict(bag_session.inside)
                    position = {key: character[key] for key in ("x", "y", "z")}
                    movement_state = Movement(position)
                    from copy import deepcopy
                    from wakfu_server.haven_bag import own_bag
                    from wakfu_server.haven_bag_furniture_world import (
                        packets as bag_furniture_packets,
                    )

                    render_owner = {
                        **bag_session.owner,
                        "haven_bag": character["haven_bag"],
                    }
                    layout_owner = deepcopy(render_owner)
                    layout_owner["haven_bag"]["furniture"] = []
                    for message_id, message_body in entry_messages(
                        fixture(13974),
                        character,
                        owner=layout_owner if owner is not None else None,
                    ):
                        send(connection, service, message_id, message_body)
                    if owner is None:
                        send(connection, service, 12187, own_bag(layout_owner))
                    join_world(generation, connection, character)
                    for packet in bag_furniture_packets(render_owner):
                        send(connection, service, *packet)
                    mark_static_sync_pending()
                    record(
                        event="haven_bag_entered",
                        actor_id=character["id"],
                        position=position,
                    )
                elif opcode in (12038, 12551) and loaded:
                    from wakfu_server.haven_chest import transfer as transfer_chest
                    from wakfu_server.haven_chest_wire import (
                        bootstrap as chest_bootstrap,
                    )
                    from wakfu_server.inventory_move import (
                        synchronization as sync_chest_inventory,
                    )
                    from wakfu_server.inventory_items import (
                        equipment_inventory as chest_registry,
                    )

                    try:
                        if chest_opening is None or fight is not None:
                            raise ValueError("No active account chest")
                        result = transfer_chest(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            opcode,
                            body,
                            opening_token=chest_opening,
                            location=character,
                        )
                        character = bag_session.refresh(character, result["character"])
                        # 318/ciH replaces existing bmM slots (including empty
                        # cells) and refreshes cYz; rich state uses item_proto.
                        # BAGS + registry reconcile the client's pending move
                        # from authoritative state without entity rebuilds.
                        for packet in (
                            sync_chest_inventory(character),
                            chest_registry(character),
                            chest_bootstrap(result["chest"]),
                        ):
                            send(connection, service, *packet)
                        record(
                            event="account_chest_transferred",
                            actor_id=character["id"],
                            opcode=opcode,
                            applied=result["applied"],
                            revision=result["chest"]["revision"],
                        )
                    except ValueError as error:
                        record(
                            event="account_chest_transfer_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=str(error),
                        )
                        if chest_opening is not None:
                            from wakfu_server.haven_chest import load as load_chest

                            current_chest = load_chest(
                                STORE, account_id, generation, character["id"]
                            )
                            for packet in (
                                sync_chest_inventory(character),
                                chest_registry(character),
                                chest_bootstrap(current_chest),
                            ):
                                send(connection, service, *packet)
                elif opcode in (12870, 12363) and loaded:
                    from wakfu_server.haven_bag_furniture_transfer import (
                        edit as edit_bag_furniture,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if (
                        opcode == 12870
                        and len(body) == 12
                        and struct.unpack_from(">H", body, 8)[0] == 11
                    ):
                        from wakfu_server import rift_transition_delivery
                        from wakfu_server.rift_dispatch_lifecycle import (
                            resolve_destination,
                        )
                        from wakfu_server.combat_terrain import map_geometry

                        try:
                            if (
                                fight is not None
                                or spectator_session is not None
                                or bag_session is not None
                            ):
                                raise ValueError(
                                    "A fight or inventory session blocks rift admission"
                                )
                            entered = rift_transition_delivery.enter(
                                STORE,
                                POSITIONS,
                                account_id,
                                generation,
                                character["id"],
                                character["map_id"],
                                body,
                                source_allowed=lambda actor, source: (
                                    actor["map_id"] == source["map_id"]
                                    and max(
                                        abs(actor["x"] - source["x"]),
                                        abs(actor["y"] - source["y"]),
                                    )
                                    <= 3
                                    and abs(actor["z"] - source["z"]) <= 2
                                ),
                                resolve_destination=lambda db, catalog, members: resolve_destination(
                                    db,
                                    catalog,
                                    members,
                                    map_geometry(catalog["map_id"]),
                                ),
                            )
                            if entered is not None:
                                deliver_rift_transition()
                                record(
                                    event="rift_entered",
                                    actor_id=character["id"],
                                    instance_id=entered["run"]["instance_id"],
                                    wave_id=entered["run"]["wave_definition_id"],
                                    member_ids=list(entered["run"]["members"]),
                                )
                                continue
                        except ValueError as error:
                            record(
                                event="rift_entry_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"), str(error)
                                ),
                            )
                            continue
                    if (
                        opcode == 12870
                        and len(body) == 12
                        and struct.unpack_from(">H", body, 8)[0] == 12
                    ):
                        from wakfu_server.haven_chest import (
                            load as load_chest,
                            validate_open as validate_chest_open,
                        )
                        from wakfu_server.haven_chest_wire import (
                            bootstrap as chest_bootstrap,
                            open_packet as chest_open_packet,
                        )

                        chest_opening = None
                        try:
                            identity = validate_chest_open(
                                character,
                                bag_session,
                                body,
                                world_static.objects(9),
                                fight_active=fight is not None
                                or spectator_session is not None,
                            )
                            cancel_crafting()
                            current_chest = load_chest(
                                STORE, account_id, generation, character["id"]
                            )
                            chest_opening = uuid.uuid4()
                            for packet in (
                                chest_bootstrap(current_chest),
                                (12401, struct.pack(">qB", character["id"], 7)),
                                (
                                    12344,
                                    struct.pack(">qh", identity, 19)
                                    + bytes.fromhex(
                                        "01020000000602000201010001010000000000"
                                    ),
                                ),
                                chest_open_packet(character["id"]),
                            ):
                                send(connection, service, *packet)
                            record(
                                event="account_chest_opened",
                                actor_id=character["id"],
                                capacity=current_chest["capacity"],
                            )
                        except ValueError as error:
                            record(
                                event="account_chest_open_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                        continue
                    if opcode == 12870 and character["map_id"] != 9:
                        try:
                            interaction = world_static.interaction(character, body)
                            # An accepted action only proves this target was
                            # registered. Keep the map-wide retry armed so
                            # other interactives can arrive after lazy loading.
                            sync_static_world(force=True)
                            if interaction["route"] != "transport_registration":
                                record(
                                    event="world_interactive_action",
                                    actor_id=character["id"],
                                    interaction=interaction,
                                    implemented=interaction["route"]
                                    == "transport_menu",
                                )
                                continue
                            kind, identity = native_transports.registration(
                                character, body
                            )
                            TRANSPORT_DISCOVERIES.discover(
                                account_id, generation, kind, identity
                            )
                            (
                                message_id,
                                message_body,
                            ) = transport_discovery.discovery_packet(kind, identity)
                            send(connection, service, message_id, message_body)
                            record(
                                event="transport_discovered",
                                account_id=account_id,
                                kind=kind,
                                transport_id=identity,
                            )
                        except ValueError as error:
                            record(
                                event="transport_registration_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                        continue
                    if (
                        bag_session is None
                        or not bag_session.is_owner
                        or not bag_session.owns(character)
                    ):
                        continue
                    try:
                        cancel_crafting()
                        previous_furniture = list(
                            character["haven_bag"].get("furniture", [])
                        )
                        result = edit_bag_furniture(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            opcode,
                            body,
                            location=character,
                        )
                        character = bag_session.refresh(character, result["character"])
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        from wakfu_server.haven_bag_furniture_world import (
                            remove as remove_furniture_scene,
                            upsert as publish_furniture_scene,
                        )

                        current_furniture = {
                            item["item_uid"]: item
                            for item in character["haven_bag"].get("furniture", [])
                        }
                        for old_item in previous_furniture:
                            new_item = current_furniture.get(old_item["item_uid"])
                            if old_item != new_item:
                                WORLD.emit_location(
                                    character["map_id"],
                                    character["instance_id"],
                                    *remove_furniture_scene(old_item),
                                )
                                if new_item is not None and new_item.get("deployed"):
                                    WORLD.emit_location(
                                        character["map_id"],
                                        character["instance_id"],
                                        *publish_furniture_scene(character, new_item),
                                    )
                        record(
                            event="haven_bag_furniture_edited",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                    except ValueError as error:
                        record(
                            event="haven_bag_furniture_edit_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13826 and loaded:
                    from wakfu_server.haven_bag_furniture_transfer import (
                        deploy as deploy_bag_furniture,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if (
                        bag_session is None
                        or not bag_session.is_owner
                        or not bag_session.owns(character)
                    ):
                        continue
                    try:
                        cancel_crafting()
                        previous_furniture_uids = {
                            item["item_uid"]
                            for item in character["haven_bag"].get("furniture", [])
                            if item.get("deployed")
                        }
                        result = deploy_bag_furniture(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            location=character,
                        )
                        character = bag_session.refresh(character, result["character"])
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        from wakfu_server.haven_bag_furniture_world import (
                            upsert as publish_furniture_scene,
                        )

                        for item in character["haven_bag"].get("furniture", []):
                            if (
                                item.get("deployed")
                                and item["item_uid"] not in previous_furniture_uids
                            ):
                                WORLD.emit_location(
                                    character["map_id"],
                                    character["instance_id"],
                                    *publish_furniture_scene(character, item),
                                )
                        record(
                            event="haven_bag_furniture_saved", actor_id=character["id"]
                        )
                    except ValueError as error:
                        record(
                            event="haven_bag_furniture_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12580 and loaded:
                    from wakfu_server.haven_bag_store import save as save_haven_bag
                    from wakfu_server.haven_bag import (
                        decode_permissions,
                        permission_payload,
                    )

                    if (
                        bag_session is None
                        or not bag_session.is_owner
                        or not bag_session.owns(character)
                    ):
                        continue
                    try:
                        locked, access = decode_permissions(body)
                        saved = save_haven_bag(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            locked=locked,
                            access=access,
                        )
                        character = bag_session.refresh(character, saved)
                        record(
                            event="haven_bag_permissions_saved",
                            actor_id=character["id"],
                        )
                    except ValueError as error:
                        record(
                            event="haven_bag_permissions_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    payload = permission_payload(character["haven_bag"])
                    send(
                        connection,
                        service,
                        13522,
                        struct.pack(">qI", character["id"], len(payload)) + payload,
                    )
                elif opcode in (12177, 13090) and loaded:
                    from wakfu_server.haven_bag_transfer import (
                        can_transfer,
                        insert,
                        remove,
                    )
                    from wakfu_server.haven_bag import own_bag

                    # Gem transfers are owner-only. A visitor can be on map 9,
                    # but only this connection's active private-bag owner may
                    # mutate its inventory or layout.
                    if not can_transfer(
                        bag_session, character, fight_active=fight is not None
                    ):
                        continue
                    try:
                        if opcode == 12177:
                            result = insert(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                location=character,
                            )
                        else:
                            occupied_by_others = any(
                                player["id"] != character["id"]
                                and player["map_id"] == 9
                                and player["instance_id"] == character["instance_id"]
                                for player in WORLD.snapshot()
                            )
                            result = remove(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                location={
                                    **character,
                                    "other_occupants": occupied_by_others,
                                },
                            )
                        character = bag_session.refresh(character, result["character"])
                        if STORE.current_session(account_id, generation):
                            for message_id, message_body in result["packets"]:
                                send(connection, service, message_id, message_body)
                        record(
                            event="haven_bag_gem_transfer_applied",
                            actor_id=character["id"],
                            opcode=opcode,
                            uid=result["uid"],
                            room=result["room"],
                            replayed=result.get("replayed", False),
                        )
                    except ValueError as error:
                        record(
                            event="haven_bag_gem_transfer_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=str(error),
                        )
                        # Refresh the authoritative room state after an invalid
                        # native request; never fabricate a success delta.
                        if STORE.current_session(account_id, generation):
                            send(connection, service, 12187, own_bag(character))
                elif opcode == 13210 and loaded:
                    from wakfu_server.haven_bag_store import (
                        save as save_haven_bag,
                        rearrange_rooms,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if (
                        bag_session is None
                        or not bag_session.is_owner
                        or not bag_session.owns(character)
                    ):
                        continue
                    try:
                        rooms = rearrange_rooms(character["haven_bag"], body)
                        saved = save_haven_bag(
                            STORE, account_id, generation, character["id"], rooms=rooms
                        )
                        character = bag_session.refresh(character, saved)
                        record(event="haven_bag_rooms_saved", actor_id=character["id"])
                    except ValueError as error:
                        record(
                            event="haven_bag_rooms_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    # cyX12187 reloads the authoritative tR configuration even
                    # after a rejected edit, rather than inventing partial ACKs.
                    send(connection, service, 12187, own_bag(character))
                elif opcode == 13434 and loaded:
                    from wakfu_server.haven_bag_store import save as save_haven_bag

                    if len(body) != 4:
                        raise ValueError("Invalid haven bag appearance request")
                    appearance_id = struct.unpack(">i", body)[0]
                    saved = save_haven_bag(
                        STORE,
                        account_id,
                        generation,
                        character["id"],
                        appearance_id=appearance_id,
                    )
                    character = (
                        bag_session.refresh(character, saved)
                        if bag_session is not None and bag_session.owns(character)
                        else saved
                    )
                    record(
                        event="haven_bag_appearance_saved",
                        actor_id=character["id"],
                        appearance_id=appearance_id,
                    )
                elif opcode == 12247 and loaded:
                    from wakfu_server.haven_bag import leave_messages
                    from wakfu_server.haven_bag import validate_leave_request

                    validate_leave_request(body)
                    if bag_session is None or not bag_session.owns(character):
                        # A missing cyV13019 notification could leave bag UI
                        # active after the exterior map was already restored.
                        for message_id, message_body in owned_haven_leave(
                            fixture(13974), character
                        ):
                            send(connection, service, message_id, message_body)
                        record(
                            event="haven_bag_leave_repaired", actor_id=character["id"]
                        )
                        continue
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    cancel_flora()
                    cancel_crafting()
                    WORLD.leave(character["id"], generation)
                    exterior = HAVEN_BAG_EXTERIORS.discard(generation, character["id"])
                    if exterior is not None:
                        outside, packet = exterior
                        WORLD.emit_location(
                            outside["map_id"], outside["instance_id"], *packet
                        )
                    character = bag_session.leave(character)
                    bag_session = None
                    position = {key: character[key] for key in ("x", "y", "z")}
                    movement_state = Movement(position)
                    for message_id, message_body in owned_haven_leave(
                        fixture(13974), character
                    ):
                        send(connection, service, message_id, message_body)
                    join_world(generation, connection, character)
                    mark_static_sync_pending()
                    record(
                        event="haven_bag_left",
                        actor_id=character["id"],
                        position=position,
                    )
                elif opcode == 13498 and loaded:
                    from wakfu_server.characters.emotes import prepare_play

                    def visible_emote_target(actor_id):
                        identity = WORLD.live_identity(character_id=actor_id)
                        return None if identity is None else identity[1]

                    emote = prepare_play(
                        STORE, account_id, generation, character, body,
                        resolve_target=visible_emote_target,
                        in_fight=lambda actor_id: COMBAT_SESSIONS.lookup_character(actor_id) is not None,
                    )
                    character["_emote_packet"] = emote["packet"]
                    character["_emote_until"] = (float("inf") if emote["duration_ms"] < 0
                        else time.monotonic() + emote["duration_ms"] / 1000)
                    WORLD.update(generation, character, *emote["packet"])
                elif opcode == 13331 and loaded:
                    movement_started = time.monotonic()
                    movement_timings = {}
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    movement_timings["cancel_occupations_ms"] = round(
                        (time.monotonic() - movement_started) * 1000, 3
                    )
                    movement = decode_body("out", opcode, body)
                    if not movement["steps"]:
                        record(
                            event="movement_zero_step_ignored",
                            actor_id=character["id"],
                            mode_id=movement["mode_id"],
                            start=movement["start_position"],
                            authoritative_position=position,
                        )
                        continue
                    start = movement["start_position"]
                    end = movement["end_position"]
                    try:
                        approved = movement_state.validate(movement)
                        if DUNGEON_ROOM_RUNTIME_AVAILABLE and is_dungeon_run(
                            character.get("instance_id", 0)
                        ):
                            from wakfu_server.maps import (
                                dungeon_physical_doors,
                                dungeon_runtime,
                            )

                            with STORE.connection() as movement_db:
                                (
                                    _,
                                    walking_config,
                                ) = dungeon_runtime.configuration_for_instance(
                                    movement_db, character["instance_id"]
                                )
                                if dungeon_physical_doors.enabled(
                                    walking_config["topology"]
                                ):
                                    walking_progress = movement_db.execute(
                                        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                                        (character["instance_id"],),
                                    ).fetchone()
                                    dungeon_physical_doors.validate_movement(
                                        walking_config["topology"],
                                        movement,
                                        unlocked_room=walking_progress["current_room"],
                                    )
                    except ValueError as error:
                        record(
                            event="movement_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(
                            connection,
                            "world",
                            13530,
                            struct.pack(
                                ">qiihBi",
                                character["id"],
                                position["x"],
                                position["y"],
                                position["z"],
                                0,
                                movement["mode_id"],
                            ),
                        )
                        continue
                    if start != position:
                        record(
                            event="movement_redirected",
                            actor_id=character["id"],
                            previous_destination=position,
                            start=start,
                        )
                    if end != position:
                        crafting_cancel_started = time.monotonic()
                        cancel_crafting()
                        movement_timings["cancel_crafting_ms"] = round(
                            (time.monotonic() - crafting_cancel_started) * 1000, 3
                        )
                    position_update_started = time.monotonic()
                    if bag_session is not None and bag_session.owns(character):
                        try:
                            character = bag_session.move(character, end)
                        except ValueError as error:
                            record(
                                event="movement_rejected",
                                actor_id=character["id"],
                                reason=str(error),
                            )
                            send(
                                connection,
                                "world",
                                13530,
                                struct.pack(
                                    ">qiihBi",
                                    character["id"],
                                    position["x"],
                                    position["y"],
                                    position["z"],
                                    0,
                                    movement["mode_id"],
                                ),
                            )
                            continue
                    else:
                        POSITIONS.merge(account_id, generation, character)
                        buffered = POSITIONS.move(
                            account_id,
                            generation,
                            character["id"],
                            position,
                            dict(end, direction=movement["steps"][-1]["direction"]),
                        )
                        character.update(
                            {key: buffered[key] for key in ("x", "y", "z", "direction")}
                        )
                    movement_state.commit(approved)
                    position = end
                    movement_timings["position_update_ms"] = round(
                        (time.monotonic() - position_update_started) * 1000, 3
                    )
                    world_publish_started = time.monotonic()
                    # The client loads/unloads scene partitions during its local
                    # walk. Queue their dynamic states after loading, not a full
                    # map reconstruction before the first walking frame.
                    scene_path = [dict(start)]
                    for step in movement["steps"]:
                        previous = scene_path[-1]
                        scene_path.append(
                            {
                                axis: previous[axis] + step["d" + axis]
                                for axis in ("x", "y", "z")
                            }
                        )
                    scene_sync.arm(
                        character["map_id"],
                        character.get("instance_id", 0),
                        scene_path,
                        time.monotonic(),
                    )
                    # The owner already follows this path locally. Rebuilding
                    # an endpoint path on it interrupts redirects and stairs.
                    # Other clients receive every packed step and its height.
                    response = wire.movement_path(character["id"], body)
                    if character.pop("_emote_packet", None) is not None:
                        from wakfu_server.characters.emotes import stopped
                        character.pop("_emote_until", None)
                        WORLD.broadcast(generation, character["id"], *stopped(character["id"]))
                    WORLD.update(
                        generation, character, 13852, response, include_sender=False
                    )
                    movement_timings["world_publish_ms"] = round(
                        (time.monotonic() - world_publish_started) * 1000, 3
                    )
                    ecology_context_started = time.monotonic()
                    if bag_session is None:
                        send_planting_context(
                            connection,
                            character,
                            include_weather=territory_weather_region_changed(
                                character["map_id"], start, end
                            ),
                        )
                    record(
                        event="movement",
                        actor_id=character["id"],
                        account_id=account_id,
                        start=start,
                        end=end,
                        steps=movement["step_count"],
                        mode_id=movement["mode_id"],
                        final_direction=movement["steps"][-1]["direction"],
                        approved_path_points=len(approved),
                        animation_owner="local_client",
                        path_echo_to_owner=False,
                        elapsed_ms=round(
                            (time.monotonic() - movement_started) * 1000, 3
                        ),
                        ecology_context_ms=round(
                            (time.monotonic() - ecology_context_started) * 1000, 3
                        ),
                        **movement_timings,
                    )
                elif opcode in (13074, 13224, 13188, 13831) and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.ecology_feedback import information

                    try:
                        request = decode_body("out", opcode, body)
                        now = time.monotonic()
                        interval = CHANNELS.minimum_interval()
                        if now - last_chat < interval:
                            raise ValueError(
                                "Espera un momento antes de enviar otro mensaje."
                            )
                        last_chat = now
                        delivered = CHANNELS.handle(
                            opcode, request, account_id, generation, character["id"]
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "El chat está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="channel_chat_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                    else:
                        record(
                            event="channel_chat",
                            actor_id=character["id"],
                            opcode=opcode,
                            delivered=delivered,
                        )
                elif opcode in (784, 657, 672, 799, 12449) and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.ecology_feedback import information

                    try:
                        packet = SOCIAL_ACTIONS.handle(
                            opcode, body, account_id, generation
                        )
                        if packet is not None:
                            send(connection, service, *packet)
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Los contactos están temporalmente indisponibles."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="social_request_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                elif (
                    opcode in (13140, 12997, 13037, 12203, 12781, 13406, 12027, 13113)
                    and loaded
                ):
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.ecology_feedback import information

                    try:
                        EXCHANGES.handle(
                            opcode, body, account_id, generation, character["id"]
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "El intercambio está temporalmente indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="exchange_request_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                    else:
                        record(
                            event="exchange_request",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                elif opcode in (1156, 1031, 1074, 1066) and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.ecology_feedback import information

                    try:
                        PARTIES.handle(
                            opcode, body, account_id, generation, character["id"]
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Le groupe est temporairement indisponible."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="party_request_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                            sqlstate=getattr(error, "sqlstate", None),
                            constraint=getattr(
                                getattr(error, "diag", None), "constraint_name", None
                            ),
                        )
                    else:
                        record(
                            event="party_request",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                elif opcode in (12455, 13765) and loaded:
                    from wakfu_server.characters.cosmetics import (
                        OwnedCosmetics,
                        actor_update,
                    )

                    try:
                        if fight is not None:
                            raise ValueError("Cosmetic selection requires exploration")
                        previous_cosmetic_character = character
                        saved = STORE.equip_owned_finishers(
                            account_id, character["id"], opcode, body
                        )
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        cosmetics = OwnedCosmetics.from_record(
                            character["owned_cosmetics"], account_id=account_id
                        )
                        send(
                            connection,
                            service,
                            13873,
                            struct.pack(">II", 2, 8)
                            + cosmetics.inventory_component()
                            + struct.pack(">I", 9)
                            + cosmetics.preset_component(),
                        )
                        cosmetic_opcode, cosmetic_body = actor_update(character)
                        send(connection, service, cosmetic_opcode, cosmetic_body)
                        WORLD.update(
                            generation,
                            character,
                            cosmetic_opcode,
                            cosmetic_body,
                            include_sender=False,
                        )
                        publish_mount_equipment(previous_cosmetic_character, character)
                        record(
                            event="owned_finishers_selected",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                    except ValueError as error:
                        record(
                            event="owned_finishers_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=str(error),
                        )
                elif opcode == 13917 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    request = decode_body("out", opcode, body)
                    text = request["text"].strip()
                    now = time.monotonic()
                    if not text or len(text) > 512 or now - last_chat < 0.2:
                        send(connection, service, 349, wire.private_chat_error(140))
                        continue
                    last_chat = now
                    try:
                        delivered = WORLD.private_chat(
                            generation,
                            character["id"],
                            account_id,
                            request["recipient"],
                            text,
                            block_reason=SOCIAL_CONTACTS.private_chat_block_reason,
                            valid_session=lambda entry: STORE.current_character_session(
                                entry[2]["account_id"], entry[0], entry[2]["id"]
                            ),
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        send(connection, service, 349, wire.private_chat_error(140))
                        record(
                            event="private_chat_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                    else:
                        record(
                            event="private_chat",
                            actor_id=character["id"],
                            delivered=delivered,
                            characters=len(text),
                        )
                elif opcode == 12366 and loaded:
                    text = decode_body("out", opcode, body)["text"].strip()
                    if text.lower() in ("!exitdungeon", "!salirmazmorra"):
                        try:
                            from wakfu_server.maps import dungeon_exit

                            def exit_member_in_fight(actor_id):
                                if actor_id == character["id"] and (
                                    fight is not None or combat_session is not None
                                ):
                                    return True
                                return (
                                    COMBAT_SESSIONS.lookup_character(actor_id)
                                    is not None
                                )

                            record(
                                event="dungeon_exit_requested",
                                actor_id=character["id"],
                                instance_id=character.get("instance_id", 0),
                            )
                            dungeon_exit.leave_automatic(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                in_fight=exit_member_in_fight,
                            )
                            deliver_dungeon_transitions(before_action=True)
                            answer = "Has salido de la mazmorra."
                        except (
                            ValueError,
                            PermissionError,
                            DatabaseError,
                            PoolTimeout,
                        ) as error:
                            answer = str(error)
                            record(
                                event="dungeon_exit_rejected",
                                actor_id=character["id"],
                                reason=answer,
                            )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(dict(character, name="Información"), answer),
                        )
                        continue
                    if (
                        text.startswith("!")
                        and os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
                    ):
                        try:
                            execute_test_command(text)
                        except (ValueError, PermissionError):
                            pass  # Rejection was sent to the chat; keep the session alive.
                        continue
                    now = time.monotonic()
                    if text and len(text) <= 512 and now - last_chat >= 0.2:
                        last_chat = now
                        WORLD.broadcast(
                            generation, character["id"], 674, wire.chat(character, text)
                        )
                        record(
                            event="chat", actor_id=character["id"], characters=len(text)
                        )
                else:
                    record(
                        event="request_rejected",
                        opcode=opcode,
                        reason="No handler for this opcode in the current session state",
                        loaded=loaded,
                        authenticated=account_id is not None,
                    )
                checkpoint_fight()
                active_request.finish()
                active_request = None
    except (EOFError, OSError, ValueError) as error:
        if active_request is not None:
            active_request.rejection("request_disconnected", str(error))
        record(
            event="disconnected",
            connection_id=connection_trace_id,
            service=service,
            error=type(error).__name__,
            detail=str(error),
            traceback=exception_frames(error),
            state_at_disconnect=safe_snapshot(
                lambda: state_summary(character, fight, fight_messages)
            ),
            native_action_id=None
            if fight_messages is None
            else fight_messages.native_action_id,
            logical_action_id=None
            if fight_messages is None
            else fight_messages.action_id,
        )
        if active_request is not None:
            active_request.finish(
                status="invalid_request"
                if isinstance(error, ValueError)
                else "disconnected"
            )
            active_request = None
    except Exception as error:
        record(
            event="unexpected_request_exception",
            service=service,
            connection_id=connection_trace_id,
            exception_type=type(error).__name__,
            reason=redact(str(error)),
            traceback=exception_frames(error),
            state_at_failure=safe_snapshot(
                lambda: state_summary(character, fight, fight_messages)
            ),
        )
        if active_request is not None:
            active_request.finish(status="unexpected_error")
            active_request = None
    finally:
        if active_request is not None:
            active_request.finish(status="interrupted")
            active_request = None
        if character is not None:
            PLANTINGS.cancel(character["id"], generation)
        if character is not None:
            HARVESTS.cancel(character["id"], generation=generation)
        if console_session is not None:
            TEST_CONSOLE.unregister(*console_session)
        if character is not None and generation is not None:
            TEST_CONSOLE.unregister(character["id"], generation)
        if "connection" in locals():
            CONNECTIONS.unregister(connection)
        from psycopg import OperationalError, InterfaceError
        from psycopg_pool import PoolTimeout
        from wakfu_server.position_redis import PositionJournalUnavailable
        from wakfu_server.session_cleanup import retry_step

        def logout_barrier(stage, operation):
            return retry_step(
                operation,
                retry_errors=(
                    OperationalError,
                    InterfaceError,
                    PoolTimeout,
                    PositionJournalUnavailable,
                    OSError,
                ),
                failed=lambda error: record(
                    event="logout_barrier_failed",
                    stage=stage,
                    actor_id=None if character is None else character["id"],
                    reason=redact(str(error)),
                ),
                renew=lambda: STORE.heartbeat(account_id, generation)
                if account_id is not None and generation is not None
                else None,
            )

        if service == "world" and flora_ticket is not None:
            logout_barrier("flora_occupation", cancel_flora)
        if service == "world":
            from wakfu_server.combat.checkpoint_worker import checkpoint_cleanup_barrier

            checkpoint_cleanup_barrier(
                lambda: logout_barrier(
                    "fight_checkpoint",
                    lambda: checkpoint_fight(
                        None
                        if combat_session is not None
                        else (
                            "ended"
                            if fight is not None and fight.phase == "finished"
                            else "aborted"
                        )
                    ),
                ),
                failed=lambda error: record(
                    event="logout_checkpoint_failed",
                    stage="save",
                    actor_id=None if character is None else character["id"],
                    reason=redact(str(error)),
                    traceback=exception_frames(error),
                ),
            )
        if service == "world" and fight is not None:

            def flush_logout_checkpoint():
                if not CHECKPOINT_WRITER.flush_fight(fight.id, timeout=10):
                    raise ValueError(
                        "Pending checkpoint exceeded logout flush deadline"
                    )

            checkpoint_cleanup_barrier(
                lambda: logout_barrier(
                    "fight_checkpoint_flush", flush_logout_checkpoint
                ),
                failed=lambda error: record(
                    event="logout_checkpoint_failed",
                    stage="flush",
                    actor_id=None if character is None else character["id"],
                    reason=redact(str(error)),
                    traceback=exception_frames(error),
                ),
            )
        shared_fight_retained = False
        last_owner_pve_abort = None
        if service == "world" and combat_session is not None and fight is not None:
            try:
                disconnected_fights = COMBAT_SESSIONS.disconnect(combat_session)
                shared_fight_retained = bool(disconnected_fights)
                if not disconnected_fights:
                    current_shared = COMBAT_SESSIONS.lookup_character(
                        combat_session.character_id
                    )
                    shared_fight_retained = (
                        current_shared is not None
                        and current_shared.participants.get(combat_session.account_id)
                        != combat_session
                    )
                if disconnected_fights:
                    shared_entry = COMBAT_SESSIONS.registry.lookup(fight.id)
                    if getattr(shared_entry, "is_duel", False):
                        forfeited = COMBAT_SESSIONS.registry.forfeit_duel(
                            combat_session
                        )
                        if forfeited:
                            # A forfeit is already a resolved duel. Persist the
                            # no-reward/full-health outcome before ending this
                            # lease; otherwise two simultaneous disconnects
                            # could leave only an in-memory winner behind.
                            logout_barrier(
                                "duel_forfeit_settlement", complete_test_fight
                            )
                            record(
                                event="friendly_duel_disconnect_forfeit",
                                actor_id=combat_session.character_id,
                                fight_id=fight.id,
                            )
                    elif shared_entry.disconnect_abort_pending:
                        # Transport loss retains the live native FSM/checkpoint.
                        # A selected replacement lease can durably take over;
                        # explicit abandonment still follows its terminal path.
                        shared_fight_retained = True
                    elif (
                        not shared_entry.connected
                        and len(
                            set(shared_entry.participants)
                            - set(shared_entry.withdrawals)
                        )
                        == 1
                        and getattr(shared_entry.runtime, "abandon_owner", None)
                        == (combat_session.account_id, combat_session.character_id)
                        and shared_entry.fight.phase == "finished"
                        and not shared_entry.settlement_ready
                    ):
                        # The abandon transaction already saved HP and marked
                        # the fight aborted; a closed ACK socket must not pin
                        # its actor IDs or group lease indefinitely.
                        last_owner_pve_abort = (fight.id, combat_session, shared_entry)
                        shared_fight_retained = False
            except ValueError:
                shared_fight_retained = False
        if (
            service == "world"
            and account_id is not None
            and character is not None
            and not shared_fight_retained
        ):
            from wakfu_server.combat_health import (
                persist_aborted_fight,
                persist_aborted_shared_fight,
            )

            # Confirm wounds before releasing the monster roster or position lease.
            def persist_exit_health():
                if last_owner_pve_abort is None:
                    return persist_aborted_fight(
                        STORE, account_id, generation, character, fight
                    )
                fight_id, exited_session, shared_abort = last_owner_pve_abort
                try:
                    all_exits = persist_aborted_shared_fight(
                        STORE, shared_abort, groups=COMBAT_GROUPS
                    )
                except ValueError as error:
                    record(
                        event="shared_pve_disconnect_cleanup_rejected",
                        actor_id=exited_session.character_id,
                        fight_id=fight_id,
                        reason=str(error),
                    )
                    return None
                return all_exits.get(exited_session.character_id)

            exited = logout_barrier(
                "fight_health",
                persist_exit_health,
            )
            if exited is not None and exited["applied"]:
                record(
                    event="combat_disconnected_health_saved",
                    actor_id=character["id"],
                    fight_id=fight.id,
                    hp=exited["character"]["hp"],
                )
            if last_owner_pve_abort is not None:
                fight_id, exited_session, shared_abort = last_owner_pve_abort
                if (
                    exited is not None
                    and COMBAT_SESSIONS.registry.retire_disconnected_pve(
                        fight_id, exited_session
                    )
                ):
                    # Durable abort has committed and registry retirement fenced
                    # every owner. Publish removal, never another active marker.
                    with shared_abort.lock:
                        shared_abort.fight.phase = "finished"
                        shared_abort.fight.winner = None
                    from wakfu_server.combat_abandon import aborted_terminal_packets

                    losing_team = shared_abort.fight.actors[
                        exited_session.character_id
                    ].team
                    publish_external_marker(shared_abort)
                    publish_spectator_state(
                        shared_abort,
                        aborted_terminal_packets(
                            shared_abort.fight,
                            shared_abort.runtime,
                            losing_team=losing_team,
                        ),
                    )
                    if shared_abort.group_lease is not None:
                        context = shared_abort.join_context or {}
                        members = context.get("monsters")
                        if members:
                            from wakfu_server.combat_monster_world import spawn_group

                            key = shared_abort.group_lease[0]
                            members = (
                                tuple(members.values())
                                if isinstance(members, dict)
                                else tuple(members)
                            )
                            WORLD.emit_location(
                                key[0],
                                key[1],
                                12608,
                                spawn_group(members, group_id=key[2]),
                            )
                            for packet in HARVESTS.availability_for(
                                key[0], key[1], [member["id"] for member in members]
                            ):
                                WORLD.emit_location(key[0], key[1], *packet)
                    record(
                        event="shared_pve_last_owner_disconnected",
                        actor_id=exited_session.character_id,
                        fight_id=fight_id,
                        durable_abort=True,
                        registry_retired=True,
                    )
                elif (
                    exited is not None
                    and COMBAT_SESSIONS.registry.retire_disconnected_abandon(
                        fight_id, exited_session
                    )
                ):
                    from wakfu_server.combat_abandon import aborted_terminal_packets

                    publish_external_marker(shared_abort)
                    publish_spectator_state(
                        shared_abort,
                        aborted_terminal_packets(
                            shared_abort.fight,
                            shared_abort.runtime,
                            losing_team=shared_abort.fight.actors[
                                exited_session.character_id
                            ].team,
                        ),
                    )
                    record(
                        event="shared_pve_abandon_disconnected",
                        actor_id=exited_session.character_id,
                        fight_id=fight_id,
                        registry_retired=True,
                    )
                else:
                    COMBAT_SESSIONS.registry.clear_disconnect_abort(fight_id)
                    shared_fight_retained = True
                    record(
                        event="shared_pve_disconnect_cleanup_pending",
                        actor_id=exited_session.character_id,
                        fight_id=fight_id,
                        durable_abort=exited is not None,
                        registry_retired=False,
                    )
        if service == "world" and account_id is not None and character is not None:
            logout_barrier(
                "position_flush",
                lambda: flush_positions(
                    account_id=account_id,
                    generation=generation,
                    character_id=character["id"],
                ),
            )
            logout_barrier(
                "position_release",
                lambda: POSITIONS.release(account_id, generation, character["id"]),
            )
        if service == "world" and not shared_fight_retained:
            if (
                fight is not None
                and fight.phase == "finished"
                and character is not None
                and group_lease is not None
                and fight.winner == fight.actors[character["id"]].team
            ):
                logout_barrier(
                    "group_finish",
                    lambda: COMBAT_GROUPS.finish(group_lease, defeated=True),
                )
            if not COMBAT_SESSIONS.registry.lease_generation_active(generation):
                logout_barrier("group_release", lambda: release_groups(generation))
        if service == "world" and account_id is not None:
            if character is not None:
                exterior = HAVEN_BAG_EXTERIORS.discard(generation, character["id"])
                if exterior is not None:
                    outside, packet = exterior
                    logout_barrier(
                        "haven_bag_exterior_remove",
                        lambda: WORLD.emit_location(
                            outside["map_id"], outside["instance_id"], *packet
                        ),
                    )
                logout_barrier(
                    "world_leave", lambda: WORLD.leave(character["id"], generation)
                )
            with LOCK:
                if LIVE.get(account_id, (None,))[0] == generation:
                    LIVE.pop(account_id, None)
            logout_barrier(
                "session_end", lambda: STORE.end_session(account_id, generation)
            )


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


def grow_planted_resources():
    while not STOPPING.wait(1):
        with PROFILER.span("background.grow_planted_resources"):
            try:
                with COMBAT_GROUPS.lock:
                    players = WORLD.snapshot()
                    states = COMBAT_GROUPS.snapshot()

                    def free_spawn(resource):
                        location = (resource["map_id"], resource["instance_id"])
                        destination = tuple(resource[k] for k in ("x", "y", "z"))
                        for player in players:
                            if (
                                player["map_id"],
                                player["instance_id"],
                            ) == location and tuple(
                                player[k] for k in ("x", "y", "z")
                            ) == destination:
                                return False
                        return not any(
                            tuple(m[k] for k in ("x", "y", "z")) == destination
                            for group in states
                            if group["key"][:2] == location
                            and group["status"] in ("available", "fighting")
                            for m in group["members"]
                        )

                    def publish_growth(result):
                        ecology = result.get("ecology")
                        if ecology and ecology["packets"]:
                            with STORE.connection() as db:
                                owner = db.execute(
                                    "SELECT account_id FROM characters WHERE id=%s",
                                    (ecology["character_id"],),
                                ).fetchone()
                                committed = STORE.character(
                                    owner["account_id"], ecology["character_id"], db
                                )
                            WORLD.publish_ecology(committed)
                            if not ecology.get("duplicate") and ecology.get(
                                "information"
                            ):
                                WORLD.information(
                                    ecology["character_id"], ecology["information"]
                                )
                        for packet in result["packets"]:
                            WORLD.emit_location(
                                result["map_id"], result["instance_id"], *packet
                            )

                    for result in PLANTINGS.mature(
                        COMBAT_GROUPS,
                        publish=publish_growth,
                        authorize_spawn=free_spawn,
                    ):
                        record(
                            event="planted_resource_grown",
                            map_id=result["map_id"],
                            instance_id=result["instance_id"],
                            resource_uid=result["resource_uid"],
                        )
            except Exception as error:
                record(event="plant_growth_error", reason=str(error))


def reproduce_monsters():
    from wakfu_server.monster_reproduction import tick
    from wakfu_server.monster_wander import edge_index
    from wakfu_server.combat_terrain import map_geometry
    import uuid

    generation = uuid.uuid4().hex
    locations, indexes = set(), {}
    while not STOPPING.wait(1):
        with PROFILER.span("background.reproduce_monsters"):
            try:
                active_maps = {p["map_id"] for p in WORLD.snapshot()}
                indexes = {
                    key: value for key, value in indexes.items() if key in active_maps
                }
                for map_id in active_maps:
                    if map_id not in indexes:
                        indexes[map_id] = edge_index(map_geometry(map_id)["edges"])
                with COMBAT_GROUPS.lock, HARVESTS.lock:
                    players = WORLD.snapshot()
                    active = {
                        (p["map_id"], p["instance_id"])
                        for p in players
                        if p["map_id"] in indexes
                    }
                    locations = tick(
                        STORE,
                        active,
                        locations,
                        generation=generation,
                        now_ms=time.monotonic_ns() // 1000000,
                        indexed_by_map=indexes,
                        players=players,
                        excluded_ids=set(HARVESTS.targets),
                        emit=WORLD.emit_location,
                    )
            except Exception as error:
                record(event="monster_reproduction_error", reason=str(error))


def expire_monster_corpses():
    from wakfu_server.monster_corpses import expire

    while not STOPPING.wait(1):
        with PROFILER.span("background.expire_monster_corpses"):
            try:
                with STORE.connection() as db:
                    for (map_id, instance_id), packets in expire(db).items():
                        # Serialize delivery with world snapshots, after SQL has
                        # collected the expired actors outside the group lock.
                        with COMBAT_GROUPS.lock:
                            for packet in packets:
                                WORLD.emit_location(map_id, instance_id, *packet)
            except Exception as error:
                record(event="monster_corpse_expiry_failed", reason=str(error))


def refresh_player_parties():
    while not STOPPING.wait(5):
        with PROFILER.span("background.refresh_player_parties"):
            try:
                PARTIES.refresh_online()
            except Exception as error:
                record(event="party_refresh_failed", reason=str(error))


def refresh_player_exchanges():
    from wakfu_server.player_exchanges import expire

    while not STOPPING.wait(1):
        with PROFILER.span("background.refresh_player_exchanges"):
            try:
                expire(STORE)
                EXCHANGES.drain()
            except Exception as error:
                record(event="exchange_refresh_failed", reason=str(error))


def mature_monsters():
    from wakfu_server.monster_maturation import tick
    import uuid

    generation = uuid.uuid4().hex
    locations = set()
    while not STOPPING.wait(1):
        with PROFILER.span("background.mature_monsters"):
            try:
                with COMBAT_GROUPS.lock, HARVESTS.lock:
                    active = {(p["map_id"], p["instance_id"]) for p in WORLD.snapshot()}
                    locations = tick(
                        STORE,
                        active,
                        locations,
                        generation=generation,
                        now_ms=time.monotonic_ns() // 1000000,
                        excluded_ids=set(HARVESTS.targets),
                        emit=WORLD.emit_location,
                    )
            except Exception as error:
                record(event="monster_maturation_error", reason=str(error))


def wander_monsters():
    from wakfu_server.monster_wander import wander_location, policy, edge_index
    from wakfu_server.combat_terrain import map_geometry

    configuration = policy(STORE)
    geometry_indexes = {}
    while not STOPPING.wait(configuration["interval_seconds"]):
        with PROFILER.span("background.wander_monsters"):
            try:
                configuration = policy(STORE)
                players = WORLD.snapshot()
                locations = {(p["map_id"], p["instance_id"]) for p in players}
                active_maps = {map_id for map_id, _ in locations}
                geometry_indexes = {
                    key: value
                    for key, value in geometry_indexes.items()
                    if key in active_maps
                }
                for map_id in active_maps:
                    if map_id not in geometry_indexes:
                        geometry_indexes[map_id] = edge_index(
                            map_geometry(map_id)["edges"]
                        )
                with COMBAT_GROUPS.lock, HARVESTS.lock:
                    harvesting = set(HARVESTS.targets)
                    for map_id, instance_id in locations:
                        moved = wander_location(
                            COMBAT_GROUPS,
                            map_id,
                            instance_id,
                            players,
                            (),
                            lambda opcode, body: WORLD.emit_location(
                                map_id, instance_id, opcode, body
                            ),
                            radius=configuration["radius"],
                            move_probability=configuration["move_probability"],
                            min_steps=configuration["min_steps"],
                            max_steps=configuration["max_steps"],
                            indexed=geometry_indexes[map_id],
                            excluded_ids=harvesting,
                        )
                        for key in moved:
                            record(
                                event="monster_group_wandered",
                                map_id=map_id,
                                instance_id=instance_id,
                                group_id=key[2],
                            )
            except Exception as error:
                record(event="monster_wander_error", reason=str(error))


def main():
    if COMBAT_TEST:
        from wakfu_server.combat_module_loading import preload_combat_modules
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

        started = time.monotonic()
        module_info = preload_combat_modules()
        static_info = prewarm_runtime_catalogs()
        import subprocess, sys

        subprocess.run(
            [
                sys.executable,
                os.path.join(
                    os.environ.get(
                        "WAKFU_AI_SDK_DIR",
                        os.path.join(os.path.dirname(__file__), "ai-service"),
                    ),
                    "prepare_catalog_cache.py",
                ),
                "--seal",
            ],
            check=True,
        )
        record(
            event="combat_catalogs_ready",
            elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            **static_info,
            **module_info,
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
        STORE.close()
        DIAGNOSTIC_LOG.close(timeout=1.0)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    from wakfu_server.territory_weather import initialize_local_baselines

    weather_baselines = initialize_local_baselines(STORE)
    record(event="territory_weather_baselines_initialized", **weather_baselines)
    if COMBAT_TEST:
        from wakfu_server.monster_initial_population import seed_configured

        seed_configured(STORE, COMBAT_GROUPS, report=record)
    from wakfu_server.performance_monitor import start_monitor

    start_monitor(PROFILER, RUNTIME / "logs/profiles/performance-latest.json", STOPPING)
    external_scheduler = os.environ.get("WAKFU_EXTERNAL_SCHEDULER", "0") == "1"
    from wakfu_server.global_tasks import GlobalTasks, SlowSaveAnnouncements

    def tick_territory_weather():
        from wakfu_server.territory_weather import tick_weather

        return tick_weather(STORE, WORLD)

    callbacks = {
        "positions_flush": flush_positions,
        "territory_weather_tick": tick_territory_weather,
    }
    global_tasks = GlobalTasks(callbacks, observer=SlowSaveAnnouncements(WORLD))
    threading.Thread(
        target=refresh_player_parties, name="wakfu-player-parties", daemon=True
    ).start()
    threading.Thread(
        target=refresh_player_exchanges, name="wakfu-player-exchanges", daemon=True
    ).start()
    if not external_scheduler:
        threading.Thread(
            target=flush_position_batches, name="wakfu-position-flusher", daemon=True
        ).start()
    if COMBAT_TEST:
        threading.Thread(
            target=expire_monster_corpses, name="wakfu-monster-corpses", daemon=True
        ).start()
        threading.Thread(
            target=grow_planted_resources, name="wakfu-plant-growth", daemon=True
        ).start()
    if COMBAT_TEST and hasattr(COMBAT_GROUPS, "move_members"):
        threading.Thread(
            target=reproduce_monsters, name="wakfu-monster-reproduction", daemon=True
        ).start()
        threading.Thread(
            target=mature_monsters, name="wakfu-monster-maturation", daemon=True
        ).start()
        threading.Thread(
            target=wander_monsters, name="wakfu-monster-wander", daemon=True
        ).start()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(RUNTIME / "server.crt", RUNTIME / "server.key")
    threading.Thread(
        target=serve_api,
        args=(STORE, os.environ.get("WAKFU_BIND_HOST", "127.0.0.1"), 18081),
        kwargs={
            "live_console": TEST_CONSOLE
            if os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
            else None,
            "global_tasks": global_tasks,
        },
        daemon=True,
    ).start()
    threading.Thread(target=listen, args=(15556, "world", context), daemon=True).start()
    listen(15558, "dispatcher", context)


if __name__ == "__main__":
    main()
