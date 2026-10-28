"""Local Python dispatcher/world prototype, seeded from the user's own capture."""
import base64
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

ROOT = Path(__file__).resolve().parent
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
from wakfu_server.planting_probability import resolver as planting_probability_resolver
from wakfu_server.planting_bonus import resolver as equipment_planting_bonus_resolver
from wakfu_server.haven_bag_garden import active_character as active_garden_character

ECOLOGY_MODE = os.environ.get("WAKFU_ECOLOGY_MODE", "inline")
if ECOLOGY_MODE not in ("inline", "external", "disabled"):
    raise ValueError("Invalid ecology execution mode")
ECOLOGY_BRIDGE = None
OPEN_PLANTING = os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1"
from wakfu_server.planting_level_policy import resolver as planting_level_bonus_resolver
from wakfu_server.planting_bonus_publisher import Publisher as PlantingBonusPublisher

NATIVE_PLANTING_BONUS = (
    not OPEN_PLANTING and os.environ.get("WAKFU_NATIVE_PLANTING_BONUS", "0") == "1"
)
COMBAT_WIRE_TRACE = os.environ.get("WAKFU_COMBAT_WIRE_TRACE", "0") == "1"
PLANTING_BONUSES = PlantingBonusPublisher(STORE)
PLANTING_BONUS_RESOLVER = (
    planting_level_bonus_resolver(STORE)
    if NATIVE_PLANTING_BONUS
    else equipment_planting_bonus_resolver(STORE)
)
PLANTINGS = Plantings(
    STORE,
    open_test_policy=OPEN_PLANTING,
    location_context=lambda stored: owned_planting_character(
        stored, WORLD, POSITIONS, store=STORE
    ),
    growth_seconds=float(os.environ.get("WAKFU_PLANT_GROWTH_SECONDS", "30")),
    probability_context=planting_probability_resolver(
        STORE, profession_bonus=PLANTING_BONUS_RESOLVER, open_test_policy=OPEN_PLANTING
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


from wakfu_server.checkpoint_watchdog import CheckpointWatchdog

CHECKPOINT_WATCHDOG = CheckpointWatchdog(
    RUNTIME / "logs/checkpoint-slow-stacks.log", timeout=5.0
)


@PROFILER.profile("persistence.position_checkpoint")
def flush_positions(*, background_budget=None, **scope):
    started = time.monotonic()
    try:
        with CHECKPOINT_WATCHDOG.watch():
            result = (
                POSITIONS.flush_background(**background_budget)
                if background_budget is not None
                else POSITIONS.flush(**scope)
            )
            count = result["characters"] if background_budget is not None else result
    except Exception as error:
        record(
            event="position_batch_timing",
            status="failed",
            elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            account_id=scope.get("account_id"),
            error_type=type(error).__name__,
        )
        raise
    if background_budget is None or result["attempted"]:
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
    return result


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


def pack_text(value, width="I"):
    data = value.encode()
    return struct.pack(">" + width, len(data)) + data


def send_shop_authentication(
    connection, service, account_id, generation, *, language=None
):
    """Issue the native shop key for initial login or an explicit renewal."""
    if language is not None:
        parts = language.replace("_", "-").split("-")
        if (
            not language.isascii()
            or not 2 <= len(language) <= 16
            or not 2 <= len(parts[0]) <= 3
            or not parts[0].isalpha()
            or any(not 2 <= len(part) <= 8 or not part.isalnum() for part in parts[1:])
        ):
            raise ValueError("Invalid shop request language")
    if account_id is None or not STORE.current_session(account_id, generation):
        raise ValueError("Shop authentication requires a current game session")
    shop_key = STORE.issue_token(account_id, "api", ttl=86400, generation=generation)
    if not STORE.current_session(account_id, generation):
        STORE.revoke_token(shop_key)
        raise ValueError("Shop authentication session changed before delivery")
    send(
        connection,
        service,
        22995,
        pack_text(shop_key) + struct.pack(">q", int((STORE.clock() + 86400) * 1000)),
    )
    record(
        event="shop_authentication_key_sent",
        account_id=account_id,
        renewal=language is not None,
        language=language,
    )


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
    pekebu = [blob for blob in characters if wire.TEMPLATE_NAME.encode("utf-8") in blob]
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


def owned_hero_template():
    """Use the owned entity format with spellbook, decks and shortcuts."""
    reader = Reader(fixture(12666))
    count = reader.number("H")
    reader.take(count * 8)
    entity = reader.take(reader.number("I"))
    if not entity or entity[0] != 10:
        raise ValueError("Missing native owned hero entity template")
    return entity


OWNED_HERO_TEMPLATE = owned_hero_template()


class AbortedNativeReturn:
    def __init__(self, owner, shared):
        self.owner, self.shared = owner, shared
        self.acknowledged = self.world_returned = False
        self.command = self.callback_flag = None

    def require(self, account_id, generation, character_id):
        owner = self.owner
        if (
            (owner.account_id, owner.generation, owner.character_id)
            != (account_id, generation, character_id)
            or self.shared.participants.get(account_id) != owner
            or character_id
            not in (getattr(self.shared, "publication_recovery_aborted", None) or {})
        ):
            raise ValueError("Aborted native return lost its selected owner")

    def packets(self):
        from copy import copy
        from wakfu_server.combat_abandon import _terminal_packets, placement_runtime

        actor = self.shared.fight.actors.get(self.owner.character_id)
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != self.owner.account_id
        ):
            raise ValueError("Aborted native return has no owned participant")
        runtime = copy(placement_runtime(self.shared.fight, self.shared.runtime))
        # This codec only reads the original roster/counters. Durable abort,
        # health, grants and the authoritative winner are never changed here.
        if getattr(self.shared, "settlement_ready", False):
            from wakfu_server.combat_results import terminal_event

            packets = [terminal_event(runtime), runtime._flush()]
        else:
            packets = _terminal_packets(runtime, actor.team)
        # Original cvF.eIl -> buH.W -> kv selects the second UID list;
        # aUH emits its negated membership flag for the actual local actor.
        # Company members on the same native team have the same membership.
        import struct

        body = packets[0][1]
        second = 14 + 8 * body[13]
        count = body[second]
        ids = struct.unpack_from(">" + "q" * count, body, second + 1)
        self.callback_flag = self.owner.character_id not in ids
        return packets

    def acknowledge(self, body):
        from wakfu_server.combat_results import continuation

        if (
            self.callback_flag is None
            or continuation(self.shared.fight.id, body) != self.callback_flag
        ):
            raise ValueError("Aborted native return has a foreign native callback flag")
        self.acknowledged = True


def written_fight_id(data, previous):
    """Observe actual successful12847 writes; never infer native construction."""
    import struct

    offset = 0
    while offset < len(data):
        length, opcode = struct.unpack_from(">IH", data, offset)
        if length < 6 or offset + length > len(data):
            raise ValueError("Invalid actually written combat frame")
        if opcode == 12847:
            previous = struct.unpack_from(">i", data, offset + 6)[0]
        offset += length
    return previous


class Connection:
    """Serialize frames sent by the receiver and other players' workers."""

    def __init__(self, socket):
        self.socket = socket
        self.write_lock = threading.RLock()
        self.item_spell_uids = set()
        from wakfu_server.combat_instance_publication import InstancePublicationTracker
        from wakfu_server.combat_external_markers import MarkerPublications

        self.instance_publications = InstancePublicationTracker()
        self.native_fight_id = None
        self.marker_publications = MarkerPublications()
        self.native_instance_scope = lambda: None
        self.interactive_publication = None
        self.interactive_scope = lambda: None
        self.interactive_trace = []
        self.ranch_scene_refresh = None

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def sendall(self, data):
        with PROFILER.span("network.send_lock"):
            self.write_lock.acquire()
        try:
            publication_scope = self.native_instance_scope()
            if self.interactive_publication is not None:
                self.interactive_trace.clear()
                data = self.interactive_publication.transform(
                    data, self.interactive_scope()
                )
            with PROFILER.span("network.send"):
                if data:
                    self.socket.sendall(data)
            self.instance_publications.after_write(data, publication_scope)
            self.marker_publications.after_write(data, publication_scope)
            self.native_fight_id = written_fight_id(data, self.native_fight_id)
            for event in self.interactive_trace:
                record(event="interactive_wire_publication", **event)
        except BaseException:
            self.instance_publications.invalidate()
            self.marker_publications.reset(None)
            if self.interactive_publication is not None:
                self.interactive_publication.clear()
            raise
        finally:
            self.interactive_trace.clear()
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
            objectives_updates = getattr(connection, "objectives_updates", None)
            if objectives_updates is not None and not connection.pending():
                import select

                readable, _, _ = select.select(
                    (connection, objectives_updates.reader), (), (), 1.0
                )
                if objectives_updates.reader in readable:
                    objectives_updates.drain()
                    if on_idle is not None and not on_idle():
                        raise ValueError("Session expired or replaced")
                if connection not in readable:
                    if not readable and on_idle is not None and not on_idle():
                        raise ValueError("Session expired or replaced")
                    continue
            chunk = connection.recv(count - len(data))
        except socket.timeout:
            if on_idle is None or not on_idle():
                raise ValueError("Session expired or replaced")
            continue
        if not chunk:
            raise EOFError()
        data.extend(chunk)
    return bytes(data)


def record_combat_wire_effect(connection, service, opcode, body):
    """Optionally log safe identity fields for outgoing native 12613 packets."""
    if not COMBAT_WIRE_TRACE or service != "world" or opcode != 12613:
        return
    try:
        from wakfu_server.combat_wire_diagnostics import (
            effect_application_metadata,
        )

        metadata = effect_application_metadata(opcode, body)
        if metadata is None:
            return
        record(
            event="combat_effect_wire",
            service=service,
            direction="out",
            target_connection_id=getattr(connection, "trace_id", None),
            **metadata,
        )
    except Exception:
        # Diagnostics run after the successful write and must never affect it.
        return


def publish_item_spell_updates(connection, service, opcode, body):
    """Remember delivered native item spell additions."""
    if service != "world":
        return
    if opcode == 12503 and len(body) >= 8 and (len(body) - 8) % 14 == 0:
        seen = getattr(connection, "item_spell_uids", None)
        if seen is not None:
            for offset in range(8, len(body), 14):
                seen.add(struct.unpack_from(">q", body, offset + 4)[0])
    if opcode == 13873 and len(body) >= 12 and body[:8] == struct.pack(">II", 1, 4):
        callback = getattr(connection, "account_item_spell_update", None)
        if callback is not None:
            callback()


def send(connection, service, opcode, body):
    if getattr(connection, "is_bot_peer", False):
        return
    write = lambda: connection.sendall(struct.pack(">IH", 6 + len(body), opcode) + body)
    if service == "world" and NATIVE_PLANTING_BONUS:
        PLANTING_BONUSES.deliver(connection, ((opcode, body),), write)
    else:
        write()
    record(
        service=service,
        direction="out",
        opcode=opcode,
        bytes=len(body),
        target_connection_id=getattr(connection, "trace_id", None),
    )
    record_combat_wire_effect(connection, service, opcode, body)
    publish_item_spell_updates(connection, service, opcode, body)


def send_batch(connection, service, packets):
    if getattr(connection, "is_bot_peer", False):
        return
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
    write = lambda: connection.sendall(b"".join(frames))
    if service == "world" and NATIVE_PLANTING_BONUS:
        PLANTING_BONUSES.deliver(connection, packets, write)
    else:
        write()
    for opcode, body in packets:
        record(
            service=service,
            direction="out",
            opcode=opcode,
            bytes=len(body),
            target_connection_id=getattr(connection, "trace_id", None),
        )
        record_combat_wire_effect(connection, service, opcode, body)
        publish_item_spell_updates(connection, service, opcode, body)


from wakfu_server.mount_publication import snapshot as mount_snapshot


def consumable_state_packets(character):
    from wakfu_server.consumable_buff_wire import snapshot

    return snapshot(character, allocate_action=lambda: next(LOCAL_WORLD_ACTIONS))


def world_state_packets(character, *, include_territory=True, reset_riding=False):
    from wakfu_server.personal_ecology import snapshot as ecology_snapshot

    from wakfu_server.emotes import retained as emote_snapshot
    from wakfu_server.world_resurrection import snapshot as death_snapshot
    from wakfu_server.territory_bonus_wire import snapshot as territory_snapshot

    return (
        *mount_snapshot(character, reset_riding=reset_riding),
        *ecology_snapshot(character),
        *emote_snapshot(character),
        *consumable_state_packets(character),
        *(
            territory_snapshot(character["id"], character.get("territory_state_id"))
            if include_territory
            else ()
        ),
        *death_snapshot(STORE, character),
    )


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


@contextmanager
def ecology_admin_coordination(scope):
    """Keep administrative application on the existing live-world fences."""
    if not COMBAT_TEST:
        raise ValueError("Persistent ecology administration is unavailable")
    with (
        COMBAT_GROUPS.lock,
        HARVESTS.lock,
        PLANTINGS.publisher_lock,
        PLANTINGS.lock,
        PLANTINGS.growth_lock,
    ):
        yield


def publish_ecology_admin_outcome(outcome):
    """Publish committed scopes without capturing a mutable player session."""
    if outcome.get("command") in ("!nuke", "!nuke-all", "!nuke-all-flora"):
        from wakfu_server.ecology_admin_runtime import cancel_plantings

        cancel_plantings(PLANTINGS, outcome)
    for map_id, instance_id, opcode, payload in outcome.get("location_packets", ()):
        WORLD.emit_location(map_id, instance_id, opcode, payload)
    from wakfu_server.ecology_context import packet as ecology_packet
    from wakfu_server.territory_cells import region_at

    with WORLD.lock:
        recipients = tuple(WORLD.players.values())
    for player_generation, peer, player in recipients:
        for map_id, instance_id, region_id in outcome.get("scopes", ()):
            if (player["map_id"], player.get("instance_id", 0)) != (
                map_id,
                instance_id,
            ):
                continue
            if (
                region_id is not None
                and region_at(map_id, player["x"], player["y"]) != region_id
            ):
                continue
            try:
                packet = ecology_packet(STORE, player, open_test_policy=OPEN_PLANTING)
            except ValueError as error:
                record(
                    event="ecology_admin_context_unavailable",
                    actor_id=player["id"],
                    reason=str(error),
                )
            else:
                with WORLD.lock:
                    active = WORLD.players.get(player["id"])
                    if (
                        active is not None
                        and active[0] == player_generation
                        and all(
                            active[2].get(key) == player.get(key)
                            for key in ("map_id", "instance_id", "x", "y", "z")
                        )
                    ):
                        WORLD.send_to(player["id"], player_generation, *packet)
            break


def validate_ecology_admin_job(db, job):
    if STOPPING.is_set():
        raise EcologyAdminCancelled("World is stopping")


ECOLOGY_ADMIN_JOBS = EcologyAdminJobs(
    STORE,
    COMBAT_GROUPS if COMBAT_TEST else None,
    players=WORLD.ecology_snapshot,
    coordination=ecology_admin_coordination,
    publish=publish_ecology_admin_outcome,
    validate_actor=validate_ecology_admin_job,
)


def submit_ecology_admin_command(
    connection, service, account_id, generation, character, command, text
):
    """Accept an authorized ecology command before any foreground checkpoint."""
    if command not in ASYNC_ECOLOGY_COMMANDS:
        return None
    if len(text.split()) != 1:
        raise ValueError("Uso: " + command)
    from wakfu_server.ecology_feedback import information

    actor_id = character["id"]

    def notify(completed):
        record(
            event="ecology_admin_job_finished",
            actor_id=actor_id,
            command=command,
            handle=completed["handle"],
            status=completed["status"],
            elapsed_ms=completed.get("elapsed_ms"),
            worker_pid=completed.get("worker_pid"),
            error_type=completed.get("error_type"),
            error_code=completed.get("error_code"),
            reason=completed.get("reason"),
            traceback=completed.get("traceback"),
            added=completed.get("added", 0),
            removed=completed.get("removed", 0),
        )
        WORLD.send_to(actor_id, generation, *information(completed["message"]))

    receipt = ECOLOGY_ADMIN_JOBS.request(
        account_id=account_id,
        generation=generation,
        character=character,
        command=command,
        notify=notify,
    )
    send(connection, service, *information(receipt["message"]))
    record(
        event="ecology_admin_job_submitted",
        actor_id=actor_id,
        command=command,
        handle=receipt["handle"],
        coalesced=receipt["coalesced"],
    )
    return {"message": receipt["message"], "ecology_job": receipt}


from wakfu_server.party_dispatch import Parties
from wakfu_server.chat_channels import Channels
from wakfu_server.exchange_dispatch import Exchanges

PARTIES = Parties(STORE, WORLD)
CHANNELS = Channels(STORE, WORLD)
EXCHANGES = Exchanges(STORE, WORLD)
BOTS_BRIDGE = None


def publish_bot_chat(sender, text, *, recipient=None):
    if BOTS_BRIDGE is None:
        return
    try:
        BOTS_BRIDGE.runtime.observe_chat(sender, text, recipient=recipient)
    except Exception as error:
        # Bot observers cannot interrupt successful human chat delivery.
        record(event="bot_chat_observation_failed", reason=type(error).__name__)


def deliver_bot_whisper(generation, character, recipient, text):
    delivered = WORLD.private_chat(
        generation,
        character["id"],
        character["account_id"],
        recipient,
        text,
        block_reason=SOCIAL_CONTACTS.private_chat_block_reason,
        valid_session=lambda entry: STORE.current_character_session(
            entry[2]["account_id"], entry[0], entry[2]["id"]
        ),
    )
    if not delivered:
        raise ValueError("Bot whisper recipient is unavailable")


from wakfu_server.guild_dispatch import (
    Guilds,
    REQUEST_OPCODES as GUILD_REQUEST_OPCODES,
)


def guild_local_entity():
    captured = fixture(15548)
    if (
        len(captured) < 11
        or len(captured) != 10 + struct.unpack_from(">H", captured, 8)[0]
    ):
        raise ValueError("Invalid native guild synchronization fixture")
    return wire.minimal_entity(captured[10:], {"level": 1})


def guild_company_packet(character, model):
    from wakfu_server.hero_wire import company
    from wakfu_server.nation_state import nation_id

    return company(
        character["account_id"],
        character["id"],
        guild_id=model["guildId"] if model else 0,
        nation_id=nation_id(character),
        company_snapshot=character["equipment_criterion_context"]["company_snapshot"],
    )


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


def refresh_guild(generation, character):
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout

    try:
        GUILDS.refresh(character["account_id"], generation, character["id"])
    except (ValueError, DatabaseError, PoolTimeout) as error:
        record(
            event="guild_refresh_failed", actor_id=character["id"], reason=str(error)
        )


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


def send_native_planting_bonus(connection, character):
    if NATIVE_PLANTING_BONUS:
        PLANTING_BONUSES.publish(
            connection,
            character,
            lambda packets: send_batch(connection, "world", packets),
        )


def send_planting_context(connection, character, *, include_weather=True):
    send_native_planting_bonus(connection, character)
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
    try:
        from wakfu_server.territory_bonuses import refresh_world

        with WORLD.lock:
            entry = WORLD.players.get(character["id"])
            bonus_generation = (
                entry[0] if entry is not None and entry[1] is connection else None
            )
        refreshed = dict(character)
        bonus_packets = refresh_world(STORE, refreshed, generation=bonus_generation)
        for key in (
            "hp",
            "max_hp",
            "hp_damage",
            "health_dead",
            "hp_zero_valid",
            "territory_health_projection",
            "equipment_hp_projection",
        ):
            if key in refreshed:
                character[key] = refreshed[key]
        for bonus_packet in bonus_packets:
            send(connection, "world", *bonus_packet)
        character["territory_stat_bonuses"] = refreshed["territory_stat_bonuses"]
        character["_published_territory_stat_bonuses"] = refreshed[
            "_published_territory_stat_bonuses"
        ]
        character["territory_state_id"] = refreshed["territory_state_id"]
        character["_published_territory_state_id"] = refreshed[
            "_published_territory_state_id"
        ]
        REGIONAL_BONUSES.mark_context_refreshed(character)
        if bonus_generation is not None:
            WORLD.update_territory_projection(
                bonus_generation,
                character,
                peer=connection,
                bonuses=character["territory_stat_bonuses"],
                regional_state_id=character["territory_state_id"],
            )
    except ValueError as error:
        record(
            event="territory_bonus_unavailable",
            actor_id=character["id"],
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
        forecast = weather.get("forecast_payload")
        if forecast is None:
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
def join_world(
    generation,
    connection,
    character,
    *,
    hydrate_heroes=True,
    defer_scene_snapshot=False,
):
    from wakfu_server.profession_store import ensure_all_learned
    from wakfu_server.consumable_world_lifecycle import synchronize

    character.update(
        synchronize(
            STORE, character["account_id"], generation, character, mode="resume"
        )
    )
    # A fresh scene load creates a new native world, unlike spectator return.
    with connection.write_lock:
        connection.marker_publications.reset(connection.native_instance_scope())

    profession = ensure_all_learned(
        STORE,
        character["account_id"],
        generation,
        character["id"],
    )
    for packet in profession["packets"]:
        send(connection, "world", *packet)
    for packet in HAVEN_BAG_EXTERIORS.snapshots(character):
        send(connection, "world", *packet)
    send_planting_context(connection, character)
    if not defer_scene_snapshot:
        for packet in PLANTINGS.snapshots(
            character["map_id"], character["instance_id"], position=character
        ):
            send(connection, "world", *packet)
    from wakfu_server import npc_world, npc_placements

    with STORE.connection() as db:
        dialogue_npcs = npc_world.load_scene(
            db, character["map_id"], character["instance_id"]
        )
        positioned_npcs = npc_placements.load_scene(
            db, character["map_id"], character["instance_id"]
        )
    for npc in dialogue_npcs:
        send(connection, "world", *npc_world.spawn(npc))
    for npc in positioned_npcs:
        send(connection, "world", *npc_placements.spawn(npc))
    from wakfu_server import heroes, hero_wire

    hero_roster = heroes.ensure_company_party(
        STORE, character["account_id"], generation, character["id"]
    )
    if hydrate_heroes:
        for hero in hero_roster["heroes"]:
            send(connection, "world", *hero_wire.activate(OWNED_HERO_TEMPLATE, hero))
            send(connection, "world", *hero_wire.statistics(hero))
    # Repeated cue activation replaces owned objects without an activation
    # event. COMPANY rebuilds native hero rows from the final owned registry.
    send(
        connection,
        "world",
        *hero_wire.company(
            character["account_id"],
            character["id"],
            guild_id=(character.get("guild_native") or {}).get("guildId", 0),
            nation_id=character.get("nation_id", 0),
            company_snapshot=character["equipment_criterion_context"][
                "company_snapshot"
            ],
        ),
    )
    if not COMBAT_TEST:
        WORLD.join(generation, connection, character)
        refresh_guild(generation, character)
        refresh_party(generation, character)
        return
    from wakfu_server.combat_monster_world import spawn_group

    # Snapshot and publishes use the same lock as group claims.
    with COMBAT_GROUPS.lock:
        WORLD.join(generation, connection, character)
        from wakfu_server.ecology_admin import admin_removed_packets

        with STORE.connection() as db:
            for packet in admin_removed_packets(
                db, character["map_id"], character["instance_id"]
            ):
                send(connection, "world", *packet)
        for packet in monster_corpse_snapshot(
            character["map_id"], character["instance_id"], peer=connection
        ):
            send(connection, "world", *packet)
        if not defer_scene_snapshot:
            for group in COMBAT_GROUPS.available(
                character["map_id"], character["instance_id"]
            ):
                send(
                    connection,
                    "world",
                    12608,
                    owned_scene_spawn_group(group["members"], group_id=group["key"][2]),
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

    refresh_guild(generation, character)


def owned_scene_spawn_group(members, *, group_id, direction=3):
    """Keep native NPC world identity aligned with durable private ownership."""
    from wakfu_server.combat_monster_world import spawn_group
    from wakfu_server.guild_haven_world import scene_context

    members = tuple(members)
    if not members:
        raise ValueError("Cannot publish an empty monster group")
    first = members[0]
    context = scene_context(STORE, first["map_id"], first["instance_id"])
    return spawn_group(
        members, group_id=group_id, direction=direction, world_context=context
    )


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
                owned_scene_spawn_group(group["members"], group_id=group_id),
            )
            for packet in HARVESTS.availability_for(
                map_id, instance_id, [m["id"] for m in group["members"]]
            ):
                WORLD.emit_location(map_id, instance_id, *packet)


def reconcile_closed_rift_login(
    store, positions, account_id, generation, character, *, live_reconnect=False
):
    """Return an interrupted, closed Rift company through its native exterior.

    This is login recovery, not a fabricated portal interaction. Native paid
    or conditional exits are never inferred, and terminal earned runs retain
    their ordinary report/exit flow. Relocation owns all company/position CAS.
    """
    instance_id = character.get("instance_id", 0)
    if live_reconnect or type(instance_id) is not int or instance_id <= 0:
        return None
    with store.connection() as db:
        row = db.execute(
            "SELECT r.catalog FROM rift_instances r JOIN combat_fights f ON f.id=r.fight_id "
            "WHERE r.instance_id=%s AND r.status='closed' AND f.status='aborted' "
            "AND NOT EXISTS(SELECT 1 FROM rift_settlement_receipts s "
            "WHERE s.instance_id=r.instance_id)",
            (instance_id,),
        ).fetchone()
    if row is None:
        return None
    catalog = row["catalog"]
    if catalog["map_id"] != character["map_id"]:
        raise ValueError("Closed Rift login differs from its native interior")
    from wakfu_server import generic_transports, rift_exit

    destinations = []
    for entry in catalog["objects"]:
        if entry["type"] != "Teleporter" or entry["map_id"] != character["map_id"]:
            continue
        source = generic_transports.source(entry["map_id"], entry["id"])
        if source is None:
            continue
        for target in source["destinations"]:
            if (
                target["criterion"].strip()
                or target["cyW"] != 0
                or target["cyX"] != 0
                or target["cyZ"] >= 0
                or target["native_altitude_walkable"] is not True
                or target["map_id"] == character["map_id"]
            ):
                continue
            destinations.append(
                {
                    **{key: target[key] for key in ("map_id", "x", "y", "z")},
                    "instance_id": 0,
                }
            )
    if len(destinations) != 1:
        raise ValueError("Closed Rift login requires one unconditional native exit")
    moved = rift_exit.relocate(
        store,
        positions,
        account_id,
        generation,
        character["id"],
        character,
        destinations[0],
    )
    if moved is None:
        raise ValueError("Closed Rift login lost its owned departure scope")
    return store.character(account_id, character["id"])


def acknowledge_rift_login_bootstrap(account_id, generation, character):
    """Called only after initial native bootstrap and World join succeeded."""
    from wakfu_server import rift_transition_delivery

    destination = rift_transition_delivery.pending(
        account_id, generation, character["id"]
    )
    if destination is not None and all(
        character[key] == destination[key]
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        rift_transition_delivery.acknowledge(
            account_id, generation, character["id"], destination
        )


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
    if (character.get("map_id"), character.get("instance_id", 0)) == (1385, 0):
        from wakfu_server import npc_protectors

        with STORE.connection() as db:
            options["protector_records"] = npc_protectors.bootstrap_records(
                db, character
            )
    if is_dungeon_run(character.get("instance_id", 0)):
        from wakfu_server import dungeon_context

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
    from wakfu_server import dungeon_native_flow

    if dungeon_native_flow.enabled(configuration["topology"]):
        return tuple(messages) + dungeon_native_flow.packets(
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


def native_current_xp_rate():
    """Publish the canonical server rate through the native single-key carrier."""
    with STORE.connection() as db:
        policy = db.execute(
            "SELECT v.xp_rate_bp FROM combat_reward_policy_active a "
            "JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton"
        ).fetchone()
    if policy is None:
        raise ValueError("Missing canonical XP presentation policy")
    return wire.native_xp_rate_packet(policy["xp_rate_bp"])


def replay(connection, start, end, account_id, character=None, *, generation=None):
    from wakfu_server.haven_chest_wire import CAPTURE_STATE_OPCODES

    account_characters = None
    registry_actor_ids = ()
    if character is not None:
        from wakfu_server.combat_drop_delivery import temporary_section

        with STORE.connection() as db:
            STORE.lock_character(db, account_id, generation, character["id"])
            character = {
                **character,
                "temporary_inventory_section": temporary_section(db, character["id"]),
            }
            registry_actor_ids = tuple(
                row["actor_id"]
                for row in db.execute(
                    "SELECT actor_id FROM world_dialogue_npcs "
                    "UNION SELECT actor_id FROM world_native_npc_placements"
                )
            )

    def owned_characters():
        nonlocal account_characters
        if account_characters is None:
            account_characters = STORE.characters(account_id)
        return account_characters

    if character is not None and start == 45:
        send(connection, "world", *native_current_xp_rate())
    for frame in FRAMES[start:end]:
        if frame["direction"] == "in":
            if frame["opcode"] in (12705, 12728):
                # Reference running effects belong to the captured actor. An
                # identity rewrite can target our player with foreign visual
                # state; only authoritative live emitters may publish effects.
                continue
            if frame["opcode"] in CAPTURE_STATE_OPCODES:
                # Account chest compartments and updates belong exclusively
                # to PostgreSQL-owned custody, never the reference account.
                continue
            if frame["opcode"] == 13369:
                # Authoritative owned task/gift publication replaces fixture state.
                continue
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
            if frame["opcode"] == 22995:
                # Never replay an official account's HTTP shop credentials.
                continue
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
                from wakfu_server.exploration_secrets import (
                    account_packet as exploration_account_packet,
                )

                with STORE.connection() as db:
                    secret_packet = exploration_account_packet(db, account_id)
                send(connection, "world", *secret_packet)
                continue
            if (
                character is not None
                and frame["opcode"] == 13873
                and original[:8] == struct.pack(">II", 1, 1)
            ):
                from wakfu_server.hero_wire import company as hero_company

                send(
                    connection,
                    "world",
                    *hero_company(
                        account_id,
                        character["id"],
                        guild_id=(character.get("guild_native") or {}).get(
                            "guildId", 0
                        ),
                        nation_id=character.get("nation_id", 0),
                        company_snapshot=character["equipment_criterion_context"][
                            "company_snapshot"
                        ],
                    ),
                )
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 10):
                from wakfu_server.emotes import (
                    packet as emote_account_packet,
                )

                send(connection, "world", *emote_account_packet(STORE, account_id))
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 11):
                from wakfu_server.haven_bag_furniture_knowledge import (
                    packet as furniture_account_packet,
                )

                send(connection, "world", *furniture_account_packet(STORE, account_id))
                from wakfu_server.haven_ranch_building_knowledge import (
                    packet as ranch_building_account_packet,
                )

                send(
                    connection,
                    "world",
                    *ranch_building_account_packet(STORE, account_id),
                )
                continue
            if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 1, 18):
                # The preceding furniture component publishes owned Ranch
                # knowledge; never overwrite it with the captured template.
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
            if frame["opcode"] == 22790:
                from wakfu_server import companions

                with STORE.connection() as companion_db:
                    companion_packet = companions.collection_packet(
                        companions.collection(companion_db, account_id)
                    )
                send(connection, "world", *companion_packet)
                continue
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
            if frame["opcode"] == 23053:
                from wakfu_server.hero_wire import (
                    configuration as hero_configuration,
                )

                send(connection, "world", *hero_configuration(original))
                send(connection, "world", *native_current_xp_rate())
                continue
            if frame["opcode"] in (23992, 23548):
                from wakfu_server.selection_capacity import (
                    packet as capacity_packet,
                )

                send(connection, "world", *capacity_packet(STORE.max_characters))
                if frame["opcode"] == 23992:
                    continue
            if frame["opcode"] == 23548:
                body = wire.character_list(CHARACTERS, account_id, owned_characters())
            elif frame["opcode"] == 12393:
                body = wire.attribute_sheets(original, owned_characters())
            elif frame["opcode"] == 12608:
                body = wire.without_captured_players(original)
                if character is not None:
                    from wakfu_server.npc_capture_scene import (
                        filter_reference_actors,
                    )

                    body = filter_reference_actors(
                        body, character, registry_actor_ids=registry_actor_ids
                    )
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
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.ecology_feedback import information

    selected = loaded = False
    scene_sync = SceneSync()
    static_sync_pending = False
    static_sync_attempts = 0
    static_sync_due = time.monotonic() + 0.75
    world_snapshot_pending = False
    world_snapshot_due = time.monotonic() + 0.75
    world_snapshot_identity = None
    account_id = generation = character = None
    hero_switch_pending = None
    bag_session = None
    ranch_session = None
    chest_opening = None
    paid_container_ticket = None
    guild_chest_session = None
    fight = None
    combat_session = None
    pending_terminal_world_recovery = None
    pending_combat_return = None
    world_respawn_retry_at = 0.0
    from wakfu_server.combat_return_command import PendingEmergencyCommand

    pending_return_command = PendingEmergencyCommand()
    publication_recovery_shared = None
    publication_recovery_attempt_token = None
    publication_recovery_attempt_due = 0.0
    publication_recovery_notice_token = None
    publication_recovery_return_due = 0.0
    aborted_native_return = None
    spectator_session = None
    npc_dialogue_session = None
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
    last_consumable_tick = 0
    last_ranch_cycle_tick = 0
    guild_daily_boundary = (None, None)
    pet_hibernation_due = 0.0
    last_shop_refresh = 0
    last_session_renewal = 0
    last_dungeon_transition_poll = 0.0
    last_dungeon_transition_report = None
    from wakfu_server.placement_deadline import Deadline

    def active_private_session():
        return ranch_session or bag_session

    def refresh_owned_character(saved):
        """Merge durable rewards/health without persisting a private scene location."""
        session = active_private_session()
        if session is None:
            return saved
        if not session.owns(character):
            raise ValueError("Combat return requires its current private scene")
        if ranch_session is not None:
            ranch_session.validate_lease(generation)
        return session.refresh(character, saved)

    def refresh_item_mutation_character(owner_id=None):
        from wakfu_server.combat_lifecycle import outside_progression

        owner_id = character["id"] if owner_id is None else owner_id
        updated = STORE.character(account_id, owner_id)
        if owner_id == character["id"]:
            updated = refresh_owned_character(updated)
        send(connection, service, *outside_progression(updated, wp=COMBAT_TEST_WP))
        return updated

    def publish_consumable_character(updated):
        from wakfu_server.consumable_world_publication import publish

        publish(
            WORLD,
            generation,
            updated,
            send=lambda opcode, body: send(connection, service, opcode, body),
        )

    def publish_nation_character(updated):
        nonlocal character
        from wakfu_server import guild_wire, nation_state

        updated = dict(updated)
        updated.update(
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            direction=character["direction"],
            **position,
        )
        selected = updated["id"] == character["id"]
        if selected:
            character = updated
            send(
                connection,
                service,
                15548,
                wire.adapt(15548, fixture(15548), account_id, character),
            )
            for packet in consumable_state_packets(character):
                send(connection, service, *packet)
            send(
                connection,
                service,
                *guild_company_packet(character, character.get("guild_native")),
            )
        else:
            from wakfu_server.hero_wire import refresh

            send(connection, service, *refresh(OWNED_HERO_TEMPLATE, updated))
        guild = updated.get("guild_native")
        packet = guild_wire.remote_actor_update(
            updated["id"],
            guild["guildId"] if guild else 0,
            guild["blazon"] if guild else 0,
            guild["level"] if guild else 0,
            guild["name"] if guild else "",
            nation_id=nation_state.nation_id(updated),
            nation_synchro=nation_state.synchro(updated),
        )
        if selected:
            WORLD.update(generation, updated, *packet, include_sender=False)
        else:
            WORLD.broadcast(generation, character["id"], *packet, include_sender=False)
        return updated

    def spawn_inventory_test_actor(body):
        from wakfu_server import item_test_spawns

        if item_test_spawns.action_class(body) is None:
            return False
        if bag_session is not None or ranch_session is not None:
            raise ValueError("Developer test actors require ordinary public ground")
        location = dict(character, **position)
        with COMBAT_GROUPS.lock:
            occupied = [
                tuple(row[key] for key in ("x", "y", "z"))
                for row in WORLD.ecology_snapshot()
                if (row["map_id"], row["instance_id"])
                == (location["map_id"], location["instance_id"])
            ]
            result = item_test_spawns.use(
                STORE,
                COMBAT_GROUPS,
                account_id,
                generation,
                character["id"],
                body,
                in_fight=fight is not None or combat_session is not None,
                location=location,
                occupied_cells=occupied,
            )
            if result["applied"]:
                for packet in result["world_packets"]:
                    WORLD.emit_location(*result["key"][:2], *packet)
        record(
            event="developer_item_test_actor",
            actor_id=character["id"],
            group_key=result["key"],
            created=result["applied"],
            consumed=0,
        )
        return True

    def activate_world_phoenix(body):
        nonlocal character
        from wakfu_server.phoenix_points import activate

        if active_private_session() is not None or spectator_session is not None:
            raise ValueError("Activa el fénix desde su mapa público")
        live = dict(character, **position)
        result = activate(
            STORE,
            account_id,
            generation,
            character["id"],
            body,
            in_fight=fight is not None or combat_session is not None,
            location=live,
        )
        character = dict(
            result["character"],
            **{
                key: live[key]
                for key in ("map_id", "instance_id", "x", "y", "z", "direction")
            },
        )
        with WORLD.lock:
            entry = WORLD.players.get(character["id"])
            if entry is not None and entry[0] == generation:
                WORLD.players[character["id"]] = (generation, entry[1], dict(character))
        # Original bDB already sets the owned point and displays soulLinked
        # before12870. Persist without reconstructing the actor or its effects.
        record(
            event="phoenix_bound",
            actor_id=character["id"],
            phoenix_id=result["saved_phoenix_id"],
            changed=result["applied"],
        )

    def request_world_respawn(body):
        from wakfu_server.world_respawn import request

        if (
            fight is not None
            or combat_session is not None
            or pending_combat_return is not None
            or pending_terminal_world_recovery is not None
            or publication_recovery_shared is not None
            or hero_switch_pending is not None
            or active_private_session() is not None
            or spectator_session is not None
            or COMBAT_SESSIONS.lookup_character(character["id"]) is not None
        ):
            raise ValueError("Completa el regreso al mundo antes de volver al fénix")
        source = dict(character, **position)

        def live():
            identity = WORLD.live_identity(character_id=character["id"])
            return bool(
                identity is not None
                and identity[0] == generation
                and identity[1]["account_id"] == account_id
                and all(
                    identity[1][key] == source[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                )
            )

        result = request(
            STORE,
            POSITIONS,
            account_id,
            generation,
            character["id"],
            body,
            source=source,
            validate_live=live,
        )
        record(
            event="world_respawn_committed",
            actor_id=character["id"],
            replayed=result["replayed"],
            policy=result["destination"]["world_respawn"]["policy"],
        )
        return deliver_rift_transition()

    def prepare_world_respawn_delivery(destination, saved):
        nonlocal world_respawn_retry_at
        from wakfu_server.world_respawn import release_position, publication
        from wakfu_server.position_buffer import PositionOwnerBusy
        from wakfu_server.position_redis import PositionJournalError

        metadata = destination.get("world_respawn")
        if metadata is None:
            return True
        if time.monotonic() < world_respawn_retry_at:
            return False
        try:
            with POSITIONS.account_barrier(account_id, blocking=False):
                if not metadata["position_released"]:
                    release_position(
                        STORE,
                        POSITIONS,
                        account_id,
                        generation,
                        character["id"],
                        destination,
                    )
                    metadata["position_released"] = True
                if not metadata["occupation_published"]:
                    send_batch(connection, service, publication(saved))
                    metadata["occupation_published"] = True
        except (
            PositionOwnerBusy,
            PositionJournalError,
            DatabaseError,
            PoolTimeout,
        ) as error:
            world_respawn_retry_at = time.monotonic() + 0.25
            record(
                event="world_respawn_delivery_pending",
                actor_id=character["id"],
                error_type=type(error).__name__,
            )
            return False
        world_respawn_retry_at = 0.0
        return True

    def resurrect_world_character(body):
        nonlocal character
        from contextlib import ExitStack
        from wakfu_server.world_resurrection import resurrect

        if not isinstance(body, bytes) or len(body) != 8:
            raise ValueError("Invalid native BenKO target packet")
        target_id = struct.unpack(">q", body)[0]
        if target_id <= 0 or fight is not None or combat_session is not None:
            raise ValueError("BenKO requires an exploration target")
        with STORE.connection() as db:
            row = db.execute(
                "SELECT c.account_id,s.character_id AS leader_id FROM characters c "
                "JOIN sessions s ON s.account_id=c.account_id "
                "WHERE c.id=%s AND c.deleted_at IS NULL AND s.expires_at>%s",
                (target_id, STORE.now()),
            ).fetchone()
        if row is None:
            raise ValueError("Resurrection target is not connected")
        with ExitStack() as barriers:
            for owner in sorted({account_id, row["account_id"]}):
                barriers.enter_context(POSITIONS.account_barrier(owner, blocking=False))
            # Account barriers fence positions and ownership; the global World
            # lock is released before SQL so unrelated players can keep moving.
            with WORLD.lock:
                source_entry = WORLD.players.get(character["id"])
                target_entry = WORLD.players.get(row["leader_id"])
                if (
                    source_entry is None
                    or source_entry[0] != generation
                    or target_entry is None
                    or target_entry[2]["account_id"] != row["account_id"]
                ):
                    raise ValueError("Resurrection target left the world")
                target_generation = target_entry[0]
                target_leader = dict(target_entry[2])
            live = {
                target_id: dict(target_leader, generation=target_generation),
                character["id"]: dict(character, **position, generation=generation),
            }
            result = resurrect(
                STORE,
                account_id,
                generation,
                character["id"],
                body,
                target_generation=target_generation,
                live_locations=live,
            )
            for packet in result["donor_packets"]:
                send(connection, service, *packet)
            target = result["target"]
            if result["donor"]["id"] == character["id"]:
                updated = refresh_owned_character(result["donor"])
                character = dict(
                    updated,
                    **{
                        key: character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                    },
                )
            if target_id == character["id"]:
                character = dict(
                    target,
                    **{
                        key: character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                    },
                )
            with WORLD.lock:
                current_target = WORLD.players.get(target_leader["id"])
                if (
                    current_target is not None
                    and current_target[0] == target_generation
                ):
                    for packet in result["target_packets"]:
                        WORLD.send_to(target_leader["id"], target_generation, *packet)
                    if target_id == target_leader["id"]:
                        target = dict(
                            target,
                            **{
                                key: current_target[2][key]
                                for key in (
                                    "map_id",
                                    "instance_id",
                                    "x",
                                    "y",
                                    "z",
                                    "direction",
                                )
                            },
                        )
                        for packet in result["world_packets"]:
                            WORLD.update(target_generation, target, *packet)
                    else:
                        for packet in result["world_packets"]:
                            WORLD.broadcast(
                                target_generation, target_leader["id"], *packet
                            )
            record(
                event="world_character_resurrected",
                actor_id=character["id"],
                target_id=target_id,
                donor_id=result["donor"]["id"],
                hp=target["hp"],
            )

    def publish_account_item_spells(*, seed=False):
        if (
            not loaded
            or character is None
            or fight is not None
            or combat_session is not None
        ):
            return
        from wakfu_server.item_spell_publication import account_inventory_packets

        with connection.write_lock:
            try:
                packets = account_inventory_packets(
                    STORE,
                    account_id,
                    generation,
                    character["id"],
                )
            except ValueError:
                return  # An obsolete socket cannot publish a replacement lease's book.
            for opcode, payload in packets:
                entries = []
                for offset in range(8, len(payload), 14):
                    uid = struct.unpack_from(">q", payload, offset + 4)[0]
                    if seed:
                        connection.item_spell_uids.add(uid)
                    elif uid not in connection.item_spell_uids:
                        entries.append(payload[offset : offset + 14])
                if entries:
                    send(connection, service, opcode, payload[:8] + b"".join(entries))

    def refresh_pet_hibernation():
        nonlocal character, pet_hibernation_due
        from wakfu_server import pet_hibernation
        from wakfu_server.mount_publication import pet_packet

        deadlines = []
        with STORE.connection() as db:
            heroes = db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                (account_id,),
            ).fetchall()
        for owner_id in (character["id"], *(row["character_id"] for row in heroes)):
            result = pet_hibernation.refresh(STORE, account_id, generation, owner_id)
            if result["next_deadline_ms"] is not None:
                deadlines.append(result["next_deadline_ms"])
            if not result["changed"]:
                continue
            saved = result["character"]
            saved.update(
                {
                    key: character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                }
            )
            for packet in result["packets"]:
                send(connection, service, *packet)
            if owner_id == character["id"]:
                character = refresh_owned_character(saved)
                WORLD.update(generation, character, *pet_packet(character))
                publish_consumable_character(character)
            else:
                from wakfu_server.hero_wire import statistics

                send(connection, service, *pet_packet(saved))
                send(connection, service, *statistics(saved))
        pet_hibernation_due = (
            time.monotonic()
            + max(0.1, (min(deadlines) - int(time.time() * 1000)) / 1000)
            if deadlines
            else time.monotonic() + 60
        )

    def play_inventory_emote(body):
        nonlocal character
        from wakfu_server.emote_item_actions import action_class, play

        if action_class(body) is None:
            return False

        def target(actor_id):
            identity = WORLD.live_identity(character_id=actor_id)
            return None if identity is None else identity[1]

        outcome = play(
            STORE,
            account_id,
            generation,
            character,
            body,
            resolve_target=target,
            in_fight=lambda actor_id: (
                actor_id == character["id"]
                and (fight is not None or combat_session is not None)
            )
            or COMBAT_SESSIONS.lookup_character(actor_id) is not None,
            occupied=lambda actor_id: actor_id in HARVESTS.pending
            or actor_id in PLANTINGS.pending,
        )
        saved = refresh_owned_character(outcome["character"])
        saved.update(
            {
                key: character[key]
                for key in ("map_id", "instance_id", "x", "y", "z", "direction")
            }
        )
        for packet in outcome["packets"]:
            send(connection, service, *packet)
        saved["_emote_packet"] = outcome["packet"]
        saved["_emote_until"] = (
            float("inf")
            if outcome["duration_ms"] < 0
            else time.monotonic() + outcome["duration_ms"] / 1000
        )
        character = saved
        WORLD.update(generation, character, *outcome["packet"])
        record(event="emote_item_used", actor_id=character["id"], consumed=1)
        return True

    def play_inventory_script(body):
        nonlocal character
        from wakfu_server.script_item_actions import action_class, descriptors, use

        if action_class(body) is None:
            return False
        source_uid = struct.unpack_from(">q", body, 4)[0]
        with STORE.connection() as db:
            owner = db.execute(
                "SELECT character_id FROM inventory_items WHERE uid=%s",
                (source_uid,),
            ).fetchone()
        if owner is None:
            raise ValueError("The visual item is unavailable")
        if owner["character_id"] != character["id"]:
            raise ValueError(
                "Select the character carrying this visual item before using it"
            )
        # Following heroes share their selected main's visible scene. The
        # consuming transaction independently fences the actual item's owner.
        location = dict(character, id=owner["character_id"])
        target = (
            struct.unpack_from(">iih", body, 13)
            if body[12]
            else tuple(location[key] for key in ("x", "y", "z"))
        )
        scene = (location["map_id"], location["instance_id"])
        action_id = struct.unpack_from(">i", body)[0]
        plan = next(
            row for row in descriptors()["items"] if row["action_id"] == action_id
        )
        present = False
        if plan["requires_mobile_target"]:
            present = any(
                (actor["map_id"], actor["instance_id"]) == scene
                and tuple(actor[key] for key in ("x", "y", "z")) == target
                and COMBAT_SESSIONS.lookup_character(actor["id"]) is None
                for actor in WORLD.ecology_snapshot()
            )
            if not present:
                present = any(
                    any(
                        tuple(actor[key] for key in ("x", "y", "z")) == target
                        for actor in group["members"]
                    )
                    for group in COMBAT_GROUPS.available(*scene)
                )
        outcome = use(
            STORE,
            account_id,
            generation,
            character["id"],
            body,
            in_fight=fight is not None or combat_session is not None,
            location=location,
            native_map_id=character["map_id"],
            target_present=present,
        )
        for packet in outcome["packets"]:
            send(connection, service, *packet)
        if outcome["character"]["id"] == character["id"]:
            saved = refresh_owned_character(outcome["character"])
            saved.update(
                {
                    key: character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                }
            )
            character = saved
        # Publish only after the inventory transaction commits. This packet is
        # a scene visual and does not refresh actor characteristics or gear.
        WORLD.emit_location(*scene, *outcome["script_packet"])
        record(
            event="script_item_used",
            actor_id=outcome["character"]["id"],
            script_id=outcome["script_id"],
            consumed=outcome["consumed"],
        )
        return True

    def mark_inventory_destination(body):
        from wakfu_server.world_marker_item_actions import action_class, use

        if action_class(body) is None:
            return False
        result = use(
            STORE,
            account_id,
            generation,
            character["id"],
            body,
            in_fight=fight is not None or combat_session is not None,
            native_map_id=native_item_world_identity(character),
            private_context=active_private_session() is not None,
        )
        record(
            event="inventory_destination_marked",
            actor_id=result["actor_id"],
            source_reference=result["source_reference"],
            consumed=result["consumed"],
            marker=result["marker"],
        )
        return True

    def open_item_recustomization(body):
        nonlocal character, selected, loaded, movement_state, hero_switch_pending
        from wakfu_server.simple_item_actions import _action_classes

        action_id = struct.unpack_from(">i", body)[0]
        if "bIb" not in _action_classes().get(action_id, ()):
            return False
        if (
            fight is not None
            or combat_session is not None
            or active_private_session() is not None
            or chest_opening is not None
            or guild_chest_session is not None
            or hero_switch_pending is not None
        ):
            raise ValueError(
                "Termina la actividad actual antes de cambiar tu personaje"
            )
        from wakfu_server.character_recustomization import request, transition_packets

        flush_positions(
            account_id=account_id, generation=generation, character_id=character["id"]
        )
        outcome = request(STORE, account_id, generation, character["id"], body)
        for packet in outcome["packets"]:
            send(connection, service, *packet)
        POSITIONS.release(account_id, generation, character["id"])
        STORE.clear_character(account_id, generation)
        WORLD.leave(character["id"], generation)
        selected = loaded = False
        hero_switch_pending = movement_state = None
        for packet in transition_packets(outcome["character"]):
            send(connection, service, *packet)
        record(
            event="item_recustomization_opened",
            actor_id=character["id"],
            mode=outcome["pending"]["mode"],
        )
        character = None
        return True

    def publish_haven_world_travel(outcome):
        nonlocal character, position, movement_state
        from wakfu_server.haven_world_travel import acknowledge

        cancel_crafting()
        WORLD.leave(character["id"], generation)
        character = outcome["character"]
        POSITIONS.attach(account_id, generation, character)
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        for packet in owned_native_bootstrap(character):
            send(connection, service, *packet)
        join_world(generation, connection, character)
        mark_static_sync_pending()
        acknowledge(
            STORE,
            account_id,
            generation,
            character["id"],
            outcome["transition"]["token"],
        )
        record(
            event="haven_world_travel",
            actor_id=character["id"],
            kind=outcome["transition"]["kind"],
        )

    def use_inventory_teleport(body):
        nonlocal character, position, movement_state, bag_session, ranch_session
        from wakfu_server import item_teleports

        if item_teleports.action_class(body) is None:
            return False
        private = active_private_session()
        if private is not None and not private.owns(character):
            raise ValueError("El traslado requiere la sesión privada actual")
        physical = None
        if private is not None:
            physical = STORE.character(account_id, character["id"])
        outcome = item_teleports.use(
            STORE,
            POSITIONS,
            account_id,
            generation,
            character["id"],
            body,
            in_fight=fight is not None or combat_session is not None,
            physical_source=physical,
            native_map_id=native_item_world_identity(character),
        )
        for packet in outcome["packets"]:
            send(connection, service, *packet)
        # SQL movement and debit have committed. Private capabilities and native
        # scene publication retire only after that owned transaction succeeds.
        leaving_ranch = ranch_session is not None
        leaving_bag = bag_session is not None
        if private is not None:
            cancel_private_scene_activity()
            if bag_session is not None:
                exterior = HAVEN_BAG_EXTERIORS.discard(
                    generation, bag_session.exterior_actor_id
                )
                if exterior is not None:
                    outside, packet = exterior
                    WORLD.emit_location(
                        outside["map_id"], outside["instance_id"], *packet
                    )
            if ranch_session is not None:
                ranch_session.leave(character)
            bag_session = ranch_session = None
        else:
            WORLD.leave(character["id"], generation)
        character = outcome["character"]
        POSITIONS.attach(account_id, generation, character)
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        bootstrap = (
            owned_haven_leave(fixture(13974), character)
            if leaving_bag
            else owned_native_bootstrap(character)
        )
        for opcode, payload in bootstrap:
            if leaving_ranch and opcode == 13019:
                continue
            send(connection, service, opcode, payload)
        join_world(generation, connection, character)
        mark_static_sync_pending()
        item_teleports.acknowledge(
            STORE,
            account_id,
            generation,
            character["id"],
            outcome["transition"]["token"],
        )
        record(
            event="inventory_item_teleported",
            actor_id=character["id"],
            native_class=outcome["native_class"],
            consumed=outcome["consumed"],
        )
        return True

    def attach_combat_return_position():
        # Private coordinates never replace the durable exterior position.
        saved = (
            STORE.character(account_id, character["id"])
            if active_private_session() is not None
            else character
        )
        return POSITIONS.attach(account_id, generation, saved)

    def combat_return_bootstrap():
        session = active_private_session()
        if session is None:
            return owned_native_bootstrap(character)
        if not session.owns(character):
            raise ValueError("Combat return lost its private scene capability")
        if ranch_session is not None:
            packets = ranch_session.entry_messages(
                fixture(13974), character, clear_bag_role=False
            )
            if character["map_id"] == 1440:
                from wakfu_server.haven_ranch_furniture import snapshot

                restored = snapshot(
                    STORE,
                    account_id,
                    generation,
                    character,
                    session=ranch_session,
                    now_ms=int(time.time() * 1000),
                )
                packets = [restored["packet"] if p[0] == 13864 else p for p in packets]
            return packets
        from wakfu_server.haven_bag import entry_messages

        return entry_messages(
            fixture(13974),
            character,
            owner=None if bag_session.is_owner else bag_session.owner,
        )

    def deliver_ranch_cycle_rewards():
        """Settle an idle owner's herd independently of combat and visitor scenes."""
        nonlocal last_ranch_cycle_tick
        if (
            not loaded
            or ranch_session is None
            or not ranch_session.parent.is_owner
            or fight is not None
            or combat_session is not None
            or spectator_session is not None
            or hero_switch_pending is not None
            or time.monotonic() - last_ranch_cycle_tick < 60
        ):
            return
        last_ranch_cycle_tick = time.monotonic()
        from wakfu_server import ranch_cycle_rewards

        try:
            packets = ranch_cycle_rewards.tick(
                STORE,
                account_id,
                generation,
                character,
                session=ranch_session,
            )
        except (ValueError, DatabaseError, PoolTimeout) as error:
            record(
                event="haven_ranch_cycle_deferred",
                actor_id=character["id"],
                reason=str(error)
                if isinstance(error, ValueError)
                else "Ranch cycle unavailable",
            )
            return
        for packet in packets:
            send(connection, service, *packet)
        if packets:
            from wakfu_server.haven_ranch_building_knowledge import scene_packet

            WORLD.emit_location(
                character["map_id"],
                character["instance_id"],
                *scene_packet(STORE, account_id, biome_id=ranch_session.biome_id),
            )

    def deliver_ranch_scene_refresh():
        """Rebuild this recipient's native Ranch scene without changing ownership."""
        pending = connection.ranch_scene_refresh
        if pending is None:
            return
        scope = (
            character["id"],
            generation,
            character["map_id"],
            character["instance_id"],
        )
        if (
            pending[:4] != scope
            or ranch_session is None
            or not ranch_session.owns(character)
        ):
            with WORLD.lock:
                if connection.ranch_scene_refresh == pending:
                    connection.ranch_scene_refresh = None
            return
        if (
            fight is not None
            or combat_session is not None
            or spectator_session is not None
            or pending_combat_return is not None
        ):
            return
        # 13864 replaces the model; recipient-specific 13974 invokes ceK.nc and
        # rebuilds its actors. Reuse the qualified same-scene return sequence.
        for packet in combat_return_bootstrap():
            send(connection, service, *packet)
        mark_static_sync_pending()
        with WORLD.lock:
            if connection.ranch_scene_refresh == pending:
                connection.ranch_scene_refresh = None
        record(
            event="haven_ranch_scene_refreshed",
            actor_id=character["id"],
            revision=pending[4],
        )

    def validate_ranch_lease():
        if not STORE.current_character_session(account_id, generation, character["id"]):
            raise ValueError("Expired ranch actor lease")

    def validate_ranch_entitlement():
        from wakfu_server.haven_ranch_authority import require_owned_entitlement

        require_owned_entitlement(STORE, account_id, generation, character)

    def cancel_private_scene_activity():
        nonlocal chest_opening

        PLANTINGS.cancel(character["id"], generation)
        HARVESTS.cancel(character["id"], generation=generation)
        cancel_flora()
        cancel_crafting()
        if chest_opening is not None:
            from wakfu_server.haven_chest_wire import close_packet as close_chest

            send(connection, service, *close_chest(character["id"]))
            chest_opening = None
        WORLD.leave(character["id"], generation)

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
        if active_private_session() is not None:
            from wakfu_server.haven_ranch_portal import (
                config_message as ranch_portal_config,
            )

            send(connection, service, *ranch_portal_config())
        ranch_furniture_scene = []
        if ranch_session is not None and ranch_session.owns(character):
            from wakfu_server.haven_ranch_furniture import (
                snapshot as ranch_furniture_snapshot,
            )

            furniture_snapshot = ranch_furniture_snapshot(
                STORE,
                account_id,
                generation,
                character,
                session=ranch_session,
                now_ms=int(STORE.now().timestamp() * 1000),
            )
            send(connection, service, *furniture_snapshot["packet"])
            ranch_furniture_scene = furniture_snapshot["scene_packets"]
        if character["map_id"] != 9:
            from wakfu_server.treasure_definition_projections import (
                project_snapshot_bodies,
            )

            for message_body in project_snapshot_bodies(
                STORE,
                character["map_id"],
                world_static.snapshots(character["map_id"], position=character),
            ):
                send(connection, service, 13984, message_body)
            for packet in ranch_furniture_scene:
                send(connection, service, *packet)
            publish_environment_scene(force=True)
            # The asset baseline also belongs to private dungeon scenes. Replay
            # its dynamic state first, then restore the run-owned door policy;
            # native default states must never reopen progression exits.
            if is_dungeon_run(character.get("instance_id", 0)):
                for message_id, message_body in owned_native_bootstrap(character):
                    if message_id == 12344:
                        send(connection, service, message_id, message_body)
        elif bag_session is not None and bag_session.owns(character):
            from wakfu_server.haven_bag_native_scene import packets as bag_scene_packets

            for message_id, message_body in bag_scene_packets(bag_session, character):
                send(connection, service, message_id, message_body)
            if bag_session.is_owner:
                from wakfu_server.haven_chest_wire import (
                    scene_packet as chest_scene_packet,
                )

                for chest_object in world_static.objects(9):
                    if chest_object["type"] == "AccountChest":
                        send(
                            connection, service, *chest_scene_packet(chest_object["id"])
                        )
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
        if packets:
            from wakfu_server.treasure_definition_projections import (
                project_snapshot_bodies,
            )

            packets = project_snapshot_bodies(STORE, character["map_id"], packets)
        if not packets and not scene_sync.last_regions:
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
            # The connection publishes each native attachment once and converts
            # retained-object hydration to in-place state updates.
        # Replay the same animated-path partitions as the static hydration.
        # Character coordinates already name the endpoint while the client is
        # still walking; selecting only that endpoint loses intermediate flora.
        for packet in PLANTINGS.snapshots(
            character["map_id"],
            character.get("instance_id", 0),
            position=character,
            chunks=scene_sync.last_regions,
        ):
            send(connection, service, *packet)
        publish_environment_scene(force=True)
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
    def send_loaded_world_snapshot(*, reconcile_markers=True):
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
            character["map_id"], character.get("instance_id", 0), position=character
        ):
            send(connection, service, *packet)
        if COMBAT_TEST:
            from wakfu_server.combat_monster_world import spawn_group
            from wakfu_server.combat_world_group_cleanup import defeated_snapshot

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
                        owned_scene_spawn_group(
                            group["members"], group_id=group["key"][2]
                        ),
                    )
        for packet in HARVESTS.availability_snapshot(
            character["map_id"], character.get("instance_id", 0)
        ):
            send(connection, service, *packet)
        if COMBAT_TEST:
            # bvU restores retained external contexts before sending 12154.
            # Serialize selection with actual writes so concurrent new markers
            # cannot be created twice for the same native recipient scene.
            with connection.write_lock:
                known = (
                    connection.marker_publications.snapshot(
                        connection.native_instance_scope()
                    )
                    if reconcile_markers
                    else None
                )
                packets = EXTERNAL_FIGHT_MARKERS.world_snapshots(
                    character["map_id"],
                    character.get("instance_id", 0),
                    exclude_character_id=character["id"],
                    known_phases=known,
                    known_rosters=(
                        connection.marker_publications.roster_snapshot(
                            connection.native_instance_scope()
                        )
                        if reconcile_markers
                        else None
                    ),
                    unbound_members=(
                        connection.marker_publications.unbound_snapshot(
                            connection.native_instance_scope()
                        )
                        if reconcile_markers
                        else None
                    ),
                )
                send_batch(connection, service, packets)

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
        send_loaded_world_snapshot(reconcile_markers=True)
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

    def native_exterior_rift_request():
        """Recognize the same real exterior request at both combat guards."""
        if (
            opcode != 12870
            or not loaded
            or character is None
            or account_id is None
            or generation is None
            or len(body) != 12
            or struct.unpack_from(">H", body, 8)[0] != 11
        ):
            return False
        from wakfu_server.rift_entry_recovery import matches_loaded_source

        try:
            return matches_loaded_source(
                STORE, WORLD, POSITIONS, account_id, generation, character["id"], body
            )
        except ValueError:
            return False

    def consume_rift_entry_combat_retirement():
        """Drop only a durably retired encounter; native entry owns its bootstrap."""
        nonlocal fight, fight_messages, combat_session, group_lease
        nonlocal checkpoint_id, checkpoint_revision, checkpoint_terminal
        nonlocal pending_terminal_world_recovery, pending_combat_return
        nonlocal publication_recovery_shared, publication_recovery_attempt_token
        nonlocal publication_recovery_notice_token, TEST_MONSTERS, TEST_MONSTERS_BY_ID
        nonlocal TEST_GROUP_KEY, fight_started_at
        from wakfu_server.combat_entry_recovery import take_entry_recovery

        old_fight_id = take_entry_recovery(
            COMBAT_SESSIONS.registry, account_id, generation, character["id"]
        )
        if old_fight_id is None or (fight is not None and fight.id != old_fight_id):
            return False
        fight = fight_messages = combat_session = group_lease = None
        if checkpoint_id == old_fight_id:
            checkpoint_id = checkpoint_revision = None
            checkpoint_terminal = True
        if (
            isinstance(pending_combat_return, dict)
            and pending_combat_return.get("fight_id") == old_fight_id
        ):
            pending_combat_return = None
            pending_return_command.clear()
        if (
            isinstance(pending_terminal_world_recovery, dict)
            and pending_terminal_world_recovery.get("fight_id") == old_fight_id
        ):
            pending_terminal_world_recovery = None
        if (
            publication_recovery_shared is not None
            and publication_recovery_shared.fight.id == old_fight_id
        ):
            publication_recovery_shared = None
            publication_recovery_attempt_token = (
                publication_recovery_notice_token
            ) = None
        TEST_MONSTERS = ()
        TEST_MONSTERS_BY_ID = {}
        TEST_GROUP_KEY = None
        fight_started_at = None
        placement_deadline.take_expired(None, time.monotonic())
        record(
            event="rift_entry_obsolete_combat_retired",
            actor_id=character["id"],
            fight_id=old_fight_id,
        )
        return True

    def deliver_rift_transition():
        nonlocal character, position, movement_state
        if not loaded or character is None or account_id is None or generation is None:
            return False
        consume_rift_entry_combat_retirement()
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
        if "world_respawn" in destination and not prepare_world_respawn_delivery(
            destination, saved
        ):
            return False
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

    from wakfu_server.custom_tasks.hooks import SelectedTaskCards
    from wakfu_server.custom_tasks.gift_source import current_local_gifts

    custom_task_cards = SelectedTaskCards()
    from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents

    environmental_events = SelectedEnvironmentalEvents(
        hero_template=OWNED_HERO_TEMPLATE,
        roster_template=CHARACTERS,
        groups=globals().get("COMBAT_GROUPS"),
    )
    from wakfu_server.national_publication import SelectedNationalProgression

    national_publication = SelectedNationalProgression()
    national_poll_at = 0.0
    environmental_poll_at = 0.0
    environmental_publication_error = None
    objectives_poll_at = 0.0
    objectives_hunt_poll_at = 0.0
    objectives_projection = None

    def deliver_custom_task_rewards(*, bootstrap=False):
        """Separate committed selected-character grant; never inside gameplay TX."""
        nonlocal character
        from wakfu_server.custom_tasks.reward_delivery import deliver
        from psycopg.errors import DeadlockDetected, LockNotAvailable

        if bootstrap:
            with STORE.connection() as db:
                active = db.execute(
                    "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
                    "ON f.id=p.fight_id WHERE p.account_id=%s AND p.character_id=%s "
                    "AND f.status IN ('placement','active') LIMIT 1",
                    (account_id, character["id"]),
                ).fetchone()
            if active is not None:
                return {
                    "deferred": True,
                    "packets": [],
                    "delivered": [],
                    "capacity_pending": [],
                    "character": character,
                }
        previous_level = character.get("level")
        try:
            result = deliver(STORE, account_id, generation, character["id"])
        except (ValueError, DeadlockDetected, LockNotAvailable) as error:
            # Delivery owns its transaction: these lock errors reach here only
            # after rollback. Keep earned rows pending for the ordinary poll;
            # do not retry inline or publish packets for uncommitted grants.
            if not STORE.current_character_session(
                account_id, generation, character["id"]
            ):
                raise
            record(
                event="custom_task_rewards_pending",
                actor_id=character["id"],
                reason=str(error),
                sqlstate=getattr(error, "sqlstate", None),
                deferred=True,
            )
            return {
                "deferred": True,
                "packets": [],
                "delivered": [],
                "capacity_pending": [],
                "character": character,
            }
        saved = result["character"]
        if not bootstrap and saved.get("level") != previous_level:
            # Durable XP reconciliation pauses regeneration; resume world policy.
            # initialize itself keeps coefficient zero for a dead character.
            saved = health_store.initialize(
                STORE,
                account_id,
                generation,
                saved["id"],
                exploration=True,
            )
            result["character"] = saved
        private = active_private_session()
        character = (
            private.refresh(character, saved)
            if private is not None and private.owns(character)
            else saved
        )
        if bootstrap:
            # Only absolute account unlock snapshots are safe before bootstrap.
            # Suppress additive XP, item insertions and unlock notifications.
            for packet in result["packets"]:
                if packet[0] == 13873:
                    send(connection, service, *packet)
            return result
        if result["delivered"]:
            from wakfu_server.combat_lifecycle import outside_progression

            send_batch(connection, service, result["packets"])
            if character.get("level") != previous_level:
                WORLD.update(
                    generation,
                    character,
                    *wire.refresh_player(PLAYER_TEMPLATE, character),
                )
                from wakfu_server.level_publication import refresh

                # Refresh owned spellbook and roster level/build availability.
                send_batch(
                    connection,
                    service,
                    refresh(
                        character,
                        STORE.characters(account_id),
                        entity_template=OWNED_HERO_TEMPLATE,
                        roster_template=CHARACTERS,
                        retained_state_packets=consumable_state_packets,
                    ),
                )
                send_native_planting_bonus(connection, character)
            send(
                connection, service, *outside_progression(character, wp=COMBAT_TEST_WP)
            )
            send(connection, service, *rich_inventory_packet(character))
        return result

    def publish_custom_task_cards():
        ready = (
            loaded
            and fight is None
            and combat_session is None
            and hero_switch_pending is None
            and spectator_session is None
        )
        if not ready or not custom_task_cards.needs_refresh(
            account_id, generation, character["id"]
        ):
            return False
        gifts = current_local_gifts()
        return custom_task_cards.refresh(
            STORE,
            WORLD,
            account_id,
            generation,
            character["id"],
            ready=ready,
            existing_packages=gifts.packages,
            cap_reached=gifts.cap_reached,
        )

    def poll_national_progression():
        nonlocal national_poll_at
        if not (
            loaded
            and character is not None
            and fight is None
            and combat_session is None
            and spectator_session is None
            and hero_switch_pending is None
        ):
            return
        now = time.monotonic()
        if now < national_poll_at:
            return
        national_poll_at = now + 1.0
        national_publication.refresh(
            STORE,
            account_id,
            generation,
            character["id"],
            publish=publish_nation_character,
        )

    def poll_environmental_events():
        """Recover committed environmental state independently of custom tasks."""
        nonlocal environmental_poll_at, environmental_publication_error, character
        if not (
            loaded
            and character is not None
            and fight is None
            and combat_session is None
            and spectator_session is None
            and hero_switch_pending is None
            and bag_session is None
        ):
            return
        now = time.monotonic()
        if now < environmental_poll_at:
            return
        environmental_poll_at = now + 1.0
        from wakfu_server.territory_cells import region_at

        try:
            region_id = region_at(character["map_id"], character["x"], character["y"])
        except ValueError:
            # Unknown territory forbids new admission but does not hide already
            # earned entitlements or prevent reconnect delivery.
            region_id = None
        location = {
            key: character.get(key, 0)
            for key in ("map_id", "instance_id", "x", "y", "z")
        }
        location["region_id"] = region_id
        try:
            from wakfu_server.objectives.environmental_archmonster_runtime import (
                poll as poll_archmonsters,
            )

            try:
                poll_archmonsters(
                    STORE,
                    WORLD,
                    COMBAT_GROUPS,
                    location=location,
                    now_ms=int(STORE.now().timestamp() * 1000),
                )
            except OSError as error:
                record(
                    event="archmonster_publication_pending",
                    map_id=location["map_id"],
                    instance_id=location["instance_id"],
                    reason=type(error).__name__,
                )
            publish_native_monster_destructions(location)
            environmental_events.refresh(
                STORE,
                WORLD,
                account_id,
                generation,
                character["id"],
                location=location,
                ready=True,
                checkpoint=lambda: flush_positions(
                    account_id=account_id,
                    generation=generation,
                    character_id=character["id"],
                ),
            )
            saved = environmental_events.claimed_character
            if saved is not None:
                previous_level = character.get("level")
                # Live movement belongs to the position registry; an earned
                # inventory/XP refresh must not copy an older persisted tile.
                saved = dict(
                    saved,
                    **{
                        key: character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    },
                )
                if saved.get("level") != previous_level:
                    initialized = health_store.initialize(
                        STORE, account_id, generation, saved["id"], exploration=True
                    )
                    saved = dict(
                        initialized,
                        **{
                            key: saved[key]
                            for key in ("map_id", "instance_id", "x", "y", "z")
                        },
                    )
                character = saved
                if character.get("level") != previous_level:
                    WORLD.update(
                        generation,
                        character,
                        *wire.refresh_player(PLAYER_TEMPLATE, character),
                    )
                    from wakfu_server.level_publication import refresh as refresh_level

                    send_batch(
                        connection,
                        service,
                        refresh_level(
                            character,
                            STORE.characters(account_id),
                            entity_template=OWNED_HERO_TEMPLATE,
                            roster_template=CHARACTERS,
                            retained_state_packets=consumable_state_packets,
                        ),
                    )
                    send_native_planting_bonus(connection, character)
        except ValueError as error:
            reason = str(error)
            if environmental_publication_error != reason:
                record(
                    event="environmental_publication_rejected",
                    actor_id=character["id"],
                    reason=reason,
                )
            environmental_publication_error = reason
            return
        environmental_publication_error = None

    def poll_external_objectives():
        """Consume asynchronous objective changes only in a ready world scene."""
        nonlocal objectives_poll_at, objectives_hunt_poll_at, objectives_projection
        from wakfu_server.custom_tasks import external

        if not external.enabled():
            return
        now = time.monotonic()
        if loaded and now >= objectives_hunt_poll_at:
            from wakfu_server.objectives import hunts

            objectives_hunt_poll_at = now + 1.0
            hunts.publish(STORE, COMBAT_GROUPS, WORLD)
        if not (
            loaded
            and character is not None
            and fight is None
            and combat_session is None
            and hero_switch_pending is None
            and spectator_session is None
        ):
            return
        updates = getattr(connection, "objectives_updates", None)
        if updates is not None:
            updates.character_id = character["id"]
        notified = updates is not None and updates.dirty.is_set()
        if now < objectives_poll_at and not notified:
            return
        if updates is not None:
            updates.dirty.clear()
        objectives_poll_at = now + 1.0
        drain_objectives_player_actions()
        from wakfu_server.custom_tasks import service as task_service

        from wakfu_server.custom_tasks.exploration import observe
        from wakfu_server.objectives.progression import (
            observe as observe_account_progression,
        )

        observe(STORE, account_id, generation, character["id"])
        observe_account_progression(STORE, account_id, generation, character["id"])
        with STORE.connection() as db:
            snapshot = task_service.snapshot(
                db,
                account_id,
                character["id"],
                section=custom_task_cards.section,
                page=custom_task_cards.page,
            )
            pending = external.pending_rewards(db, character["id"])
        identity = (account_id, generation, character["id"], snapshot)
        if pending:
            deliver_custom_task_rewards()
        from wakfu_server.objectives.notices import deliver as deliver_objective_notices
        from wakfu_server.ecology_feedback import information

        with STORE.connection() as db:
            deliver_objective_notices(
                db,
                account_id,
                generation,
                character["id"],
                lambda text: send(connection, service, *information(text)),
            )
        if notified or identity != objectives_projection:
            custom_task_cards.changed(character["id"], (character["id"],))
            publish_custom_task_cards()
            objectives_projection = identity

    def execute_objectives_command(text, *, browser_action=None):
        """Public objective navigation and fenced private weekly challenge entry."""
        nonlocal character, position, movement_state
        from wakfu_server.command_permissions import authorize_command
        from wakfu_server.custom_tasks import external
        from wakfu_server.ecology_feedback import information

        arguments = text.split()
        command = arguments[0].lower() if arguments else ""
        try:
            authorize_command(STORE, account_id, text)
            if not external.enabled():
                raise ValueError("The objectives service is not enabled.")
            if not (
                loaded
                and character is not None
                and fight is None
                and combat_session is None
                and hero_switch_pending is None
                and spectator_session is None
            ):
                raise ValueError("Objectives require a ready scene outside combat.")
            if command == "!adventures":
                if len(arguments) != 1:
                    raise ValueError("Usage: !adventures")
                from wakfu_server.custom_tasks.player_actions import launch_url

                with STORE.connection() as db:
                    url = launch_url(db, account_id, character["id"], generation)
                send(connection, service, *information("Open your adventures: " + url))
                return {"success": True, "message": "Adventures link created."}
            if command == "!tasks":
                from wakfu_server.custom_tasks.sections import parse

                section, page = parse(arguments[1:])
                custom_task_cards.select_view(section, page)
                publish_custom_task_cards()
                send(
                    connection,
                    service,
                    *information(
                        "Gifts window updated. Use !tasks <section> <page> to browse objectives."
                    ),
                )
                return {"success": True, "message": "Objectives view updated."}
            if (
                command != "!challenge"
                or len(arguments) != 2
                or arguments[1].lower() not in ("weekly", "return", "abandon")
            ):
                raise ValueError("Usage: !challenge weekly | return | abandon")
            if bag_session is not None or ranch_session is not None:
                raise ValueError(
                    "Leave your private scene before entering a weekly challenge."
                )
            from wakfu_server.objectives import challenges
            from wakfu_server.combat_terrain import map_geometry

            action = arguments[1].lower()
            with POSITIONS.account_barrier(account_id):
                flush_positions(account_id=account_id)
                with COMBAT_GROUPS.lock:
                    with STORE.connection() as db:
                        db.execute(
                            "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                            (account_id,),
                        )
                        STORE.lock_character(
                            db, account_id, generation, character["id"], selected=True
                        )
                        if browser_action is not None:
                            from wakfu_server.custom_tasks.player_actions import (
                                lock_running,
                            )

                            lock_running(db, browser_action)
                        if action == "weekly":
                            run = challenges.enter_weekly(
                                db,
                                COMBAT_GROUPS,
                                account_id,
                                character["id"],
                                geometry_loader=map_geometry,
                            )
                        else:
                            run = challenges.current_run(
                                db, account_id, character["id"]
                            )
                            challenges.return_from_challenge(
                                db,
                                account_id,
                                character["id"],
                                abandon=action == "abandon",
                            )
                        moved_ids = tuple(
                            row["character_id"]
                            for row in db.execute(
                                "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s",
                                (run["attempt_id"],),
                            ).fetchall()
                        )
                        saved = STORE.character(account_id, character["id"], db)
                        if browser_action is not None:
                            from wakfu_server.custom_tasks.player_actions import finish

                            if not finish(
                                db,
                                browser_action,
                                {
                                    "success": True,
                                    "message": "Weekly challenge action completed.",
                                    "map_id": saved["map_id"],
                                    "instance_id": saved.get("instance_id", 0),
                                },
                            ):
                                raise ValueError(
                                    "Adventures action is no longer executable."
                                )
                for member_id in moved_ids:
                    POSITIONS.release(account_id, generation, member_id)
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
            send(
                connection,
                service,
                *information(
                    "Weekly challenge ready. Defeat the private group, then use !challenge return."
                    if action == "weekly"
                    else "Returned from the weekly challenge."
                ),
            )
            return {
                "success": True,
                "message": "Weekly challenge action completed.",
                "map_id": character["map_id"],
                "instance_id": character.get("instance_id", 0),
            }
        except (ValueError, PermissionError) as error:
            send(connection, service, *information(str(error)))
            record(
                event="objectives_command_rejected",
                actor_id=character["id"],
                command=command,
                reason=str(error),
            )
            return {"success": False, "error": str(error)}

    def drain_objectives_player_actions():
        """Browser requests run on this socket's scene-owning dispatcher only."""
        from wakfu_server.custom_tasks import player_actions

        if not (
            loaded
            and character is not None
            and fight is None
            and combat_session is None
            and hero_switch_pending is None
            and spectator_session is None
            and not static_sync_pending
            and not world_snapshot_pending
        ):
            return
        identity = {
            "account_id": account_id,
            "character_id": character["id"],
            "generation": generation,
        }
        with STORE.connection() as db:
            action = player_actions.claim(db, identity)
        if action is None:
            return
        target = action["target"]
        if target.get("kind") == "weekly" and target.get("action") in (
            "weekly",
            "return",
            "abandon",
        ):
            result = execute_objectives_command(
                "!challenge " + target["action"], browser_action=action
            )
        elif target.get("kind") == "travel":
            result = execute_objectives_travel(action)
        elif target.get("kind") == "seasonal_entry":
            result = execute_objectives_seasonal_entry(action)
        elif target.get("kind") == "pvp":
            result = execute_objectives_pvp(action)
        else:
            result = {"success": False, "error": "Unsupported adventures action."}
        with STORE.connection() as db:
            player_actions.finish(db, action, result)

    def publish_entry_inventory(before):
        """Publish committed bag, personal and account entrance-item quantities."""
        from wakfu_server.inventory_move import synchronization
        from wakfu_server.quest_inventory import changes as quest_changes
        from wakfu_server.exploration_secrets import account_packet

        send(connection, service, *synchronization(character))
        send(connection, service, *rich_inventory_packet(character))
        for packet in quest_changes(before, character):
            send(connection, service, *packet)
        with STORE.connection() as db:
            packet = account_packet(db, account_id)
        send(connection, service, *packet)

    def publish_public_transport(destination_route, saved, *, generic_route):
        """Publish one committed native public transition through its usual path."""
        nonlocal character, position, movement_state
        cancel_crafting()
        WORLD.leave(character["id"], generation)
        prior_inventory = character
        character = saved
        POSITIONS.attach(account_id, generation, character)
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        messages = (
            owned_native_bootstrap(character, direction=destination_route["direction"])
            if generic_route
            else transports.bootstrap(character, destination_route)
        )
        for message_id, message_body in messages:
            send(connection, service, message_id, message_body)
        if destination_route.get("item_payment") is not None:
            publish_entry_inventory(prior_inventory)
        # Publish heavy dynamic entities once, after map-ready.
        join_world(
            generation,
            connection,
            character,
            defer_scene_snapshot=character["map_id"] != 9,
        )
        mark_static_sync_pending()
        record(
            event="map_transition",
            actor_id=character["id"],
            map_id=character["map_id"],
            position=position,
        )

    def execute_objectives_travel(
        action, *, resolve_destination=None, related_accounts=(), defer_receipt=False
    ):
        """Resolve curated public arrivals again and commit receipt with travel."""
        nonlocal character, position, movement_state
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import player_travel
        from wakfu_server.ecology_feedback import information
        from contextlib import ExitStack

        try:
            if (
                bag_session is not None
                or ranch_session is not None
                or character.get("instance_id", 0)
            ):
                raise ValueError(
                    "Leave your private instance before using adventures travel."
                )
            accounts = sorted(set((account_id, *related_accounts)))
            with ExitStack() as barriers:
                for owner_id in accounts:
                    barriers.enter_context(POSITIONS.account_barrier(owner_id))
                    flush_positions(account_id=owner_id)
                with STORE.connection() as db:
                    db.execute(
                        "SELECT id FROM accounts WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                        (accounts,),
                    )
                    STORE.lock_character(
                        db, account_id, generation, character["id"], selected=True
                    )
                    player_actions.lock_running(db, action)
                    if (
                        db.execute(
                            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                            "WHERE p.character_id=%s AND f.status IN ('placement','active') "
                            "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id "
                            "AND w.character_id=p.character_id) LIMIT 1",
                            (character["id"],),
                        ).fetchone()
                        is not None
                    ):
                        raise ValueError(
                            "Finish your current combat before travelling."
                        )
                    cost = 0
                    if resolve_destination is None:
                        spec = player_travel.resolve(db, action, action["action_key"])
                        destination, cost = spec["target"], spec["cost_kamas"]
                        if action["target"] != {
                            "kind": "travel",
                            "destination": destination,
                            "cost_kamas": cost,
                        }:
                            raise ValueError(
                                "This destination or price changed; refresh adventures before travelling."
                            )
                        remaining_kamas = player_actions.charge_travel(db, action, cost)
                    else:
                        destination = resolve_destination(db, action)
                    saved = STORE.transition_map_in_transaction(
                        db,
                        account_id,
                        generation,
                        character["id"],
                        character,
                        destination,
                    )
                    result = {
                        "success": True,
                        "message": "Travel completed.",
                        "map_id": saved["map_id"],
                        "instance_id": saved.get("instance_id", 0),
                        "cost_kamas": cost,
                    }
                    if defer_receipt:
                        db.execute(
                            "UPDATE objectives_player_actions SET status='pending' "
                            "WHERE id=%s AND status='running'",
                            (action["id"],),
                        )
                    elif not player_actions.finish(db, action, result):
                        raise ValueError("Adventures action is no longer executable.")
                    moved_ids = (character["id"],) + tuple(
                        row["character_id"]
                        for row in db.execute(
                            "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                            (account_id,),
                        ).fetchall()
                    )
                for member_id in moved_ids:
                    POSITIONS.release(account_id, generation, member_id)
            cancel_crafting()
            WORLD.leave(character["id"], generation)
            prior_inventory = character
            character = saved
            POSITIONS.attach(account_id, generation, character)
            position = {key: character[key] for key in ("x", "y", "z")}
            movement_state = Movement(position)
            for packet in owned_native_bootstrap(character):
                send(connection, service, *packet)
            join_world(
                generation,
                connection,
                character,
                defer_scene_snapshot=character["map_id"] != 9,
            )
            mark_static_sync_pending()
            if (
                action["target"].get("kind") == "seasonal_entry"
                and action["target"].get("route_kind") == "public"
            ):
                publish_entry_inventory(prior_inventory)
            if cost:
                send(
                    connection,
                    service,
                    12753,
                    wire.account_kamas_update(remaining_kamas),
                )
            return result
        except (ValueError, PermissionError) as error:
            send(connection, service, *information(str(error)))
            record(
                event="objectives_travel_rejected",
                actor_id=character["id"],
                reason=str(error),
            )
            return {"success": False, "error": str(error)}

    def execute_objectives_seasonal_entry(action):
        """Enter a reviewed native seasonal route with an atomic action receipt."""
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import seasonal_entry
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server import (
            dungeon_transport,
            dungeon_entry_access,
            teleporter_approach,
        )
        from wakfu_server.ecology_feedback import information

        try:
            if action["target"].get("route_kind") == "public":
                from wakfu_server import generic_transports
                from wakfu_server import seasonal_transport
                from wakfu_server.dungeon_entry_payment import consume

                def public_destination(db, queued):
                    target = seasonal_entry.resolve(db, queued)
                    actor = STORE.character(account_id, character["id"], db)
                    source = generic_transports.source(
                        target["entry_map_id"], target["source_id"]
                    )
                    native = next(
                        (
                            item
                            for item in (source or {}).get("destinations", ())
                            if item["destination_id"] == target["destination_id"]
                        ),
                        None,
                    )
                    if native is None or native["criterion"] != target["criterion"]:
                        raise ValueError(
                            "Seasonal island route changed; refresh Adventures."
                        )
                    resolved = generic_transports.resolve(
                        actor,
                        seasonal_entry.request(target),
                        source_allowed=teleporter_approach.callback(
                            movement_state,
                            map_id=target["entry_map_id"],
                            instance_id=0,
                        ),
                        criterion_evaluator=seasonal_transport.evaluator(STORE, actor),
                        allow_item_payment=True,
                    )
                    if (
                        resolved["destination"]["map_id"]
                        != target["destination_map_id"]
                    ):
                        raise ValueError(
                            "Seasonal island route changed; refresh Adventures."
                        )
                    price = resolved.get("item_payment")
                    if price:
                        consume(
                            db,
                            (character["id"],),
                            price["reference"],
                            price["quantity"],
                        )
                    return resolved["destination"]

                return execute_objectives_travel(
                    action, resolve_destination=public_destination
                )
            if bag_session is not None or ranch_session is not None:
                raise ValueError(
                    "Leave your private instance before entering a dungeon."
                )
            with STORE.connection() as db:
                target = seasonal_entry.resolve(db, action)
            body = seasonal_entry.request(target)
            resolved = dungeon_transport.resolve_request(target["entry_map_id"], body)
            if resolved is None or (
                resolved["route"].key != target["route_key"]
                or resolved["route"].criterion != target["criterion"]
                or resolved["route"].start_map_id != target["destination_map_id"]
            ):
                raise ValueError("Seasonal dungeon route changed; refresh Adventures.")
            geometry = map_geometry(resolved["route"].start_map_id)

            def initialize(db, session):
                player_actions.lock_running(db, action)
                # Recheck the published route fence in the entry transaction.
                active = db.execute(
                    "SELECT revision FROM native_catalog_active WHERE id=1"
                ).fetchone()
                if active is None or active["revision"] != target["catalog_revision"]:
                    raise ValueError("Seasonal catalog changed; refresh Adventures.")
                if not player_actions.finish(
                    db,
                    action,
                    {
                        "success": True,
                        "message": "Dungeon entered.",
                        "instance_id": session["instance_id"],
                    },
                ):
                    raise ValueError("Adventures action is no longer executable.")
                dungeon_runtime.initialize_instance(
                    db,
                    session,
                    groups=COMBAT_GROUPS,
                    geometry=geometry,
                )

            dungeon_transport.enter(
                STORE,
                account_id,
                generation,
                character["id"],
                target["entry_map_id"],
                body,
                criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                    STORE,
                    criterion,
                    character=actor,
                    destination_map_id=target["destination_map_id"],
                ),
                source_allowed=teleporter_approach.callback(
                    movement_state,
                    map_id=target["entry_map_id"],
                    instance_id=0,
                ),
                resolve_destination=dungeon_runtime.entry_destination,
                initialize_instance=initialize,
                positions=POSITIONS,
            )
            deliver_dungeon_transitions(before_action=True)
            return {"success": True, "message": "Dungeon entered."}
        except (ValueError, PermissionError) as error:
            send(connection, service, *information(str(error)))
            return {"success": False, "error": str(error)}

    def execute_objectives_pvp(action):
        """Meet selected opponents or observe the real event-bound native duel."""
        nonlocal character, spectator_session, spectator_fight_id
        from wakfu_server.custom_tasks import player_actions
        from wakfu_server.objectives import pvp
        from wakfu_server.combat_terrain import map_geometry

        def destination(db, queued):
            current = pvp.resolve(db, queued, queued["action_key"])["target"]
            if current["event_id"] != queued["target"]["event_id"]:
                raise ValueError("Hourly PvP event changed.")
            if current["action"] == "meet":
                opponent = db.execute(
                    "SELECT c.* FROM sessions s JOIN characters c ON c.id=s.character_id "
                    "AND c.account_id=s.account_id WHERE s.account_id=%s AND s.character_id=%s "
                    "AND s.generation=%s AND s.expires_at>CURRENT_TIMESTAMP FOR UPDATE OF s,c",
                    (
                        current["opponent_account_id"],
                        current["opponent_character_id"],
                        current["opponent_generation"],
                    ),
                ).fetchone()
                if opponent is None:
                    raise ValueError("The PvP opponent is no longer available.")
                if (
                    db.execute(
                        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                        (opponent["id"],),
                    ).fetchone()
                    is not None
                ):
                    raise ValueError("The PvP opponent is currently fighting.")
            else:
                invitation = db.execute(
                    "SELECT map_id,instance_id,challenger_x AS x,challenger_y AS y,challenger_z AS z "
                    "FROM friendly_duel_invitations WHERE fight_id=%s AND status='accepted'",
                    (current["fight_id"],),
                ).fetchone()
                if invitation is None:
                    raise ValueError("The hourly PvP fight is no longer available.")
                opponent = invitation
            occupied = [
                tuple(row[key] for key in ("x", "y", "z"))
                for row in db.execute(
                    "SELECT c.x,c.y,c.z FROM sessions s JOIN characters c ON c.id=s.character_id "
                    "WHERE s.expires_at>CURRENT_TIMESTAMP AND c.map_id=%s AND c.instance_id=0",
                    (opponent["map_id"],),
                ).fetchall()
            ]
            return player_actions.nearby_public_floor(
                map_geometry(opponent["map_id"]), opponent, occupied=occupied
            )

        try:
            with STORE.connection() as db:
                current = pvp.resolve(db, action, action["action_key"])["target"]
            if current["action"] == "meet":
                return execute_objectives_travel(
                    action,
                    resolve_destination=destination,
                    related_accounts=(current["opponent_account_id"],),
                )
            if (character["map_id"], character.get("instance_id", 0)) != (
                current["map_id"],
                current["instance_id"],
            ):
                return execute_objectives_travel(
                    action, resolve_destination=destination, defer_receipt=True
                )
            shared = COMBAT_SESSIONS.registry.lookup(current["fight_id"])
            if not public_objectives_duel(shared):
                raise ValueError("This fight is not a public hourly PvP challenge.")
            with STORE.connection() as db:
                player_actions.lock_running(db, action)
                pvp.resolve(db, action, action["action_key"])
                observer = spectator_session_for_current_character()
                if spectator_waiting_for_ack(shared):
                    db.execute(
                        "UPDATE objectives_player_actions SET status='pending' WHERE id=%s "
                        "AND status='running'",
                        (action["id"],),
                    )
                    return {
                        "success": True,
                        "message": "Waiting for the current native action.",
                    }
                publish_spectator_state(shared)
                delivery = SPECTATORS.enter(
                    observer,
                    current["fight_id"],
                    authorize=lambda _session, _fight_id: True,
                )
                result = {
                    "success": True,
                    "message": "Watching hourly PvP.",
                    "fight_id": current["fight_id"],
                }
                if not player_actions.finish(db, action, result):
                    SPECTATORS.disconnect(observer)
                    raise ValueError("Adventures action is no longer executable.")
            spectator_session = observer
            spectator_fight_id = current["fight_id"]
            for packet in delivery.packets:
                send(connection, service, *packet)
            return result
        except (ValueError, PermissionError, KeyError) as error:
            return {"success": False, "error": str(error)}

    def publish_heroes(roster):
        nonlocal pet_hibernation_due
        pet_hibernation_due = 0.0
        from wakfu_server import hero_wire, hero_private_scene

        roster = hero_private_scene.project(
            roster, active_private_session(), character, generation
        )
        for hero in roster["heroes"]:
            send(connection, service, *hero_wire.activate(OWNED_HERO_TEMPLATE, hero))
            send(connection, service, *hero_wire.statistics(hero))
        send(
            connection,
            service,
            *hero_wire.company(
                account_id,
                roster["leader"]["id"],
                guild_id=(roster["leader"].get("guild_native") or {}).get("guildId", 0),
                nation_id=roster["leader"].get("nation_id", 0),
                company_snapshot=roster["leader"]["equipment_criterion_context"][
                    "company_snapshot"
                ],
            ),
        )
        refresh_party(generation, roster["leader"])

    def prepare_rift_start(body):
        """Return None if unrelated, a startable run, or False after refusal."""
        if character is None or not (1 << 58) < character.get("instance_id", 0) < (
            1 << 59
        ):
            return None
        from wakfu_server import rift_entry_adapter

        loading_member = None
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

                    frozen_members = db.execute(
                        "SELECT c.id,c.account_id,c.name,s.generation,"
                        "s.character_id AS selected_character_id FROM characters c "
                        "JOIN sessions s ON s.account_id=c.account_id WHERE c.id=ANY(%s)",
                        (run["members"],),
                    ).fetchall()
                    # Heroes share their selected main's transport. Durable
                    # authorization above still checks every frozen member.
                    members = [
                        row
                        for row in frozen_members
                        if row["id"] == row["selected_character_id"]
                    ]
                    if {row["id"] for row in frozen_members} != set(run["members"]) or {
                        row["account_id"] for row in members
                    } != {row["account_id"] for row in frozen_members}:
                        raise ValueError(
                            "Every frozen rift owner must have a selected participant"
                        )
                    for row in members:
                        if (
                            rift_transition_delivery.pending(
                                row["account_id"], row["generation"], row["id"]
                            )
                            is not None
                        ):
                            loading_member = row["name"]
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
                            loading_member = row["name"]
                            raise ValueError(
                                "Every frozen rift member must finish loading the interior"
                            )
            return run
        except ValueError as error:
            record(
                event="rift_start_rejected", actor_id=character["id"], reason=str(error)
            )
            from wakfu_server.ecology_feedback import information

            loading_name = "".join(
                char for char in str(loading_member or "") if char.isprintable()
            )[:64]
            loading_message = (
                "No se puede iniciar la brecha: espera a que "
                + loading_name
                + " termine de cargar la brecha."
                if loading_name
                else (
                    "No se puede iniciar la brecha: espera a que todos los "
                    "integrantes terminen de cargar el interior."
                )
            )
            message = {
                "Wait for every frozen rift member to load the interior": loading_message,
                "Every frozen rift member must finish loading the interior": loading_message,
                "Every frozen rift owner must have a selected participant": (
                    "No se puede iniciar la brecha: cada cuenta debe tener "
                    "seleccionado un integrante de la compañía."
                ),
                "Frozen rift members left the instance": (
                    "No se puede iniciar la brecha: todos los integrantes "
                    "deben estar dentro de la misma brecha."
                ),
                "Missing native ultimate rift key": (
                    "No se puede iniciar la brecha: falta la llave necesaria."
                ),
            }.get(
                str(error),
                "No se pudo iniciar la brecha. Revisa la compañía y vuelve a usar el altar.",
            )
            send(connection, service, *information(message))
            return False

    def checkpoint_accepted_rift(shared, candidate, runtime, packets):
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_dispatch_lifecycle import (
            actor_reservation_shortfall,
            replenish_actor_ids,
        )

        # A wave count is not an actor-ID budget. Reserve only when this
        # private accepted preview actually needs another native ID block.
        if actor_reservation_shortfall(candidate):
            with STORE.connection() as rift_db:
                replenish_actor_ids(rift_db, candidate)

        def initialize_equipment_wave(current, actors, monsters):
            from wakfu_server.combat_server_spell import server_runtime
            from wakfu_server.rift_wave_initialization import initialize_registered_wave

            characters, decks = COMBAT_SESSIONS.player_sources(current)
            source_id = min(characters)
            factory, _ = server_runtime(
                characters[source_id],
                current.rift_monsters,
                decks[source_id],
                action_id=runtime.action_id,
                critical=False,
                player_characters=characters,
                deck_blobs=decks,
            )
            dispatcher, outbox = factory(
                current, {"native_retained_container": {"present": False}}
            )
            with current.effect_resolution():
                initialize_registered_wave(
                    dispatcher,
                    actors=actors,
                    monsters=monsters,
                    player_ids=tuple(characters),
                )
            return tuple(outbox)

        prepared = finish_accepted_action(
            candidate,
            runtime,
            packets,
            initialize_actor=lambda current, actor, monster: (),
            initialize_wave=initialize_equipment_wave,
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
                from wakfu_server import dungeon_native_flow

                if dungeon_native_flow.enabled(configuration["topology"]):
                    # Native room progress is committed by settlement; publish without automatic travel.
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
                        physical_packets = dungeon_native_flow.packets(
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
                                owned_scene_spawn_group(
                                    group["members"], group_id=group["key"][2]
                                ),
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
                from wakfu_server.dungeon_position_barrier import (
                    run_auto_transition,
                )

                run_auto_transition(
                    STORE,
                    POSITIONS,
                    character["instance_id"],
                    pending["fight_id"],
                    transition=transition,
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
                STORE,
                account_id,
                generation,
                character["id"],
                event,
                fixture_provider=fixture,
            )
            cancel_crafting()
            WORLD.leave(character["id"], generation)
            prior_inventory = character
            character = plan.character
            POSITIONS.attach(account_id, generation, character)
            position = {key: character[key] for key in ("x", "y", "z")}
            movement_state = Movement(position)
            for message_id, message_body in plan.packets:
                send(connection, service, message_id, message_body)
            if event.get("transition_kind") == "entry":
                publish_entry_inventory(prior_inventory)
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
    flora_retry_body = None
    environment_ticket = None
    pending_artifact_action = None
    environment_seat = None
    environment_scene_identity = None
    environment_scene_states = {}
    last_environment_refresh = 0.0

    def cancel_artifact_action(reason):
        nonlocal pending_artifact_action
        if pending_artifact_action is not None:
            record(
                event="exploration_artifact_cancelled",
                actor_id=pending_artifact_action["owner"][2],
                reason=reason,
            )
            pending_artifact_action = None

    def artifact_owner_identity(owner):
        return (
            account_id,
            generation,
            owner["id"],
            owner["map_id"],
            owner.get("instance_id", 0),
            owner["x"],
            owner["y"],
            owner["z"],
        )

    def artifact_failure_message(error):
        messages = {
            "hammer_unavailable": "El martillo todavía no puede despejar estas rocas.",
            "position": "Acércate al punto de uso del artefacto.",
        }
        return messages.get(
            getattr(error, "public_code", None),
            "No se pudo usar el artefacto. Inténtalo de nuevo.",
        )

    def artifact_position_allowed(owner):
        """Bind zero-mask native branches to accepted owned movement only."""
        if owner["map_id"] != character["map_id"] or owner.get(
            "instance_id", 0
        ) != character.get("instance_id", 0):
            return False
        current = tuple(owner[key] for key in ("x", "y", "z"))
        approved = tuple(movement_state.approved)
        return (
            current in approved
            if approved
            else current == tuple(character[key] for key in ("x", "y", "z"))
        )

    def admit_artifact_action(route, request_body, owner):
        """Publish admitted native scripts and retain only a delayed transition."""
        nonlocal pending_artifact_action
        for visual in route.get("script_packets", ()):
            if visual["broadcast"]:
                WORLD.broadcast(generation, owner["id"], *visual["packet"])
            else:
                send(connection, service, *visual["packet"])
        delay_ms = route["delay_ms"]
        if delay_ms == 0:
            return False
        pending_artifact_action = dict(
            owner=artifact_owner_identity(owner),
            body=bytes(request_body),
            route=route,
            due_at=time.monotonic() + delay_ms / 1000,
        )
        record(
            event="exploration_artifact_waiting",
            actor_id=owner["id"],
            object_id=route["interactive_element_id"],
            delay_ms=delay_ms,
        )
        return True

    def complete_artifact_action():
        """Revalidate delayed native travel on idle without blocking the reader."""
        nonlocal pending_artifact_action
        pending = pending_artifact_action
        if pending is None:
            return
        if (
            not loaded
            or character is None
            or artifact_owner_identity(character) != pending["owner"]
            or environment_blocked()
            or environment_ticket is not None
        ):
            cancel_artifact_action("Owner, source or occupation changed")
            return
        if time.monotonic() < pending["due_at"]:
            return
        from wakfu_server import exploration_artifact_actions, teleporter_approach
        from wakfu_server.position_buffer import PositionOwnerBusy

        try:
            if not STORE.current_character_session(
                account_id, generation, character["id"]
            ):
                raise ValueError("Exploration action session expired")
            flush_positions(
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
            )
            route = pending["route"]
            saved = exploration_artifact_actions.transition(
                STORE,
                account_id,
                generation,
                character["id"],
                pending["body"],
                expected_plan=route,
                source_allowed=teleporter_approach.callback(
                    movement_state,
                    map_id=character["map_id"],
                    instance_id=character.get("instance_id", 0),
                ),
                position_allowed=artifact_position_allowed,
                blocked=environment_blocked(),
            )
        except PositionOwnerBusy:
            return
        except ValueError as error:
            cancel_artifact_action(str(error))
            from wakfu_server.ecology_feedback import information

            send(connection, service, *information(artifact_failure_message(error)))
            return
        pending_artifact_action = None
        publish_public_transport(route, saved, generic_route=True)

    def cancel_environment(*, publish=True):
        nonlocal environment_ticket, environment_seat, paid_container_ticket
        cancel_artifact_action("Environment action cancelled")
        if paid_container_ticket is not None:
            from wakfu_server.paid_containers import cancel

            result = cancel(
                STORE, account_id, generation, character, paid_container_ticket
            )
            paid_container_ticket = None
            if publish:
                for packet in result["packets"]:
                    WORLD.emit_location(*result["location"], *packet)
                publish_environment_scene(force=True)
        if environment_ticket is not None:
            from wakfu_server.environment_interactions import cancel

            cancel(STORE, account_id, generation, environment_ticket["character_id"])
            environment_ticket = None
        if environment_seat is not None:
            from wakfu_server.environment_seats import release

            occupied = environment_seat
            result = release(STORE, account_id, generation, occupied["character_id"])
            environment_seat = None
            if publish:
                for packet in result["packets"]:
                    send(connection, service, *packet)
                publish_environment_scene(force=True)

    def environment_actor_is_hero():
        from wakfu_server.heroes import ensure_company_party

        roster = ensure_company_party(STORE, account_id, generation, character["id"])
        if roster["leader"]["id"] == character["id"]:
            return False
        if any(hero["id"] == character["id"] for hero in roster["heroes"]):
            return True
        raise ValueError("Environment actor is outside the owned company")

    def environment_blocked(*, allow_seated=False, allow_paid=False):
        if (
            fight is not None
            or combat_session is not None
            or spectator_session is not None
            or bag_session is not None
            or flora_ticket is not None
            or (paid_container_ticket is not None and not allow_paid)
            or (environment_seat is not None and not allow_seated)
        ):
            return True
        with PLANTINGS.lock:
            planting = character["id"] in PLANTINGS.pending
        with HARVESTS.lock:
            harvesting = character["id"] in HARVESTS.pending
        if planting or harvesting:
            return True
        from wakfu_server.crafting import current

        return current(STORE, account_id, generation, character["id"]) is not None

    def publish_environment_scene(*, force=False):
        import itertools

        nonlocal environment_scene_identity, environment_scene_states
        nonlocal last_environment_refresh
        if (
            not loaded
            or character is None
            or fight is not None
            or combat_session is not None
            or spectator_session is not None
            or character.get("instance_id", 0) != 0
        ):
            return
        now = time.monotonic()
        if not force and now - last_environment_refresh < 1:
            return
        from wakfu_server.environment_interactions import snapshots
        from wakfu_server.world_scene_sync import chunk, neighborhood

        selected = neighborhood(chunk(character))
        nearby = {
            row["id"]
            for row in world_static.objects(character["map_id"])
            if chunk((row["x"], row["y"])) in selected
        }
        identity = (
            character["map_id"],
            character.get("instance_id", 0),
            chunk(character),
        )
        previous = (
            environment_scene_states if environment_scene_identity == identity else {}
        )
        current = {}
        from wakfu_server.environment_seats import snapshots as seat_snapshots

        from wakfu_server.environment_doors import snapshots as door_snapshots
        from wakfu_server.treasure_chests import snapshots as treasure_snapshots
        from wakfu_server.paid_containers import snapshots as paid_container_snapshots

        for packet in itertools.chain(
            snapshots(STORE, character["map_id"]),
            seat_snapshots(STORE, character["map_id"]),
            door_snapshots(
                STORE, character["map_id"], character.get("instance_id", 0), nearby
            ),
            treasure_snapshots(
                STORE, account_id, character["map_id"], character_id=character["id"]
            ),
            paid_container_snapshots(
                STORE, character["map_id"], character.get("instance_id", 0)
            ),
        ):
            object_id = struct.unpack_from(">q", packet[1])[0]
            if object_id not in nearby:
                continue
            if force or previous.get(object_id) != packet:
                send(connection, service, *packet)
            current[object_id] = packet
        environment_scene_identity, environment_scene_states = identity, current
        last_environment_refresh = now

    def complete_environment_occupation():
        nonlocal environment_ticket, character
        if environment_ticket is None:
            return
        if (
            not loaded
            or character is None
            or environment_blocked()
            or any(
                character.get(key) != environment_ticket[key]
                for key in ("map_id", "x", "y", "z")
            )
        ):
            cancel_environment()
            return
        if STORE.now() < environment_ticket["due_at"]:
            return
        from wakfu_server.environment_interactions import complete

        try:
            result = complete(
                STORE,
                account_id,
                generation,
                character["id"],
                environment_ticket["token"],
                location=character,
                is_hero=environment_actor_is_hero(),
            )
        except ValueError as error:
            cancel_environment()
            record(
                event="environment_occupation_rejected",
                actor_id=character["id"],
                reason=str(error),
            )
            return
        for packet in result["packets"]:
            send(connection, service, *packet)
        if result.get("character") is not None:
            saved = result["character"]
            character.update(
                {key: saved[key] for key in ("inventory_items", "inventory_containers")}
            )
        environment_ticket = None

    def publish_native_monster_destructions(location):
        """Retry committed removals; socket failure never reverses their receipt."""
        from wakfu_server.objectives.environmental_destroy_publication import publish

        try:
            return publish(
                STORE,
                WORLD,
                COMBAT_GROUPS,
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                now_ms=int(STORE.now().timestamp() * 1000),
            )
        except OSError as error:
            record(
                event="environmental_monster_destroy_publication_pending",
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                reason=type(error).__name__,
            )
            return 0

    def try_native_monster_destroy(body):
        """Handle only durable event-owned targets; leave NPC cnT requests alone."""
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.ecology_feedback import information

        if type(body) is not bytes or len(body) != 16:
            return False
        target_id, action_id = struct.unpack(">qq", body)
        try:
            current = owned_planting_character(character, WORLD, POSITIONS, store=STORE)

            def reachable(owner, monster):
                source = tuple(owner[key] for key in ("x", "y", "z"))
                target = tuple(monster[key] for key in ("x", "y", "z"))
                return any(
                    tuple(a) == source and tuple(b) == target
                    for a, b in map_geometry(owner["map_id"])["edges"]
                )

            with COMBAT_GROUPS.lock:
                with STORE.connection() as db:
                    owned = db.execute(
                        "SELECT 1 FROM environmental_owned_groups g "
                        "JOIN environmental_owned_group_members m USING(instance_id,group_ordinal) "
                        "WHERE g.map_id=%s AND g.world_instance_id=%s AND m.monster_id=%s",
                        (current["map_id"], current["instance_id"], target_id),
                    ).fetchone()
                    if owned is None:
                        return False
                    from wakfu_server.objectives import environmental_monster_actions
                    from wakfu_server.objectives import environmental_monster_destroy
                    from wakfu_server.objectives.environmental_gameplay import (
                        committed_monster_destroy,
                    )

                    environmental_monster_actions.decode_request(body)
                    now_ms = int(STORE.now().timestamp() * 1000)
                    receipt = environmental_monster_destroy.commit(
                        STORE,
                        db,
                        account_id,
                        generation,
                        current,
                        body,
                        groups=COMBAT_GROUPS,
                        reachable=reachable,
                        loaded=loaded,
                        blocked=(
                            fight is not None
                            or combat_session is not None
                            or spectator_session is not None
                            or hero_switch_pending is not None
                            or bag_session is not None
                            or ranch_session is not None
                        ),
                        location_context=lambda stored: owned_planting_character(
                            stored, WORLD, POSITIONS, store=STORE
                        ),
                        now_ms=now_ms,
                    )
                    if not receipt["replayed"]:
                        committed_monster_destroy(db, receipt)
            publish_native_monster_destructions(receipt)
            poll_environmental_events()
            record(
                event="environmental_monster_destroyed",
                actor_id=receipt["character_id"],
                monster_id=receipt["monster_id"],
                action_id=receipt["action_id"],
                replayed=receipt["replayed"],
            )
        except (ValueError, DatabaseError, PoolTimeout) as error:
            record(
                event="environmental_monster_destroy_rejected",
                actor_id=character["id"],
                target_id=target_id,
                action_id=action_id,
                reason=type(error).__name__,
            )
            send(
                connection,
                service,
                *information(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Native monster destruction is temporarily unavailable."
                ),
            )
        return True

    def cancel_flora():
        nonlocal flora_ticket, flora_retry_body
        flora_retry_body = None
        cancel_environment()
        if flora_ticket is not None:
            from wakfu_server.resource_collect import cancel

            cancel(STORE, flora_ticket)
            flora_ticket = None

    def complete_flora_occupation(body):
        nonlocal character, flora_ticket, flora_retry_body
        from wakfu_server.resource_collect import (
            complete,
            acknowledge_publication,
            HarvestNotReady,
        )

        if flora_ticket is None:
            return
        try:
            if fight is not None:
                raise ValueError("La cosecha requiere estar fuera del combate")
            with PLANTINGS.publisher_lock:
                result = complete(
                    STORE,
                    flora_ticket,
                    body,
                    location_context=lambda stored: owned_planting_character(
                        stored, WORLD, POSITIONS, store=STORE
                    ),
                )
                for message_id, payload in result["world_packets"]:
                    WORLD.emit_location(
                        result["map_id"], result["instance_id"], message_id, payload
                    )
                acknowledge_publication(STORE, result)
            flora_ticket = None
            flora_retry_body = None
            if result["applied"]:
                saved = STORE.character(account_id, character["id"])
                character = (
                    active_private_session().refresh(character, saved)
                    if active_private_session() is not None
                    else saved
                )
            for message_id, payload in result["packets"]:
                if message_id == 13574:
                    WORLD.update(
                        generation, character, message_id, payload, include_sender=False
                    )
                send(connection, service, message_id, payload)
            if result["applied"]:
                send_native_planting_bonus(connection, character)
            record(
                event="resource_harvest_completed",
                actor_id=character["id"],
                applied=result["applied"],
                ecology=result.get("outcome", {}).get("ecology", {}).get("reason"),
            )
        except HarvestNotReady:
            # Keep the owned operation; the idle poll finishes it at its deadline.
            flora_retry_body = body
        except ValueError as error:
            cancel_flora()
            record(
                event="resource_harvest_rejected",
                actor_id=character["id"],
                reason=str(error),
            )
            from wakfu_server.ecology_feedback import information
            from wakfu_server.player_action_feedback import failure_message

            send(
                connection,
                service,
                *information(failure_message("harvest", error)),
            )

    def cancel_crafting():
        cancel_environment()
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
            if current["id"] == character["id"]:
                WORLD.update(generation, current, *packet)
            else:
                # Heroes share the leader's world subscription, rather than
                # owning a separate registered world connection.
                send(connection, service, *packet)
                WORLD.broadcast(
                    generation, character["id"], *packet, include_sender=False
                )
        send_native_planting_bonus(connection, current)

    @PROFILER.profile("combat.checkpoint")
    def checkpoint_fight(status=None, *, deliver=True):
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
            if combat_session is not None and deliver:
                # Live presentation retains its existing ordered drain. Logout
                # checkpoints the canonical state independently of a dead socket;
                # other owners' outboxes and the native ACK remain untouched.
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
        from wakfu_server.combat_encounter_scene_helpers import reward_eligible_members
        from wakfu_server.item_test_spawns import (
            is_fight as is_developer_test_fight,
            finish as finish_developer_test_group,
        )

        committed_task_candidates = []
        reward_monsters = reward_eligible_members(fight, TEST_MONSTERS)

        def mark_committed_custom_tasks():
            custom_task_cards.changed(
                character["id"],
                tuple(
                    update["character_id"]
                    for update in committed_task_candidates
                    if update["account_id"] == account_id
                    and update["result"]["updated"]
                ),
            )

        def settle_achievements(db, members, candidate):
            if (getattr(candidate, "rift_wave_state", None) or {}).get(
                "outcome"
            ) == "administrative_victory":
                return {}
            if is_developer_test_fight(db, candidate.id):
                return {}
            from wakfu_server.achievements.combat_adapter import settle_participants

            try:
                admitted = COMBAT_SESSIONS.registry.lookup(candidate.id)
            except ValueError:
                # Legacy non-registry settlement has no environmental origin.
                admitted = None
            from wakfu_server.objectives.environmental_gameplay import (
                scene_from_admission,
            )

            environmental_scene = (
                scene_from_admission(admitted) if admitted is not None else None
            )
            from wakfu_server.combat_aguabrial_story import settle_aguabrial_story

            story_packets = settle_aguabrial_story(STORE, db, candidate, members)
            delivery = settle_participants(
                db,
                STORE,
                candidate,
                members,
                reward_eligible_members(candidate, TEST_MONSTERS),
                environmental_scene=environmental_scene,
            )
            # Collect metadata only; mark dirty after the enclosing commit.
            committed_task_candidates.extend(delivery.get("custom_task_updates", ()))
            # Durable notification keys remain pending until a complete native
            # bootstrap covers their state; disconnect never loses progress.
            packets_by_owner = {
                owner: list(packets)
                for owner, packets in delivery["packets_by_owner"].items()
            }
            for owner, packets in story_packets.items():
                packets_by_owner.setdefault(owner, []).extend(packets)
            return packets_by_owner

        if combat_session is not None:
            from wakfu_server.combat_lifecycle import prepare_finish_shared
            from wakfu_server.monster_removal_ecology import (
                finish as finish_world_group,
            )
            from wakfu_server import combat_reward_context, reward_policy
            from wakfu_server import combat_drops, combat_drop_delivery
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.inventory_items import equipment_inventory

            shared = refresh_shared_combat()
            if shared is None:
                raise ValueError("Shared fight registry entry is unavailable")
            owner_characters, _ = COMBAT_SESSIONS.player_sources(fight)
            from wakfu_server.combat_terminal_metadata import (
                owner_characters_for_finish,
                registered_summon_actor_ids,
                registered_summon_metadata,
            )

            owner_characters = owner_characters_for_finish(
                STORE, shared, fight, owner_characters
            )
            summon_actor_ids = registered_summon_actor_ids(fight)
            from wakfu_server.combat_companions import registered_companion_ids

            companion_actor_ids = registered_companion_ids(fight)
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
                    if actor.controlled
                    and actor.id not in summon_actor_ids
                    and actor.id not in companion_actor_ids
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
                character.update(
                    refresh_owned_character(
                        STORE.character(account_id, character["id"])
                    )
                )
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
                if actor.controlled
                and actor.id not in summon_actor_ids
                and actor.id not in companion_actor_ids
            }
            metadata.update(registered_summon_metadata(fight))
            metadata.update(
                {
                    identity: dict(kind="monster", ref=source["ref"])
                    for identity in companion_actor_ids
                    for source in (fight.native_companion_sources[str(identity)],)
                }
            )
            metadata.update(
                {
                    monster_id: dict(kind="monster", ref=monster["ref"])
                    for monster_id, monster in TEST_MONSTERS_BY_ID.items()
                }
            )
            frozen_contexts = {}

            def settle_rift_rewards(db):
                from wakfu_server import rift_runtime
                from wakfu_server import rift_rewards
                from wakfu_server.combat_encounter_roles import assigned_roles

                rift_roles = assigned_roles(fight)

                eligible = tuple(
                    actor.id
                    for actor in fight.actors.values()
                    if actor.id in owner_characters
                    and actor.team == rift_roles.player_team
                    and not getattr(actor, "pve_withdrawn", False)
                )
                return rift_runtime.settle(
                    db,
                    fight.rift_wave_state["instance_id"],
                    fight.id,
                    outcome=(
                        "closed"
                        if fight.rift_wave_state.get("outcome")
                        in ("capacity_exhausted", "administrative_victory")
                        else "won"
                        if fight.winner == rift_roles.player_team
                        else "lost"
                        if fight.winner == rift_roles.npc_team
                        else "closed"
                    ),
                    turn=fight.native_timeline_round,
                    reconcile_earned_rewards=True,
                    apply_rewards=lambda reward_db, run, result: rift_rewards.apply(
                        reward_db,
                        run,
                        result,
                        store=STORE,
                        eligible_character_ids=eligible,
                        fight=fight,
                    ),
                )

            def shared_policy(db, member, source):
                if is_developer_test_fight(db, fight.id):
                    from wakfu_server.combat_rewards import Policy

                    return Policy()
                if getattr(fight, "rift_wave_state", None) is not None:
                    from wakfu_server import rift_currency_rewards
                    from wakfu_server.combat_encounter_roles import assigned_roles

                    # Loot receipts must exist before per-member native reports are built.
                    settle_rift_rewards(db)
                    return rift_currency_rewards.resolve(
                        STORE,
                        db,
                        account_id=member["account_id"],
                        generation=member["session_generation"],
                        character_id=member["character_id"],
                        fight=fight,
                        character=source,
                        eligible_character_ids=tuple(
                            actor.id
                            for actor in fight.actors.values()
                            if actor.id in owner_characters
                            and actor.team == assigned_roles(fight).player_team
                            and not getattr(actor, "pve_withdrawn", False)
                        ),
                    )
                context, drop_context = combat_reward_context.settlement_contexts(
                    db,
                    fight,
                    source,
                    reward_monsters,
                    encounter_kind=combat_reward_context.authoritative_encounter_kind(
                        db,
                        fight.id,
                        None if group_lease is None else group_lease[0],
                        dungeon_runtime_available=DUNGEON_ROOM_RUNTIME_AVAILABLE,
                    ),
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
                if is_developer_test_fight(db, fight.id):
                    return {"loots": [], "packets": []}
                if getattr(fight, "rift_wave_state", None) is not None:
                    from wakfu_server import rift_rewards

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
                from wakfu_server.combat_companions import loot_profiles

                batch = combat_drops.resolve(
                    STORE,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=member["character_id"],
                    fight_id=fight.id,
                    monsters=[
                        {"actor_id": monster["id"], "reference": monster["ref"]}
                        for monster in reward_monsters
                    ],
                    prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                    shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
                    can_loot=True,
                    fight_context=drop_context,
                    companion_rolls=loot_profiles(fight, member["character_id"]),
                )
                from wakfu_server.quest_inventory import changes as quest_changes

                before_loot = STORE.character(
                    member["account_id"], member["character_id"], db
                )
                combat_drop_delivery.apply(STORE, db, batch)
                saved = STORE.character(
                    member["account_id"], member["character_id"], db
                )
                return {
                    "loots": combat_drops.report_loots(
                        batch, loot_actor_id=member["character_id"]
                    ),
                    "packets": [
                        *quest_changes(before_loot, saved),
                        synchronization(saved),
                        equipment_inventory(saved),
                        combat_drop_delivery.temporary_update(
                            db, member["character_id"]
                        ),
                    ],
                }

            def shared_group_settlement(db, owner_account, owner_character, defeated):
                if group_lease is not None:
                    developer_result = finish_developer_test_group(
                        db, COMBAT_GROUPS, group_lease
                    )
                    if developer_result is not None:
                        return developer_result
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

                    retain(db, fight, reward_monsters)
                if (
                    outcome["applied"]
                    and DUNGEON_ROOM_RUNTIME_AVAILABLE
                    and group_lease[0][1] > 0
                ):
                    from wakfu_server import dungeon_progression, dungeon_runtime
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
                prepared = prepare_finish_shared(
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
                    progression_resolver=settle_achievements,
                    expected_accounts=set(current_shared.participants),
                    owner_character_ids={
                        owner: session.character_id
                        for owner, session in current_shared.participants.items()
                    },
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

                mark_committed_custom_tasks()
                return prepared

            if group_lease is None:
                COMBAT_SESSIONS.settle_finished(
                    combat_session, fight.id, prepare_shared_packets
                )
            else:

                def prepare_grouped_shared_packets(current_shared):
                    # settle_finished already owns the frozen fight. Acquire
                    # groups here, in the same order as terminal marker
                    # publication, and retain them through the SQL commit.
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
                        return prepare_shared_packets(current_shared)

                COMBAT_SESSIONS.settle_finished(
                    combat_session, fight.id, prepare_grouped_shared_packets
                )
            refresh_shared_combat()
            drain_shared_combat()
            checkpoint_fight("ended")
            character.update(
                refresh_owned_character(STORE.character(account_id, character["id"]))
            )
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
        from wakfu_server import combat_reward_context, reward_policy

        def resolve_fight_reward(db):
            if is_developer_test_fight(db, fight.id):
                from wakfu_server.combat_rewards import Policy

                return Policy()
            context = combat_reward_context.build_context(
                fight, character, reward_monsters
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
            if is_developer_test_fight(db, fight.id):
                return {"loots": [], "packets": []}
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
                    {"actor_id": m["id"], "reference": m["ref"]}
                    for m in reward_monsters
                ],
                prospecting_bonus=combat_drops.native_prospection_bonus(actor),
                shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
                can_loot=True,
                fight_context=combat_reward_context.build_drop_context(
                    fight, character, reward_monsters
                ),
            )
            from wakfu_server.quest_inventory import changes as quest_changes

            before_loot = STORE.character(account_id, character["id"], db)
            combat_drop_delivery.apply(STORE, db, batch)
            saved = STORE.character(account_id, character["id"], db)
            return {
                "loots": combat_drops.report_loots(batch),
                "packets": [
                    *quest_changes(before_loot, saved),
                    synchronization(saved),
                    equipment_inventory(saved),
                    combat_drop_delivery.temporary_update(db, character["id"]),
                ],
            }

        def settle_individual_group(db, lease, defeated):
            developer_result = finish_developer_test_group(db, COMBAT_GROUPS, lease)
            if developer_result is not None:
                return developer_result
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

                retain(db, fight, reward_monsters)
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
                progression_resolver=settle_achievements,
                groups=COMBAT_GROUPS,
                group_lease=group_lease,
                group_settlement=settle_individual_group,
            )
        mark_committed_custom_tasks()
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
            stored = (
                character.get("builds", {})
                .get(character.get("active_build_index", 0), {})
                .get("deck")
            )
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
            stored = (
                character.get("builds", {})
                .get(character.get("active_build_index", 0), {})
                .get("deck")
            )
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

    def consume_command_combat_recovery(*, bootstrap=True):
        """Consume cancellation only at a socket action/idle boundary."""
        nonlocal publication_recovery_shared
        if character is None:
            return False
        from wakfu_server.combat_command_recovery import take_cancelled
        from wakfu_server.combat_shared import Session

        owner = combat_session or Session(
            account_id,
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )
        pending = take_cancelled(COMBAT_SESSIONS.registry, owner)
        if pending is None:
            return False
        publication_recovery_shared = pending
        if bootstrap:
            return continue_aborted_publication_recovery()
        return recover_aborted_publication_cohort(bootstrap=False)

    def command_recovery_holds_request(opcode, body=None):
        """Drop stale combat actions but keep chat after completed world recovery."""
        recovering = consume_command_combat_recovery()
        if not recovering:
            recovering = continue_aborted_publication_recovery()
        if not recovering:
            return False
        if opcode == 12925 and aborted_native_return is not None:
            return False
        if (
            opcode == 12366
            and body is not None
            and aborted_native_return is not None
            and aborted_native_return.command is None
        ):
            from wakfu_server.combat_return_command import PendingEmergencyCommand

            aborted_native_return.require(account_id, generation, character["id"])
            command = PendingEmergencyCommand()
            identity = (account_id, generation, character["id"])
            if command.retain(opcode, body, identity):
                aborted_native_return.command = command.take(
                    identity,
                    valid_session=lambda: STORE.current_character_session(*identity),
                )
        return not (
            opcode == 12366
            and fight is None
            and combat_session is None
            and publication_recovery_shared is None
        )

    def attach_command_combat():
        """Bind selected emergency custody without publishing a fight constructor."""
        nonlocal combat_session, fight, fight_messages, group_lease
        nonlocal TEST_MONSTERS, TEST_MONSTERS_BY_ID, TEST_GROUP_KEY, fight_started_at
        nonlocal checkpoint_id, checkpoint_revision, checkpoint_terminal
        from wakfu_server.combat_command_recovery import bind_selected
        from wakfu_server.combat_shared import Session

        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is None:
            return None
        owner = Session(
            account_id,
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )
        shared = bind_selected(
            STORE, COMBAT_SESSIONS.registry, owner, CHECKPOINT_WRITER
        )
        combat_session, fight, fight_messages = owner, shared.fight, shared.runtime
        group_lease = shared.group_lease
        context = shared.join_context or {}
        TEST_MONSTERS_BY_ID = getattr(
            fight, "rift_monsters", context.get("monsters", {})
        )
        TEST_MONSTERS = tuple(TEST_MONSTERS_BY_ID.values())
        TEST_GROUP_KEY = context.get("group_key")
        fight_started_at = context.get("fight_started_at", time.monotonic())
        checkpoint_id, checkpoint_revision = fight.id, shared.checkpoint_revision
        checkpoint_terminal = shared.checkpoint_terminal
        return shared

    def emergency_exit_current_combat():
        """Commit an explicit escape before travel, independently of native ACKs."""
        nonlocal publication_recovery_shared
        from wakfu_server.combat_command_recovery import (
            bind_selected,
            cancel,
            release_settled,
            take_cancelled,
        )

        if combat_session is not None:
            pending = take_cancelled(COMBAT_SESSIONS.registry, combat_session)
            if pending is not None:
                publication_recovery_shared = pending
                recover_aborted_publication_cohort(bootstrap=False)
                return True
        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is None:
            shared = deferred_native_combat_attachment()
        if shared is None:
            return False
        owner = shared.participants.get(account_id)
        if owner is None or owner.character_id != character["id"]:
            raise ValueError("La sesión seleccionada cambió antes de salir del combate")
        if owner.generation != generation:
            from wakfu_server.combat_shared import Session

            owner = Session(
                account_id,
                character["id"],
                generation,
                character["map_id"],
                character.get("instance_id", 0),
            )
            shared = bind_selected(
                STORE, COMBAT_SESSIONS.registry, owner, CHECKPOINT_WRITER
            )
        if character["id"] in (
            getattr(shared, "publication_recovery_aborted", None) or {}
        ):
            publication_recovery_shared = shared
            return recover_aborted_publication_cohort(bootstrap=False)
        if not CHECKPOINT_WRITER.flush_fight(shared.fight.id, timeout=10):
            raise ValueError(
                "La escritura del combate sigue pendiente; vuelve a intentar salir"
            )
        if getattr(shared, "is_duel", False):
            if combat_session is None:
                attach_command_combat()
            if shared.fight.phase != "finished":
                COMBAT_SESSIONS.registry.forfeit_duel(owner, reason="defeat")
            if not shared.settlement_ready:
                refresh_shared_combat()
                complete_test_fight()
        if shared.settlement_ready:
            result = release_settled(STORE, COMBAT_SESSIONS.registry, owner)
        else:
            result = cancel(
                STORE,
                COMBAT_SESSIONS.registry,
                owner,
                groups=COMBAT_GROUPS,
                checkpoint_writer=CHECKPOINT_WRITER,
            )
            marker = EXTERNAL_FIGHT_MARKERS.remove(shared.fight.id)
            if marker is not None:
                WORLD.emit_location(
                    shared.map_id,
                    shared.instance_id,
                    *marker,
                    exclude_sessions=tuple(
                        (participant.character_id, participant.generation)
                        for participant in shared.participants.values()
                    ),
                )
            if shared.group_lease is not None:
                publish_full_abandon_group(shared, {"group_restored": True})
        if result is None:
            return False
        take_cancelled(COMBAT_SESSIONS.registry, owner)
        publication_recovery_shared = result["shared"]
        return recover_aborted_publication_cohort(bootstrap=False)

    @PROFILER.profile("admin.command")
    def execute_test_command(text, *, authorized_by=None):
        nonlocal character, position, movement_state, fight, fight_messages
        nonlocal bag_session, ranch_session
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
            if command == "!astrub" and target is None and issuer == account_id:
                if len(text.split()) != 1:
                    raise ValueError("Uso: !astrub")
                emergency_exit_current_combat()
                if (
                    aborted_native_return is not None
                    and not aborted_native_return.world_returned
                ):
                    aborted_native_return.command = text
                    return {
                        "message": "El combate está cancelado; finalizando su salida."
                    }
            if (
                command in ("!astrub", "!tp")
                and target is None
                and issuer == account_id
                and deferred_native_combat_attachment() is not None
            ):
                fields = text.split()
                if len(fields) != (1 if command == "!astrub" else 5):
                    raise ValueError("Uso: !astrub | !tp mapa x y z")
                from wakfu_server.combat_terrain import map_geometry

                destination = (
                    (527, 0, 32, 0)
                    if command == "!astrub"
                    else tuple(int(value) for value in fields[1:])
                )
                if destination[1:] not in {
                    tuple(cell) for cell in map_geometry(destination[0])["cells"]
                }:
                    raise ValueError("La casilla de destino no es transitable")
                abort_waiting_publication_cohort()
                if (
                    aborted_native_return is not None
                    and not aborted_native_return.world_returned
                ):
                    aborted_native_return.command = text
                    return {
                        "message": "El combate está cancelado; finalizando su salida."
                    }
                if deferred_native_combat_attachment() is not None:
                    return {
                        "message": "El combate ya se abandonó; el regreso al mapa sigue pendiente. Repite el comando al terminar de cargar."
                    }
            if command == "!merkamundo":
                from wakfu_server.guild_haven_world import create_assignment
                from wakfu_server.haven_world_travel import travel

                words = text.split()
                if target is not None or issuer != account_id or len(words) > 2:
                    raise ValueError(
                        "Uso: !merkamundo [asignar|salir] (solo el personaje propio)"
                    )
                if active_private_session() is not None:
                    raise ValueError(
                        "Sal del merkasaco o Rancho antes de cambiar de Merkamundo"
                    )
                action = words[1].lower() if len(words) == 2 else "entrar"
                if action == "asignar":
                    with STORE.connection() as db:
                        member = db.execute(
                            "SELECT guild_id FROM guild_members WHERE character_id=%s",
                            (character["id"],),
                        ).fetchone()
                    if member is None:
                        raise ValueError("El personaje debe pertenecer a un gremio")
                    binding = create_assignment(
                        STORE,
                        account_id,
                        generation,
                        character["id"],
                        member["guild_id"],
                    )
                    answer = "Merkamundo asignado al gremio " + str(binding["guild_id"])
                elif action in ("entrar", "salir"):
                    outcome = travel(
                        STORE,
                        POSITIONS,
                        account_id,
                        generation,
                        character["id"],
                        leave=action == "salir",
                    )
                    publish_haven_world_travel(outcome)
                    answer = (
                        "Has salido del Merkamundo"
                        if action == "salir"
                        else "Has entrado al Merkamundo de tu gremio"
                    )
                else:
                    raise ValueError("Uso: !merkamundo [asignar|salir]")
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
            if command == "!chest":
                from wakfu_server.haven_chest import deposit_all
                from wakfu_server.haven_chest_wire import (
                    action_result as chest_action_result,
                    bootstrap as chest_bootstrap,
                )
                from wakfu_server.inventory_move import synchronization
                from wakfu_server.inventory_items import equipment_inventory

                if (
                    text.split() != ["!chest", "depositall"]
                    or target is not None
                    or issuer != account_id
                ):
                    raise ValueError(
                        "Uso: !chest depositall (solo el personaje propio)"
                    )
                if (
                    chest_opening is None
                    or fight is not None
                    or combat_session is not None
                ):
                    raise ValueError(
                        "Abre tu cofre fuera de combate antes de depositar"
                    )
                result = deposit_all(
                    STORE,
                    account_id,
                    generation,
                    character["id"],
                    opening_token=chest_opening,
                    location=character,
                    ranch_session=ranch_session,
                )
                character = active_private_session().refresh(
                    character, result["character"]
                )
                for owner in result.get("inventory_characters", (character,)):
                    for packet in (synchronization(owner), equipment_inventory(owner)):
                        send(connection, service, *packet)
                for packet in (chest_bootstrap(result["chest"]), chest_action_result()):
                    send(connection, service, *packet)
                record(
                    event="account_chest_deposited_all",
                    actor_id=character["id"],
                    applied=result["applied"],
                    revision=result["chest"]["revision"],
                )
                answer = "Depósito completado; los objetos equipados y de misión permanecen en el inventario"
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
            if command == "!foodclear":
                from wakfu_server.consumable_world_lifecycle import clear_for_test
                from wakfu_server.consumable_buff_wire import delta

                if len(text.split()) != 1 or target is not None or issuer != account_id:
                    raise ValueError("Uso: !foodclear (solo el personaje propio)")
                if fight is not None or combat_session is not None:
                    raise ValueError(
                        "Sal del combate antes de retirar los efectos de comida"
                    )
                previous = character
                character = clear_for_test(STORE, account_id, generation, character)
                for packet in delta(
                    previous,
                    character,
                    allocate_action=lambda: next(LOCAL_WORLD_ACTIONS),
                ):
                    WORLD.broadcast(generation, character["id"], *packet)
                publish_consumable_character(character)
                answer = "Efectos de consumibles retirados; puedes iniciar la siguiente prueba"
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
            from wakfu_server.custom_tasks import external as objectives_mode

            if objectives_mode.enabled() and command in (
                "!astrub",
                "!tp",
                "!nivel",
                "!item",
                "!kamas",
                "!mob",
            ):
                from wakfu_server.objectives.challenges import mark_scene_test

                with STORE.connection() as challenge_db:
                    source = challenge_db.execute(
                        "SELECT c.instance_id,r.attempt_id FROM characters c "
                        "JOIN objectives_challenge_runs r ON r.instance_id=c.instance_id "
                        "AND r.map_id=c.map_id AND r.owner_account_id=c.account_id "
                        "AND r.returned_at IS NULL WHERE c.id=%s AND c.account_id=%s",
                        (character["id"], account_id),
                    ).fetchone()
                    if source is not None and command not in ("!astrub", "!tp"):
                        mark_scene_test(challenge_db, source["instance_id"])
                if source is not None:
                    if command == "!astrub":
                        from wakfu_server.objectives.challenges import (
                            return_from_challenge,
                        )

                        with POSITIONS.account_barrier(account_id):
                            flush_positions(account_id=account_id)
                            with STORE.connection() as challenge_db:
                                moved_ids = tuple(
                                    row["character_id"]
                                    for row in challenge_db.execute(
                                        "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s",
                                        (source["attempt_id"],),
                                    ).fetchall()
                                )
                                return_from_challenge(
                                    challenge_db,
                                    account_id,
                                    character["id"],
                                    abandon=True,
                                )
                                character = STORE.character(
                                    account_id, character["id"], challenge_db
                                )
                            for member_id in moved_ids:
                                POSITIONS.release(account_id, generation, member_id)
                    elif command == "!tp":
                        raise ValueError(
                            "Use !challenge abandon before leaving the weekly challenge."
                        )
            if command in ("!winfight", "!losefight"):
                from wakfu_server.combat_test_commands import finish
                from wakfu_server.combat_command_recovery import (
                    apply_outcome,
                    bind_current_owners,
                    release_deferred_owners,
                )

                if len(text.split()) != 1 or target is not None:
                    raise ValueError("Uso: !winfight | !losefight")
                if issuer != account_id:
                    raise ValueError("El comando solo afecta al combate propio")
                command_from_world = fight is None and combat_session is None
                if command_from_world:
                    attach_command_combat()
                if fight is None and combat_session is None:
                    answer = "No hay ningún combate pendiente."
                    send(connection, service, *information(answer))
                    return {"message": answer}
                from wakfu_server.custom_tasks import external as objectives_mode

                if objectives_mode.enabled() and fight is not None:
                    from wakfu_server.objectives.challenges import mark_test_fight

                    with STORE.connection() as challenge_db:
                        mark_test_fight(challenge_db, fight.id)
                if combat_session is not None:
                    bind_current_owners(
                        STORE,
                        COMBAT_SESSIONS.registry,
                        character["id"],
                        CHECKPOINT_WRITER,
                    )
                    shared_outcome = apply_outcome(
                        COMBAT_SESSIONS.registry,
                        combat_session,
                        win=command == "!winfight",
                    )
                    if shared_outcome is None:
                        emergency_exit_current_combat()
                        answer = "El combate ya está cerrado."
                        send(connection, service, *information(answer))
                        return {"message": answer}
                    refresh_shared_combat()
                else:
                    terminal = finish(
                        fight,
                        fight_messages,
                        account_id=account_id,
                        character_id=character["id"],
                        win=command == "!winfight",
                    )
                    fight, fight_messages = terminal.fight, terminal.runtime
                record(
                    event="test_console_combat_outcome",
                    command=command,
                    actor_id=character["id"],
                    account_id=account_id,
                    fight_id=fight.id,
                    winner=fight.winner,
                )
                outcome_actor = fight.actors.get(character["id"])
                outcome_won = (
                    fight.winner == outcome_actor.team
                    if outcome_actor is not None
                    and outcome_actor.controlled
                    and outcome_actor.owner_id == account_id
                    and fight.winner in (0, 1)
                    else None
                )
                complete_test_fight()
                checkpoint_fight("ended")
                if combat_session is not None:
                    completed_shared = COMBAT_SESSIONS.registry.lookup(fight.id)
                    release_deferred_owners(
                        STORE, COMBAT_SESSIONS.registry, completed_shared
                    )
                if command_from_world:
                    emergency_exit_current_combat()
                    if (
                        aborted_native_return is None
                        or aborted_native_return.world_returned
                    ):
                        send_batch(connection, service, combat_return_bootstrap())
                        join_world(generation, connection, character)
                        mark_static_sync_pending()
                answer = (
                    "El combate ya está cerrado."
                    if outcome_won is None
                    else "Combate ganado."
                    if outcome_won
                    else "Combate perdido."
                )
                send(
                    connection,
                    service,
                    674,
                    wire.chat(dict(character, name="Consola local"), answer),
                )
                return {"message": answer}
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
                if args[0].startswith("eco-"):
                    receipt = ECOLOGY_ADMIN_JOBS.status(args[0])
                    if receipt.get("account_id") != issuer and not is_admin(
                        STORE, issuer
                    ):
                        raise PermissionError("El recibo pertenece a otra cuenta")

                    from wakfu_server.ecology_feedback import (
                        information as ecology_information,
                    )

                    send(connection, service, *ecology_information(receipt["message"]))
                    return {"message": receipt["message"], "ecology_job": receipt}
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
            ecology_submission = submit_ecology_admin_command(
                connection, service, account_id, generation, character, command, text
            )
            if ecology_submission is not None:
                return ecology_submission
            if command in (
                "!tp",
                "!astrub",
                "!mob",
                "!item",
                "!equip",
                "!unequip",
                "!nivel",
            ) and (fight is not None or combat_session is not None):
                if fight is not None and fight.phase == "finished":
                    raise ValueError(
                        "El combate terminó, pero su cierre sigue pendiente. Cierra la pantalla de resultados. "
                        "Si no responde, desconecta a todo el grupo y pide a un administrador "
                        "inspeccionar y cancelar la recuperación del combate "
                        + str(fight.id)
                        + "."
                    )
                raise ValueError(
                    "Termina el combate antes de modificar el mundo o el inventario."
                )
            if bag_session is not None and (
                command == "!tp" or (command == "!mob" and ranch_session is None)
            ):
                raise ValueError(
                    "Sal del combate o del merkasaco antes de usar este comando."
                )
            if command == "!astrub" and ranch_session is not None:
                validate_ranch_lease()
            flush_positions(
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
            )
            from contextlib import contextmanager

            ecology_command = command in (
                "!nuke",
                "!nuke-all",
                "!genesis",
                "!genesis-all",
                "!eco-status",
                "!nuke-all-flora",
                "!genesis-all-flora",
            )

            ecology_coordination = ecology_admin_coordination

            def publish_ecology_admin(outcome):
                publish_ecology_admin_outcome(dict(outcome, command=command))

            result = execute(
                STORE,
                COMBAT_GROUPS if COMBAT_TEST else None,
                account_id,
                generation,
                character,
                text,
                authorized_by=issuer,
                ecology_players=WORLD.ecology_snapshot if ecology_command else (),
                ecology_coordination=ecology_coordination if ecology_command else None,
                ecology_publish=publish_ecology_admin if ecology_command else None,
                private_scene=ranch_session,
                positions=POSITIONS,
            )
            if result["action"] == "tp" and deliver_rift_transition():
                # Native departure already owns one complete scene bootstrap.
                pass
            elif result["action"] == "tp":
                leaving_ranch = command == "!astrub" and ranch_session is not None
                leaving_private = command == "!astrub" and bag_session is not None
                if command == "!astrub" and bag_session is not None:
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    cancel_flora()
                    exterior = HAVEN_BAG_EXTERIORS.discard(
                        generation, bag_session.exterior_actor_id
                    )
                    if exterior is not None:
                        outside, packet = exterior
                        WORLD.emit_location(
                            outside["map_id"], outside["instance_id"], *packet
                        )
                    if ranch_session is not None:
                        ranch_session.leave(character)
                    bag_session = None
                    ranch_session = None
                cancel_crafting()
                WORLD.leave(character["id"], generation)
                character = result["character"]
                POSITIONS.attach(account_id, generation, character)
                position = {key: character[key] for key in ("x", "y", "z")}
                movement_state = Movement(position)
                transition_messages = (
                    owned_haven_leave(fixture(13974), character)
                    if leaving_private
                    else owned_native_bootstrap(character)
                )
                for message_id, message_body in transition_messages:
                    # Ranch entry already cleared the non-nullsafe bpq controller.
                    if leaving_ranch and message_id == 13019:
                        continue
                    send(connection, service, message_id, message_body)
                join_world(generation, connection, character)
                mark_static_sync_pending()
            else:
                character = (
                    active_private_session().refresh(character, result["character"])
                    if active_private_session() is not None
                    and active_private_session().owns(character)
                    else result["character"]
                )
                for message_id, message_body in result["packets"]:
                    send(connection, service, message_id, message_body)
                if result["action"] == "nivel":
                    from wakfu_server.level_publication import refresh

                    for message_id, message_body in refresh(
                        character,
                        STORE.characters(account_id),
                        entity_template=OWNED_HERO_TEMPLATE,
                        roster_template=CHARACTERS,
                        retained_state_packets=consumable_state_packets,
                    ):
                        send(connection, service, message_id, message_body)
                    send_native_planting_bonus(connection, character)
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
            wire.chat(dict(character, name="Consola local"), answer.splitlines()[0]),
        )
        for line in answer.splitlines()[1:]:
            send(
                connection,
                service,
                674,
                wire.chat(dict(character, name="Consola local"), line),
            )
        if failure is not None:
            raise failure
        summary = {"message": answer}
        if "item" in result:
            summary["item"] = {
                key: result["item"][key]
                for key in ("uid", "reference", "quantity", "container", "slot")
                if key in result["item"]
            }
        if "group_key" in result:
            summary["group_key"] = list(result["group_key"])
            summary["actor_ids"] = [member["id"] for member in result["members"]]
        return summary

    def shared_action_incident(
        runtime,
        action_type,
        body,
        source,
        owner_deck,
        characters,
        decks,
        *,
        actor_id=None,
        turn_id=None,
    ):
        if not os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
            return nullcontext()
        try:
            from wakfu_server.combat_shared_incident_capture import (
                current_shared_incident,
                shared_incidents_suppressed,
            )

            if shared_incidents_suppressed():
                return nullcontext()
            from wakfu_server.combat_incident_capture import (
                incident_enabled,
                incident_scope,
            )

            if not incident_enabled():
                return nullcontext()
            # End-turn obtains authority through its actual runtime providers.
            # Do not add a diagnostic Store read that gameplay never performs;
            # those providers record their consumed sources when invoked.
            action = dict(type=action_type, owner_id=combat_session.account_id)
            if action_type == "end_turn":
                action.update(actor_id=actor_id, turn_id=turn_id)
            else:
                action["body"] = body
                if action_type != "move":
                    action["critical"] = (
                        False
                        if action_type == "player_unarmed"
                        else (
                            None
                            if COMBAT_TEST_CRITICAL_BRANCH == "auto"
                            else COMBAT_TEST_CRITICAL_BRANCH == "critical"
                        )
                    )
            # This records the actual connected operation. Its providers are not
            # accredited as equivalent to the isolated offline authority recipe.
            inputs = dict(
                authority_recipe="observed-live-server-v1",
                map_id=combat_session.map_id if source is None else source["map_id"],
                native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
                area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
                == "1",
                recipient_evidence="intended-participant-accounts-not-confirmed-routing",
                client_request_body=body,
            )
            if characters is not None:
                inputs.update(
                    character=source,
                    monsters=TEST_MONSTERS_BY_ID,
                    deck_blob=owner_deck,
                    player_characters=characters,
                    deck_blobs=decks,
                )
            outer = current_shared_incident()
            if outer is not None:
                outer.attach(
                    runtime, action, inputs, session=dict(requester=combat_session)
                )
                return nullcontext(outer)
            return incident_scope(
                runtime,
                action,
                inputs,
                session=dict(requester=combat_session),
                recipients=tuple(
                    sorted(
                        {
                            actor.owner_id
                            for actor in runtime.fight.actors.values()
                            if actor.owner_id is not None
                        }
                    )
                ),
            )
        except Exception as error:
            # Diagnostics must never replace the gameplay result or exception.
            try:
                record(
                    event="combat_incident_setup_failed",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
            return nullcontext()

    def current_combat_stats(actor, state=None):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_input_observation import observe_fact

        current_fight = fight if state is None else state
        if actor.id in getattr(current_fight, "native_summon_registrations", {}):
            from wakfu_server.combat_summon_stats import registered_summon_stats

            stats = registered_summon_stats(actor, current_fight, character["map_id"])
            observe_fact("current_combat_stats.summon_actor", actor.id)
            observe_fact("current_combat_stats.summon", stats)
            return stats
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
        companion_source = getattr(current_fight, "native_companion_sources", {}).get(
            str(actor.id)
        )
        if companion_source is not None:
            from wakfu_server.combat_companions import registered_source

            registered_source(current_fight, actor, companion_source)
            return actual_monster_actor_stats(
                companion_source,
                actor,
                current_fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
                fight=current_fight,
            )
        if actor.controlled:
            source = (
                STORE.character(actor.owner_id, actor.id) if COMBAT_TEST else character
            )
            observe_fact("current_combat_stats.player_source", source)
            stats = actual_actor_stats(
                source,
                actor,
                fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
            )
            observe_fact("current_combat_stats.player", stats)
            return stats
        source = TEST_MONSTERS_BY_ID[actor.id]
        observe_fact("current_combat_stats.monster_source", source)
        stats = actual_monster_actor_stats(
            source,
            actor,
            fight.id,
            wp_current=wp_current,
            wp_maximum=wp_maximum,
            direction=3,
        )
        observe_fact("current_combat_stats.monster", stats)
        return stats

    @PROFILER.profile("combat.refresh")
    def refresh_shared_combat(*, blocking=True):
        nonlocal fight, fight_messages, group_lease, TEST_MONSTERS, TEST_MONSTERS_BY_ID
        nonlocal pve_withdrawal_pending, combat_session, loaded, fight_started_at
        if combat_session is None or fight is None:
            return None
        try:
            shared = COMBAT_SESSIONS.registry.lookup(fight.id, blocking=blocking)
        except ValueError:
            retired = publication_recovery_shared
            if continue_aborted_publication_recovery():
                return retired
            raise
        if shared is None:
            return False
        fight = shared.fight
        fight_messages = shared.runtime
        receipt = shared.withdrawals.get(combat_session.account_id)
        if (
            getattr(shared, "full_abandon_owner", None) is not None
            and receipt is not None
            and receipt["session"] == combat_session
            and not receipt.get("full_abort_requester", False)
            and combat_session.account_id not in shared.returned
        ):
            pve_withdrawal_pending = receipt
            fight = fight_messages = None
            combat_session = group_lease = None
            loaded = False
            return shared  # Native12925 now selects the existing private-return branch.
        group_lease = getattr(shared, "group_lease", group_lease)
        context = shared.join_context or {}
        placement_origin = context.get("fight_started_at")
        if (
            fight.phase == "placement"
            and not shared.disconnect_abort_pending
            and placement_origin is not None
            and placement_origin != fight_started_at
        ):
            # Another owner may have completed the paused cohort. Every socket
            # must use the same resumed placement origin, including early waiters.
            fight_started_at = placement_origin
            placement_deadline.start(
                fight.id, context.get("duration_ms"), placement_origin
            )
        monsters = getattr(fight, "rift_monsters", context.get("monsters"))
        if monsters is not None:
            if getattr(fight, "rift_wave_state", None) is not None:
                context["monsters"] = monsters
            TEST_MONSTERS_BY_ID = monsters
            TEST_MONSTERS = tuple(monsters.values())
        return shared

    def publish_full_abandon_group(shared, result):
        if not result.get("group_restored") or shared.group_lease is None:
            return
        from wakfu_server.ecology_admin import current_available
        from wakfu_server.combat_monster_world import spawn_group

        key = shared.group_lease[0]
        members = current_available(STORE, key)
        if members:
            WORLD.emit_location(
                key[0],
                key[1],
                12608,
                owned_scene_spawn_group(members, group_id=key[2]),
                exclude_generation=generation,
            )

    def publish_external_marker(shared):
        if shared is None:
            return
        with shared.lock:
            return _publish_external_marker_locked(shared)

    def _publish_external_marker_locked(shared):
        """Publish public-world marker deltas, never to fight participants."""
        if not COMBAT_TEST or shared is None or getattr(shared, "is_duel", False):
            return
        fight = getattr(shared, "fight", None)
        if fight is None:
            return

        def public_member_packet(actor, source_fight):
            from wakfu_server.combat_multiplayer_wire import added
            from wakfu_server.combat_public_fighter_stats import (
                public_player_fighter_stats,
            )

            from wakfu_server.combat_actor import actual_actor_stats, actor_effects
            from wakfu_server.breed_resources import live_wp

            companion_source = getattr(
                source_fight, "native_companion_sources", {}
            ).get(str(actor.id))
            if companion_source is not None:
                from wakfu_server.combat_companions import registered_source
                from wakfu_server.combat_actor import actual_monster_actor_stats

                registered_source(source_fight, actor, companion_source)
                wp_current, wp_maximum = live_wp(source_fight, actor.id)
                return added(
                    source_fight.id,
                    actor.id,
                    actor_type=5,
                    team=actor.team,
                    stats=actual_monster_actor_stats(
                        companion_source,
                        actor,
                        source_fight.id,
                        wp_current=wp_current,
                        wp_maximum=wp_maximum,
                        fight=source_fight,
                    ),
                    effects=actor_effects(),
                )

            # A complete native snapshot already owns current gear/resources.
            # Legacy actors without it retain the full character reducer.
            source = (
                STORE.combat_public_character(actor.owner_id, actor.id)
                if getattr(actor, "effect_stats", None) is not None
                else STORE.character(actor.owner_id, actor.id)
            )
            wp_current, wp_maximum = live_wp(source_fight, actor.id)
            stats = actual_actor_stats(
                source,
                actor,
                source_fight.id,
                fight=source_fight,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
            )
            public = public_player_fighter_stats(
                stats, actor_id=actor.id, fight_id=source_fight.id
            )
            # Native ckT uses fighter stats for external membership; it does
            # not replay cvg effects or SQ. Preserve the existing canonical
            # empty effect descriptor instead of exposing owned retained rows.
            return added(
                source_fight.id,
                actor.id,
                actor_type=0,
                team=actor.team,
                stats=public,
                effects=actor_effects(),
            )

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
            try:
                packet = EXTERNAL_FIGHT_MARKERS.update(
                    shared, member_packet=public_member_packet
                )
            except (KeyError, TypeError, ValueError) as error:
                record(
                    event="combat_external_marker_publish_failed",
                    fight_id=fight.id,
                    reason=str(error),
                )
                return
        if packet is None or packet[0] == 12233:
            # Existing native contexts need an incremental member add; a
            # second13753 would replace their retained external model.
            exclusions = frozenset(
                (owner.character_id, owner.generation)
                for owner in (
                    *getattr(shared, "participants", {}).values(),
                    *SPECTATORS.sessions(fight.id),
                )
            )
            with WORLD.lock:
                peers = tuple(
                    peer
                    for lease, peer, owner in WORLD.players.values()
                    if not getattr(peer, "is_bot_peer", False)
                    and (owner["map_id"], owner.get("instance_id", 0))
                    == (shared.map_id, shared.instance_id)
                    and (owner["id"], lease) not in exclusions
                )
            for peer in peers:
                try:
                    with peer.write_lock:
                        scope = peer.native_instance_scope()
                        phases = peer.marker_publications.snapshot(scope)
                        if fight.id not in phases:
                            continue
                        delta = EXTERNAL_FIGHT_MARKERS.world_snapshots(
                            shared.map_id,
                            shared.instance_id,
                            known_phases=phases,
                            known_rosters=peer.marker_publications.roster_snapshot(
                                scope
                            ),
                            unbound_members=peer.marker_publications.unbound_snapshot(
                                scope
                            ),
                            only_fight_id=fight.id,
                        )
                        if packet is not None:
                            # The existing uniform transition below follows this
                            # roster repair in the SAME publication pass.
                            delta = tuple(row for row in delta if row[0] != 12233)
                        WORLD._send_batch(peer, delta)
                except (KeyError, TypeError, ValueError) as error:
                    record(
                        event="combat_external_marker_recipient_failed",
                        fight_id=fight.id,
                        target_connection_id=getattr(peer, "trace_id", None),
                        reason=str(error),
                    )
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
                    from wakfu_server.combat_world_group_cleanup import (
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
    def drain_shared_combat(*, blocking=True):
        if combat_session is None or fight is None:
            return

        delivered_batches = {}

        def deliver(owner, batches):
            for batch in batches:
                if batch.public_events:
                    delivered_batches.setdefault(batch.sequence, []).append(
                        batch.packets
                    )
            packets = tuple(packet for batch in batches for packet in batch.packets)
            if not packets:
                return
            if any(packet[0] == 12847 for packet in packets):
                # Membership is committed before outboxes drain. Replay icons
                # after the native fight constructor for late join/reconnect.
                from wakfu_server.combat_tactical_markers import snapshots

                packets += snapshots(COMBAT_SESSIONS.registry, owner, fight.id)
            if (
                owner.account_id == combat_session.account_id
                and owner.generation == combat_session.generation
                and owner.character_id == combat_session.character_id
            ):
                send_batch(connection, service, packets)
            else:
                WORLD.send_batch_to(owner.character_id, owner.generation, packets)

        if (
            COMBAT_SESSIONS.dispatch_connected(fight.id, deliver, blocking=blocking)
            is None
        ):
            return False
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
        return True

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
            public_pvp_duel=public_objectives_duel(shared),
        )
        if getattr(shared.fight, "rift_wave_state", None) is not None:
            from wakfu_server.rift_combat_adapter import world_snapshot

            return tuple(world_snapshot(shared.fight)) + tuple(packets)
        return packets

    def public_objectives_duel(shared):
        if not getattr(shared, "is_duel", False):
            return False
        from wakfu_server.custom_tasks.external import enabled

        if not enabled():
            return False
        with STORE.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM objectives_pvp_events WHERE fight_id=%s "
                    "AND status IN ('in_fight','completed','expired')",
                    (shared.fight.id,),
                ).fetchone()
                is not None
            )

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
        if (
            not COMBAT_TEST
            or shared is None
            or (
                getattr(shared, "is_duel", False) and not public_objectives_duel(shared)
            )
        ):
            return
        try:
            from wakfu_server.combat_abandon import (
                committed_abandon_team,
                aborted_terminal_packets,
            )

            abandon_team = (
                committed_abandon_team(getattr(shared, "runtime", None))
                if shared.fight.phase == "finished"
                else None
            )
            if (
                shared.fight.phase == "finished"
                and not getattr(shared, "settlement_ready", False)
                and abandon_team is None
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
                    fallback_packet=lambda: (
                        aborted_terminal_packets(
                            shared.fight, shared.runtime, losing_team=abandon_team
                        )[0]
                        if abandon_team is not None
                        else terminal_event(copy(shared.runtime))
                    ),
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
                    visible=not getattr(shared, "is_duel", False)
                    or public_objectives_duel(shared),
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

    def recover_pending_terminal_world():
        """Return a fresh login after its deferred terminal settlement commits."""
        nonlocal pending_terminal_world_recovery
        nonlocal combat_session, fight, fight_messages, group_lease
        nonlocal checkpoint_id, checkpoint_revision, checkpoint_terminal
        if pending_terminal_world_recovery is None or combat_session is None:
            return False
        shared = COMBAT_SESSIONS.registry.lookup(fight.id)
        if not shared.settlement_ready:
            return False
        recovered = COMBAT_SESSIONS.recover_settled_world(
            combat_session,
            character,
            wp=COMBAT_TEST_WP,
            pending_world_recovery=pending_terminal_world_recovery,
        )
        if recovered is None:
            raise ValueError("Pending terminal world recovery was not completed")
        character.update(recovered["character"])
        send_batch(connection, service, recovered["packets"])
        record(
            event="combat_pending_terminal_world_recovered",
            actor_id=character["id"],
            fight_id=fight.id,
            health_applied=recovered["applied"],
            native_fight_attached=False,
        )
        pending_terminal_world_recovery = None
        combat_session = fight = fight_messages = group_lease = None
        checkpoint_id = checkpoint_revision = None
        checkpoint_terminal = False
        return True

    def adopt_shared_duel():
        """Attach a loaded owner to its existing shared combat FSM/outbox."""
        nonlocal combat_session, fight, fight_messages, group_lease
        nonlocal TEST_MONSTERS, TEST_MONSTERS_BY_ID, TEST_GROUP_KEY
        nonlocal fight_started_at, checkpoint_id, checkpoint_revision
        nonlocal checkpoint_terminal
        nonlocal pending_terminal_world_recovery
        if (
            not COMBAT_TEST
            or not loaded
            or character is None
            or (
                (combat_session is not None or fight is not None)
                and deferred_native_combat_attachment() is None
            )
        ):
            return False
        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is None:
            return False
        owner = shared.participants.get(account_id)
        if owner is None or not COMBAT_SESSIONS.reconnect_owner_matches(
            shared, COMBAT_SESSIONS.session(account_id, generation, character)
        ):
            return False
        # A participant who has completed native12925 is back in the world
        # even while the other owner is still viewing the settled result.
        # Never let an idle/reconnect callback reattach that returned socket.
        if account_id in shared.returned or account_id in shared.withdrawals:
            return False
        staged_entry = getattr(shared, "pending_publication_recoveries", {}).get(
            account_id
        )
        resume_staged = (
            staged_entry is not None
            and staged_entry.session == owner
            and owner.generation == generation
            and account_id not in shared.connected
        )
        if owner.generation != generation or resume_staged:
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
            if not resume_staged and not CHECKPOINT_WRITER.flush_for_takeover(
                shared.fight.id, account_id, owner.generation, generation, timeout=10
            ):
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

            from wakfu_server.combat_instance_publication_recovery import (
                rebind_recovered_owner,
                requires_publication_recovery,
            )

            publication_recovery = (
                (connection.instance_publications, connection.native_instance_scope())
                if requires_publication_recovery(shared.fight)
                else None
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
                prepare_authority=(
                    (
                        lambda current_fight, current_shared, current_session: rebind_recovered_owner(
                            current_fight,
                            current_shared,
                            current_session,
                            publication_recovery,
                            session_live=COMBAT_SESSIONS.registry._lease_live,
                            owner_matches=COMBAT_SESSIONS.reconnect_owner_matches,
                        )
                    )
                    if publication_recovery is not None
                    else None
                ),
                fresh_world=(
                    shared.fight.phase == "finished"
                    and not getattr(shared, "is_duel", False)
                    and getattr(shared.runtime, "abandon_owner", None) is None
                ),
            )
            shared = COMBAT_SESSIONS.registry.lookup(shared.fight.id)
            pending_terminal_world_recovery = shared.pending_world_recoveries.get(
                account_id
            )
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
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_waiting,
        )

        if publication_recovery_waiting(shared):
            # Durable membership is attached, but native gameplay and transport
            # bootstrap remain paused until every required real owner returns.
            return True
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

    def deferred_native_combat_attachment():
        """Keep selected owners in their retained fight while peers reattach."""
        if not COMBAT_TEST or not loaded or character is None:
            return None
        shared = COMBAT_SESSIONS.lookup_character(character["id"])
        if shared is None:
            shared = publication_recovery_shared
            if not getattr(shared, "publication_recovery_aborted", None):
                return None
        owner = shared.participants.get(account_id)
        if owner is None or owner.character_id != character["id"]:
            return None
        if account_id in shared.returned or account_id in shared.withdrawals:
            return None
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_waiting,
            requires_publication_recovery,
        )

        if getattr(shared, "publication_recovery_aborted", None):
            return shared
        if not requires_publication_recovery(shared.fight):
            return None
        if owner.generation != generation or publication_recovery_waiting(shared):
            return shared
        return None

    def recover_aborted_publication_cohort(*, bootstrap=True):
        """Return every waiting socket after a complete durable cohort abort."""
        nonlocal character, fight, fight_messages, combat_session, group_lease
        nonlocal checkpoint_id, checkpoint_revision, checkpoint_terminal
        nonlocal pending_terminal_world_recovery, publication_recovery_shared
        nonlocal publication_recovery_attempt_token, publication_recovery_notice_token
        nonlocal position, movement_state, TEST_MONSTERS, TEST_MONSTERS_BY_ID
        nonlocal TEST_GROUP_KEY, fight_started_at
        nonlocal aborted_native_return
        shared = publication_recovery_shared
        exits = getattr(shared, "publication_recovery_aborted", None)
        if not exits or character is None:
            return False
        previous = shared.participants.get(account_id)
        if (
            previous is None
            or previous.generation != generation
            or previous.character_id != character["id"]
            or character["id"] not in exits
        ):
            return False
        if not STORE.current_character_session(account_id, generation, character["id"]):
            raise ValueError("Aborted native return has a stale selected session")
        if getattr(connection, "native_fight_id", None) == shared.fight.id:
            if aborted_native_return is None:
                pending = AbortedNativeReturn(previous, shared)
                pending.require(account_id, generation, character["id"])
                packets = pending.packets()
                send_batch(connection, service, packets)
                aborted_native_return = pending
                record(
                    event="combat_aborted_native_cleanup_sent",
                    actor_id=character["id"],
                    fight_id=shared.fight.id,
                )
                return True
            aborted_native_return.require(account_id, generation, character["id"])
            if not aborted_native_return.acknowledged:
                return True
        # Reload rather than replaying the exit's character snapshot: an
        # explicit console relocation may already have committed its new map.
        saved = STORE.character(account_id, character["id"])
        WORLD.leave(character["id"], generation)
        character.update(refresh_owned_character(saved))
        attach_combat_return_position()
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        fight = fight_messages = combat_session = group_lease = None
        checkpoint_id = checkpoint_revision = None
        checkpoint_terminal = False
        pending_terminal_world_recovery = None
        TEST_MONSTERS = ()
        TEST_MONSTERS_BY_ID = {}
        TEST_GROUP_KEY = None
        fight_started_at = None
        placement_deadline.take_expired(None, time.monotonic())
        publication_recovery_shared = None
        publication_recovery_attempt_token = publication_recovery_notice_token = None
        if aborted_native_return is not None:
            aborted_native_return.world_returned = True
            if aborted_native_return.command is None:
                aborted_native_return = None
        if bootstrap:
            send_batch(connection, service, combat_return_bootstrap())
            join_world(generation, connection, character)
            mark_static_sync_pending()
        record(
            event="combat_publication_recovery_aborted_world_return",
            actor_id=character["id"],
            fight_id=shared.fight.id,
        )
        return True

    def finish_aborted_native_return(body):
        """Consume the original12925 only after this socket's native cleanup."""
        nonlocal publication_recovery_return_due
        pending = aborted_native_return
        if pending is None or character is None:
            raise ValueError("No aborted native cleanup awaits this callback")
        pending.require(account_id, generation, character["id"])
        if not STORE.current_character_session(account_id, generation, character["id"]):
            raise ValueError("Aborted native return has a stale selected session")
        pending.acknowledge(body)
        publication_recovery_return_due = 0.0
        return continue_aborted_publication_recovery()

    def complete_aborted_native_return():
        """Retry a recorded native completion without manufacturing its ACK."""
        nonlocal aborted_native_return
        pending = aborted_native_return
        if pending is None or not pending.acknowledged or character is None:
            raise ValueError("Aborted native cleanup has not completed")
        pending.require(account_id, generation, character["id"])
        if not STORE.current_character_session(account_id, generation, character["id"]):
            raise ValueError("Aborted native return has a stale selected session")
        command = pending.command
        connection.native_fight_id = None
        if not pending.world_returned:
            recover_aborted_publication_cohort(bootstrap=command is None)
        if command is not None:
            if command.lower() in ("!exitdungeon", "!salirmazmorra"):
                execute_dungeon_exit_command(_native_return_retry=True)
            else:
                execute_test_command(command)
        record(
            event="combat_aborted_native_cleanup_completed",
            actor_id=character["id"],
            fight_id=pending.shared.fight.id,
            native_return_ack=True,
        )
        aborted_native_return = None
        return True

    def continue_aborted_publication_recovery():
        """Keep an already committed abort retryable during transient DB contention."""
        nonlocal publication_recovery_return_due, publication_recovery_notice_token
        nonlocal publication_recovery_shared
        if aborted_native_return is not None and aborted_native_return.world_returned:
            try:
                complete_aborted_native_return()
            except (DatabaseError, PoolTimeout, TimeoutError):
                pass  # The exact command remains attached to this native ACK.
            return True
        shared = publication_recovery_shared
        if not getattr(shared, "publication_recovery_aborted", None):
            return False
        owner = shared.participants.get(account_id)
        if (
            character is None
            or owner is None
            or (owner.generation, owner.character_id) != (generation, character["id"])
        ):
            publication_recovery_shared = None
            return False
        now = time.monotonic()
        if now < publication_recovery_return_due:
            return True
        publication_recovery_return_due = now + 1.0
        from wakfu_server.position_buffer import PositionOwnerBusy

        try:
            if aborted_native_return is not None and aborted_native_return.acknowledged:
                complete_aborted_native_return()
            else:
                recover_aborted_publication_cohort()
        except (ValueError, DatabaseError, PoolTimeout, PositionOwnerBusy) as error:
            token = ("world_return", shared.fight.id, generation)
            if publication_recovery_notice_token != token:
                publication_recovery_notice_token = token
                record(
                    event="combat_publication_recovery_world_return_pending",
                    actor_id=character["id"],
                    fight_id=shared.fight.id,
                    reason=type(error).__name__,
                )
                send(
                    connection,
                    service,
                    *information(
                        "El combate ya se abandonó y el progreso está guardado. "
                        "El regreso al mapa está pendiente; espera un momento."
                    ),
                )
        return True

    def attempt_shared_combat_attachment():
        """Retry on actual source progress; coalesce unchanged waiting feedback."""
        nonlocal publication_recovery_shared, publication_recovery_attempt_token
        nonlocal publication_recovery_attempt_due, publication_recovery_notice_token
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_token,
            requires_publication_recovery,
        )

        if continue_aborted_publication_recovery():
            return True
        shared = (
            None
            if character is None
            else COMBAT_SESSIONS.lookup_character(character["id"])
        )
        if shared is None or not requires_publication_recovery(shared.fight):
            return adopt_shared_duel()
        publication_recovery_shared = shared
        if not shared.lock.acquire(blocking=False):
            return False
        try:
            token = (
                publication_recovery_token(shared),
                connection.instance_publications.lease.current,
            )
        finally:
            shared.lock.release()
        now = time.monotonic()
        if (
            token == publication_recovery_attempt_token
            and now < publication_recovery_attempt_due
        ):
            return False
        publication_recovery_attempt_token = token
        publication_recovery_attempt_due = now + 1.0
        error = None
        try:
            result = adopt_shared_duel()
        except (ValueError, KeyError) as rejected:
            error = rejected
            result = False
        waiting = deferred_native_combat_attachment() is not None
        if waiting and token != publication_recovery_notice_token:
            publication_recovery_notice_token = token
            record(
                event="combat_publication_recovery_waiting",
                actor_id=character["id"],
                fight_id=shared.fight.id,
                reason="participant_publications_pending"
                if error is None
                else type(error).__name__,
            )
            current_owner = shared.participants.get(account_id)
            can_abandon = (
                not shared.connected
                and shared.disconnect_abort_pending
                and current_owner is not None
                and current_owner.generation == generation
                and account_id in shared.pending_publication_recoveries
            )
            message = (
                "El combate está pausado mientras se recupera la conexión del grupo. "
                "Los participantes que se desconectaron deben volver a entrar. "
            )
            message += (
                "Puedes abandonar el combate para volver al mapa."
                if can_abandon
                else "Espera a que termine la recuperación; si persiste, vuelve a conectar."
            )
            send(connection, service, *information(message))
        if not waiting and error is not None:
            raise error
        if not waiting:
            publication_recovery_attempt_token = (
                publication_recovery_notice_token
            ) = None
            publication_recovery_shared = None
        return result

    def abort_waiting_publication_cohort():
        """Explicitly abandon an unbootstrapped, fully paused owner cohort."""
        nonlocal publication_recovery_shared
        shared = deferred_native_combat_attachment()
        if shared is None:
            return False
        publication_recovery_shared = shared
        owner = shared.participants.get(account_id)
        if owner is None or owner.generation != generation:
            attempt_shared_combat_attachment()
            owner = shared.participants.get(account_id)
        if owner is None or owner.generation != generation:
            raise ValueError(
                "La recuperación aún no permite abandonar. Vuelve a conectar e inténtalo otra vez."
            )
        from wakfu_server.combat_health import persist_aborted_shared_fight

        result = COMBAT_SESSIONS.registry.abort_pending_publication_recovery(
            owner,
            persist=lambda current: persist_aborted_shared_fight(
                STORE, current, groups=COMBAT_GROUPS
            ),
        )
        # Waiting peers retain this same shared object even after index
        # retirement. Their next idle returns them through the same world path.
        shared.publication_recovery_aborted = result["exits"]
        marker = EXTERNAL_FIGHT_MARKERS.remove(shared.fight.id)
        if marker is not None:
            WORLD.emit_location(
                shared.map_id,
                shared.instance_id,
                *marker,
                exclude_sessions=tuple(
                    (participant.character_id, participant.generation)
                    for participant in shared.participants.values()
                ),
            )
        if shared.group_lease is not None:
            publish_full_abandon_group(shared, {"group_restored": True})
        continue_aborted_publication_recovery()
        send(
            connection,
            service,
            *information(
                "Se abandonó el combate pausado del grupo. Se guardaron la vida y "
                "las heridas de todos. Puedes continuar cuando termine de cargar el mapa."
            ),
        )
        return True

    @PROFILER.profile("combat.readiness")
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

        def initialize_encounter_states(
            preview, action_id, characters, decks, monsters
        ):
            from wakfu_server.combat_consumable_lifecycle import refresh_participants

            characters.update(refresh_participants(STORE, characters, preview.id))
            source_id = next(iter(characters))
            source = characters[source_id]
            from wakfu_server import boss_score, boss_score_runtime

            if getattr(preview, "rift_wave_state", None) is None:
                with STORE.connection() as score_db:
                    score_snapshot = boss_score.prepare_snapshot(
                        score_db,
                        preview.id,
                        monsters={
                            identity: {
                                "ref": monster["ref"],
                                "team": preview.actors[identity].team,
                            }
                            for identity, monster in monsters.items()
                            if identity in preview.actors
                        },
                        player_ids=tuple(characters),
                        player_team=preview.actors[source_id].team,
                    )
                    boss_score_runtime.install(preview, score_snapshot)
            if not is_dungeon_run(source.get("instance_id", 0)):
                return preview, ()
            from wakfu_server.dungeon_stele_states import (
                initialize as initialize_stele_states,
            )

            def native_factory(state, boss_id):
                factory, _ = server_runtime(
                    source,
                    monsters,
                    decks[source_id],
                    action_id=action_id,
                    critical=False,
                    player_characters=characters,
                    deck_blobs=decks,
                )
                return factory

            with STORE.connection() as db:
                preview, receipt, packets = initialize_stele_states(
                    db, preview, monsters, runtime_factory=native_factory
                )
            return preview, tuple(packets)

        if combat_session is not None:
            from wakfu_server.fight_store import activate

            shared = refresh_shared_combat()

            @PROFILER.profile("combat.readiness.prepare")
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
                    encounter_initializer=lambda preview, action_id, characters, decks: (
                        initialize_encounter_states(
                            preview,
                            action_id,
                            characters,
                            decks,
                            shared.join_context["monsters"],
                        )
                    ),
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

        stored_deck = (
            character.get("builds", {})
            .get(character.get("active_build_index", 0), {})
            .get("deck")
        )
        deck = bytes.fromhex(stored_deck) if stored_deck else default_deck(character)

        def initialize_legacy(preview, action_id):
            legacy_characters = {character["id"]: character}
            preview, encounter_packets = initialize_encounter_states(
                preview,
                action_id,
                legacy_characters,
                {character["id"]: deck},
                TEST_MONSTERS_BY_ID,
            )
            from wakfu_server.combat_attachment_authority import for_characters

            attachments = for_characters(STORE, legacy_characters)
            preview, owned_packets = prepare_server_initialization(
                legacy_characters[character["id"]],
                TEST_MONSTERS_BY_ID,
                preview,
                account_id,
                deck,
                action_id=action_id,
                attachment_authority=attachments,
                fight_start=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            )
            return preview, (*encounter_packets, *owned_packets)

        candidate, candidate_messages, packets = prepare_ready(
            fight,
            account_id,
            ready,
            initialize=initialize_legacy,
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

    def finish_combat_return_after_position_flush(
        *, abandoned, shared_return, shared_state
    ):
        """Resume a consumed12925 only after its position fence succeeds."""
        connection.native_fight_id = None
        nonlocal position, movement_state
        nonlocal group_lease, fight, fight_messages, combat_session

        attach_combat_return_position()
        position = {key: character[key] for key in ("x", "y", "z")}
        movement_state = Movement(position)
        WORLD.leave(character["id"], generation)
        for message_id, payload in combat_return_bootstrap():
            send(connection, service, message_id, payload)
        from wakfu_server.level_publication import (
            combat_return as refresh_return_spells,
        )

        send_batch(
            connection,
            service,
            refresh_return_spells(
                character,
                STORE.characters(account_id),
                participant_ids=tuple(
                    actor.id
                    for actor in fight.actors.values()
                    if actor.controlled
                    and actor.owner_id == account_id
                    and str(actor.id)
                    not in getattr(fight, "native_companion_sources", {})
                ),
                entity_template=OWNED_HERO_TEMPLATE,
                roster_template=CHARACTERS,
                retained_state_packets=consumable_state_packets,
            ),
        )
        from wakfu_server import companions

        with STORE.connection() as companion_db:
            companion_collection = companions.collection(companion_db, account_id)
        send(connection, service, *companions.refresh_packet(companion_collection))
        from wakfu_server.combat_monster_world import spawn_group

        if group_lease is not None and (not shared_return or abandoned):
            with COMBAT_GROUPS.lock:
                defeated = (
                    not abandoned and fight.winner == fight.actors[character["id"]].team
                )
                restored = COMBAT_GROUPS.finish(group_lease, defeated=defeated)
                if restored and not defeated:
                    from wakfu_server.ecology_admin import current_available

                    map_id, instance_id, group_id = group_lease[0]
                    restored_members = current_available(STORE, group_lease[0])
                    if restored_members:
                        WORLD.emit_location(
                            map_id,
                            instance_id,
                            12608,
                            owned_scene_spawn_group(
                                restored_members, group_id=group_id
                            ),
                            exclude_generation=generation,
                        )
                        for packet in HARVESTS.availability_for(
                            map_id,
                            instance_id,
                            [member["id"] for member in restored_members],
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
            if getattr(shared_state, "full_abandon_owner", None) is None:
                if not COMBAT_SESSIONS.registry.retire_abandoned_single_owner(
                    fight.id, combat_session
                ):
                    raise ValueError("Shared PvE abandon was not safely retired")
        elif shared_return:
            # Persist the terminal checkpoint while the shared registry entry
            # exists. mark_returned may retire it when this is the last owner.
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
        deliver_custom_task_rewards()
        custom_task_cards.changed(character["id"], (character["id"],))
        publish_custom_task_cards()

    def execute_dungeon_exit_command(*, _native_return_retry=False):
        try:
            from wakfu_server import dungeon_exit

            emergency_exit_current_combat()
            if (
                aborted_native_return is not None
                and not aborted_native_return.world_returned
            ):
                aborted_native_return.command = "!exitdungeon"
                return
            with STORE.connection() as exit_db:
                has_dungeon = (
                    exit_db.execute(
                        "SELECT 1 FROM dungeon_instances WHERE instance_id=%s",
                        (character.get("instance_id", 0),),
                    ).fetchone()
                    is not None
                )
            if not has_dungeon:
                execute_test_command("!astrub")
                return

            def exit_member_in_fight(actor_id):
                if actor_id == character["id"] and (
                    fight is not None or combat_session is not None
                ):
                    return True
                return COMBAT_SESSIONS.lookup_character(actor_id) is not None

            record(
                event="dungeon_exit_requested",
                actor_id=character["id"],
                instance_id=character.get("instance_id", 0),
            )
            try:
                dungeon_exit.leave_automatic(
                    STORE,
                    account_id,
                    generation,
                    character["id"],
                    in_fight=exit_member_in_fight,
                    positions=POSITIONS,
                )
            except ValueError:
                # Administrative relocation closes company membership
                # even when this dungeon has no reviewed native exit.
                execute_test_command("!astrub")
                return
            deliver_dungeon_transitions(before_action=True)
            answer = "Has salido de la mazmorra."
        except (
            ValueError,
            PermissionError,
            DatabaseError,
            PoolTimeout,
        ) as error:
            if _native_return_retry and isinstance(error, (DatabaseError, PoolTimeout)):
                raise
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
        return

    @PROFILER.profile("session.idle")
    def idle():
        if STOPPING.is_set():
            return False
        nonlocal last_health_tick, last_consumable_tick, last_session_renewal, console_session
        nonlocal spectator_session, spectator_fight_id
        nonlocal spectator_terminal_pending
        nonlocal character, last_shop_refresh, pending_combat_return
        nonlocal guild_daily_boundary
        if loaded and character is not None and hero_switch_pending is None:
            from wakfu_server.guild_member_lifecycle import (
                synchronize as synchronize_guild,
            )

            character.update(WORLD.guild_projection(character["id"], generation))
            try:
                guild_in_combat = (
                    fight is not None
                    or combat_session is not None
                    or spectator_session is not None
                    or pending_combat_return is not None
                )
                guild_publication_pending = character.get(
                    "_guild_member_publication_pending", False
                )
                updated, guild_changed = synchronize_guild(
                    STORE,
                    account_id,
                    generation,
                    character,
                    in_combat=guild_in_combat,
                )
                character = (
                    refresh_owned_character(updated) if guild_changed else updated
                )
                if (guild_changed or guild_publication_pending) and not guild_in_combat:
                    character["_guild_member_publication_pending"] = True
                    publish_consumable_character(character)
                    character.pop("_guild_member_publication_pending", None)
            except (ValueError, DatabaseError, PoolTimeout) as error:
                record(
                    event="guild_member_refresh_retry",
                    actor_id=character["id"],
                    reason=type(error).__name__,
                )
            from wakfu_server.guild_daily_quests import synchronize_owned

            try:
                boundary, packets = synchronize_owned(
                    STORE,
                    account_id,
                    generation,
                    character["id"],
                    next_boundary_ms=(
                        guild_daily_boundary[1]
                        if guild_daily_boundary[0] == character["id"]
                        else None
                    ),
                )
                for packet in packets:
                    send(connection, service, *packet)
                guild_daily_boundary = (character["id"], boundary)
            except (ValueError, DatabaseError, PoolTimeout) as error:
                record(
                    event="guild_daily_refresh_retry",
                    actor_id=character["id"],
                    reason=type(error).__name__,
                )
        mailbox = getattr(connection, "native_ai_diagnostics", None)
        if mailbox is not None:
            owner = (
                account_id,
                generation,
                None if character is None else character["id"],
            )
            diagnostics, dropped = mailbox.drain(owner)
            for fields in diagnostics:
                record(**fields)
            if dropped:
                record(event="combat_background_diagnostics_dropped", count=dropped)
        if character is not None and not loaded:
            character.update(WORLD.guild_projection(character["id"], generation))
        if account_id is not None:
            now = time.monotonic()
            renew = now - last_session_renewal >= 10
            health_started = time.monotonic()
            try:
                session_health = STORE.session_health(
                    account_id, generation, renew=renew
                )
            except Exception as error:
                CHECKPOINT_WRITER.observe_database_health(
                    account_id, generation, error=error
                )
                raise
            if renew and session_health["valid"]:
                checkpoint_recovery = CHECKPOINT_WRITER.observe_database_health(
                    account_id,
                    generation,
                    renewed_until=session_health["renewed_until"],
                )
                if checkpoint_recovery["resumed"]:
                    record(
                        event="combat_checkpoint_health_recovery", **checkpoint_recovery
                    )
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
            if hero_switch_pending is not None:
                # The selected hero joins World only after its native ACK.
                # Keep the account lease alive while deferring all actor
                # publication and timers until that registration completes.
                return True
            if pending_combat_return is not None:
                pending = pending_combat_return
                try:
                    completed = pending["retry"].attempt(
                        now=time.monotonic(),
                        flush=lambda: flush_positions(**pending["scope"]),
                        complete=pending["complete"],
                        busy=lambda error, attempt: record(
                            event="combat_return_position_pending",
                            actor_id=character["id"],
                            fight_id=pending["fight_id"],
                            attempt=attempt,
                            pending_seconds=round(
                                time.monotonic() - pending["started_at"], 3
                            ),
                            reason=redact(str(error)),
                        )
                        if attempt == 1 or attempt % 30 == 0
                        else None,
                    )
                except ValueError as error:
                    record(
                        event="combat_return_rejected",
                        actor_id=character["id"],
                        fight_id=pending["fight_id"],
                        reason=str(error),
                    )
                    pending_combat_return = None
                    pending_return_command.clear()
                    return True
                if completed:
                    pending_combat_return = None
                    command = pending_return_command.take(
                        (account_id, generation, character["id"]),
                        valid_session=lambda: STORE.current_character_session(
                            account_id, generation, character["id"]
                        ),
                    )
                    if command is not None:
                        # The real return callback has completed its durable
                        # position fence and retired membership. Run the same
                        # command handlers once; never replay native 12925.
                        if command.lower() in ("!exitdungeon", "!salirmazmorra"):
                            execute_dungeon_exit_command()
                        else:
                            try:
                                execute_test_command(command)
                            except (ValueError, PermissionError):
                                pass  # The normal command handler sent its rejection.
                else:
                    return True
            if consume_command_combat_recovery():
                return True
            if continue_aborted_publication_recovery():
                return True
            deliver_rift_transition()
            if (
                combat_session is None
                or deferred_native_combat_attachment() is not None
            ):
                try:
                    attempt_shared_combat_attachment()
                except (ValueError, KeyError) as error:
                    record(
                        event="friendly_duel_attach_rejected",
                        actor_id=None if character is None else character["id"],
                        reason=str(error),
                    )
            if deferred_native_combat_attachment() is not None:
                # No world movement, deadline, ACK or native callback may run
                # against a partially reattached publication cohort.
                return True
            if combat_session is not None:
                # This runs on the socket reader before reading its next frame.
                # Leave reliable outboxes queued while another combat operation
                # owns the locks, so unrelated chat/input can still be read.
                if refresh_shared_combat(blocking=False) is False:
                    return True
                if drain_shared_combat(blocking=False) is False:
                    return True
                if fight is not None and fight.phase == "finished":
                    try:
                        shared_state = COMBAT_SESSIONS.registry.lookup(fight.id)
                        from wakfu_server.combat_terminal_retry import (
                            pending_terminal_settlement,
                        )

                        if pending_terminal_settlement(shared_state):
                            complete_test_fight()
                        recover_pending_terminal_world()
                    except ValueError as error:
                        record(
                            event="combat_terminal_settlement_retry",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            reason=str(error),
                        )
            deliver_rift_transition()
            deliver_dungeon_transitions()
            deliver_ranch_scene_refresh()
            deliver_ranch_cycle_rewards()
            if not sync_loaded_world_snapshot():
                sync_static_world()
            sync_scene_world()
            if environment_seat is not None and (
                fight is not None
                or combat_session is not None
                or spectator_session is not None
            ):
                cancel_environment()
            complete_environment_occupation()
            complete_artifact_action()
            if (
                flora_retry_body is not None
                and flora_ticket is not None
                and STORE.now() >= flora_ticket["completes_at"]
            ):
                complete_flora_occupation(flora_retry_body)
            publish_environment_scene()
            poll_national_progression()
            poll_environmental_events()
            poll_external_objectives()
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
                    from wakfu_server.combat_effective_control import (
                        effective_server_controlled,
                    )
                    from wakfu_server.combat_automatic_npc_turn import (
                        requires_automatic_npc_turn_end,
                    )

                    if (
                        fight.phase == "active"
                        and fight.current is not None
                        and (
                            effective_server_controlled(fight, fight.current)
                            or requires_automatic_npc_turn_end(fight, fight.current)
                        )
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
                and time.monotonic() >= pet_hibernation_due
            ):
                refresh_pet_hibernation()
            if (
                loaded
                and character is not None
                and time.monotonic() - last_consumable_tick >= 5
            ):
                from wakfu_server.consumable_world_publication import (
                    synchronize_and_publish,
                )

                last_consumable_tick = time.monotonic()
                character = synchronize_and_publish(
                    STORE,
                    account_id,
                    generation,
                    character,
                    in_combat=fight is not None or combat_session is not None,
                    allocate_action=lambda: next(LOCAL_WORLD_ACTIONS),
                    send=lambda opcode, body: send(connection, service, opcode, body),
                    broadcast_main=lambda opcode, body: WORLD.broadcast(
                        generation,
                        character["id"],
                        opcode,
                        body,
                    ),
                    publish_main=publish_consumable_character,
                )
            if (
                loaded
                and character is not None
                and fight is None
                and combat_session is None
                and spectator_session is None
            ):
                bonus_packets = REGIONAL_BONUSES.packets_for(
                    character, generation, connection
                )
                for bonus_packet in bonus_packets:
                    send(connection, "world", *bonus_packet)
                if bonus_packets:
                    REGIONAL_BONUSES.acknowledge(
                        character, generation, connection, bonus_packets
                    )
            if (
                loaded
                and character is not None
                and fight is None
                and combat_session is None
                and time.monotonic() - last_shop_refresh >= 1
            ):
                from psycopg import Error as DatabaseError
                from psycopg_pool import PoolTimeout
                from wakfu_server import shop_refresh

                last_shop_refresh = time.monotonic()
                try:
                    purchase = shop_refresh.pending(STORE, account_id, character)
                    if purchase is not None:
                        for message_id, payload in purchase["packets"]:
                            send(connection, service, message_id, payload)
                        character = purchase["character"]
                        shop_refresh.acknowledge(
                            STORE, account_id, character["id"], purchase["order_ids"]
                        )
                        record(
                            event="shop_purchase_delivered",
                            actor_id=character["id"],
                            order_ids=purchase["order_ids"],
                        )
                except (ValueError, DatabaseError, PoolTimeout) as error:
                    record(
                        event="shop_purchase_delivery_retry",
                        actor_id=character["id"],
                        reason=type(error).__name__,
                    )
            if (
                loaded
                and character is not None
                and fight is None
                and combat_session is None
                and time.monotonic() - last_health_tick >= 1
            ):
                last_health_tick = time.monotonic()
                updates = health_store.tick_company(
                    STORE, account_id, generation, character["id"], character["hp"]
                )
                for saved in updates:
                    is_main = saved["id"] == character["id"]
                    if is_main:
                        character.update(
                            hp=saved["hp"],
                            max_hp=saved["max_hp"],
                            hp_damage=saved["hp_damage"],
                            health_dead=saved["health_dead"],
                        )
                    if not saved["health_changed"]:
                        continue
                    packet = health.packet(
                        saved["id"], saved["hp"], saved["regeneration_coefficient"]
                    )
                    if is_main:
                        WORLD.update(generation, character, 12436, packet)
                    else:
                        # Heroes share their main's audience, not a world presence row.
                        WORLD.broadcast(generation, character["id"], 12436, packet)
                    record(
                        event="health_regenerated",
                        actor_id=saved["id"],
                        previous_hp=saved["previous_hp"],
                        hp=saved["hp"],
                        max_hp=saved["max_hp"],
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
        # Preserve remote TLS handshake tolerance before normal polling.
        raw.settimeout(10)
        with context.wrap_socket(raw, server_side=True) as connection:
            connection.settimeout(1)
            connection = Connection(connection)
            connection.trace_id = connection_trace_id
            if service == "world":
                connection.account_item_spell_update = publish_account_item_spells
            from wakfu_server.custom_tasks import external as external_objectives

            if service == "world" and external_objectives.enabled():
                from wakfu_server.custom_tasks.external_updates import subscribe

                connection.objectives_updates = subscribe(STORE, STOPPING)
            if service == "world":
                from wakfu_server.interactive_publication import InteractivePublication
                from wakfu_server.seasonal_native_gateway import attachment

                trace_ids = os.environ.get("WAKFU_INTERACTIVE_TRACE_IDS", "")
                trace_account = os.environ.get("WAKFU_INTERACTIVE_TRACE_ACCOUNT", "")
                connection.interactive_publication = InteractivePublication(
                    world_static.objects,
                    trace=connection.interactive_trace.append,
                    trace_ids={int(value) for value in trace_ids.split(",") if value},
                    trace_account_id=int(trace_account) if trace_account else None,
                    trace_limit=512 if trace_ids else 0,
                    attachment_projector=attachment,
                )
                connection.interactive_scope = lambda: (
                    dict(
                        session_id=connection_trace_id,
                        generation=generation,
                        account_id=account_id,
                        character_id=character["id"],
                        map_id=character["map_id"],
                        instance_id=character.get("instance_id", 0),
                    )
                    if character is not None and generation is not None
                    else None
                )
                connection.native_instance_scope = (
                    lambda: (
                        account_id,
                        generation,
                        character["id"],
                        character["map_id"],
                        character["instance_id"],
                    )
                    if account_id is not None and generation and character is not None
                    else None
                )
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
                    activity_scope=ECOLOGY_BRIDGE.interactive()
                    if ECOLOGY_BRIDGE is not None and service == "world"
                    else None,
                )
                record(
                    service=service,
                    direction="in",
                    opcode=opcode,
                    route=route,
                    bytes=len(body),
                )
                if pending_combat_return is not None and opcode not in (314, 23354):
                    if pending_return_command.retain(
                        opcode, body, (account_id, generation, character["id"])
                    ):
                        send(
                            connection,
                            service,
                            *information(
                                "Comando guardado; se ejecutará al completar el regreso del combate."
                            ),
                        )
                    # The terminal return packets are already published. Hold
                    # follow-up gameplay until the position fence completes.
                    # Native ping replies and server-clock synchronization still
                    # pass through; the ACK and return side effects never replay.
                    pending_combat_return["held_requests"] += 1
                    if (
                        pending_combat_return["held_requests"] == 1
                        or pending_combat_return["held_requests"] % 100 == 0
                    ):
                        record(
                            event="combat_return_request_held",
                            actor_id=character["id"],
                            fight_id=pending_combat_return["fight_id"],
                            opcode=opcode,
                            held_requests=pending_combat_return["held_requests"],
                        )
                    continue
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
                        attempt_shared_combat_attachment()
                    except (ValueError, KeyError) as error:
                        record(
                            event="friendly_duel_attach_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                if command_recovery_holds_request(opcode, body):
                    continue
                if combat_session is not None and fight is not None:
                    refresh_shared_combat()
                if (
                    opcode not in (314, 23354, 13952, 12366)
                    and not (opcode == 12925 and aborted_native_return is not None)
                    and deferred_native_combat_attachment() is not None
                ):
                    record(
                        event="combat_publication_recovery_action_deferred",
                        actor_id=character["id"],
                        opcode=opcode,
                    )
                    continue
                if loaded:
                    deliver_rift_transition()
                    deliver_dungeon_transitions(before_action=True)
                if guild_chest_session is not None and (
                    fight is not None
                    or spectator_session is not None
                    or bag_session is not None
                    or character is None
                    or character["id"] != guild_chest_session.character_id
                    or opcode == 13331
                ):
                    guild_chest_session.close(clear=True)
                    guild_chest_session = None
                from wakfu_server.haven_chest import (
                    can_access_location as chest_location_allowed,
                )

                if chest_opening is not None and (
                    fight is not None
                    or spectator_session is not None
                    or bag_session is None
                    or not chest_location_allowed(character, bag_session, ranch_session)
                    or opcode == 13331
                ):
                    chest_opening = None
                # All transactional actions/DB refreshes see the last approved
                # outside-world position; own-bag moves remain session-only.
                if character is not None and opcode != 13331:
                    from wakfu_server.position_buffer import PositionOwnerBusy

                    try:
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                    except PositionOwnerBusy:
                        # Reject this action before any mutation; another
                        # writer retains the dirty authoritative position.
                        record(
                            event="request_position_busy",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(
                                dict(character, name="Consola local"),
                                "Guardado de posición en curso. Reintenta la acción.",
                            ),
                        )
                        continue
                artifact_action_request = False
                if pending_artifact_action is not None and opcode == 12870:
                    cancel_artifact_action("Another interactive action started")
                if loaded and character is not None and opcode == 12870:
                    from wakfu_server.phoenix_points import (
                        recognizes as phoenix_activation,
                    )

                    if phoenix_activation(body):
                        from psycopg import Error as PhoenixDatabaseError
                        from psycopg_pool import PoolTimeout as PhoenixPoolTimeout

                        try:
                            activate_world_phoenix(body)
                        except (
                            ValueError,
                            PhoenixDatabaseError,
                            PhoenixPoolTimeout,
                        ) as error:
                            reason = (
                                str(error)
                                if isinstance(error, ValueError)
                                else "Reintenta la vinculación con el fénix"
                            )
                            send(connection, service, *information(reason))
                            record(
                                event="phoenix_binding_rejected",
                                actor_id=character["id"],
                                reason=reason,
                            )
                        continue
                    from wakfu_server import exploration_artifact_actions
                    from wakfu_server.seasonal_native_gateway import activation

                    artifact_action_request = exploration_artifact_actions.recognizes(
                        character, body
                    ) or (
                        len(body) == 12
                        and exploration_artifact_actions.projection_required(
                            character["map_id"], struct.unpack_from(">q", body)[0]
                        )
                    )
                    try:
                        artifact_body = exploration_artifact_actions.activation(
                            character, body
                        )
                        if artifact_body is not None:
                            body = artifact_body
                        artifact_action_request = (
                            exploration_artifact_actions.recognizes(character, body)
                        )
                        gateway = activation(character, body)
                    except ValueError as error:
                        record(
                            event="seasonal_gateway_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                            original_opcode=12870,
                        )
                        from wakfu_server.ecology_feedback import information

                        send(
                            connection,
                            service,
                            *information(
                                artifact_failure_message(error)
                                if artifact_action_request
                                else str(error)
                            ),
                        )
                        continue
                    if gateway is not None:
                        record(
                            event="seasonal_gateway_activated",
                            actor_id=character["id"],
                            original_opcode=12870,
                            resolved_opcode=12296,
                            route_key=gateway["route_key"],
                            source_id=gateway["source_id"],
                            destination_map_id=gateway["destination_map_id"],
                        )
                        opcode, body = 12296, gateway["body"]
                if (
                    opcode == 13429
                    and paid_container_ticket is not None
                    and len(body) == 3
                    and struct.unpack_from(">h", body, 1)[0] in (13, 28)
                ):
                    from wakfu_server import paid_containers

                    try:
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        result = paid_containers.finish(
                            STORE,
                            account_id,
                            generation,
                            character,
                            paid_container_ticket,
                            body,
                            loaded=loaded,
                            blocked=environment_blocked(allow_paid=True),
                            is_hero=environment_actor_is_hero(),
                        )
                        character = result["character"]
                        paid_container_ticket = None
                        for packet in result["packets"]:
                            if packet[0] == 12344:
                                WORLD.emit_location(*result["location"], *packet)
                            else:
                                send(connection, service, *packet)
                        publish_environment_scene(force=True)
                        record(
                            event="paid_container_finished",
                            actor_id=character["id"],
                            state=result["state"],
                            replay=result["replay"],
                        )
                    except ValueError as error:
                        from wakfu_server.ecology_feedback import information

                        send(connection, service, *information(str(error)))
                        record(
                            event="paid_container_finish_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    continue
                if opcode == 13429 and environment_seat is not None and len(body) == 3:
                    seat_phase, seat_occupation = struct.unpack(">Bh", body)
                    if seat_occupation == 16:
                        if seat_phase == 3:
                            cancel_environment()
                        # Phase2 completes the sitting animation; occupancy remains.
                        continue
                if flora_ticket is not None and opcode in (
                    13331,
                    13686,
                    12296,
                    13578,
                    12247,
                    13130,
                    13220,
                    13284,
                    13481,
                ):
                    cancel_flora()
                if (
                    environment_ticket is not None
                    or environment_seat is not None
                    or paid_container_ticket is not None
                    or pending_artifact_action is not None
                ) and opcode in (
                    12117,
                    13520,
                    13241,
                    13413,
                    13331,
                    13686,
                    12296,
                    13578,
                    12247,
                    13130,
                    13220,
                    13284,
                    13481,
                    12219,
                    12006,
                    12054,
                ):
                    cancel_environment()
                if character is not None and opcode in (13686, 12296, 13578, 12247):
                    HARVESTS.cancel(character["id"], generation=generation)
                    PLANTINGS.cancel(character["id"], generation)
                if (
                    fight is not None
                    and opcode
                    in (
                        13686,
                        12296,
                        13578,
                        12247,
                        13331,
                        13434,
                        12580,
                        13210,
                        13826,
                        12870,
                        12363,
                    )
                    and not native_exterior_rift_request()
                ):
                    record(
                        event="combat_world_action_rejected",
                        actor_id=character["id"],
                        opcode=opcode,
                        reason="World action is unavailable during combat",
                    )
                    from wakfu_server.travel_storage_feedback import (
                        blocked_world_rejection,
                    )

                    blocked_feedback = blocked_world_rejection(opcode, body)
                    if blocked_feedback is not None:
                        send(connection, service, *blocked_feedback)
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
                        13284,
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
                        12510,
                        12593,
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
                    publish_account_item_spells(seed=True)
                    destination_route = transports.for_map(character["map_id"])
                    if destination_route:
                        for message_id, message_body in transports.bootstrap(
                            character, destination_route
                        ):
                            if opcode != 14689 or message_id != 13256:
                                send(connection, service, message_id, message_body)
                    elif character["map_id"] != 1134:
                        for message_id, message_body in owned_native_bootstrap(
                            character
                        ):
                            if opcode != 14689 or message_id != 13256:
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
                    acknowledge_rift_login_bootstrap(account_id, generation, character)
                    from wakfu_server import item_teleports

                    recovered_travel = item_teleports.pending(
                        STORE, account_id, generation, character["id"]
                    )
                    if recovered_travel is not None:
                        item_teleports.acknowledge(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            recovered_travel["transition"]["token"],
                        )
                    from wakfu_server import haven_world_travel

                    recovered_haven_world = haven_world_travel.pending(
                        STORE, account_id, generation, character["id"]
                    )
                    if recovered_haven_world is not None:
                        haven_world_travel.acknowledge(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            recovered_haven_world["transition"]["token"],
                        )
                    resume_settled_shared_combat()
                    publish_custom_task_cards()
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
                            0
                            if fight is not None or combat_session is not None
                            else health.exploration_coefficient(
                                character["max_hp"], character["hp"]
                            ),
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
                        13284,
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
                        12510,
                        12593,
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
                if opcode == 12197 and loaded and COMBAT_TEST:
                    from wakfu_server.combat_party_prompt import (
                        accepted_join_request,
                    )

                    try:
                        accepted_body = accepted_join_request(body)
                    except ValueError as error:
                        record(event="party_combat_answer_rejected", reason=str(error))
                        continue
                    if accepted_body is None:
                        continue
                    # coK's boolean is acceptance; coU's boolean is autoLock.
                    opcode, body = 13241, accepted_body
                if opcode == 13175 and loaded and character is not None:
                    from wakfu_server.achievements.service import tracking_request

                    try:
                        packets = tracking_request(
                            STORE, account_id, generation, character["id"], body
                        )
                    except ValueError as error:
                        record(event="achievement_tracking_rejected", reason=str(error))
                        continue
                    send_batch(connection, service, packets)
                    continue
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
                            with LOCK:
                                previous = LIVE.get(account_id)
                            generation = STORE.begin_session(
                                account_id,
                                previous_generation=None
                                if previous is None
                                else previous[0],
                            )
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
                        from wakfu_server.server_identity import (
                            configured_server_name,
                            rename_realm,
                        )

                        send(
                            connection,
                            service,
                            453,
                            rename_realm(REALMS, configured_server_name(STORE)),
                        )
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
                    send_shop_authentication(
                        connection, service, account_id, generation
                    )
                elif opcode == 22954:
                    try:
                        request = decode_body("out", opcode, body)
                        send_shop_authentication(
                            connection,
                            service,
                            account_id,
                            generation,
                            language=request["language"],
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        from wakfu_server.ecology_feedback import information

                        send(
                            connection,
                            service,
                            *information(
                                "No se pudo conectar con la tienda. Cierra y vuelve "
                                "a abrir la tienda; si persiste, reconecta al juego."
                            ),
                        )
                        record(
                            event="shop_authentication_rejected",
                            account_id=account_id,
                            reason=type(error).__name__,
                        )
                elif opcode == 13488:
                    if account_id is None or body != b"\x00":
                        raise ValueError("Invalid character selection request")
                    spectator_terminal_pending = None
                    if combat_session is not None and fight is not None:
                        shared_selection = refresh_shared_combat()
                        if (
                            not getattr(shared_selection, "is_duel", False)
                            and getattr(shared_selection.fight, "phase", None)
                            == "finished"
                        ):
                            terminal_selection_fight_id = fight.id
                            terminal_selection_error = None
                            try:
                                if not shared_selection.settlement_ready:
                                    complete_test_fight()
                                if pending_terminal_world_recovery is not None:
                                    recover_pending_terminal_world()
                                else:
                                    drain_shared_combat()
                            except (ValueError, DatabaseError, PoolTimeout) as error:
                                terminal_selection_error = str(error)
                            if combat_session is not None:
                                # A selector request is not a native12925 ACK.
                                # Keep attached terminal ownership until the
                                # real return, or an already-proven fresh-login
                                # world recovery, completes its durable return.
                                record(
                                    event="combat_terminal_character_selection_deferred",
                                    actor_id=character["id"],
                                    fight_id=terminal_selection_fight_id,
                                    settlement_ready=shared_selection.settlement_ready,
                                    reason=terminal_selection_error,
                                    native_return_ack=False,
                                )
                                send(
                                    connection,
                                    service,
                                    674,
                                    wire.chat(
                                        dict(character, name="Consola local"),
                                        "Cierra el resultado del combate antes de cambiar de personaje.",
                                    ),
                                )
                                continue
                    if combat_session is not None and fight is not None:
                        from wakfu_server.combat_pve_withdraw import (
                            has_other_live_owner,
                        )

                        if not getattr(
                            shared_selection, "is_duel", False
                        ) and has_other_live_owner(
                            shared_selection.fight, combat_session
                        ):
                            try:
                                pve_withdrawal_pending = COMBAT_SESSIONS.withdraw_pve(
                                    combat_session, character, b""
                                )
                            except ValueError as error:
                                shared_selection = refresh_shared_combat()
                                if (
                                    getattr(shared_selection, "is_duel", False)
                                    or getattr(shared_selection.fight, "phase", None)
                                    != "finished"
                                ):
                                    raise
                                # The authoritative withdrawal rejects before
                                # writes if another owner just ended the fight.
                                # Preserve the terminal session for its real ACK.
                                record(
                                    event="combat_terminal_character_selection_deferred",
                                    actor_id=character["id"],
                                    fight_id=shared_selection.fight.id,
                                    settlement_ready=shared_selection.settlement_ready,
                                    reason=str(error),
                                    native_return_ack=False,
                                )
                                send(
                                    connection,
                                    service,
                                    674,
                                    wire.chat(
                                        dict(character, name="Consola local"),
                                        "Cierra el resultado del combate antes de cambiar de personaje.",
                                    ),
                                )
                                continue
                            publish_external_marker(shared_selection)
                            character.update(
                                refresh_owned_character(
                                    pve_withdrawal_pending["character"]
                                )
                            )
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
                                from wakfu_server.combat_shared_abandon import (
                                    requires_shared_abort,
                                )

                                if requires_shared_abort(
                                    shared_selection.fight, combat_session
                                ):
                                    abandoned_selection = (
                                        COMBAT_SESSIONS.abandon_shared_pve(
                                            combat_session,
                                            character,
                                            b"",
                                            groups=COMBAT_GROUPS,
                                            shared=shared_selection,
                                        )
                                    )
                                    fight = shared_selection.fight
                                    selection_runtime = shared_selection.runtime
                                else:
                                    abandoned_selection = prepare_selection_abandon(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        selection_runtime,
                                        b"",
                                    )
                                    shared_selection.runtime = selection_runtime
                                character.update(
                                    refresh_owned_character(
                                        abandoned_selection["character"]
                                    )
                                )
                                if not abandoned_selection.get("shared_full_abort"):
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
                            if abandoned_selection.get("shared_full_abort"):
                                publish_full_abandon_group(
                                    shared_selection, abandoned_selection
                                )
                                drain_shared_combat()
                                returned_selection = (
                                    COMBAT_SESSIONS.return_withdrawn_pve(
                                        combat_session,
                                        fight.id,
                                        character,
                                        struct.pack(">iB", fight.id, 1),
                                        wp=COMBAT_TEST_WP,
                                        pending=shared_selection.withdrawals[
                                            account_id
                                        ],
                                    )
                                )
                                character.update(
                                    refresh_owned_character(
                                        returned_selection["character"]
                                    )
                                )
                            else:
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
                            generation,
                            bag_session.exterior_actor_id
                            if bag_session is not None
                            else character["id"],
                        )
                        if exterior is not None:
                            outside, packet = exterior
                            WORLD.emit_location(
                                outside["map_id"], outside["instance_id"], *packet
                            )
                        WORLD.leave(character["id"], generation)
                    selected = loaded = False
                    hero_switch_pending = None
                    character = None
                    movement_state = None
                    bag_session = None
                    ranch_session = None
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
                        if not created.get("recustomized"):
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
                        character = select_created_character(
                            STORE, account_id, generation, created["id"]
                        )
                        deliver_custom_task_rewards(bootstrap=True)
                        character = health_store.initialize(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            exploration=True,
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
                    if selected:
                        from wakfu_server.character_selection_retry import (
                            already_selected_owned_character,
                        )

                        if already_selected_owned_character(
                            STORE, account_id, generation, character, request
                        ):
                            record(
                                event="character_selection_retry_ignored",
                                character_id=character["id"],
                            )
                            continue
                    if account_id is None or selected:
                        raise ValueError(
                            "Authentication required or character already selected"
                        )
                    from wakfu_server.heroes import CompanySelectionRejected

                    pending_character = STORE.character(
                        account_id, request["character_id"]
                    )
                    if pending_character.get("recustomization"):
                        if request["character_name"] != pending_character["name"]:
                            raise ValueError("Character name mismatch")
                        from wakfu_server.character_recustomization import (
                            transition_packets,
                        )

                        for packet in transition_packets(pending_character):
                            send(connection, service, *packet)
                        continue
                    try:
                        character = STORE.select_character(
                            account_id, generation, request["character_id"]
                        )
                    except CompanySelectionRejected as error:
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(connection, service, 23082, b"\x01")
                        send(
                            connection,
                            service,
                            *information(failure_message("hero_selection", error)),
                        )
                        record(
                            event="character_selection_rejected",
                            account_id=account_id,
                            character_id=request["character_id"],
                            reason=str(error),
                        )
                        continue
                    if is_dungeon_run(character.get("instance_id", 0)):
                        from wakfu_server import dungeon_recovery, dungeon_runtime
                        from wakfu_server.combat_terrain import map_geometry

                        recovery = dungeon_recovery.resume_member(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            character["instance_id"],
                            in_fight=lambda actor_id: COMBAT_SESSIONS.lookup_character(
                                actor_id
                            )
                            is not None,
                        )
                        character = STORE.character(account_id, character["id"])
                        if is_dungeon_run(character.get("instance_id", 0)):
                            with STORE.connection() as dungeon_db:
                                dungeon_runtime.ensure_current_room(
                                    dungeon_db,
                                    COMBAT_GROUPS,
                                    character["instance_id"],
                                    map_geometry(character["map_id"]),
                                )
                    from wakfu_server import heroes

                    heroes.select_main(STORE, account_id, generation, character["id"])
                    from wakfu_server import companions

                    with STORE.connection() as companion_db:
                        companion_db.execute(
                            "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                            (account_id,),
                        )
                        STORE.lock_character(
                            companion_db, account_id, generation, character["id"]
                        )
                        companions.select_main(
                            companion_db, account_id, character["id"]
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
                    recovered_rift = reconcile_closed_rift_login(
                        STORE,
                        POSITIONS,
                        account_id,
                        generation,
                        character,
                        live_reconnect=live_reconnect,
                    )
                    if recovered_rift is not None:
                        character = recovered_rift
                        record(
                            event="closed_rift_login_recovered",
                            actor_id=character["id"],
                            map_id=character["map_id"],
                            instance_id=character["instance_id"],
                        )
                    deliver_custom_task_rewards(bootstrap=True)
                    character = health_store.initialize(
                        STORE,
                        account_id,
                        generation,
                        character["id"],
                        exploration=not live_reconnect,
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
                    send(connection, service, *builds.selection_message(character))
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
                elif opcode == 13932 and loaded:
                    from wakfu_server.position_buffer import PositionOwnerBusy
                    from wakfu_server.position_redis import PositionJournalError

                    try:
                        request_world_respawn(body)
                    except (
                        ValueError,
                        DatabaseError,
                        PoolTimeout,
                        PositionOwnerBusy,
                        PositionJournalError,
                    ) as error:
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Reintenta el regreso al fénix"
                        )
                        send(connection, service, *information(reason))
                        record(
                            event="world_respawn_rejected",
                            actor_id=character["id"],
                            reason=reason,
                        )
                elif opcode == 12239 and loaded:
                    from psycopg import Error as ResurrectionDatabaseError
                    from psycopg_pool import PoolTimeout as ResurrectionPoolTimeout
                    from wakfu_server.position_buffer import PositionOwnerBusy

                    try:
                        resurrect_world_character(body)
                    except (
                        ValueError,
                        ResurrectionDatabaseError,
                        ResurrectionPoolTimeout,
                        PositionOwnerBusy,
                    ) as error:
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Reintenta la resurrección"
                        )
                        send(connection, service, *information(reason))
                        record(
                            event="world_resurrection_rejected",
                            actor_id=character["id"],
                            reason=reason,
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
                        pet_hibernation_due = 0.0
                        saved = result["character"]
                        if saved["id"] == character["id"]:
                            updated = refresh_owned_character(saved)
                            updated.update(
                                {
                                    key: character[key]
                                    for key in (
                                        "map_id",
                                        "instance_id",
                                        "x",
                                        "y",
                                        "z",
                                        "direction",
                                    )
                                }
                            )
                            character = updated
                            saved = character
                        if result["applied"]:
                            # PET attaches the actor observer to the refreshed
                            # rich item model. XP itself belongs to ProtoPet.
                            from wakfu_server.mount_publication import pet_packet

                            if saved["id"] == character["id"]:
                                WORLD.update(
                                    generation,
                                    character,
                                    *pet_packet(character),
                                )
                                publish_consumable_character(character)
                            else:
                                from wakfu_server.territory_bonuses import world_packet

                                send(connection, service, *pet_packet(saved))
                                send(connection, service, *world_packet(saved))
                            for packet in mount_snapshot(saved):
                                send(connection, service, *packet)
                        record(
                            event="mount_food_fed",
                            actor_id=saved["id"],
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
                    from wakfu_server.craft_station import (
                        native_catalog as craft_catalog,
                        resolve_current as resolve_craft_station,
                    )
                    from wakfu_server.craft_wire import request as craft_request
                    from wakfu_server.craft_wire import (
                        occupation_request as craft_occupation_request,
                    )
                    from wakfu_server.craft_wire import result as craft_result

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
                                lambda saved: active_private_session().refresh(
                                    character, saved
                                )
                            )
                            if active_private_session() is not None
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
                    from wakfu_server.craft_station import (
                        native_catalog as craft_catalog,
                        resolve_current as resolve_craft_station,
                    )
                    from wakfu_server.craft_wire import result as craft_result

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
                                lambda saved: active_private_session().refresh(
                                    character, saved
                                )
                            )
                            if active_private_session() is not None
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
                            else saved
                        )
                        send_native_planting_bonus(connection, character)
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
                            from wakfu_server.resource_domains import (
                                is_mineral,
                                is_fish,
                            )

                            if is_mineral(resource["resource_reference"]):
                                from wakfu_server.mining_navigation import reachable

                                return reachable(current, resource)
                            if is_fish(resource["resource_reference"]):
                                from wakfu_server.fishing_navigation import reachable

                                return reachable(current, resource)
                            from wakfu_server.haven_bag_garden import is_private_garden

                            if is_private_garden(current):
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
                            location_context=lambda stored: owned_planting_character(
                                stored, WORLD, POSITIONS, store=STORE
                            ),
                        )
                        PLANTINGS.cancel(character["id"], generation)
                        HARVESTS.cancel(character["id"], generation=generation)
                        flora_ticket = reserve(
                            STORE,
                            account_id,
                            generation,
                            prepared,
                            location_context=lambda stored: owned_planting_character(
                                stored, WORLD, POSITIONS, store=STORE
                            ),
                        )
                        WORLD.emit_location(
                            prepared["character"]["map_id"],
                            prepared["character"]["instance_id"],
                            *start_packet(
                                prepared["character"],
                                prepared["resource"],
                                dict(
                                    prepared["rule"],
                                    duration_ms=flora_ticket["duration_ms"],
                                ),
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
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("harvest", error)),
                        )
                elif (
                    opcode == 13429
                    and loaded
                    and len(body) == 3
                    and struct.unpack(">Bh", body)[1] == 3
                ):
                    complete_flora_occupation(body)
                elif opcode == 13284 and loaded:
                    from wakfu_server.item_appearance_fusion import (
                        use as fuse_item_appearance,
                    )
                    from wakfu_server.ecology_feedback import information

                    try:
                        fusion = fuse_item_appearance(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            in_fight=fight is not None or combat_session is not None,
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo fusionar la apariencia; inténtalo de nuevo"
                        )
                        send(connection, service, *information(reason))
                        record(
                            event="item_appearance_fusion_rejected",
                            actor_id=character["id"],
                            reason=reason,
                        )
                        continue
                    saved = fusion["character"]
                    if saved["id"] == character["id"]:
                        updated = refresh_owned_character(saved)
                        updated.update(
                            {
                                key: character[key]
                                for key in (
                                    "map_id",
                                    "instance_id",
                                    "x",
                                    "y",
                                    "z",
                                    "direction",
                                )
                            }
                        )
                        character = saved = updated
                    for packet in fusion["packets"]:
                        send(connection, service, *packet)
                    from wakfu_server.equipment_appearance import snapshot_packet

                    if saved["id"] == character["id"]:
                        WORLD.update(generation, character, *snapshot_packet(saved))
                    else:
                        send(connection, service, *snapshot_packet(saved))
                        WORLD.broadcast(
                            generation,
                            character["id"],
                            *snapshot_packet(saved),
                            include_sender=False,
                        )
                    record(
                        event="item_appearance_fused",
                        actor_id=saved["id"],
                        stat_uid=fusion["stat_uid"],
                        appearance_ref=fusion["appearance_ref"],
                        consumed=fusion["consumed"],
                    )
                elif opcode == 12851:
                    if (
                        account_id is None
                        or generation is None
                        or not selected
                        or character is None
                    ):
                        raise ValueError(
                            "Inventory journal requires a selected character"
                        )
                    from wakfu_server.inventory_deferred_journal import query

                    send(
                        connection,
                        service,
                        *query(
                            STORE,
                            account_id,
                            generation,
                            body,
                        ),
                    )
                elif opcode == 13220 and loaded:
                    from psycopg import Error as ItemDatabaseError
                    from psycopg_pool import PoolTimeout as ItemPoolTimeout
                    from wakfu_server.simple_item_actions import (
                        action_class as simple_item_action_class,
                        use as use_simple_item_action,
                    )

                    from wakfu_server import haven_world_bombs

                    if (
                        len(body) >= 4
                        and struct.unpack_from(">i", body)[0]
                        in haven_world_bombs.ACTIONS
                    ):
                        try:
                            bombing = haven_world_bombs.use(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                in_fight=fight is not None
                                or combat_session is not None,
                                context=dict(character, **position),
                            )
                        except (
                            ValueError,
                            ItemDatabaseError,
                            ItemPoolTimeout,
                        ) as error:
                            reason = (
                                str(error)
                                if isinstance(error, ValueError)
                                else "No se pudo utilizar la bomba; inténtalo de nuevo"
                            )
                            record(
                                event="haven_world_bomb_rejected",
                                actor_id=character["id"],
                                reason=reason,
                            )
                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"), reason
                                ),
                            )
                            continue
                        # Source/population committed; delivery failure must not
                        # re-enter the consuming transaction or roll it back.
                        character = refresh_owned_character(bombing["character"])
                        character.update(position)
                        for packet in bombing["packets"]:
                            send(connection, service, *packet)
                        for packet in bombing["scene_packets"]:
                            WORLD.emit_location(*bombing["scene"], *packet)
                        record(
                            event="haven_world_bomb_used",
                            actor_id=character["id"],
                            removed=bombing["removed_count"],
                            receipt_id=bombing["receipt_id"],
                        )
                        continue
                    simple_item_result = None
                    try:
                        simple_class = simple_item_action_class(body)
                        if simple_class is None:
                            from wakfu_server import companions, haven_ranch_herd

                            if haven_ranch_herd.action_class(body) is not None:
                                simple_class = "bHz"
                                simple_item_result = haven_ranch_herd.use(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    body,
                                    in_fight=(
                                        fight is not None
                                        or combat_session is not None
                                        or spectator_session is not None
                                    ),
                                )
                            elif companions.action_class(body) is not None:
                                simple_class = "bHE"
                                simple_item_result = companions.use(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    body,
                                    in_fight=fight is not None
                                    or combat_session is not None,
                                )
                            elif open_item_recustomization(body):
                                continue
                            if simple_item_result is None and play_inventory_emote(
                                body
                            ):
                                continue
                            if simple_item_result is None and use_inventory_teleport(
                                body
                            ):
                                continue
                            if simple_item_result is None and play_inventory_script(
                                body
                            ):
                                continue
                            if (
                                simple_item_result is None
                                and spawn_inventory_test_actor(body)
                            ):
                                continue
                            if (
                                simple_item_result is None
                                and mark_inventory_destination(body)
                            ):
                                continue
                            if simple_item_result is None:
                                from wakfu_server import (
                                    conversion_item_actions,
                                    restat_item_actions,
                                    neutrality_item_actions,
                                    captain_map_item_actions,
                                    journal_part_item_actions,
                                    achievement_item_actions,
                                    binding_kit_item_actions,
                                )

                                for actions in (
                                    conversion_item_actions,
                                    restat_item_actions,
                                    neutrality_item_actions,
                                    captain_map_item_actions,
                                    journal_part_item_actions,
                                    achievement_item_actions,
                                    binding_kit_item_actions,
                                ):
                                    handled = actions.action_class(body)
                                    if handled is not None:
                                        simple_class = handled
                                        simple_item_result = actions.use(
                                            STORE,
                                            account_id,
                                            generation,
                                            character["id"],
                                            body,
                                            in_fight=fight is not None
                                            or combat_session is not None,
                                        )
                                        break
                            from wakfu_server.scenario_item_actions import (
                                action_class as scenario_item_action_class,
                                use as read_scenario_item,
                            )

                            if (
                                simple_item_result is None
                                and scenario_item_action_class(body) is not None
                            ):
                                reading = read_scenario_item(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    body,
                                    in_fight=fight is not None
                                    or combat_session is not None,
                                )
                                for packet in reading["packets"]:
                                    send(connection, service, *packet)
                                record(
                                    event="scenario_item_read",
                                    actor_id=character["id"],
                                    scenario_id=reading["scenario_id"],
                                    consumed=reading["consumed"],
                                )
                                continue
                            from wakfu_server.book_item_actions import (
                                action_class as book_action_class,
                                use as read_book_item,
                            )

                            if (
                                simple_item_result is None
                                and book_action_class(body) is not None
                            ):
                                book_result = read_book_item(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    body,
                                    in_fight=fight is not None,
                                    native_map_id=native_item_world_identity(character),
                                )
                                record(
                                    event="book_item_read",
                                    actor_id=book_result["character"]["id"],
                                    background_id=book_result["background_id"],
                                    consumed=book_result["consumed"],
                                )
                                continue
                            from wakfu_server.random_item_actions import (
                                action_class as random_item_action_class,
                                use as use_random_item_action,
                            )

                            if simple_item_result is None:
                                simple_class = random_item_action_class(body)
                            if simple_item_result is None and simple_class is not None:
                                simple_item_result = use_random_item_action(
                                    STORE,
                                    account_id,
                                    generation,
                                    character["id"],
                                    body,
                                    in_fight=fight is not None,
                                    native_map_id=native_item_world_identity(character),
                                )
                        elif simple_class is not None:
                            simple_item_result = use_simple_item_action(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                in_fight=fight is not None,
                                native_map_id=native_item_world_identity(character),
                            )
                    except (ValueError, ItemDatabaseError, ItemPoolTimeout) as error:
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo utilizar el objeto; inténtalo de nuevo"
                        )
                        record(
                            event="simple_item_action_rejected",
                            actor_id=character["id"],
                            reason=reason,
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(dict(character, name="Consola local"), reason),
                        )
                        continue
                    if simple_item_result is not None:
                        # Publication is outside the consuming transaction and
                        # its error catch. Reconnect repairs a failed delivery;
                        # it must never repeat an already committed grant.
                        saved = simple_item_result["character"]
                        if saved["id"] == character["id"]:
                            saved = refresh_owned_character(saved)
                        else:
                            saved = dict(saved)
                        # Buffered movement and private scene coordinates are
                        # live authority. Item/XP hydration must not move either
                        # the selected actor or its following hero to SQL's
                        # durable exterior/previous position.
                        saved.update(
                            map_id=character["map_id"],
                            instance_id=character["instance_id"],
                            direction=character["direction"],
                            **position,
                        )
                        simple_packets = list(simple_item_result["packets"])
                        if simple_class == "bHK":
                            from wakfu_server.combat_lifecycle import (
                                outside_progression,
                            )

                            simple_packets[-1] = outside_progression(
                                saved, wp=COMBAT_TEST_WP
                            )
                        elif simple_item_result.get("xp_changed"):
                            from wakfu_server.combat_lifecycle import (
                                outside_progression,
                            )

                            # Earned mission XP notifications precede the final
                            # absolute progression and level snapshot.
                            simple_packets.append(
                                outside_progression(saved, wp=COMBAT_TEST_WP)
                            )
                        if simple_item_result.get("nation_changed"):
                            # The original passport scenario reads the updated
                            # nation. Publish identity before its private UI event.
                            saved = publish_nation_character(saved)
                        for message_id, message_body in simple_packets:
                            send(connection, service, message_id, message_body)
                        if saved["id"] == character["id"]:
                            character = saved
                            if simple_class == "bHK" or simple_item_result.get(
                                "xp_changed"
                            ):
                                WORLD.update(
                                    generation,
                                    character,
                                    *wire.refresh_player(PLAYER_TEMPLATE, character),
                                )
                                publish_consumable_character(character)
                            elif simple_item_result.get("characteristics_changed"):
                                publish_consumable_character(character)
                        else:
                            from wakfu_server.hero_wire import refresh

                            if not simple_item_result.get("characteristics_changed"):
                                send(
                                    connection,
                                    service,
                                    *refresh(OWNED_HERO_TEMPLATE, saved),
                                )
                            from wakfu_server.hero_wire import statistics

                            send(connection, service, *statistics(saved))
                        record(
                            event="simple_item_action_used",
                            actor_id=saved["id"],
                            native_class=simple_class,
                            consumed=simple_item_result["consumed"],
                        )
                        continue
                    item_action_class = None
                    try:
                        from wakfu_server.cosmetic_learning import (
                            learn_item,
                            request_action_class,
                        )

                        item_action_class = request_action_class(body)
                        if item_action_class != "bIi":
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
                            if saved["id"] == character["id"]:
                                character = refresh_owned_character(saved)
                            for message_id, message_body in result["packets"]:
                                send(connection, service, message_id, message_body)
                            record(event="item_learned", actor_id=saved["id"])
                            continue
                        if fight is not None:
                            raise ValueError("Sal del combate para plantar")

                        character = owned_planting_character(
                            character,
                            WORLD,
                            POSITIONS,
                            store=STORE,
                            generation=generation,
                        )
                        WORLD.refresh_location(generation, character)

                        if ECOLOGY_MODE == "external":
                            HARVESTS.cancel(character["id"], generation=generation)
                            PLANTINGS.cancel(character["id"], generation)
                            intent_id = PLANTINGS.ecology_intents.enqueue(
                                account_id, generation, character, body
                            )
                            record(
                                event="planting_preparation_enqueued",
                                actor_id=character["id"],
                                intent_id=intent_id,
                            )
                            continue

                        from wakfu_server.planting_cells import authorize
                        from wakfu_server.combat_terrain import map_geometry

                        def authorize_planting(current, request, seed, resource):
                            from wakfu_server.haven_bag_garden import is_private_garden

                            if is_private_garden(current):
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
                                        current["map_id"],
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

                        HARVESTS.cancel(character["id"], generation=generation)
                        send_native_planting_bonus(connection, character)
                        # Challenges and checkpoints take account ownership first.
                        # The planting location context reenters this owner lock.
                        with POSITIONS.account_barrier(account_id), COMBAT_GROUPS.lock:
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
                            event="planting_rejected"
                            if item_action_class == "bIi"
                            else "item_learning_rejected",
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
                        if fight is not None or (
                            bag_session is not None and ranch_session is None
                        ):
                            raise ValueError(
                                "La recolección requiere estar fuera del combate y del merkasaco"
                            )
                        if ranch_session is not None:
                            ranch_session.validate_lease(generation)
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
                                location_context=refresh_owned_character,
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
                            with POSITIONS.account_barrier(
                                account_id
                            ), COMBAT_GROUPS.lock:
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
                                character = owned_planting_character(
                                    saved,
                                    WORLD,
                                    POSITIONS,
                                    store=STORE,
                                    generation=generation,
                                )
                                send_planting_context(connection, character)
                            custom_tasks = result.get("custom_task_update") or {}
                            if custom_tasks.get("updated"):
                                deliver_custom_task_rewards()
                                custom_task_cards.changed(
                                    character["id"], (character["id"],)
                                )
                                publish_custom_task_cards()
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
                                location_context=refresh_owned_character,
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
                            character = refresh_owned_character(
                                STORE.character(account_id, character["id"])
                            )
                            send(connection, service, *equipment_inventory(character))
                            send_native_planting_bonus(connection, character)
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
                    from wakfu_server.friendly_duel_wire import cancellation

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
                        from wakfu_server.friendly_duel_wire import (
                            decode_challenge,
                        )
                        from wakfu_server.friendly_duels import (
                            cancel_undelivered_invitation,
                            invite_challenge,
                            owned_duel_target,
                        )

                        request = decode_challenge(body)
                        identity = WORLD.live_identity(
                            character_id=request["target_character_id"]
                        )
                        challenger_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        own_target = (
                            owned_duel_target(
                                STORE,
                                challenger_session,
                                request["target_character_id"],
                            )
                            if identity is None
                            or identity[1]["account_id"] == account_id
                            else None
                        )
                        if identity is None and own_target is None:
                            raise ValueError("Duel target is offline")
                        if own_target is not None:
                            from wakfu_server.combat_shared import Session

                            target_generation, target_character = generation, own_target
                            target_session = Session(
                                account_id,
                                own_target["id"],
                                generation,
                                own_target["map_id"],
                                own_target.get("instance_id", 0),
                            )
                            delivery_character_id = character["id"]
                        else:
                            target_generation, target_character = identity
                            target_session = COMBAT_SESSIONS.session(
                                target_character["account_id"],
                                target_generation,
                                target_character,
                            )
                            delivery_character_id = target_character["id"]
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        flush_positions(
                            account_id=target_character["account_id"],
                            generation=target_generation,
                            character_id=delivery_character_id,
                        )
                        result = invite_challenge(
                            STORE, challenger_session, target_session, body
                        )
                        if not WORLD.send_to(
                            delivery_character_id,
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
                    from wakfu_server.friendly_duel_wire import cancellation

                    try:
                        if (
                            not COMBAT_TEST
                            or fight is not None
                            or bag_session is not None
                        ):
                            raise ValueError(
                                "Duel answer is unavailable in this session"
                            )
                        from wakfu_server.friendly_duel_runtime import (
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

                        from wakfu_server.combat_terrain import prepare_terrain

                        def prepare_duel(
                            db,
                            fight_id,
                            invitation,
                            challenger,
                            target,
                            *,
                            prepared_terrain=None,
                        ):
                            prepared = prepare_and_register(
                                STORE,
                                COMBAT_SESSIONS,
                                db,
                                fight_id,
                                invitation,
                                challenger,
                                target,
                                auto_locked=bool(invitation["auto_lock"]),
                                prepared_terrain=prepared_terrain,
                            )
                            rollback = prepared.pop("rollback")
                            return prepared, rollback

                        result = answer_challenge(
                            STORE,
                            COMBAT_SESSIONS.session(account_id, generation, character),
                            body,
                            prepare_duel=prepare_duel,
                            prewarm_duel=prepare_terrain,
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
                        if (
                            fight is not None
                            or combat_session is not None
                            or bag_session is not None
                        ):
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
                        candidate_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        joined_actor = COMBAT_SESSIONS.player_actor(
                            candidate_session, team=target.team
                        )
                        shared = COMBAT_SESSIONS.join(
                            candidate_session,
                            body,
                            joined_actor,
                            expected_fight_id=fight_id,
                            native_publication=(
                                connection.instance_publications,
                                connection.native_instance_scope(),
                            ),
                        )
                        from wakfu_server.objectives.environmental_gameplay import (
                            remember_admission,
                        )

                        remember_admission(shared, account_id, character)
                        combat_session = candidate_session
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
                    from wakfu_server.combat_spectator_wire import (
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
                    from wakfu_server.combat_spectator_wire import (
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
                    if rift_start_run is False:
                        continue
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
                        or (bag_session is not None and ranch_session is None)
                        or (
                            ranch_session is not None
                            and not ranch_session.owns(character)
                        )
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
                        scene_helper_manifest = None
                        if rift_start_run is None:
                            from wakfu_server.combat_encounter_scene_helpers import (
                                prepare_scene_roster,
                            )

                            TEST_MONSTERS, scene_helper_manifest = prepare_scene_roster(
                                STORE, character, TEST_MONSTERS
                            )
                        from wakfu_server.combat_operational_admission import (
                            require_operational_encounter,
                        )

                        try:
                            require_operational_encounter(TEST_MONSTERS)
                        except ValueError as error:
                            send(
                                connection,
                                service,
                                674,
                                wire.chat(
                                    dict(character, name="Consola local"),
                                    str(error),
                                ),
                            )
                            continue
                        TEST_MONSTERS_BY_ID = {m["id"]: m for m in TEST_MONSTERS}
                        entry_stage("group_selected")
                        from wakfu_server.combat_arena_policy import (
                            cell_budget,
                            size_range,
                        )

                        with STORE.connection() as arena_policy_db:
                            arena_cell_budget = cell_budget(arena_policy_db)
                            arena_size_range = size_range(arena_policy_db)
                            arena_room_cells = None
                            if (
                                rift_start_run is None
                                and DUNGEON_ROOM_RUNTIME_AVAILABLE
                                and is_dungeon_run(character.get("instance_id", 0))
                            ):
                                from wakfu_server.dungeon_runtime import (
                                    combat_room_cells,
                                )

                                arena_room_cells = combat_room_cells(
                                    arena_policy_db,
                                    TEST_GROUP_KEY,
                                    (character["x"], character["y"], character["z"]),
                                    [(m["x"], m["y"], m["z"]) for m in TEST_MONSTERS],
                                )
                        from wakfu_server.combat_actor_snapshot import (
                            native_actor_catalog,
                        )

                        formation_catalog = native_actor_catalog()
                        arena = local_arena(
                            character["map_id"],
                            character["id"],
                            (character["x"], character["y"], character["z"]),
                            [(m["x"], m["y"], m["z"]) for m in TEST_MONSTERS],
                            automatic_cell_budget=arena_cell_budget,
                            size_range=arena_size_range,
                            allowed_cells=arena_room_cells,
                            member_radii=tuple(
                                formation_catalog["npc_profiles"][str(m["ref"])][
                                    "physical_radius"
                                ]
                                for m in TEST_MONSTERS
                            ),
                            player_radius=formation_catalog["default_actor_radius"],
                            stage_callback=lambda stage, elapsed_ms, thread_cpu_ms: record(
                                event="combat_arena_stage",
                                stage=stage,
                                map_id=character["map_id"],
                                elapsed_ms=round(elapsed_ms, 3),
                                thread_cpu_ms=round(thread_cpu_ms, 3),
                            ),
                        )
                        from wakfu_server.combat_encounter_scene_layout import (
                            prepare_encounter_scene,
                        )

                        if scene_helper_manifest is not None:
                            from wakfu_server.combat_encounter_scene_helpers import (
                                adapt_helper_placement,
                            )

                            arena[
                                "native_encounter_scene_helpers"
                            ] = scene_helper_manifest
                            arena = adapt_helper_placement(
                                character, TEST_MONSTERS, arena
                            )

                        if rift_start_run is not None:
                            from wakfu_server.rift_encounter_roles import (
                                prepare_rift_arena,
                            )

                            arena = prepare_rift_arena(
                                character,
                                TEST_MONSTERS,
                                arena,
                                rift_start_run["catalog"],
                                rift_start_run["policy"],
                            )
                        arena = prepare_encounter_scene(character, TEST_MONSTERS, arena)
                        entry_stage("arena_selected")
                        from wakfu_server import territory_bonuses

                        with STORE.connection() as territory_db:
                            character = territory_bonuses.reconcile_owned(
                                STORE,
                                account_id,
                                generation,
                                character,
                                db=territory_db,
                            )
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
                            from wakfu_server.dungeon_fight_binding import (
                                bind_room_group,
                            )

                            def dungeon_binding(db, fight_id):
                                from wakfu_server.dungeon_difficulty import (
                                    encounter_scaling,
                                )

                                profile = encounter_scaling(
                                    db, character["instance_id"]
                                )
                                return bind_room_group(
                                    db,
                                    TEST_GROUP_KEY,
                                    character["id"],
                                    fight_id,
                                    player_team=(
                                        0
                                        if arena.get("native_encounter_roles") is None
                                        else arena["native_encounter_roles"][
                                            "player_team"
                                        ]
                                    ),
                                    expected_selection_revision=(
                                        None
                                        if profile is None
                                        else profile["selection_revision"]
                                    ),
                                )

                        entry_boundary = {}

                        def capture_entry_boundary(db, identity):
                            from types import SimpleNamespace
                            from wakfu_server.neo_regeneration import (
                                freeze_fight_configuration,
                            )

                            if dungeon_binding is not None:
                                dungeon_binding(db, identity)
                            entry_boundary["health"] = db.execute(
                                "SELECT id,account_id,hp,max_hp,hp_damage,health_dead,hp_zero_valid "
                                "FROM characters WHERE id=%s AND account_id=%s",
                                (character["id"], account_id),
                            ).fetchone()
                            configuration = SimpleNamespace()
                            freeze_fight_configuration(db, configuration)
                            entry_boundary[
                                "configuration"
                            ] = configuration.native_system_configuration
                            from wakfu_server.combat_protector_fight_condition import (
                                capture_world_registry_record,
                            )

                            entry_boundary[
                                "protector_registry"
                            ] = capture_world_registry_record(db, character, identity)

                        from wakfu_server.combat_encounter_roles import (
                            assigned_roles,
                            roles_from_record,
                        )

                        entry_role_record = arena.get("native_encounter_roles")
                        entry_roles = (
                            assigned_roles(None)
                            if entry_role_record is None
                            else roles_from_record(
                                entry_role_record,
                                map_id=arena["map_id"],
                                monster_references=[m["ref"] for m in TEST_MONSTERS],
                            )
                        )
                        durable_fight_id = create_fight_identity(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            team=entry_roles.player_team,
                            on_created=capture_entry_boundary,
                        )
                        from wakfu_server.neo_regeneration import (
                            project_entry_character,
                        )

                        character = project_entry_character(
                            character, entry_boundary["health"]
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
                            terrain_effect_id=arena["terrain_effect_id"],
                            terrain_instance_id=terrain_instance_id,
                            duration_ms=placement_duration,
                        )
                        candidate.native_system_configuration = entry_boundary[
                            "configuration"
                        ]
                        candidate.native_protector_registry = entry_boundary[
                            "protector_registry"
                        ]
                        with connection.write_lock:
                            connection.instance_publications.bind_encounter(
                                candidate,
                                connection.native_instance_scope(),
                                npc_ids=tuple(m["id"] for m in TEST_MONSTERS),
                                player_id=character["id"],
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
                        if scene_helper_manifest is not None:
                            from wakfu_server.combat_encounter_objective_spirit import (
                                authorize_spirit_scene,
                            )

                            with STORE.connection() as scene_db:
                                authorize_spirit_scene(
                                    STORE,
                                    scene_db,
                                    candidate,
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                    monster_references=tuple(
                                        monster["ref"] for monster in TEST_MONSTERS
                                    ),
                                )
                        if tuple(m["ref"] for m in TEST_MONSTERS) == (1723,):
                            from wakfu_server.combat_aguabrial_scene import (
                                authorize_aguabrial_scene,
                            )

                            with STORE.connection() as scene_db:
                                authorize_aguabrial_scene(
                                    STORE,
                                    scene_db,
                                    candidate,
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                    monster_references=(1723,),
                                )
                        if tuple(m["ref"] for m in TEST_MONSTERS) == (2880,):
                            from wakfu_server.combat_abomination_scene import (
                                authorize_admission as authorize_abomination_scene,
                            )

                            with STORE.connection() as scene_db:
                                authorize_abomination_scene(
                                    STORE,
                                    scene_db,
                                    candidate,
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                    monster_references=(2880,),
                                )
                        if dungeon_binding is not None:
                            from wakfu_server.dungeon_scaling_entry import (
                                initialize as initialize_dungeon_scaling,
                            )

                            with STORE.connection() as scaling_db:
                                candidate, scaling_receipt = initialize_dungeon_scaling(
                                    scaling_db, candidate, TEST_MONSTERS_BY_ID
                                )
                            entry_stage("dungeon_scaling_initialized")
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
                        # Placement serializers publish each actor's initialized facing.
                        # Preserve it: resetting controlled actors to EAST also makes
                        # inherited summon appearances request unavailable 0_ clips.
                        from wakfu_server.combat_monster_world import remove_message

                        if rift_start_run is None:
                            with COMBAT_GROUPS.lock:
                                group_lease, members = COMBAT_GROUPS.claim(
                                    TEST_GROUP_KEY, generation, candidate.id
                                )
                                from wakfu_server.item_test_spawns import (
                                    is_fight as is_developer_test_fight,
                                )

                                with STORE.connection() as test_group_db:
                                    developer_test_encounter = is_developer_test_fight(
                                        test_group_db, candidate.id
                                    )
                                from wakfu_server.custom_tasks import (
                                    external as objectives_mode,
                                )

                                if (
                                    objectives_mode.enabled()
                                    and not developer_test_encounter
                                ):
                                    from wakfu_server.objectives.challenges import (
                                        bind_fight,
                                    )

                                    with STORE.connection() as challenge_db:
                                        bind_fight(
                                            challenge_db, *TEST_GROUP_KEY, candidate.id
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
                        character.update(
                            hp=saved["hp"],
                            max_hp=saved["max_hp"],
                            hp_damage=saved["hp_damage"],
                            health_dead=saved["health_dead"],
                        )
                        fight_started_at = time.monotonic()
                        combat_session = COMBAT_SESSIONS.session(
                            account_id, generation, character
                        )
                        from wakfu_server.combat_heroes import admit_owned_heroes
                        from wakfu_server.combat_bootstrap import (
                            placement_messages,
                            player_payload,
                        )
                        from wakfu_server.combat_actor import (
                            monster_actor_stats,
                            actor_effects,
                        )
                        from wakfu_server.breed_resources import live_wp

                        with STORE.connection() as hero_db:
                            hero_admission = admit_owned_heroes(
                                hero_db,
                                STORE,
                                combat_session,
                                candidate,
                                private_scene=ranch_session,
                                frozen_members=(
                                    rift_start_run["members"]
                                    if rift_start_run is not None
                                    else None
                                ),
                            )
                            candidate = hero_admission["fight"]
                            from wakfu_server.combat_instance_publication import (
                                refresh_owned_encounter,
                            )

                            refresh_owned_encounter(candidate)
                            from wakfu_server.combat_companions import (
                                admit_owned_companions,
                            )

                            companion_admission = admit_owned_companions(
                                hero_db,
                                STORE,
                                combat_session,
                                candidate,
                                owner_character=character,
                            )
                            candidate = companion_admission["fight"]
                            hero_packets = (
                                tuple(
                                    (12608, wire.spawn_player(PLAYER_TEMPLATE, source))
                                    for source in hero_admission["characters"].values()
                                )
                                + companion_admission["packets"]
                            )
                            from wakfu_server.combat_bootstrap import (
                                should_rebuild_placement,
                            )

                            if should_rebuild_placement(
                                candidate,
                                (
                                    *hero_admission["actors"],
                                    *companion_admission["actors"],
                                ),
                            ):
                                sources = {
                                    character["id"]: character,
                                    **hero_admission["characters"],
                                }
                                actor_payloads = {}
                                for placement_actor in candidate.actors.values():
                                    wp_current, wp_maximum = live_wp(
                                        candidate, placement_actor.id
                                    )
                                    if (
                                        placement_actor.controlled
                                        and placement_actor.id
                                        not in companion_admission["sources"]
                                    ):
                                        actor_payloads[
                                            placement_actor.id
                                        ] = player_payload(
                                            sources[placement_actor.id],
                                            placement_actor,
                                            candidate.id,
                                            wp=wp_current,
                                        )
                                    else:
                                        source = {
                                            **TEST_MONSTERS_BY_ID,
                                            **companion_admission["sources"],
                                        }[placement_actor.id]
                                        if (
                                            placement_actor.id
                                            not in companion_admission["sources"]
                                        ):
                                            source = dict(
                                                source,
                                                **dict(
                                                    zip(
                                                        ("x", "y", "z"),
                                                        placement_actor.position,
                                                    )
                                                ),
                                            )
                                        if (
                                            placement_actor.id
                                            in companion_admission["sources"]
                                            or placement_actor.id
                                            in getattr(
                                                candidate,
                                                "native_npc_initialization_receipts",
                                                {},
                                            )
                                            or placement_actor.id
                                            in getattr(
                                                candidate,
                                                "native_npc_ai_actors",
                                                frozenset(),
                                            )
                                            or placement_actor.id
                                            in getattr(
                                                candidate,
                                                "native_dungeon_scaling_receipt",
                                                {},
                                            ).get("actor_ids", ())
                                        ):
                                            from wakfu_server.combat_actor import (
                                                actual_monster_actor_stats,
                                            )
                                            from wakfu_server.breed_resources import (
                                                live_wp,
                                            )

                                            wp = live_wp(candidate, placement_actor.id)
                                            stats = actual_monster_actor_stats(
                                                source,
                                                placement_actor,
                                                candidate.id,
                                                wp_current=wp[0],
                                                wp_maximum=wp[1],
                                                fight=candidate,
                                            )
                                        else:
                                            stats = monster_actor_stats(
                                                source,
                                                candidate.id,
                                                direction=3,
                                                obstacle_id=placement_actor.native_obstacle_id,
                                            )
                                        effects = actor_effects()
                                        if placement_actor.id in companion_admission[
                                            "sources"
                                        ] or placement_actor.id in getattr(
                                            candidate,
                                            "native_dungeon_scaling_receipt",
                                            {},
                                        ).get(
                                            "actor_ids", ()
                                        ):
                                            from wakfu_server.combat_remote_effects import (
                                                initial_npc_actor_effects,
                                            )

                                            effects = initial_npc_actor_effects(
                                                candidate, placement_actor.id
                                            )
                                        actor_payloads[placement_actor.id] = (
                                            stats,
                                            effects,
                                        )
                                packets = placement_messages(
                                    candidate,
                                    arena,
                                    actor_payloads,
                                    terrain_effect_id=arena["terrain_effect_id"],
                                    terrain_instance_id=terrain_instance_id,
                                    leaders={
                                        candidate.actors[
                                            character["id"]
                                        ].team: character["id"],
                                        candidate.actors[
                                            TEST_MONSTERS[0]["id"]
                                        ].team: TEST_MONSTERS[0]["id"],
                                    },
                                    duration_ms=placement_duration,
                                    viewer_id=character["id"],
                                )
                        from wakfu_server.objectives.environmental_gameplay import (
                            admission_origin,
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
                                "terrain_effect_id": arena["terrain_effect_id"],
                                "terrain_instance_id": terrain_instance_id,
                                "leaders": {
                                    candidate.actors[character["id"]].team: character[
                                        "id"
                                    ],
                                    candidate.actors[
                                        TEST_MONSTERS[0]["id"]
                                    ].team: TEST_MONSTERS[0]["id"],
                                },
                                "duration_ms": placement_duration,
                                "hero_appearance": lambda source: (
                                    12608,
                                    wire.spawn_player(PLAYER_TEMPLATE, source),
                                ),
                                "frozen_company_members": (
                                    rift_start_run["members"]
                                    if rift_start_run is not None
                                    else None
                                ),
                                "monsters": TEST_MONSTERS_BY_ID,
                                "group_key": TEST_GROUP_KEY,
                                "fight_started_at": fight_started_at,
                                "world_marker_cells": (
                                    (character["x"], character["y"]),
                                ),
                                "environmental_admission_origins": {
                                    account_id: admission_origin(character),
                                },
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
                            with shared_rift.lock, COMBAT_SESSIONS.registry.lock:
                                if (
                                    COMBAT_SESSIONS.registry.fights.get(candidate.id)
                                    is not shared_rift
                                ):
                                    raise ValueError(
                                        "Rift company registration changed before assembly"
                                    )
                                with STORE.connection() as rift_db:
                                    from wakfu_server.combat_heroes import (
                                        frozen_main_sessions,
                                    )

                                    party_rows = frozen_main_sessions(
                                        rift_db, STORE, rift_start_run["members"]
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
                                    from wakfu_server.combat_owner_publication import (
                                        publication_for_world_member,
                                    )

                                    from wakfu_server.combat_encounter_roles import (
                                        assigned_roles,
                                    )

                                    player_team = assigned_roles(
                                        shared_rift.fight
                                    ).player_team
                                    COMBAT_SESSIONS.join(
                                        member_session,
                                        # coU's trailing byte is autoLock, not
                                        # the actor's team. Initial company
                                        # assembly must admit the full frozen
                                        # roster before applying any join lock.
                                        struct.pack(">qB", character["id"], 0),
                                        COMBAT_SESSIONS.player_actor(
                                            member_session, team=player_team
                                        ),
                                        expected_fight_id=candidate.id,
                                        native_publication=publication_for_world_member(
                                            WORLD,
                                            member,
                                            map_id=member_character["map_id"],
                                            instance_id=member_character["instance_id"],
                                        ),
                                    )
                                candidate = shared_rift.fight
                                if {
                                    actor.id
                                    for actor in candidate.actors.values()
                                    if actor.controlled
                                    and str(actor.id)
                                    not in getattr(
                                        candidate, "native_companion_sources", {}
                                    )
                                } != set(rift_start_run["members"]):
                                    raise ValueError(
                                        "Rift combat differs from the frozen real company"
                                    )
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
                                    from wakfu_server.rift_key_admission import (
                                        contract as rift_key_contract,
                                        publication as rift_key_publication,
                                    )

                                    key_packets = (
                                        rift_key_publication(
                                            rift_db, STORE, account_id, character["id"]
                                        )
                                        if rift_key_contract(rift_start_run["catalog"])
                                        else ()
                                    )
                                if key_packets:
                                    from wakfu_server.inventory_move import (
                                        reload_inventory,
                                    )

                                    character = reload_inventory(
                                        STORE, account_id, character
                                    )
                                for key_packet in key_packets:
                                    send(connection, service, *key_packet)
                                # Initial joins have already expanded the shared
                                # roster. Bootstrap the starter from that exact
                                # final state, using the same native path as peers.
                                packets = COMBAT_SESSIONS.placement_bootstrap(
                                    candidate, shared_rift, combat_session
                                )
                        fight = candidate
                        for hero_packet in hero_packets:
                            send(connection, service, *hero_packet)
                        for hero_actor in hero_admission["actors"]:
                            send(
                                connection,
                                service,
                                12436,
                                health.packet(hero_actor.id, hero_actor.hp, 0),
                            )
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
                        starter_delivery = None
                        if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                            try:
                                from wakfu_server.combat_delivery_observation import (
                                    begin_direct_bootstrap,
                                    finish_direct_bootstrap,
                                )

                                starter_delivery = begin_direct_bootstrap(
                                    fight.id, combat_session, packets
                                )
                            except Exception:
                                pass
                        try:
                            for message_id, payload in packets:
                                send(connection, service, message_id, payload)
                        except BaseException as error:
                            if starter_delivery is not None:
                                try:
                                    finish_direct_bootstrap(
                                        starter_delivery, error=error
                                    )
                                except Exception:
                                    pass
                            raise
                        else:
                            if starter_delivery is not None:
                                try:
                                    finish_direct_bootstrap(starter_delivery)
                                except Exception:
                                    pass
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
                        from wakfu_server.combat_party_prompt import (
                            notify as notify_party_combat,
                        )

                        notify_party_combat(
                            STORE,
                            WORLD,
                            COMBAT_SESSIONS,
                            COMBAT_SESSIONS.registry.lookup(fight.id),
                            character["id"],
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
                            from wakfu_server.dungeon_fight_binding import (
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
                            from wakfu_server.dungeon_fight_binding import (
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
                elif opcode in (12543, 12519, 12597) and loaded:
                    try:
                        if combat_session is None or fight is None:
                            raise ValueError(
                                "Tactical signaling requires owned fight membership"
                            )
                        from wakfu_server import combat_tactical_markers
                        from wakfu_server.combat_terminal_metadata import (
                            registered_summon_actor_ids,
                        )

                        refresh_shared_combat()
                        selected_actor = fight.actors[combat_session.character_id]
                        current_actor = fight.current
                        if (
                            current_actor is not None
                            and current_actor.controlled
                            and current_actor.owner_id == combat_session.account_id
                            and current_actor.id
                            not in registered_summon_actor_ids(fight)
                        ):
                            selected_actor = current_actor
                        result = combat_tactical_markers.handle(
                            COMBAT_SESSIONS.registry,
                            combat_session,
                            fight.id,
                            selected_actor.id,
                            opcode,
                            body,
                        )
                        if result["accepted"]:
                            checkpoint_fight()
                            drain_shared_combat()
                        record(
                            event="combat_tactical_signal",
                            fight_id=fight.id,
                            actor_id=selected_actor.id,
                            opcode=opcode,
                            accepted=result["accepted"],
                        )
                    except ValueError as error:
                        record(
                            event="combat_tactical_signal_rejected",
                            opcode=opcode,
                            actor_id=None if character is None else character["id"],
                            reason=str(error),
                        )
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
                                    connected_action_source,
                                )

                                source, owner_deck = connected_action_source(
                                    candidate,
                                    characters,
                                    decks,
                                    combat_session.character_id,
                                    combat_session.account_id,
                                    cast_request["actor_id"],
                                )
                                with shared_action_incident(
                                    runtime,
                                    "player_spell",
                                    body,
                                    source,
                                    owner_deck,
                                    characters,
                                    decks,
                                ) as incident:
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
                                    if incident is not None:
                                        incident.packets(packets)
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
                                incident_request=dict(opcode=13260, body=body)
                                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                                else None,
                            )
                            prepare_finished = time.monotonic()
                            refresh_shared_combat()
                            drain_shared_combat()
                            transaction = action_results["transaction"]
                            delivery = action_results["delivery"]
                            checkpoint_fight()
                            record(
                                event="combat_cast",
                                requested_actor_id=cast_request["actor_id"],
                                requested_spell_uid=cast_request["spell_uid"],
                                requested_target=cast_request["target"],
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
                        deck_hex = (
                            character["builds"]
                            .get(character.get("active_build_index", 0), {})
                            .get("deck")
                        )
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
                            requested_actor_id=cast_request["actor_id"],
                            requested_spell_uid=cast_request["spell_uid"],
                            requested_target=cast_request["target"],
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
                                with shared_action_incident(
                                    runtime,
                                    "player_unarmed"
                                    if request["item_uid"] == -1
                                    else "player_weapon",
                                    body,
                                    source,
                                    decks.get(actor_id),
                                    characters,
                                    decks,
                                ) as incident:
                                    if request["item_uid"] == -1:
                                        from wakfu_server.equipment import (
                                            validate_sheet,
                                        )
                                        from wakfu_server.combat_melee import (
                                            prepare_server_unarmed,
                                        )
                                        from wakfu_server.combat_input_observation import (
                                            observe_fact,
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
                                            effect_uid=observe_fact(
                                                "shared_weapon.unarmed_effect_uid",
                                                secrets.randbelow(2**60) + 1,
                                            ),
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
                                            else COMBAT_TEST_CRITICAL_BRANCH
                                            == "critical",
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
                                    if incident is not None:
                                        incident.packets(packets)
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
                                incident_request=dict(opcode=12889, body=body)
                                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                                else None,
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
                            deck_hex = (
                                character["builds"]
                                .get(character.get("active_build_index", 0), {})
                                .get("deck")
                            )
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
                        if deferred_native_combat_attachment() is not None:
                            if body != b"":
                                raise ValueError("Invalid native abandon request")
                            from wakfu_server.position_buffer import PositionOwnerBusy

                            try:
                                abort_waiting_publication_cohort()
                            except (
                                ValueError,
                                DatabaseError,
                                PoolTimeout,
                                PositionOwnerBusy,
                            ) as error:
                                record(
                                    event="combat_publication_recovery_abort_rejected",
                                    actor_id=character["id"],
                                    reason=type(error).__name__,
                                )
                                send(
                                    connection,
                                    service,
                                    *information(
                                        "No se pudo completar el abandono del combate pausado. "
                                        "Espera un momento y vuelve a intentarlo."
                                    ),
                                )
                            continue
                        if combat_session is not None:
                            if body != b"":
                                raise ValueError("Invalid native abandon request")
                            shared = refresh_shared_combat()
                            if shared.fight.phase == "finished":
                                if (
                                    getattr(shared, "full_abandon_owner", None)
                                    == combat_session
                                ):
                                    continue  # Its already-queued native abort is authoritative.
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
                                from wakfu_server.combat_pve_withdraw import (
                                    has_other_live_owner,
                                )

                                if has_other_live_owner(shared.fight, combat_session):
                                    pve_withdrawal_pending = (
                                        COMBAT_SESSIONS.withdraw_pve(
                                            combat_session, character, body
                                        )
                                    )
                                    publish_external_marker(shared)
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
                                    from wakfu_server.combat_shared_abandon import (
                                        requires_shared_abort,
                                    )

                                    if requires_shared_abort(
                                        shared.fight, combat_session
                                    ):
                                        abandoned = COMBAT_SESSIONS.abandon_shared_pve(
                                            combat_session,
                                            character,
                                            body,
                                            groups=COMBAT_GROUPS,
                                            shared=shared,
                                        )
                                        fight = shared.fight
                                        fight_messages = shared.runtime
                                    else:
                                        abandoned = prepare_abandon(
                                            STORE,
                                            account_id,
                                            generation,
                                            character,
                                            abandon_messages,
                                            body,
                                        )
                                        fight_messages = (
                                            shared.runtime
                                        ) = abandon_messages
                                    character.update(
                                        refresh_owned_character(abandoned["character"])
                                    )
                                # Checkpoint lookup and outbox draining acquire
                                # the registry. Keep them outside the per-fight
                                # mutation lock, after durable abandonment.
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
                                if abandoned.get("shared_full_abort"):
                                    publish_full_abandon_group(shared, abandoned)
                                    drain_shared_combat()
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
                        character.update(
                            refresh_owned_character(abandoned["character"])
                        )
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
                elif opcode == 12925 and aborted_native_return is not None:
                    try:
                        finish_aborted_native_return(body)
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        record(
                            event="combat_aborted_native_return_rejected",
                            actor_id=None if character is None else character["id"],
                            reason=str(error),
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
                        connection.native_fight_id = None
                        character.update(refresh_owned_character(returned["character"]))
                        for packet in returned["packets"]:
                            send(connection, service, *packet)
                        attach_combat_return_position()
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        WORLD.leave(character["id"], generation)
                        for packet in combat_return_bootstrap():
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
                        connection.native_fight_id = None
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
                        shared_state = None
                        shared_return = combat_session is not None
                        duel_return = False
                        abandoned = (
                            getattr(fight_messages, "abandon_owner", None) is not None
                        )
                        if shared_return:
                            from wakfu_server.combat_pve_withdraw import (
                                has_other_live_owner,
                            )

                            refresh_shared_combat()
                            shared_state = COMBAT_SESSIONS.registry.lookup(fight.id)
                            if abandoned:
                                if (
                                    getattr(shared_state, "is_duel", False)
                                    or has_other_live_owner(
                                        shared_state.fight, combat_session
                                    )
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

                            if (
                                shared_return
                                and getattr(shared_state, "full_abandon_owner", None)
                                is not None
                            ):
                                returned = COMBAT_SESSIONS.return_withdrawn_pve(
                                    combat_session,
                                    fight.id,
                                    character,
                                    body,
                                    wp=COMBAT_TEST_WP,
                                    pending=shared_state.withdrawals[account_id],
                                )
                            elif shared_return:
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
                        character.update(refresh_owned_character(returned["character"]))
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
                        from wakfu_server.position_lifecycle import (
                            PendingPositionReturn,
                        )

                        position_scope = dict(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        pending_retry = PendingPositionReturn(now=time.monotonic())
                        pending_started = time.monotonic()

                        def position_busy(error, attempt):
                            if attempt == 1 or attempt % 30 == 0:
                                record(
                                    event="combat_return_position_pending",
                                    actor_id=character["id"],
                                    fight_id=fight.id,
                                    attempt=attempt,
                                    pending_seconds=round(
                                        time.monotonic() - pending_started, 3
                                    ),
                                    reason=redact(str(error)),
                                )

                        def finish_return():
                            finish_combat_return_after_position_flush(
                                abandoned=abandoned,
                                shared_return=shared_return,
                                shared_state=shared_state,
                            )

                        if not pending_retry.attempt(
                            now=time.monotonic(),
                            flush=lambda: flush_positions(**position_scope),
                            complete=finish_return,
                            busy=position_busy,
                        ):
                            pending_combat_return = dict(
                                retry=pending_retry,
                                scope=position_scope,
                                complete=finish_return,
                                fight_id=fight.id,
                                started_at=pending_started,
                                held_requests=0,
                            )
                    except ValueError as error:
                        record(
                            event="combat_return_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12593:
                    from wakfu_server.world_orientation import apply_exploration

                    try:
                        character = apply_exploration(
                            STORE,
                            POSITIONS,
                            WORLD,
                            account_id,
                            generation,
                            character,
                            body,
                            loaded=loaded,
                            fight=fight,
                        )
                        record(
                            event="world_orientation",
                            actor_id=character["id"],
                            direction=character["direction"],
                        )
                    except ValueError as error:
                        record(
                            event="world_orientation_rejected",
                            actor_id=character["id"] if character is not None else None,
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
                    from wakfu_server.combat_movement_runtime import (
                        apply_client,
                        decode_request,
                    )
                    from wakfu_server.combat_actor import actual_actor_stats

                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition

                        try:
                            movement_actor_id, _ = decode_request(body)
                            movement_result = {}

                            def shared_move(candidate, runtime):
                                characters, decks = COMBAT_SESSIONS.player_sources(
                                    candidate
                                )
                                from wakfu_server.combat_cast_delivery_source import (
                                    connected_action_source,
                                )

                                source, owner_deck = connected_action_source(
                                    candidate,
                                    characters,
                                    decks,
                                    combat_session.character_id,
                                    combat_session.account_id,
                                    movement_actor_id,
                                )
                                with shared_action_incident(
                                    runtime,
                                    "move",
                                    body,
                                    source,
                                    owner_deck,
                                    characters,
                                    decks,
                                ) as incident:
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
                                    if incident is not None:
                                        incident.packets(packets)
                                    movement_result["event"] = event
                                    return Transition(
                                        candidate, runtime, tuple(packets)
                                    )

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                movement_actor_id,
                                shared_move,
                                incident_request=dict(opcode=12161, body=body)
                                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                                else None,
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                            checkpoint_fight()
                            record(
                                event="combat_movement",
                                actor_id=movement_actor_id,
                                movement=movement_result.get("event"),
                            )
                        except ValueError as error:
                            record(
                                event="combat_movement_rejected",
                                actor_id=combat_session.character_id,
                                reason=str(error),
                            )
                            from wakfu_server.combat_movement_rejection import (
                                queue_shared_movement_rejection,
                            )

                            try:
                                if queue_shared_movement_rejection(
                                    COMBAT_SESSIONS.registry,
                                    combat_session,
                                    fight.id,
                                    body,
                                ):
                                    drain_shared_combat()
                            except (
                                ValueError,
                                DatabaseError,
                                PoolTimeout,
                            ) as correction_error:
                                record(
                                    event="combat_movement_correction_deferred",
                                    actor_id=combat_session.character_id,
                                    error_type=type(correction_error).__name__,
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
                        from wakfu_server.combat_movement_rejection import (
                            movement_rejection_packet,
                        )

                        try:
                            correction = movement_rejection_packet(
                                fight_messages,
                                account_id,
                                body,
                                session_is_current=STORE.current_character_session(
                                    account_id, generation, character["id"]
                                ),
                            )
                            if correction is not None:
                                send(connection, service, *correction)
                        except (
                            ValueError,
                            DatabaseError,
                            PoolTimeout,
                        ) as correction_error:
                            record(
                                event="combat_movement_correction_deferred",
                                actor_id=character["id"],
                                error_type=type(correction_error).__name__,
                            )
                elif opcode == 12403 and fight_messages is not None:
                    if combat_session is not None:
                        from wakfu_server.combat_shared import Transition

                        try:
                            actor_id, actor_turn = struct.unpack(">qh", body)

                            def shared_end_turn(candidate, runtime):
                                with shared_action_incident(
                                    runtime,
                                    "end_turn",
                                    body,
                                    None,
                                    None,
                                    None,
                                    None,
                                    actor_id=actor_id,
                                    turn_id=actor_turn,
                                ) as incident:
                                    packets = runtime.end_turn(
                                        combat_session.account_id, actor_id, actor_turn
                                    )
                                    if incident is not None:
                                        incident.packets(packets)
                                    return Transition(
                                        candidate, runtime, tuple(packets)
                                    )

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                actor_id,
                                shared_end_turn,
                                incident_request=dict(opcode=12403, body=body)
                                if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                                else None,
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
                        from wakfu_server.combat_effective_control import (
                            effective_input_owner,
                        )

                        current = fight.current
                        if (
                            fight.phase == "active"
                            and current is not None
                            and effective_input_owner(fight, current) == account_id
                            and fight_messages.awaiting_ack is None
                        ):
                            recovery_body = struct.pack(">i", fight.id)
                            if combat_session is not None:
                                published = COMBAT_SESSIONS.recover_timeline(
                                    combat_session,
                                    fight.id,
                                    recovery_body,
                                    now_ms=int(time.time() * 1000),
                                )
                                refresh_shared_combat()
                                drain_shared_combat()
                                if published:
                                    checkpoint_fight()
                            else:
                                for message_id, payload in fight_messages.recover(
                                    account_id,
                                    recovery_body,
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
                        if combat_session is not None:
                            published = COMBAT_SESSIONS.recover_timeline(
                                combat_session,
                                fight.id,
                                body,
                                now_ms=int(time.time() * 1000),
                            )
                            refresh_shared_combat()
                            drain_shared_combat()
                            if published:
                                checkpoint_fight()
                        else:
                            for message_id, payload in fight_messages.recover(
                                account_id, body, now_ms=int(time.time() * 1000)
                            ):
                                send(connection, service, message_id, payload)
                        record(
                            event="combat_timeline_recovered",
                            actor_id=character["id"],
                            fight_id=fight.id,
                        )
                        if CHECKPOINT_WRITER.recover_pending(
                            fight.id,
                            account_id,
                            generation,
                            request_token=(13332, bytes(body), last_session_renewal),
                        ):
                            record(
                                event="combat_checkpoint_owned_recovery",
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
                elif opcode in (12014, 13068) and loaded:
                    from wakfu_server.captured_roster_management import (
                        manage,
                        decode_request,
                    )
                    from wakfu_server.captured_roster_selection import (
                        owned_request_character,
                    )
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    try:
                        requested_owner_id, _, _ = decode_request(opcode, body)
                        managed_record = {}
                        if combat_session is not None:
                            from wakfu_server.combat_shared import Transition

                            def shared_manage(candidate, runtime):
                                owner = owned_request_character(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    requested_owner_id,
                                    fight=candidate,
                                )
                                managed_record.update(
                                    manage(
                                        STORE,
                                        account_id,
                                        generation,
                                        owner,
                                        opcode,
                                        body,
                                        fight=candidate,
                                    )
                                )
                                return Transition(candidate, runtime, ())

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                requested_owner_id,
                                shared_manage,
                                require_turn=requested_owner_id != character["id"],
                            )
                            refresh_shared_combat()
                            checkpoint_fight()
                        else:
                            managed_record = manage(
                                STORE,
                                account_id,
                                generation,
                                character,
                                opcode,
                                body,
                                fight=fight,
                            )
                            if fight is not None:
                                checkpoint_fight()
                        if requested_owner_id == character["id"]:
                            character["captured_roster"] = managed_record
                        record(
                            event="symbiot_management",
                            actor_id=requested_owner_id,
                            opcode=opcode,
                            selected_slot=managed_record["selected_slot"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        record(
                            event="symbiot_management_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=str(error),
                        )
                elif opcode == 13571 and loaded:
                    from wakfu_server.captured_roster_selection import (
                        select,
                        request_owner,
                        owned_request_character,
                    )
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    try:
                        requested_owner_id = request_owner(body)
                        selected_record = {}
                        if combat_session is not None:
                            from wakfu_server.combat_shared import Transition

                            def shared_select(candidate, runtime):
                                owner = owned_request_character(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    requested_owner_id,
                                    fight=candidate,
                                )
                                selected_record.update(
                                    select(
                                        STORE,
                                        account_id,
                                        owner,
                                        body,
                                        fight=candidate,
                                    )
                                )
                                return Transition(candidate, runtime, ())

                            COMBAT_SESSIONS.execute(
                                combat_session,
                                fight.id,
                                requested_owner_id,
                                shared_select,
                                require_turn=requested_owner_id != character["id"],
                            )
                            refresh_shared_combat()
                            checkpoint_fight()
                        else:
                            selected_record = select(
                                STORE, account_id, character, body, fight=fight
                            )
                            if fight is not None:
                                checkpoint_fight()
                        if requested_owner_id == character["id"]:
                            character["captured_roster"] = selected_record
                        record(
                            event="symbiot_selection",
                            actor_id=requested_owner_id,
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
                    from wakfu_server.inventory_items import equipment_inventory
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.shard_identification import identify
                    from wakfu_server.shard_identification_wire import response
                    from wakfu_server.inventory_move import (
                        reload_inventory,
                        synchronization,
                    )
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None:
                            raise ValueError(
                                "No puedes identificar objetos durante un combate."
                            )
                        result = identify(
                            STORE, account_id, generation, character["id"], body
                        )
                        updated_owner = refresh_item_mutation_character(
                            result["character_id"]
                        )
                        if updated_owner["id"] == character["id"]:
                            character = updated_owner
                        send(connection, service, *synchronization(updated_owner))
                        send(connection, service, *response(result))
                        if result["status"] == 0:
                            send(
                                connection, service, *equipment_inventory(updated_owner)
                            )
                        if result["cost_kamas"] > 0 and result["status"] == 0:
                            with STORE.connection() as db:
                                balance = db.execute(
                                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                                    (account_id,),
                                ).fetchone()["kamas"]
                            send(connection, service, 12753, struct.pack(">q", balance))
                        record(
                            event="inventory_socket_identification",
                            actor_id=result["character_id"],
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
                    from wakfu_server.inventory_items import equipment_inventory
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.element_selection import select as select_elements
                    from wakfu_server.inventory_move import (
                        reload_inventory,
                        synchronization,
                    )
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None:
                            raise ValueError(
                                "No puedes seleccionar elementos durante un combate."
                            )
                        result = select_elements(
                            STORE, account_id, generation, character["id"], body
                        )
                        updated_owner = refresh_item_mutation_character(
                            result["character_id"]
                        )
                        if updated_owner["id"] == character["id"]:
                            character = updated_owner
                        send(connection, service, *synchronization(updated_owner))
                        send(connection, service, *result["packet"])
                        send(connection, service, *equipment_inventory(updated_owner))
                        if result.get("cost_kamas", 0) > 0:
                            send(
                                connection,
                                service,
                                12753,
                                struct.pack(">q", result["wallet_kamas"]),
                            )
                        record(
                            event="inventory_elements_selected",
                            actor_id=result["character_id"],
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
                    from wakfu_server.inventory_items import equipment_inventory
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
                        updated_owner = refresh_item_mutation_character(
                            result["character_id"]
                        )
                        if updated_owner["id"] == character["id"]:
                            character = updated_owner
                        response_packets = (
                            bonus_installation_packets(updated_owner["id"], result)
                            if opcode == 13269
                            else packets(updated_owner["id"], result)
                        )
                        for message_id, message_body in response_packets:
                            send(connection, service, message_id, message_body)
                        send(connection, service, *result["equipment_packet"])
                        record(
                            event="inventory_socket_enchantment_changed",
                            actor_id=updated_owner["id"],
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                    from wakfu_server.inventory_consumable_effects import use
                    from wakfu_server.inventory_move import (
                        synchronization,
                        reload_inventory,
                    )
                    from psycopg import Error as ConsumableDatabaseError
                    from psycopg_pool import PoolTimeout as ConsumablePoolTimeout

                    try:
                        result = use(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            expected_hp=character["hp"],
                            in_fight=fight is not None,
                            native_map_id=native_item_world_identity(character),
                        )
                    except (
                        ValueError,
                        ConsumableDatabaseError,
                        ConsumablePoolTimeout,
                    ) as error:
                        character = reload_inventory(STORE, account_id, character)
                        send(connection, service, *synchronization(character))
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo utilizar el consumible; inténtalo de nuevo"
                        )
                        send(
                            connection,
                            service,
                            674,
                            wire.chat(dict(character, name="Consola local"), reason),
                        )
                        record(
                            event="inventory_food_rejected",
                            actor_id=character["id"],
                            reason=reason,
                        )
                        continue
                    # The transaction is committed. Publication failures must
                    # never be mistaken for an uncommitted consumable action.
                    saved = result["character"]
                    main_owner = saved["id"] == character["id"]
                    if main_owner:
                        saved = refresh_owned_character(saved)
                        saved.update(
                            map_id=character["map_id"],
                            instance_id=character["instance_id"],
                            direction=character["direction"],
                            **position,
                        )
                    else:
                        saved = dict(saved)
                    for packet in result["packets"]:
                        send(connection, service, *packet)
                    from wakfu_server.inventory_animation import consumable_emote

                    for emote in result.get("emotes", ()):
                        action_id = next(LOCAL_WORLD_ACTIONS)
                        animation = consumable_emote(
                            actor_id=saved["id"],
                            action_id=action_id,
                            effect_uid=(1 << 48) + action_id,
                            effect_id=emote["effect_id"],
                            emote_id=emote["emote_id"],
                        )
                        if main_owner:
                            WORLD.broadcast(generation, saved["id"], *animation)
                        else:
                            send(connection, service, *animation)
                    if result.get("native_consumable"):
                        from wakfu_server.consumable_buff_wire import delta

                        for packet in delta(
                            result["previous_character"],
                            saved,
                            allocate_action=lambda: next(LOCAL_WORLD_ACTIONS),
                        ):
                            if main_owner:
                                WORLD.broadcast(generation, saved["id"], *packet)
                            else:
                                send(connection, service, *packet)
                        if main_owner:
                            publish_consumable_character(saved)
                        else:
                            from wakfu_server import hero_wire

                            send(
                                connection,
                                service,
                                *hero_wire.refresh(OWNED_HERO_TEMPLATE, saved),
                            )
                            send(connection, service, *hero_wire.statistics(saved))
                            for packet in consumable_state_packets(saved):
                                send(connection, service, *packet)
                    if main_owner:
                        character = saved
                    from wakfu_server.inventory_items import equipment_inventory

                    send(connection, service, *equipment_inventory(saved))
                    record(
                        event="inventory_food_used",
                        actor_id=saved["id"],
                        hp=saved["hp"],
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                    from wakfu_server.temporary_recycling import recycle
                    from wakfu_server.ecology_feedback import information

                    try:
                        result = recycle(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        character = (
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                        if saved["id"] == character["id"]:
                            character = (
                                active_private_session().refresh(character, saved)
                                if active_private_session() is not None
                                and active_private_session().owns(character)
                                else saved
                            )
                            saved = character
                        # The UID-only request may target a loaded owned hero.
                        # Preserve the selected main and publish the actual owner.
                        send(connection, service, *synchronization(saved))
                        send(connection, service, *equipment_inventory(saved))
                        send(connection, service, *result["packets"][-1])
                        record(
                            event="inventory_recycled",
                            actor_id=saved["id"],
                            applied=result["applied"],
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("recycling", error)),
                        )
                        record(
                            event="inventory_recycling_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                elif opcode == 13057 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server import exchange_machine
                    from wakfu_server.inventory_move import synchronization
                    from wakfu_server.inventory_items import equipment_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        request = exchange_machine.decode(body)
                        POSITIONS.flush(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        station = exchange_machine.station(character, request)
                        result = exchange_machine.purchase(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            location=character,
                            station=station,
                            blocked=environment_blocked(),
                        )
                        saved = result["character"]
                        if saved["id"] == character["id"]:
                            character = refresh_owned_character(saved)
                            saved = character
                        send(connection, service, *synchronization(saved))
                        send(connection, service, *equipment_inventory(saved))
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        record(
                            event="exchange_machine_purchased",
                            **request,
                        )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        send(
                            connection,
                            service,
                            *information(
                                str(error)
                                if isinstance(error, ValueError)
                                else "Exchange purchase is temporarily unavailable."
                            ),
                        )
                        record(
                            event="exchange_machine_purchase_rejected",
                            actor_id=character["id"],
                            reason=str(error)
                            if isinstance(error, ValueError)
                            else type(error).__name__,
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
                        if saved["id"] == character["id"]:
                            character = refresh_owned_character(saved)
                            saved = character
                        for message_id, message_body in result["packets"]:
                            send(connection, service, message_id, message_body)
                        record(event="inventory_item_destroyed", actor_id=saved["id"])
                        from wakfu_server.inventory_items import equipment_inventory

                        send(connection, service, *equipment_inventory(saved))
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
                            else saved
                        )
                        record(event="inventory_item_moved", actor_id=character["id"])
                        from wakfu_server.inventory_items import equipment_inventory

                        for owner_id in result.get(
                            "affected_characters", (character["id"],)
                        ):
                            owner = (
                                character
                                if owner_id == character["id"]
                                else STORE.character(account_id, owner_id)
                            )
                            send(connection, service, *equipment_inventory(owner))
                    except ValueError as error:
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("inventory_move", error)),
                        )
                        character = reload_inventory(STORE, account_id, character)
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        from wakfu_server import (
                            heroes,
                            hero_wire,
                            hero_private_scene,
                        )
                        from wakfu_server.inventory_items import equipment_inventory

                        with STORE.connection() as db:
                            roster = heroes.load_roster(
                                db, STORE, account_id, character["id"]
                            )
                        roster = hero_private_scene.project(
                            roster, active_private_session(), character, generation
                        )
                        for hero in roster["heroes"]:
                            send(
                                connection,
                                service,
                                *hero_wire.refresh(OWNED_HERO_TEMPLATE, hero),
                            )
                            send(connection, service, *equipment_inventory(hero))
                        record(
                            event="inventory_move_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13686 and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.travel_storage_feedback import rejection

                    try:
                        from wakfu_server import native_boats
                        from wakfu_server import transport_criteria

                        with PROFILER.span("transport.native.resolve"):
                            if native_boats.source(character, body) is not None:
                                from wakfu_server.combat_terrain import map_geometry

                                destination_route = native_boats.resolve(
                                    character,
                                    body,
                                    source_allowed=lambda actor, origin: native_boats.admit_source(
                                        STORE,
                                        account_id,
                                        generation,
                                        actor,
                                        origin,
                                        blocked=environment_blocked(),
                                    ),
                                    geometry=map_geometry,
                                    criterion_evaluator=transport_criteria.evaluator(
                                        STORE, character
                                    ),
                                )
                            else:
                                destination_route = native_transports.resolve(
                                    character,
                                    body,
                                    known_ids=known_transports(account_id),
                                    waive_criteria=ALL_ZAAPS,
                                )
                        with PROFILER.span("transport.native.commit"):
                            saved = STORE.transition_map(
                                account_id,
                                generation,
                                character["id"],
                                character,
                                destination_route["destination"],
                            )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        record(
                            event="native_transport_rejected",
                            actor_id=character["id"],
                            reason=str(error)
                            if isinstance(error, ValueError)
                            else type(error).__name__,
                        )
                        send(connection, service, *rejection("transport", error))
                    else:
                        with PROFILER.span("transport.native.publish"):
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
                            # Publish heavy dynamic entities once, after map-ready.
                            join_world(
                                generation,
                                connection,
                                character,
                                defer_scene_snapshot=character["map_id"] != 9,
                            )
                            mark_static_sync_pending()
                        record(
                            event="native_map_transition",
                            actor_id=character["id"],
                            source_id=destination_route["source_id"],
                            destination_id=destination_route["destination_id"],
                            map_id=character["map_id"],
                            position=position,
                        )
                elif opcode == 12463 and loaded:
                    from wakfu_server import nation_state, guild_wire

                    try:
                        if fight is not None:
                            raise ValueError(
                                "La inscripción requiere estar fuera de combate."
                            )
                        saved = nation_state.enroll(
                            STORE, account_id, generation, character["id"], body
                        )
                        character = (
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
                            else saved
                        )
                        character = publish_nation_character(character)
                        record(
                            event="nation_enrolled",
                            actor_id=character["id"],
                            nation_id=nation_state.nation_id(character),
                        )
                    except ValueError as error:
                        send(connection, service, *information(str(error)))
                        record(
                            event="nation_enrollment_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12223 and loaded:
                    from wakfu_server import dungeon_context, dungeon_difficulty

                    try:
                        if fight is not None:
                            raise ValueError(
                                "Dungeon difficulty cannot change during combat"
                            )
                        request = dungeon_difficulty.decode_request(body)
                        if request["character_id"] != character["id"]:
                            raise ValueError(
                                "Dungeon request targets another character"
                            )
                        chosen = dungeon_difficulty.select(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            stasis_level=request["stasis_level"],
                            expected_instance_id=request["instance_id"],
                        )
                        instance_id = chosen["instance_id"]
                        packet = dungeon_context.update_packet(
                            STORE, instance_id, fight_in_progress=False
                        )
                        maps = {
                            player["map_id"]
                            for player in WORLD.snapshot()
                            if player["instance_id"] == instance_id
                        }
                        for map_id in maps:
                            WORLD.emit_location(map_id, instance_id, *packet)
                        record(
                            event="dungeon_difficulty_selected",
                            actor_id=character["id"],
                            instance_id=instance_id,
                            stasis_level=chosen["stasis_level"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        send(connection, service, *information(str(error)))
                        record(
                            event="dungeon_difficulty_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif loaded and (opcode == 12296 or artifact_action_request):
                    from wakfu_server import generic_transports, teleporter_approach

                    generic_route = False
                    try:
                        if artifact_action_request:
                            from wakfu_server import exploration_artifact_actions

                            if environment_blocked() or environment_ticket is not None:
                                raise ValueError(
                                    "Exploration action is blocked by the current activity"
                                )
                            if not STORE.current_character_session(
                                account_id, generation, character["id"]
                            ):
                                raise ValueError("Exploration action session expired")
                            flush_positions(
                                account_id=account_id,
                                generation=generation,
                                character_id=character["id"],
                            )
                            destination_route = exploration_artifact_actions.admit(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                source_allowed=teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character.get("instance_id", 0),
                                ),
                                position_allowed=artifact_position_allowed,
                                blocked=environment_blocked(),
                            )
                            artifact_owner = dict(
                                character, **destination_route["origin"]
                            )
                            if admit_artifact_action(
                                destination_route, body, artifact_owner
                            ):
                                continue
                            generic_route = True
                        if (1 << 58) < character.get("instance_id", 0) < (1 << 59):
                            from wakfu_server import rift_exit

                            from wakfu_server.position_buffer import PositionOwnerBusy

                            try:
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
                            except PositionOwnerBusy:
                                record(
                                    event="request_position_busy",
                                    actor_id=character["id"],
                                    opcode=opcode,
                                )
                                send(
                                    connection,
                                    service,
                                    674,
                                    wire.chat(
                                        dict(character, name="Consola local"),
                                        "Guardado de posición en curso. Reintenta la acción.",
                                    ),
                                )
                                continue
                            if exited is not None:
                                deliver_rift_transition()
                                continue
                        if (
                            not artifact_action_request
                            and DUNGEON_TRANSITION_OUTBOX_AVAILABLE
                            and DUNGEON_ROOM_RUNTIME_AVAILABLE
                        ):
                            from wakfu_server import (
                                dungeon_transport,
                                dungeon_criteria,
                                dungeon_runtime,
                            )
                            from wakfu_server.combat_terrain import map_geometry

                            if is_dungeon_run(character.get("instance_id", 0)):
                                from wakfu_server import (
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
                                from wakfu_server import dungeon_native_flow

                                if (
                                    source_id
                                    in dungeon_native_flow.disabled_source_ids(
                                        dungeon_config["topology"],
                                        generic_transports._CATALOG,
                                    )
                                ):
                                    raise ValueError(
                                        "Native source is explicitly excluded by the local dungeon policy"
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
                                    from wakfu_server import dungeon_native_flow

                                    if dungeon_native_flow.enabled(
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
                                        if not dungeon_native_flow.exit_available(
                                            dungeon_config["topology"],
                                            physical_exit,
                                            completed=exit_progress["status"]
                                            == "completed",
                                        ):
                                            raise ValueError(
                                                "Native dungeon exit is locked"
                                            )
                                    dungeon_exit.leave(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        body,
                                        source_allowed=approach,
                                        in_fight=dungeon_member_in_fight,
                                        positions=POSITIONS,
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
                                        topology=dungeon_config["topology"],
                                        positions=POSITIONS,
                                        on_arrival=(
                                            lambda db, instance_id: dungeon_runtime.ensure_current_room(
                                                db,
                                                COMBAT_GROUPS,
                                                instance_id,
                                                map_geometry(character["map_id"]),
                                            )
                                        )
                                        if dungeon_config["topology"].get(
                                            "branch_routes"
                                        )
                                        else None,
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
                                from wakfu_server import (
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
                                        STORE,
                                        criterion,
                                        character=actor,
                                        destination_map_id=configured_entry[
                                            "route"
                                        ].start_map_id,
                                    ),
                                    source_allowed=teleporter_approach.callback(
                                        movement_state,
                                        map_id=character["map_id"],
                                        instance_id=character.get("instance_id", 0),
                                    ),
                                    resolve_destination=dungeon_runtime.entry_destination,
                                    positions=POSITIONS,
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
                        if not artifact_action_request and (
                            not verified_tutorial
                            and identity is not None
                            and generic_transports.source(character["map_id"], identity)
                            is not None
                        ):
                            from wakfu_server import seasonal_transport

                            destination_route = generic_transports.resolve(
                                character,
                                body,
                                source_allowed=teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character.get("instance_id", 0),
                                ),
                                criterion_evaluator=seasonal_transport.evaluator(
                                    STORE, character
                                ),
                                allow_item_payment=True,
                            )
                            generic_route = True
                        elif not artifact_action_request:
                            destination_route = transports.resolve(character, body)
                        if artifact_action_request:
                            saved = exploration_artifact_actions.transition(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                                expected_plan=destination_route,
                                source_allowed=teleporter_approach.callback(
                                    movement_state,
                                    map_id=character["map_id"],
                                    instance_id=character.get("instance_id", 0),
                                ),
                                position_allowed=artifact_position_allowed,
                                blocked=environment_blocked(),
                            )
                        elif destination_route.get("item_payment") is not None:
                            from wakfu_server import seasonal_transport

                            saved = seasonal_transport.transition(
                                STORE,
                                account_id,
                                generation,
                                character,
                                destination_route,
                            )
                        else:
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
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(
                                artifact_failure_message(error)
                                if artifact_action_request
                                else failure_message("transport", error)
                            ),
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
                        publish_public_transport(
                            destination_route, saved, generic_route=generic_route
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                        if index == previous_mount_character["active_build_index"]:
                            send(
                                connection,
                                service,
                                *builds.selection_message(character),
                            )
                            publish_mount_equipment(previous_mount_character, character)
                            from wakfu_server.combat_lifecycle import (
                                outside_progression,
                            )

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
                            active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                    try:
                        request_id, index, blobs = builds.decode(body)
                        if request_id <= 0:
                            raise ValueError("Invalid build character identity")
                        if not builds.valid_index(index):
                            raise ValueError("Invalid build index")
                    except (ValueError, UnicodeError) as error:
                        # A stale hero editor must not terminate the world session.
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("build_save", error)),
                        )
                        record(
                            event="build_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(connection, service, *builds.capacity_message(character))
                        messages = (
                            [
                                (
                                    12284,
                                    builds.rejection_response(
                                        character,
                                        character["active_build_index"],
                                        status=2,
                                    ),
                                )
                            ]
                            if fight is not None
                            else builds.rejection_messages(
                                character,
                                character["active_build_index"],
                                wp=COMBAT_TEST_WP,
                                status=2,
                            )
                        )
                        for message_id, message_body in messages:
                            send(connection, service, message_id, message_body)
                        continue
                    build_character = character
                    try:
                        build_character = STORE.character(account_id, request_id)
                        previous_build_character = build_character
                        if (
                            fight is not None
                            and index == build_character["active_build_index"]
                        ):
                            raise builds.BuildOccupationError(
                                "Active build cannot be saved during combat"
                            )
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
                        build_character = saved
                        if request_id == character["id"]:
                            character = (
                                active_private_session().refresh(character, saved)
                                if active_private_session() is not None
                                and active_private_session().owns(character)
                                else saved
                            )
                            build_character = character
                    except (ValueError, UnicodeError) as error:
                        reason = str(error)
                        status = builds.rejection_status(error)
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("build_save", error)),
                        )
                        saved = STORE.character(account_id, build_character["id"])
                        build_character = saved
                        if request_id == character["id"]:
                            character = (
                                active_private_session().refresh(character, saved)
                                if active_private_session() is not None
                                and active_private_session().owns(character)
                                else saved
                            )
                            build_character = character
                        send(
                            connection,
                            service,
                            *builds.capacity_message(build_character),
                        )
                        messages = (
                            builds.rejection_messages(
                                build_character, index, wp=COMBAT_TEST_WP, status=status
                            )
                            if request_id == character["id"] and fight is None
                            else [
                                (
                                    12284,
                                    builds.rejection_response(
                                        build_character, index, status=status
                                    ),
                                )
                            ]
                        )
                        for message_id, message_body in messages:
                            send(connection, service, message_id, message_body)
                        record(
                            event="build_rejected",
                            actor_id=request_id,
                            build_index=index,
                            reason=str(error),
                        )
                    else:
                        if previous_build_character.get(
                            "inventory_items"
                        ) != build_character.get("inventory_items"):
                            from wakfu_server.inventory_move import synchronization
                            from wakfu_server.inventory_items import equipment_inventory

                            send(connection, service, *synchronization(build_character))
                            send(
                                connection,
                                service,
                                *equipment_inventory(build_character),
                            )
                        send(
                            connection,
                            service,
                            *builds.capacity_message(build_character),
                        )
                        if index != build_character["active_build_index"]:
                            # cER acknowledges all sheet fields without replacing
                            # the live actor's combat resources or selected gear.
                            messages = [
                                (12284, builds.response(build_character, index))
                            ]
                        elif request_id == character["id"]:
                            messages = builds.response_messages(
                                build_character, index, wp=COMBAT_TEST_WP
                            )
                        else:
                            from wakfu_server import hero_wire

                            messages = [
                                (12284, builds.response(build_character, index)),
                                hero_wire.refresh(OWNED_HERO_TEMPLATE, build_character),
                                hero_wire.statistics(build_character),
                            ]
                        for message_id, message_body in messages:
                            send(connection, service, message_id, message_body)
                        if index == build_character["active_build_index"]:
                            publish_mount_equipment(
                                previous_build_character, build_character
                            )
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
                    if character["map_id"] == 9 or ranch_session is not None:
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
                elif opcode in (12844, 12004, 14616, 12531, 13994) and loaded:
                    from wakfu_server.ecology_feedback import information
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    try:
                        if guild_chest_session is None:
                            raise ValueError("No active guild chest")
                        result, packets = guild_chest_session.handle(
                            opcode,
                            body,
                            character,
                            world_static.objects(character["map_id"]),
                            blocked=fight is not None
                            or spectator_session is not None
                            or bag_session is not None,
                        )
                        if "character" in result:
                            updated = result["character"]
                            for key in (
                                "inventory_items",
                                "inventory_containers",
                                "kamas",
                            ):
                                if key in updated:
                                    character[key] = updated[key]
                            from wakfu_server.inventory_move import synchronization

                            send(connection, service, *synchronization(updated))
                            send(connection, service, *rich_inventory_packet(updated))
                            send(
                                connection,
                                service,
                                12753,
                                wire.account_kamas_update(updated["kamas"]),
                            )
                        for packet in packets:
                            send(connection, service, *packet)
                        record(
                            event="guild_chest_request",
                            actor_id=character["id"],
                            opcode=opcode,
                            applied=result.get("applied", False),
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        if guild_chest_session is not None:
                            guild_chest_session.close(clear=True)
                        guild_chest_session = None
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Guild chest is temporarily unavailable."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="guild_chest_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                elif opcode in (12038, 12529, 12551, 13050) and loaded:
                    from wakfu_server.haven_chest import transfer as transfer_chest
                    from wakfu_server.haven_chest_wire import (
                        action_result as chest_action_result,
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
                            ranch_session=ranch_session,
                        )
                        character = active_private_session().refresh(
                            character, result["character"]
                        )
                        # 318/ciH replaces existing bmM slots (including empty
                        # cells) and refreshes cYz; rich state uses item_proto.
                        # BAGS + registry reconcile the client's pending move
                        # from authoritative state without entity rebuilds.
                        for owner in result.get("inventory_characters", (character,)):
                            for packet in (
                                sync_chest_inventory(owner),
                                chest_registry(owner),
                            ):
                                send(connection, service, *packet)
                        for packet in (
                            chest_bootstrap(result["chest"]),
                            chest_action_result(),
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
                        send(connection, service, *chest_action_result(rejected=True))
                        from wakfu_server.ecology_feedback import information

                        send(connection, service, *information(str(error)))
                        if chest_opening is not None:
                            from wakfu_server.haven_chest import load as load_chest

                            current_chest = load_chest(
                                STORE, account_id, generation, character["id"]
                            )
                            from wakfu_server import heroes

                            with STORE.connection() as db:
                                roster = heroes.load_roster(
                                    db, STORE, account_id, character["id"]
                                )
                            for owner in (character, *roster["heroes"]):
                                for packet in (
                                    sync_chest_inventory(owner),
                                    chest_registry(owner),
                                ):
                                    send(connection, service, *packet)
                            send(connection, service, *chest_bootstrap(current_chest))
                elif opcode == 12686 and loaded:
                    from wakfu_server import dungeon_stele
                    from wakfu_server.ecology_feedback import information

                    try:
                        if (
                            fight is not None
                            or spectator_session is not None
                            or bag_session is not None
                        ):
                            raise ValueError(
                                "Stele selection is unavailable during combat or a bag visit"
                            )
                        packets = dungeon_stele.activate(
                            STORE, account_id, generation, character["id"], body
                        )
                        character = STORE.character(account_id, character["id"])
                        for packet in packets:
                            send(connection, service, *packet)
                    except ValueError as error:
                        record(
                            event="dungeon_stele_selection_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(connection, service, *information(str(error)))
                elif loaded and (
                    opcode in (12380, 13982)
                    or (
                        opcode == 12870
                        and len(body) == 12
                        and (
                            struct.unpack_from(">q", body)[0] == 36028
                            or (
                                ranch_session is not None
                                and struct.unpack_from(">H", body, 8)[0] == 18
                            )
                        )
                    )
                ):
                    from wakfu_server.haven_ranch import (
                        RanchSession,
                        leave_messages as ranch_leave_messages,
                    )
                    from wakfu_server.haven_ranch_authority import (
                        portal_target,
                        biome_target,
                        validate_return,
                    )
                    from wakfu_server.combat_terrain import map_geometry
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None or spectator_session is not None:
                            raise ValueError(
                                "Ranch travel is unavailable during combat"
                            )
                        if opcode == 13982 or (
                            opcode == 12870
                            and struct.unpack_from(">H", body, 8)[0] == 18
                        ):
                            if opcode == 13982:
                                validate_return(
                                    character,
                                    ranch_session,
                                    body,
                                    validate_lease=validate_ranch_lease,
                                )
                            else:
                                from wakfu_server.haven_ranch_portal import (
                                    validate_exit,
                                )

                                validate_exit(
                                    character,
                                    ranch_session,
                                    body,
                                    validate_lease=validate_ranch_lease,
                                )
                            cancel_private_scene_activity()
                            character = ranch_session.leave(character)
                            ranch_session = None
                            packets = ranch_leave_messages(
                                fixture(13974), character, bag_session
                            )
                        else:
                            if opcode == 12870:
                                if ranch_session is not None:
                                    raise ValueError(
                                        "Nested ranch entry is unavailable"
                                    )
                                target = portal_target(
                                    character,
                                    bag_session,
                                    body,
                                    validate_lease=validate_ranch_lease,
                                    validate_entitlement=validate_ranch_entitlement,
                                    geometry=map_geometry(9),
                                )
                                child = RanchSession(
                                    bag_session,
                                    character,
                                    target,
                                    lease=generation,
                                    now_ms=int(time.time() * 1000),
                                )
                            else:
                                target = biome_target(
                                    character,
                                    ranch_session,
                                    body,
                                    validate_lease=validate_ranch_lease,
                                    validate_entitlement=validate_ranch_entitlement,
                                )
                                child = RanchSession(
                                    bag_session,
                                    ranch_session.return_point,
                                    target,
                                    lease=generation,
                                    now_ms=int(time.time() * 1000),
                                )
                            cancel_private_scene_activity()
                            clear_bag_role = ranch_session is None
                            ranch_session = child
                            character = dict(child.inside)
                            packets = child.entry_messages(
                                fixture(13974),
                                character,
                                clear_bag_role=clear_bag_role,
                            )
                            if character["map_id"] == 1440:
                                from wakfu_server.haven_ranch_furniture import (
                                    snapshot as ranch_furniture_snapshot,
                                )

                                initial_ranch = ranch_furniture_snapshot(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    session=child,
                                    now_ms=int(time.time() * 1000),
                                )
                                # Native scene geometry is built during map transition.
                                packets = [
                                    initial_ranch["packet"]
                                    if packet[0] == 13864
                                    else packet
                                    for packet in packets
                                ]
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        for packet in packets:
                            send(connection, service, *packet)
                        join_world(
                            generation,
                            connection,
                            character,
                            hydrate_heroes=ranch_session is None,
                        )
                        if ranch_session is None:
                            from wakfu_server.haven_bag import own_bag
                            from wakfu_server.haven_bag_furniture_world import (
                                packets as bag_furniture_packets,
                            )

                            render_owner = {
                                **bag_session.owner,
                                "haven_bag": character["haven_bag"],
                            }
                            from copy import deepcopy

                            layout_owner = deepcopy(render_owner)
                            layout_owner["haven_bag"]["furniture"] = []
                            send(connection, service, 12187, own_bag(layout_owner))
                            for packet in bag_furniture_packets(render_owner):
                                send(connection, service, *packet)
                        mark_static_sync_pending()
                    except ValueError as error:
                        send(connection, service, *information(str(error)))
                        record(
                            event="ranch_travel_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif (
                    loaded
                    and ranch_session is not None
                    and opcode == 12870
                    and (
                        len(body) == 12
                        and struct.unpack_from(">q", body)[0] in (36068, 36069)
                    )
                ):
                    from wakfu_server.haven_ranch_bridges import (
                        activate as activate_ranch_bridge,
                    )
                    from wakfu_server.inventory_move import synchronization
                    from wakfu_server.inventory_items import equipment_inventory
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None or spectator_session is not None:
                            raise ValueError(
                                "Ranch bridges are unavailable during combat"
                            )
                        result = activate_ranch_bridge(
                            STORE,
                            account_id,
                            generation,
                            character,
                            body,
                            session=ranch_session,
                        )
                        character = ranch_session.refresh(
                            character, result["character"]
                        )
                        for packet in result.get("private_packets", []):
                            send(connection, service, *packet)
                        for packet in (
                            synchronization(character),
                            equipment_inventory(character),
                        ):
                            send(connection, service, *packet)
                        for packet in result["scene_packets"]:
                            WORLD.emit_location(
                                character["map_id"], character["instance_id"], *packet
                            )
                        record(
                            event="haven_ranch_bridge_activated",
                            actor_id=character["id"],
                            applied=result["applied"],
                        )
                    except ValueError as error:
                        record(
                            event="haven_ranch_bridge_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        send(connection, service, *information(str(error)))
                elif loaded and opcode in (12068, 12320):
                    from wakfu_server import ranch_reward_retrieval
                    from wakfu_server.ecology_feedback import information

                    try:
                        if (
                            fight is not None
                            or combat_session is not None
                            or spectator_session is not None
                        ):
                            raise ValueError(
                                "Ranch rewards are unavailable during combat"
                            )
                        cancel_crafting()
                        result = ranch_reward_retrieval.retrieve(
                            STORE,
                            account_id,
                            generation,
                            character,
                            opcode,
                            body,
                            session=ranch_session,
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Ranch rewards unavailable; retry"
                        )
                        send(connection, service, *information(reason))
                        record(
                            event="haven_ranch_rewards_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=reason,
                        )
                    else:
                        if result["recipient_character_id"] == character["id"]:
                            character = refresh_owned_character(result["character"])
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        from wakfu_server.haven_ranch_building_knowledge import (
                            scene_packet,
                        )

                        WORLD.emit_location(
                            character["map_id"],
                            character["instance_id"],
                            *scene_packet(
                                STORE, account_id, biome_id=ranch_session.biome_id
                            ),
                        )
                        record(
                            event="haven_ranch_rewards_retrieved",
                            actor_id=character["id"],
                            recipient_character_id=result["recipient_character_id"],
                            opcode=opcode,
                            applied=result["applied"],
                            reward_uids=result["reward_uids"],
                        )
                elif loaded and opcode in (13541, 12617, 13017, 13961):
                    from wakfu_server import haven_ranch_herd
                    from wakfu_server.ecology_feedback import information

                    try:
                        if (
                            fight is not None
                            or combat_session is not None
                            or spectator_session is not None
                        ):
                            raise ValueError(
                                "Ranch creatures are unavailable during combat"
                            )
                        cancel_crafting()
                        if opcode == 13017:
                            result = haven_ranch_herd.rename(
                                STORE,
                                account_id,
                                generation,
                                character["id"],
                                body,
                            )
                        elif opcode == 13961:
                            result = haven_ranch_herd.release(
                                STORE,
                                account_id,
                                generation,
                                character,
                                body,
                                session=ranch_session,
                            )
                        elif opcode == 13541:
                            result = haven_ranch_herd.deploy(
                                STORE,
                                account_id,
                                generation,
                                character,
                                body,
                                session=ranch_session,
                                geometry=map_geometry(1440),
                            )
                        else:
                            result = haven_ranch_herd.repack(
                                STORE,
                                account_id,
                                generation,
                                character,
                                body,
                                session=ranch_session,
                            )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        if opcode == 13541:
                            send(
                                connection,
                                service,
                                12391,
                                struct.pack(">qB", 1440, False),
                            )
                        elif opcode == 12617:
                            send(
                                connection, service, 12657, struct.pack(">qh", 1440, 99)
                            )
                        reason = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "Ranch creature operation failed; retry"
                        )
                        send(connection, service, *information(reason))
                        record(
                            event="haven_ranch_creature_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=reason,
                        )
                    else:
                        # Native deltas update the current account's fxS library;
                        # visitors receive only the actual host-tagged scene model.
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        scope = (
                            result.get("scene_scope")
                            if opcode in (13017, 13961)
                            else (character["map_id"], character["instance_id"])
                        )
                        if scope is not None:
                            from wakfu_server.haven_ranch_building_knowledge import (
                                scene_packet,
                            )

                            packet = scene_packet(STORE, account_id, biome_id=1)
                            WORLD.emit_location(*scope, *packet)
                            WORLD.request_ranch_scene_refresh(
                                *scope,
                                exclude_generation=None
                                if result.get("refresh_scene")
                                else generation,
                            )
                        record(
                            event="haven_ranch_creature_changed",
                            actor_id=character["id"],
                            opcode=opcode,
                            applied=result.get("applied", True),
                        )
                elif (
                    loaded
                    and ranch_session is not None
                    and opcode in (12671, 12662, 13480)
                ):
                    from wakfu_server import (
                        haven_ranch_buildings,
                        haven_ranch_building_wire,
                    )
                    from wakfu_server.ecology_feedback import information

                    rejected_uid = None
                    if opcode == 12662 and len(body) >= 8:
                        rejected_uid = struct.unpack_from(">q", body)[0]
                        if rejected_uid <= 0:
                            rejected_uid = None
                    try:
                        if (
                            fight is not None
                            or combat_session is not None
                            or spectator_session is not None
                        ):
                            raise ValueError(
                                "Ranch buildings are unavailable during combat"
                            )
                        cancel_crafting()
                        result = haven_ranch_buildings.operate(
                            STORE,
                            account_id,
                            generation,
                            character,
                            opcode,
                            body,
                            session=ranch_session,
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        if opcode != 12662 or rejected_uid is not None:
                            send(
                                connection,
                                service,
                                *haven_ranch_building_wire.rejected(
                                    opcode,
                                    character["map_id"],
                                    uid=rejected_uid,
                                ),
                            )
                        send(
                            connection,
                            service,
                            *information(
                                str(error)
                                if isinstance(error, ValueError)
                                else "Ranch buildings are temporarily unavailable."
                            ),
                        )
                        record(
                            event="haven_ranch_building_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                    else:
                        for packet in result["packets"]:
                            WORLD.emit_location(
                                character["map_id"], character["instance_id"], *packet
                            )
                        if result["changed"]:
                            from wakfu_server import haven_ranch_building_knowledge

                            send(
                                connection,
                                service,
                                *haven_ranch_building_knowledge.packet(
                                    STORE, account_id
                                ),
                            )
                            WORLD.emit_location(
                                character["map_id"],
                                character["instance_id"],
                                *haven_ranch_building_knowledge.scene_packet(
                                    STORE, account_id, biome_id=1
                                ),
                            )
                        record(
                            event="haven_ranch_building_changed",
                            actor_id=character["id"],
                            opcode=opcode,
                            changed=result["changed"],
                        )
                elif (
                    loaded
                    and ranch_session is not None
                    and (
                        opcode == 12766
                        or opcode == 12363
                        or (
                            opcode == 12870
                            and len(body) == 12
                            and struct.unpack_from(">H", body, 8)[0] in (23, 29)
                        )
                    )
                ):
                    from wakfu_server import haven_ranch_furniture
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None or spectator_session is not None:
                            raise ValueError(
                                "Ranch furniture is unavailable during combat"
                            )
                        cancel_crafting()
                        if opcode == 12766:
                            result = haven_ranch_furniture.deploy(
                                STORE,
                                account_id,
                                generation,
                                character,
                                body,
                                session=ranch_session,
                                geometry=map_geometry(1440),
                            )
                        else:
                            result = haven_ranch_furniture.edit(
                                STORE,
                                account_id,
                                generation,
                                character,
                                opcode,
                                body,
                                session=ranch_session,
                                geometry=map_geometry(1440),
                            )
                        for packet in result["packets"]:
                            WORLD.emit_location(
                                character["map_id"], character["instance_id"], *packet
                            )
                        record(
                            event="haven_ranch_furniture_changed",
                            actor_id=character["id"],
                            opcode=opcode,
                        )
                    except ValueError as error:
                        record(
                            event="haven_ranch_furniture_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=str(error),
                        )
                        send(connection, service, *information(str(error)))
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
                            if spectator_session is not None or bag_session is not None:
                                raise ValueError(
                                    "A fight or inventory session blocks rift admission"
                                )
                            if fight is not None or combat_session is not None:
                                if not native_exterior_rift_request():
                                    raise ValueError(
                                        "A live fight blocks native rift admission"
                                    )
                            entered = rift_transition_delivery.enter(
                                STORE,
                                POSITIONS,
                                account_id,
                                generation,
                                character["id"],
                                character["map_id"],
                                body,
                                world=WORLD,
                                combat_registry=COMBAT_SESSIONS.registry,
                                groups=COMBAT_GROUPS,
                                checkpoint_writer=CHECKPOINT_WRITER,
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
                            from wakfu_server.ecology_feedback import information
                            from wakfu_server.player_action_feedback import (
                                failure_message,
                            )

                            send(
                                connection,
                                service,
                                *information(failure_message("rift_entry", error)),
                            )
                            continue
                    if opcode == 12870 and len(body) == 12:
                        target_id, target_action, target_parameter = struct.unpack(
                            ">qHH", body
                        )
                        if target_action in (12, 13) and any(
                            row["id"] == target_id and row["type"] == "Stele"
                            for row in world_static.objects(character["map_id"])
                        ):
                            from wakfu_server import dungeon_stele
                            from wakfu_server.ecology_feedback import information

                            try:
                                if target_parameter != 0:
                                    raise ValueError(
                                        "Invalid stele interaction parameter"
                                    )
                                if (
                                    fight is not None
                                    or spectator_session is not None
                                    or bag_session is not None
                                ):
                                    raise ValueError(
                                        "Stele interaction is unavailable during combat or a bag visit"
                                    )
                                if (
                                    dungeon_stele.definition(
                                        STORE, character["map_id"], target_id
                                    )
                                    is None
                                ):
                                    raise ValueError("Unknown native stele placement")
                                if target_action == 12:
                                    cancel_environment()
                                    cancel_crafting()
                                    packets = dungeon_stele.browse(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        target_id,
                                    )
                                else:
                                    packets = dungeon_stele.close(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        target_id,
                                    )
                                for packet in packets:
                                    send(connection, service, *packet)
                            except ValueError as error:
                                record(
                                    event="dungeon_stele_interaction_rejected",
                                    actor_id=character["id"],
                                    reason=str(error),
                                )
                                if target_action == 12:
                                    send(
                                        connection,
                                        service,
                                        *dungeon_stele.cancel_packet(character["id"]),
                                    )
                                send(connection, service, *information(str(error)))
                            continue
                        target = next(
                            (
                                row
                                for row in world_static.objects(character["map_id"])
                                if row["id"] == target_id
                                and row["type"] == "GuildStorageBox"
                            ),
                            None,
                        )
                        if target is not None and target_action in (12, 13):
                            if guild_chest_session is not None:
                                guild_chest_session.close()
                            guild_chest_session = None
                            if target_action == 12:
                                from wakfu_server.guild_chest_dispatch import (
                                    GuildChestSession,
                                )
                                from wakfu_server.ecology_feedback import information
                                from psycopg import Error as DatabaseError
                                from psycopg_pool import PoolTimeout

                                try:
                                    guild_chest_session = GuildChestSession(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        body,
                                        world_static.objects(character["map_id"]),
                                        blocked=fight is not None
                                        or spectator_session is not None
                                        or bag_session is not None,
                                        world=WORLD,
                                        objects_for=world_static.objects,
                                        blocked_now=lambda: fight is not None
                                        or spectator_session is not None
                                        or bag_session is not None,
                                    )
                                    cancel_crafting()
                                    for packet in guild_chest_session.publish_current():
                                        send(connection, service, *packet)
                                    record(
                                        event="guild_chest_opened",
                                        actor_id=character["id"],
                                        object_id=target_id,
                                        guild_id=guild_chest_session.guild_id,
                                    )
                                except (
                                    ValueError,
                                    DatabaseError,
                                    PoolTimeout,
                                ) as error:
                                    guild_chest_session = None
                                    text = (
                                        str(error)
                                        if isinstance(error, ValueError)
                                        else "Guild chest is temporarily unavailable."
                                    )
                                    send(connection, service, *information(text))
                                    record(
                                        event="guild_chest_open_rejected",
                                        actor_id=character["id"],
                                        reason=type(error).__name__,
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
                            close_packet as chest_close_packet,
                        )

                        from psycopg import Error as DatabaseError
                        from psycopg_pool import PoolTimeout
                        from wakfu_server.travel_storage_feedback import rejection

                        chest_opening = None
                        try:
                            with PROFILER.span("storage.chest.open.validate"):
                                identity = validate_chest_open(
                                    character,
                                    bag_session,
                                    body,
                                    world_static.objects(character["map_id"]),
                                    fight_active=fight is not None
                                    or spectator_session is not None,
                                    ranch_session=ranch_session,
                                )
                            cancel_crafting()
                            with PROFILER.span("storage.chest.open.load"):
                                current_chest = load_chest(
                                    STORE, account_id, generation, character["id"]
                                )
                            with PROFILER.span("storage.chest.open.publish"):
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
                        except (ValueError, DatabaseError, PoolTimeout) as error:
                            chest_opening = None
                            record(
                                event="account_chest_open_rejected",
                                actor_id=character["id"],
                                reason=str(error)
                                if isinstance(error, ValueError)
                                else type(error).__name__,
                            )
                            send(
                                connection,
                                service,
                                *chest_close_packet(character["id"]),
                            )
                            send(connection, service, *rejection("chest_open", error))
                        continue
                    if opcode == 12870 and len(body) == 12:
                        stool_id, stool_action, stool_parameter = struct.unpack(
                            ">qHH", body
                        )
                        stool = next(
                            (
                                row
                                for row in world_static.objects(character["map_id"])
                                if row["id"] == stool_id and row["type"] == "Stool"
                            ),
                            None,
                        )
                        if stool is not None:
                            try:
                                from wakfu_server import (
                                    environment_seats,
                                    environment_seat_animations,
                                )

                                # This proximity limit is server policy, not bDV.am geometry.
                                in_range = (
                                    abs(character["x"] - stool["x"])
                                    + abs(character["y"] - stool["y"])
                                    <= 4
                                    and abs(character["z"] - stool["z"]) <= 1
                                )
                                result = environment_seats.sit(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    body,
                                    in_range=in_range,
                                    animation_verified=environment_seat_animations.supported(
                                        character, ordinary_actor=True
                                    ),
                                    blocked=environment_blocked(allow_seated=True)
                                    or environment_ticket is not None,
                                )
                                environment_seat = result if stool_action == 6 else None
                                for packet in result["packets"]:
                                    send(connection, service, *packet)
                                publish_environment_scene(force=True)
                            except ValueError as error:
                                record(
                                    event="stool_interaction_rejected",
                                    actor_id=character["id"],
                                    object_id=stool_id,
                                    reason=str(error),
                                )
                            continue
                    if opcode == 12870 and len(body) == 12:
                        from wakfu_server import nation_board

                        board_id = struct.unpack_from(">q", body)[0]
                        if (
                            nation_board.definition(character["map_id"], board_id)
                            is not None
                        ):
                            try:
                                packet = nation_board.open_selection(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    body,
                                    blocked=environment_blocked(),
                                )
                                send(connection, service, *packet)
                            except ValueError as error:
                                record(
                                    event="nation_board_rejected",
                                    actor_id=character["id"],
                                    object_id=board_id,
                                    reason=str(error),
                                )
                            continue
                    if opcode == 12870 and len(body) == 12:
                        door_id = struct.unpack_from(">q", body)[0]
                        door = next(
                            (
                                row
                                for row in world_static.objects(character["map_id"])
                                if row["id"] == door_id and row["type"] == "Door"
                            ),
                            None,
                        )
                        if door is not None and not is_dungeon_run(
                            character.get("instance_id", 0)
                        ):
                            from wakfu_server import environment_doors

                            if (
                                environment_doors.definition(
                                    STORE, character["map_id"], door_id
                                )
                                is not None
                            ):
                                try:
                                    result = environment_doors.interact(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        body,
                                        blocked=environment_blocked(),
                                    )
                                    send(connection, service, *result["packet"])
                                    publish_environment_scene(force=True)
                                except ValueError as error:
                                    record(
                                        event="ordinary_door_rejected",
                                        actor_id=character["id"],
                                        object_id=door_id,
                                        reason=str(error),
                                    )
                                continue
                    if opcode == 12870 and character["map_id"] != 9:
                        try:
                            from wakfu_server import environment_interactions

                            if len(body) != 12:
                                raise ValueError(
                                    "Invalid native environment interaction length"
                                )
                            environment_id = struct.unpack_from(">q", body)[0]
                            from wakfu_server import paid_containers

                            if (
                                paid_containers.definition(
                                    STORE, character["map_id"], environment_id
                                )
                                is not None
                            ):
                                flush_positions(
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                )
                                result = paid_containers.begin(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    body,
                                    loaded=loaded,
                                    blocked=environment_blocked(allow_paid=True)
                                    or environment_ticket is not None,
                                    is_hero=environment_actor_is_hero(),
                                )
                                paid_container_ticket = result["token"]
                                character = result["character"]
                                for packet in result["packets"]:
                                    if packet[0] == 12344:
                                        WORLD.emit_location(
                                            *result["location"], *packet
                                        )
                                    else:
                                        send(connection, service, *packet)
                                publish_environment_scene(force=True)
                                record(
                                    event="paid_container_started",
                                    actor_id=character["id"],
                                    object_id=environment_id,
                                    replay=result["replay"],
                                )
                                continue
                            from wakfu_server import native_generic_rewards

                            if (
                                native_generic_rewards.definition(
                                    STORE, character["map_id"], environment_id
                                )
                                is not None
                            ):
                                flush_positions(
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                )
                                result = native_generic_rewards.claim(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    body,
                                    loaded=loaded,
                                    blocked=environment_blocked()
                                    or environment_ticket is not None,
                                )
                                character = result["character"]
                                for packet in (
                                    *result["visual_packets"],
                                    *result["packets"],
                                ):
                                    send(connection, service, *packet)
                                if result["notification_key"]:
                                    from wakfu_server.achievements.service import (
                                        acknowledge_notifications,
                                    )

                                    with STORE.connection() as notification_db:
                                        acknowledge_notifications(
                                            notification_db,
                                            character,
                                            [result["notification_key"]],
                                        )
                                record(
                                    event="native_generic_reward_claim",
                                    actor_id=character["id"],
                                    object_id=environment_id,
                                    replay=result["replay"],
                                )
                                continue
                            from wakfu_server import treasure_chests

                            if (
                                treasure_chests.definition(
                                    STORE, character["map_id"], environment_id
                                )
                                is not None
                            ):
                                flush_positions(
                                    account_id=account_id,
                                    generation=generation,
                                    character_id=character["id"],
                                )
                                previous_level = character["level"]
                                result = treasure_chests.claim(
                                    STORE,
                                    account_id,
                                    generation,
                                    character,
                                    body,
                                    loaded=loaded,
                                    blocked=environment_blocked()
                                    or environment_ticket is not None,
                                    is_hero=environment_actor_is_hero(),
                                )
                                character = result["character"]
                                for packet in result.get("visual_packets", ()):
                                    send(connection, service, *packet)
                                for packet in result["packets"]:
                                    send(connection, service, *packet)
                                if any(
                                    packet[0] == 13613 for packet in result["packets"]
                                ):
                                    from wakfu_server.combat_lifecycle import (
                                        outside_progression,
                                    )

                                    if character["level"] != previous_level:
                                        character = health_store.initialize(
                                            STORE,
                                            account_id,
                                            generation,
                                            character["id"],
                                            exploration=True,
                                        )
                                        WORLD.update(
                                            generation,
                                            character,
                                            *wire.refresh_player(
                                                PLAYER_TEMPLATE, character
                                            ),
                                        )
                                        from wakfu_server.level_publication import (
                                            refresh,
                                        )

                                        send_batch(
                                            connection,
                                            service,
                                            refresh(
                                                character,
                                                STORE.characters(account_id),
                                                entity_template=OWNED_HERO_TEMPLATE,
                                                roster_template=CHARACTERS,
                                                retained_state_packets=consumable_state_packets,
                                            ),
                                        )
                                        send_native_planting_bonus(
                                            connection, character
                                        )
                                    send(
                                        connection,
                                        service,
                                        *outside_progression(
                                            character, wp=COMBAT_TEST_WP
                                        ),
                                    )
                                    send(
                                        connection,
                                        service,
                                        *rich_inventory_packet(character),
                                    )
                                if result.get("notification_key"):
                                    from wakfu_server.achievements.service import (
                                        acknowledge_notifications,
                                    )

                                    with STORE.connection() as achievement_db:
                                        acknowledge_notifications(
                                            achievement_db,
                                            character,
                                            [result["notification_key"]],
                                        )
                                publish_environment_scene(force=True)
                                record(
                                    event="treasure_claim",
                                    actor_id=character["id"],
                                    object_id=environment_id,
                                    replay=result["replay"],
                                    content_id=result.get("receipt", {}).get(
                                        "content_id"
                                    ),
                                    native_bindings=result.get("opened", []),
                                )
                                continue
                            environment_rule = environment_interactions.definition(
                                STORE, character["map_id"], environment_id
                            )
                            if environment_rule is not None:
                                blocked = environment_blocked()
                                if environment_rule["kind"] == "well":
                                    environment_ticket = environment_interactions.begin(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        body,
                                        blocked=blocked,
                                        is_hero=environment_actor_is_hero(),
                                    )
                                    record(
                                        event="environment_well_started",
                                        actor_id=character["id"],
                                        object_id=environment_id,
                                        due_at=str(environment_ticket["due_at"]),
                                    )
                                else:
                                    result = environment_interactions.toggle(
                                        STORE,
                                        account_id,
                                        generation,
                                        character,
                                        body,
                                        blocked=blocked
                                        or environment_ticket is not None,
                                    )
                                    # Each observer publishes only its loaded native
                                    # neighborhood; other peers observe this on idle.
                                    publish_environment_scene(force=True)
                                continue
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
                        character = active_private_session().refresh(
                            character, result["character"]
                        )
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
                        from wakfu_server.ecology_feedback import information
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("furniture", error)),
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
                        character = active_private_session().refresh(
                            character, result["character"]
                        )
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
                        visit_permission_payload,
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
                        character = active_private_session().refresh(character, saved)
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
                    payload = visit_permission_payload(character["haven_bag"])
                    WORLD.emit_location(
                        9,
                        bag_session.bag_instance_id,
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
                        character = active_private_session().refresh(
                            character, result["character"]
                        )
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
                        character = active_private_session().refresh(character, saved)
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
                        active_private_session().refresh(character, saved)
                        if active_private_session() is not None
                        and active_private_session().owns(character)
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
                    if ranch_session is not None:
                        validate_ranch_lease()
                        character = ranch_session.leave(character)
                        ranch_session = None
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
                    exterior = HAVEN_BAG_EXTERIORS.discard(
                        generation,
                        bag_session.exterior_actor_id
                        if bag_session is not None
                        else character["id"],
                    )
                    if exterior is not None:
                        outside, packet = exterior
                        WORLD.emit_location(
                            outside["map_id"], outside["instance_id"], *packet
                        )
                    character = bag_session.leave(character)
                    bag_session = None
                    ranch_session = None
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
                elif opcode in (13191, 13345, 12019) and loaded:
                    from wakfu_server import companion_equipment
                    from wakfu_server.ecology_feedback import information
                    from psycopg import Error as CompanionDatabaseError
                    from psycopg_pool import PoolTimeout as CompanionPoolTimeout

                    companion_identity = None
                    try:
                        companion_identity = (
                            companion_equipment.decode_save(body)[0]
                            if opcode == 13191
                            else companion_equipment.identity_request(body)
                        )
                        handler = {
                            13191: companion_equipment.save,
                            13345: companion_equipment.retrieve_all,
                            12019: companion_equipment.unlink,
                        }[opcode]
                        handler_options = {}
                        if opcode == 13191:
                            from wakfu_server.combat_companion_owned_equipment_adapter import (
                                preflight_custody,
                            )

                            # The command's locked Store snapshot and NPC row
                            # are the only sources for this side-effect-free
                            # factory preflight. The active Ready path repeats
                            # it against the actual companion Actor and pin.
                            handler_options[
                                "native_admission"
                            ] = lambda companion, owner, entries, level: preflight_custody(
                                owner, companion, entries, level
                            )
                        result = handler(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            body,
                            in_fight=fight is not None or combat_session is not None,
                            **handler_options,
                        )
                        saved = result["character"]
                        character = dict(
                            character,
                            inventory_items=saved["inventory_items"],
                            inventory_containers=saved["inventory_containers"],
                        )
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        refresh_party(generation, character)
                        record(
                            event="companion_inventory_action",
                            actor_id=character["id"],
                            companion_id=companion_identity,
                            opcode=opcode,
                        )
                    except (
                        ValueError,
                        CompanionDatabaseError,
                        CompanionPoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo modificar el compañero"
                        )
                        if opcode in (13191, 13345) and companion_identity is not None:
                            send(
                                connection,
                                service,
                                *companion_equipment.response(
                                    companion_identity, error=True
                                ),
                            )
                        send(connection, service, *information(text))
                        record(
                            event="companion_inventory_action_rejected",
                            actor_id=character["id"],
                            companion_id=companion_identity,
                            opcode=opcode,
                            reason=text,
                        )
                elif opcode == 12555 and loaded:
                    from wakfu_server import companions
                    from wakfu_server import hero_private_scene
                    from wakfu_server.ecology_feedback import information
                    from psycopg import Error as CompanionDatabaseError
                    from psycopg_pool import PoolTimeout as CompanionPoolTimeout

                    try:
                        if fight is not None or combat_session is not None:
                            raise ValueError(
                                "Companion roster cannot change during combat"
                            )
                        hero_private_scene.authorize(
                            active_private_session(), character, generation
                        )
                        with PARTIES._guard(character["id"]):
                            with POSITIONS.account_barrier(account_id):
                                flush_positions(account_id=account_id)
                                companions.add_to_party(
                                    STORE, account_id, generation, character["id"], body
                                )
                            refresh_party(generation, character)
                        send(connection, service, *companions.added_result())
                        record(event="companion_added", actor_id=character["id"])
                    except (
                        ValueError,
                        CompanionDatabaseError,
                        CompanionPoolTimeout,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, ValueError)
                            else "No se pudo añadir el compañero"
                        )
                        result = (
                            14
                            if "combat" in text
                            else 11
                            if "full" in text
                            else 13
                            if "Dead" in text
                            else 15
                        )
                        send(connection, service, *companions.added_result(result))
                        send(connection, service, *information(text))
                        record(
                            event="companion_add_rejected",
                            actor_id=character["id"],
                            reason=text,
                        )
                elif opcode == 12219 and loaded:
                    from wakfu_server import heroes, hero_wire
                    from wakfu_server.ecology_feedback import information

                    try:
                        if fight is not None or combat_session is not None:
                            raise ValueError("Hero roster cannot change during combat")
                        target = hero_wire.add_request(body)
                        from wakfu_server import hero_private_scene

                        hero_private_scene.authorize(
                            active_private_session(), character, generation
                        )
                        with POSITIONS.account_barrier(account_id):
                            flush_positions(account_id=account_id)
                            roster = heroes.add(
                                STORE, account_id, generation, character["id"], target
                            )
                        publish_heroes(roster)
                        send(connection, service, *hero_wire.added_success())
                        record(
                            event="hero_added", actor_id=character["id"], hero_id=target
                        )
                    except ValueError as error:
                        text = str(error)
                        result = (
                            14
                            if "combat" in text
                            else 11
                            if "full" in text
                            else 13
                            if "Dead" in text
                            else 15
                        )
                        send(connection, service, *hero_wire.added_result(result))
                        send(connection, service, *information(text))
                        record(
                            event="hero_add_rejected",
                            actor_id=character["id"],
                            reason=text,
                        )
                elif opcode == 12006 and loaded:
                    from wakfu_server import heroes, hero_wire
                    from wakfu_server.ecology_feedback import information
                    from wakfu_server.player_action_feedback import failure_message
                    from wakfu_server.position_buffer import PositionOwnerBusy

                    switch_target = None
                    try:
                        switch_target = hero_wire.switch_request(body)
                        if hero_switch_pending is not None:
                            raise ValueError("A native hero switch is already pending")
                        if fight is not None or combat_session is not None:
                            raise ValueError(
                                "Native hero switching is unavailable during combat"
                            )
                        target = switch_target
                        private_session = active_private_session()
                        if private_session is not None and not private_session.owns(
                            character
                        ):
                            raise ValueError(
                                "Hero switch requires the current private scene session"
                            )
                        if npc_dialogue_session is not None:
                            npc_dialogue_session.close()
                            npc_dialogue_session = None
                        previous_character = character
                        PLANTINGS.cancel(character["id"], generation)
                        HARVESTS.cancel(character["id"], generation=generation)
                        cancel_flora()
                        cancel_crafting()
                        if chest_opening is not None:
                            from wakfu_server.haven_chest_wire import (
                                close_packet as close_chest,
                            )

                            send(connection, service, *close_chest(character["id"]))
                        chest_opening = None
                        with POSITIONS.account_barrier(account_id):
                            flush_positions(account_id=account_id)
                            roster = heroes.switch_main(
                                STORE, account_id, generation, character["id"], target
                            )
                            previous_character_id = character["id"]
                            WORLD.leave(previous_character_id, generation)
                            character = roster["leader"]
                            POSITIONS.attach(account_id, generation, character)
                            if private_session is not None:
                                character = private_session.rebind(
                                    previous_character, character
                                )
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        # cwE must hand off the native master before the full
                        # owned component refresh. An open class dialog still
                        # resolves the old master until its csF completion.
                        hero_switch_pending = character["id"]
                        send(
                            connection,
                            service,
                            *hero_wire.switched_result(character["id"]),
                        )
                        record(
                            event="hero_main_switch_pending",
                            actor_id=character["id"],
                            previous_id=previous_character_id,
                        )
                    except (ValueError, PositionOwnerBusy) as error:
                        if switch_target is not None:
                            send(
                                connection,
                                service,
                                *hero_wire.switched_result(
                                    switch_target,
                                    2
                                    if fight is not None or combat_session is not None
                                    else 6,
                                ),
                            )
                        send(
                            connection,
                            service,
                            *information(failure_message("hero_switch", error)),
                        )
                        record(
                            event="hero_switch_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12054 and loaded:
                    from wakfu_server import hero_wire
                    from wakfu_server.ecology_feedback import information
                    from wakfu_server.player_action_feedback import failure_message

                    try:
                        target = hero_wire.switch_request(body)
                        if hero_switch_pending is None:
                            if target != character["id"]:
                                raise ValueError(
                                    "Native hero switch completion has no pending target"
                                )
                            continue
                        if target != hero_switch_pending or target != character["id"]:
                            raise ValueError(
                                "Native hero switch completion targets another character"
                            )
                        if not STORE.current_character_session(
                            account_id, generation, target
                        ):
                            raise ValueError(
                                "Native hero switch completion belongs to a replaced session"
                            )
                        if is_dungeon_run(character.get("instance_id", 0)):
                            from wakfu_server import dungeon_context

                            # The same native scene now belongs to the new main.
                            # Publish its actual context under that actor's scope
                            # before later combat admission consumes the receipt.
                            with STORE.connection() as db:
                                fighting = db.execute(
                                    "SELECT EXISTS(SELECT 1 FROM combat_fights f "
                                    "JOIN dungeon_room_encounters e ON e.fight_id=f.id "
                                    "WHERE e.instance_id=%s AND e.status='active' "
                                    "AND f.status IN ('placement','active')) AS fighting",
                                    (character["instance_id"],),
                                ).fetchone()["fighting"]
                            send(
                                connection,
                                service,
                                *dungeon_context.update_packet(
                                    STORE,
                                    character["instance_id"],
                                    fight_in_progress=fighting,
                                ),
                            )
                        send(
                            connection,
                            service,
                            *hero_wire.refresh(OWNED_HERO_TEMPLATE, character),
                        )
                        send(connection, service, *hero_wire.statistics(character))
                        # The native post-swap cinematic waits for the selected
                        # actor's format22 GUILD_LOCAL_INFO consumer, even when
                        # the character has no guild. Format10 lacks this section.
                        send(
                            connection,
                            service,
                            15548,
                            wire.adapt(15548, fixture(15548), account_id, character),
                        )
                        from wakfu_server.private_scene_heroes import (
                            messages as private_hero_messages,
                        )

                        for packet in private_hero_messages(
                            active_private_session(), character, generation=generation
                        ):
                            send(connection, service, *packet)
                        join_world(
                            generation, connection, character, hydrate_heroes=False
                        )
                        send(connection, service, *rich_inventory_packet(character))
                        from wakfu_server.inventory_move import synchronization

                        send(connection, service, *synchronization(character))
                        hero_switch_pending = None
                        publish_custom_task_cards()
                        record(event="hero_main_switched", actor_id=character["id"])
                    except ValueError as error:
                        send(
                            connection,
                            service,
                            *information(failure_message("hero_switch", error)),
                        )
                        record(
                            event="hero_switch_completion_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    else:
                        deliver_custom_task_rewards()
                elif opcode == 13498 and loaded:
                    from wakfu_server.emotes import prepare_play

                    def visible_emote_target(actor_id):
                        identity = WORLD.live_identity(character_id=actor_id)
                        return None if identity is None else identity[1]

                    try:
                        emote = prepare_play(
                            STORE,
                            account_id,
                            generation,
                            character,
                            body,
                            resolve_target=visible_emote_target,
                            in_fight=lambda actor_id: (
                                actor_id == character["id"]
                                and (fight is not None or combat_session is not None)
                            )
                            or COMBAT_SESSIONS.lookup_character(actor_id) is not None,
                            occupied=lambda actor_id: actor_id in HARVESTS.pending
                            or actor_id in PLANTINGS.pending,
                        )
                        character["_emote_packet"] = emote["packet"]
                        character["_emote_until"] = (
                            float("inf")
                            if emote["duration_ms"] < 0
                            else time.monotonic() + emote["duration_ms"] / 1000
                        )
                        WORLD.update(generation, character, *emote["packet"])
                    except ValueError as error:
                        from wakfu_server.emotes import (
                            packet as emote_account_packet,
                        )

                        record(
                            event="emote_play_rejected",
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
                        send(
                            connection,
                            service,
                            *emote_account_packet(STORE, account_id),
                        )
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
                        from wakfu_server import native_boat_arrivals
                        from wakfu_server.combat_terrain import map_geometry

                        native_boat_arrivals.validate_movement(
                            character, movement, geometry=map_geometry
                        )
                        if ranch_session is not None and ranch_session.owns(character):
                            from wakfu_server.haven_ranch_bridges import blocked_cells

                            with STORE.connection() as bridge_db:
                                bridge_blockers = blocked_cells(
                                    bridge_db, character["instance_id"]
                                )
                            start_cell = movement_state.key(movement["start_position"])
                            if any(
                                (x, y) in bridge_blockers
                                for x, y, _ in approved - {start_cell}
                            ):
                                raise ValueError(
                                    "Build the Ranch bridge before crossing"
                                )
                        from wakfu_server import environment_doors

                        environment_doors.validate_movement(STORE, character, movement)
                        if DUNGEON_ROOM_RUNTIME_AVAILABLE and is_dungeon_run(
                            character.get("instance_id", 0)
                        ):
                            from wakfu_server import (
                                dungeon_native_flow,
                                dungeon_runtime,
                            )

                            with STORE.connection() as movement_db:
                                (
                                    _,
                                    walking_config,
                                ) = dungeon_runtime.configuration_for_instance(
                                    movement_db, character["instance_id"]
                                )
                                if dungeon_native_flow.enabled(
                                    walking_config["topology"]
                                ):
                                    walking_progress = movement_db.execute(
                                        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                                        (character["instance_id"],),
                                    ).fetchone()
                                    dungeon_native_flow.validate_movement(
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
                    if (
                        active_private_session() is not None
                        and active_private_session().owns(character)
                    ):
                        try:
                            character = active_private_session().move(character, end)
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
                        from wakfu_server.emotes import stopped

                        character.pop("_emote_until", None)
                        WORLD.broadcast(
                            generation, character["id"], *stopped(character["id"])
                        )
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
                elif opcode == 13222 and loaded and try_native_monster_destroy(body):
                    pass
                elif opcode in (13222, 12058, 12535) and loaded:
                    from wakfu_server import npc_dialogue, npc_world

                    if not npc_dialogue.interactions_enabled():
                        if npc_dialogue_session is not None or opcode in (12058, 12535):
                            send(
                                connection,
                                service,
                                *npc_dialogue.disabled_response(npc_dialogue_session),
                            )
                        npc_dialogue_session = None
                        continue

                    from wakfu_server import npc_objective_facts
                    from wakfu_server.ecology_feedback import information
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout

                    try:
                        if fight is not None or spectator_session is not None:
                            if npc_dialogue_session is not None:
                                npc_dialogue_session.close()
                            npc_dialogue_session = None
                            raise ValueError(
                                "NPC dialogue is unavailable during combat"
                            )

                        def dialogue_rows():
                            with STORE.connection() as db:
                                return npc_world.load_scene(
                                    db, character["map_id"], character["instance_id"]
                                )

                        def dialogue_facts():
                            # Keep the current leased scene position. Reading
                            # owned objective facts must not reload SQL exterior
                            # coordinates while inside a private scene.
                            with STORE.connection() as db:
                                return npc_objective_facts.load(
                                    db, account_id, character["id"]
                                )

                        if opcode == 12058:
                            if npc_dialogue_session is None:
                                raise ValueError("No NPC conversation is active")
                            request = npc_dialogue.decode_request(opcode, body)
                            packet = npc_dialogue_session.choose(
                                request["node_id"], request["choice_id"]
                            )
                        else:
                            if opcode == 13222:
                                actor_id, action_id = npc_world.decode_interaction(body)
                            else:
                                request = npc_dialogue.decode_request(opcode, body)
                                row = next(
                                    (
                                        npc
                                        for npc in dialogue_rows()
                                        if npc_world.matches_open_request(npc, request)
                                    ),
                                    None,
                                )
                                if row is None:
                                    raise ValueError("Unavailable NPC dialogue root")
                                actor_id, action_id = (
                                    row["actor_id"],
                                    row["action_ids"][0],
                                )
                            if npc_dialogue_session is not None:
                                npc_dialogue_session.close()
                            npc_dialogue_session, packet = npc_world.begin(
                                lambda: character,
                                dialogue_rows,
                                actor_id,
                                action_id,
                                facts_provider=dialogue_facts,
                            )
                        if packet is not None:
                            send(connection, service, *packet)
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                    ) as error:
                        send(
                            connection,
                            service,
                            *information(
                                str(error)
                                if isinstance(error, ValueError)
                                else "NPC dialogue is temporarily unavailable."
                            ),
                        )
                        record(
                            event="npc_dialogue_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                elif opcode == 13397 and loaded:
                    from wakfu_server.guild_daily_quests import activate
                    from wakfu_server.ecology_feedback import information

                    try:
                        result = activate(
                            STORE, account_id, generation, character["id"], body
                        )
                        for packet in result["packets"]:
                            send(connection, service, *packet)
                        record(
                            event="guild_daily_quest_activated",
                            actor_id=character["id"],
                            definition_id=result["definition_id"],
                            applied=result["applied"],
                        )
                    except (ValueError, DatabaseError, PoolTimeout) as error:
                        send(
                            connection,
                            service,
                            *information(
                                str(error)
                                if isinstance(error, ValueError)
                                else "Guild quests are temporarily unavailable."
                            ),
                        )
                        record(
                            event="guild_daily_quest_rejected",
                            actor_id=character["id"],
                            reason=type(error).__name__,
                        )
                elif opcode in GUILD_REQUEST_OPCODES and loaded:
                    from psycopg import Error as DatabaseError
                    from psycopg_pool import PoolTimeout
                    from wakfu_server.ecology_feedback import information

                    try:
                        GUILDS.handle(
                            opcode, body, account_id, generation, character["id"]
                        )
                        GUILDS.drain_pending()
                        live = WORLD.live_identity(character_id=character["id"])
                        if live is not None and live[0] == generation:
                            for key in ("guild_native", "guild_moderation_factor"):
                                if key in live[1]:
                                    character[key] = live[1][key]
                        if opcode in (13757, 12937, 12575):
                            updated = STORE.character(account_id, character["id"])
                            for key in (
                                "inventory_items",
                                "inventory_containers",
                                "guild_native",
                                "guild_moderation_factor",
                            ):
                                if key in updated:
                                    character[key] = updated[key]
                            send(connection, service, *rich_inventory_packet(updated))
                            from wakfu_server.inventory_move import synchronization

                            send(connection, service, *synchronization(updated))
                            send(
                                connection,
                                service,
                                13021,
                                struct.pack(">q", STORE.account_kamas(account_id)),
                            )
                    except (
                        ValueError,
                        UnicodeError,
                        DatabaseError,
                        PoolTimeout,
                        NotImplementedError,
                    ) as error:
                        text = (
                            str(error)
                            if isinstance(error, (ValueError, NotImplementedError))
                            else "Guild service is temporarily unavailable."
                        )
                        send(connection, service, *information(text))
                        record(
                            event="guild_request_rejected",
                            actor_id=character["id"],
                            opcode=opcode,
                            reason=type(error).__name__,
                        )
                elif (
                    opcode in (13074, 13224, 13188, 13831, 12116, 13702, 12387)
                    and loaded
                ):
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
                    opcode
                    in (13140, 12997, 13037, 12510, 12203, 12781, 13406, 12027, 13113)
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
                        from wakfu_server.player_action_feedback import failure_message

                        send(
                            connection,
                            service,
                            *information(failure_message("exchange", error)),
                        )
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
                        owned_hero_removal = False
                        if opcode == 1074:
                            from wakfu_server import party_wire
                            from wakfu_server import heroes

                            request = party_wire.member_request(
                                body, allow_companions=True
                            )
                            if request["member_id"] < 0:
                                from wakfu_server import companions
                                from wakfu_server import hero_private_scene

                                hero_private_scene.authorize(
                                    active_private_session(), character, generation
                                )
                                with PARTIES._guard(character["id"]):
                                    with STORE.connection() as companion_db:
                                        selected = companion_db.execute(
                                            "SELECT 1 FROM account_companion_slots s "
                                            "JOIN player_party_members m ON m.character_id=s.owner_character_id "
                                            "WHERE s.account_id=%s AND s.owner_character_id=%s "
                                            "AND s.companion_id=%s AND m.party_id=%s",
                                            (
                                                account_id,
                                                character["id"],
                                                -request["member_id"],
                                                request["group_id"],
                                            ),
                                        ).fetchone()
                                    if selected is None:
                                        raise ValueError(
                                            "El compañero no pertenece a tu compañía actual"
                                        )
                                    companions.remove_from_party(
                                        STORE,
                                        account_id,
                                        generation,
                                        character["id"],
                                        -request["member_id"],
                                    )
                                    with STORE.connection() as companion_db:
                                        recipients = companion_db.execute(
                                            "SELECT character_id FROM player_party_members WHERE party_id=%s",
                                            (request["group_id"],),
                                        ).fetchall()
                                    packet = party_wire.removed(
                                        request["group_id"],
                                        [request["member_id"]],
                                        allow_companions=True,
                                    )
                                    for member in recipients:
                                        live = WORLD.live_identity(
                                            character_id=member["character_id"]
                                        )
                                        if live is not None:
                                            WORLD.send_to(
                                                member["character_id"], live[0], *packet
                                            )
                                    refresh_party(generation, character)
                                record(
                                    event="companion_removed",
                                    actor_id=character["id"],
                                    companion_id=-request["member_id"],
                                )
                                continue
                            with STORE.connection() as hero_db:
                                hero_slot = hero_db.execute(
                                    "SELECT s.character_id FROM account_hero_slots s "
                                    "JOIN player_party_members m ON m.character_id=%s "
                                    "WHERE s.account_id=%s AND s.character_id=%s AND m.party_id=%s",
                                    (
                                        character["id"],
                                        account_id,
                                        request["member_id"],
                                        request["group_id"],
                                    ),
                                ).fetchone()
                            if hero_slot is not None:
                                from wakfu_server import hero_private_scene

                                hero_private_scene.authorize(
                                    active_private_session(), character, generation
                                )
                                with PARTIES._guard(character["id"]):
                                    with STORE.connection() as hero_db:
                                        members = hero_db.execute(
                                            "SELECT character_id FROM player_party_members "
                                            "WHERE party_id=%s",
                                            (request["group_id"],),
                                        ).fetchall()
                                    if character["id"] not in {
                                        member["character_id"] for member in members
                                    }:
                                        raise ValueError("No perteneces a ese grupo.")
                                    recipients = [
                                        WORLD.live_identity(
                                            character_id=member["character_id"]
                                        )
                                        for member in members
                                    ]
                                    with POSITIONS.account_barrier(account_id):
                                        flush_positions(account_id=account_id)
                                        roster = heroes.remove(
                                            STORE,
                                            account_id,
                                            generation,
                                            character["id"],
                                            request["member_id"],
                                        )
                                    packet = party_wire.removed(
                                        request["group_id"], [request["member_id"]]
                                    )
                                    for live in recipients:
                                        if live is not None:
                                            WORLD.send_to(
                                                live[1]["id"], live[0], *packet
                                            )
                                    publish_heroes(roster)
                                record(
                                    event="hero_removed",
                                    actor_id=character["id"],
                                    hero_id=request["member_id"],
                                    party_id=request["group_id"],
                                )
                                owned_hero_removal = True
                        if not owned_hero_removal:
                            PARTIES.handle(
                                opcode, body, account_id, generation, character["id"]
                            )
                            if opcode == 1074:
                                refresh_party(generation, character)
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
                    from wakfu_server.cosmetics import (
                        OwnedCosmetics,
                        actor_update,
                    )

                    try:
                        previous_cosmetic_character = character
                        saved = STORE.equip_owned_finishers(
                            account_id, character["id"], opcode, body
                        )
                        character = (
                            dict(character, owned_cosmetics=saved["owned_cosmetics"])
                            if fight is not None
                            else active_private_session().refresh(character, saved)
                            if active_private_session() is not None
                            and active_private_session().owns(character)
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
                        # Combat keeps its actor/resource snapshots; publish appearance on return.
                        if fight is None:
                            cosmetic_opcode, cosmetic_body = actor_update(character)
                            send(connection, service, cosmetic_opcode, cosmetic_body)
                            WORLD.update(
                                generation,
                                character,
                                cosmetic_opcode,
                                cosmetic_body,
                                include_sender=False,
                            )
                            publish_mount_equipment(
                                previous_cosmetic_character, character
                            )
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
                        if delivered:
                            publish_bot_chat(
                                character, text, recipient=request["recipient"]
                            )
                        record(
                            event="private_chat",
                            actor_id=character["id"],
                            delivered=delivered,
                            characters=len(text),
                        )
                elif opcode == 12366 and loaded:
                    text = decode_body("out", opcode, body)["text"].strip()
                    local_command = text.split(None, 1)[0].lower() if text else ""
                    if local_command in ("!tasks", "!challenge", "!adventures"):
                        execute_objectives_command(text)
                        continue
                    if local_command == "!nacion":
                        from psycopg import Error as DatabaseError
                        from psycopg_pool import PoolTimeout
                        from wakfu_server import nation_state
                        from wakfu_server.ecology_feedback import information

                        try:
                            nation_state.local_selection_request(text)
                            if fight is not None:
                                raise ValueError(
                                    "La inscripción requiere estar fuera de combate."
                                )
                            now = time.monotonic()
                            if now - last_chat < CHANNELS.minimum_interval():
                                raise ValueError(
                                    "Espera un momento antes de enviar otro mensaje."
                                )
                            packet = nation_state.open_selection(
                                STORE, account_id, generation, character["id"]
                            )
                            send(connection, service, *packet)
                            last_chat = now
                        except (
                            ValueError,
                            UnicodeError,
                            DatabaseError,
                            PoolTimeout,
                        ) as error:
                            message = (
                                str(error)
                                if isinstance(error, ValueError)
                                else (
                                    "La selección de nación está temporalmente indisponible."
                                )
                            )
                            send(connection, service, *information(message))
                            record(
                                event="nation_selection_rejected",
                                actor_id=character["id"],
                                reason=type(error).__name__,
                            )
                        continue
                    if text.lower() in ("!exitdungeon", "!salirmazmorra"):
                        execute_dungeon_exit_command()
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
                        publish_bot_chat(character, text)
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
                if opcode not in (
                    13917,
                    12366,
                    13074,
                    13224,
                    13188,
                    13831,
                    12116,
                    13702,
                    12387,
                ):
                    # Chat does not mutate the fight. Its reader must not wait
                    # for a combat outbox drain or serialize a Rift checkpoint.
                    # Gameplay and terminal paths retain their durable barriers.
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
        # Stop ecology occupancy before potentially blocking combat/storage cleanup.
        if service == "world" and character is not None and generation is not None:
            WORLD.deactivate_ecology(character["id"], generation)
        publication_connection = locals().get("connection")
        if isinstance(publication_connection, Connection):
            updates = getattr(publication_connection, "objectives_updates", None)
            if updates is not None:
                updates.close()
            publication_connection.instance_publications.invalidate()
        if guild_chest_session is not None:
            guild_chest_session.close()
            guild_chest_session = None
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

        if service == "world" and (
            environment_ticket is not None
            or environment_seat is not None
            or pending_artifact_action is not None
        ):
            logout_barrier(
                "environment_occupation", lambda: cancel_environment(publish=False)
            )
        if service == "world" and flora_ticket is not None:
            logout_barrier("flora_occupation", cancel_flora)
        if (
            service == "world"
            and character is not None
            and generation is not None
            and "consume_rift_entry_combat_retirement" in locals()
        ):
            consume_rift_entry_combat_retirement()
            from wakfu_server.combat_entry_recovery import discard_entry_recovery

            discard_entry_recovery(COMBAT_SESSIONS.registry, account_id, generation)
        if service == "world" and combat_session is not None:
            from wakfu_server.combat_command_recovery import take_cancelled

            cancelled = take_cancelled(COMBAT_SESSIONS.registry, combat_session)
            if cancelled is None:
                cancelled = publication_recovery_shared
            exits = getattr(cancelled, "publication_recovery_aborted", None) or {}
            if character is not None and character["id"] in exits:
                # The health/abort transaction already committed. Never let
                # this socket's older active FSM write another checkpoint.
                fight = fight_messages = combat_session = group_lease = None
                checkpoint_id = checkpoint_revision = None
                checkpoint_terminal = True
        if service == "world":
            from wakfu_server.checkpoint_worker import checkpoint_cleanup_barrier

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
                        ),
                        deliver=False,
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
            from wakfu_server.combat_pve_withdraw import has_other_live_owner

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
                        and not has_other_live_owner(shared_entry.fight, combat_session)
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
                        from wakfu_server.ecology_admin import current_available

                        key = shared_abort.group_lease[0]
                        members = current_available(STORE, key)
                        if members:
                            from wakfu_server.combat_monster_world import spawn_group

                            WORLD.emit_location(
                                key[0],
                                key[1],
                                12608,
                                owned_scene_spawn_group(members, group_id=key[2]),
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
            from wakfu_server.consumable_world_lifecycle import synchronize

            logout_barrier(
                "consumable_clocks",
                lambda: synchronize(
                    STORE,
                    account_id,
                    generation,
                    character,
                    mode="pause",
                    in_combat=fight is not None,
                ),
            )
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
                exterior = HAVEN_BAG_EXTERIORS.discard(
                    generation,
                    bag_session.exterior_actor_id
                    if bag_session is not None
                    else character["id"],
                )
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


def refresh_regional_bonuses():
    """Inline-mode producer; SQL preparation never holds gameplay locks."""
    from wakfu_server.territory_bonus_updates import prepare

    epoch = uuid.uuid4().hex
    tick = 0
    while not STOPPING.wait(1):
        tick += 1
        try:
            snapshot = dict(
                world_epoch=epoch, players=WORLD.ecology_snapshot(), planning_tick=tick
            )
            for proposal in prepare(STORE, snapshot):
                REGIONAL_BONUSES.apply(proposal, world_epoch=epoch)
        except Exception as error:
            record(event="regional_bonus_prepare_retry", reason=type(error).__name__)


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
    from contextlib import contextmanager, ExitStack

    @contextmanager
    def coordination(_stage, _map_id, _instance_id):
        # Keep each mutation/publication fenced against claims and harvests,
        # but release global registries between independent birth tickets.
        labels = {
            "absent": "observe",
            "observe": "observe",
            "attempt": "attempt",
            "publish": "publish",
        }
        label = labels[_stage]
        with ExitStack() as fences:
            with PROFILER.span("background.reproduction_guard_wait." + label):
                fences.enter_context(COMBAT_GROUPS.lock)
                fences.enter_context(HARVESTS.lock)
            with PROFILER.span("background.reproduction_guard_held." + label):
                yield WORLD.snapshot(), set(HARVESTS.targets)

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
                    excluded_ids=(),
                    emit=WORLD.emit_location,
                    coordination=coordination,
                )
            except Exception as error:
                record(event="monster_reproduction_error", reason=str(error))


def expire_monster_corpses():
    from wakfu_server.monster_corpses import expire

    last_test_expiry = 0.0
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
        if time.monotonic() - last_test_expiry >= 10:
            last_test_expiry = time.monotonic()
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


def mature_monsters():
    from wakfu_server.monster_maturation import tick
    from contextlib import contextmanager, ExitStack
    import uuid

    @contextmanager
    def coordination(stage, _map_id, _instance_id):
        label = "observe" if stage == "absent" else stage
        with ExitStack() as fences:
            with PROFILER.span("background.maturation_guard_wait." + label):
                fences.enter_context(COMBAT_GROUPS.lock)
                fences.enter_context(HARVESTS.lock)
            with PROFILER.span("background.maturation_guard_held." + label):
                yield WORLD.snapshot(), set(HARVESTS.targets)

    generation = uuid.uuid4().hex
    locations = set()
    while not STOPPING.wait(1):
        with PROFILER.span("background.mature_monsters"):
            try:
                active = {(p["map_id"], p["instance_id"]) for p in WORLD.snapshot()}
                locations = tick(
                    STORE,
                    active,
                    locations,
                    generation=generation,
                    now_ms=time.monotonic_ns() // 1000000,
                    excluded_ids=(),
                    emit=WORLD.emit_location,
                    coordination=coordination,
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
    global ECOLOGY_BRIDGE, BOTS_BRIDGE
    intergame_server = None
    intergame_thread = None
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
    if COMBAT_TEST and ECOLOGY_MODE == "inline":
        from wakfu_server.monster_initial_population import seed_configured

        seed_configured(STORE, COMBAT_GROUPS, report=record)
    from wakfu_server.performance_monitor import start_monitor

    start_monitor(PROFILER, RUNTIME / "logs/profiles/performance-latest.json", STOPPING)
    from wakfu_server.global_tasks import GlobalTasks, SlowSaveAnnouncements
    from wakfu_server.position_checkpoint_worker import PositionCheckpointWorker

    def tick_territory_weather():
        from wakfu_server.territory_weather import tick_weather

        return tick_weather(STORE, WORLD)

    callbacks = {"positions_flush": flush_positions}
    if ECOLOGY_MODE == "inline":
        callbacks["territory_weather_tick"] = tick_territory_weather
        threading.Thread(
            target=refresh_regional_bonuses, name="wakfu-regional-bonuses", daemon=True
        ).start()
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
    if COMBAT_TEST and ECOLOGY_MODE == "inline":
        threading.Thread(
            target=expire_monster_corpses, name="wakfu-monster-corpses", daemon=True
        ).start()
        threading.Thread(
            target=grow_planted_resources, name="wakfu-plant-growth", daemon=True
        ).start()
    if (
        COMBAT_TEST
        and ECOLOGY_MODE == "inline"
        and hasattr(COMBAT_GROUPS, "move_members")
    ):
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
            "live_console": TEST_CONSOLE
            if os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
            else None,
            "global_tasks": global_tasks,
            "ecology_bridge": ECOLOGY_BRIDGE,
            "bots_bridge": BOTS_BRIDGE,
            "combat_recovery": CombatAdminRecovery(
                STORE,
                COMBAT_SESSIONS.registry,
                POSITIONS,
                groups=COMBAT_GROUPS,
                checkpoint_writer=CHECKPOINT_WRITER,
            )
            if COMBAT_TEST
            else None,
        },
        daemon=True,
    ).start()
    threading.Thread(target=listen, args=(15556, "world", context), daemon=True).start()
    listen(15558, "dispatcher", context)


if __name__ == "__main__":
    main()
