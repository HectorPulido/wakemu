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
from wakfu_server.request_diagnostics import (
    RequestTrace, current_request, request_context, state_summary, redact, exception_frames, safe_snapshot,
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
from wakfu_server.shutdown import Connections

CONNECTIONS = Connections()
STOPPING = threading.Event()
from wakfu_server.live_console import LiveConsole

TEST_CONSOLE = LiveConsole()
from wakfu_server import world_clock
from wakfu_server import health, health_store

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
STORE = Store(os.environ.get("WAKFU_DATABASE", RUNTIME / "world.sqlite3"))
from wakfu_server.monster_collect import Harvests

HARVESTS = Harvests(STORE)
from wakfu_server.planting_runtime import Plantings

OPEN_PLANTING = os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1"
PLANTINGS = Plantings(
    STORE,
    open_test_policy=OPEN_PLANTING,
    growth_seconds=float(os.environ.get("WAKFU_PLANT_GROWTH_SECONDS", "30")),
)
if os.environ.get("WAKFU_REDIS_URL"):
    import redis
    from wakfu_server.build_journal import BuildJournal

    STORE.build_journal = BuildJournal(
        STORE,
        redis.Redis.from_url(
            os.environ["WAKFU_REDIS_URL"], socket_connect_timeout=2, socket_timeout=2
        ),
        flush_interval=1200,
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
LIVE = {}
LOCAL_WORLD_ACTIONS = itertools.count(1)
from wakfu_server.position_redis import create as create_positions


def position_lease_active(account_id, generation, character_id):
    with LOCK:
        live = LIVE.get(account_id)
        return live is not None and live[0] == generation


POSITIONS, POSITION_RECOVERY = create_positions(
    STORE, lease_active=position_lease_active, url=os.environ.get("WAKFU_REDIS_URL")
)
POSITION_FLUSH_SECONDS = float(os.environ.get("WAKFU_POSITION_FLUSH_SECONDS", "2"))
if not 0.1 <= POSITION_FLUSH_SECONDS <= 30:
    raise ValueError("WAKFU_POSITION_FLUSH_SECONDS must be between 0.1 and 30")


def flush_positions(**scope):
    count = POSITIONS.flush(**scope)
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

COMBAT_TEST_CRITICAL_BRANCH = os.environ.get("WAKFU_COMBAT_CRITICAL_BRANCH", "normal")
if COMBAT_TEST_CRITICAL_BRANCH not in ("normal", "critical"):
    raise ValueError("WAKFU_COMBAT_CRITICAL_BRANCH must be normal or critical")
MONSTER_RESPAWN_SECONDS = float(
    os.environ.get("WAKFU_LOCAL_MONSTER_RESPAWN_SECONDS", "0")
)
if not math.isfinite(MONSTER_RESPAWN_SECONDS) or MONSTER_RESPAWN_SECONDS < 0:
    raise ValueError("Invalid local monster respawn interval")
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

    if os.environ.get("WAKFU_REDIS_URL"):
        import redis
        from wakfu_server.combat_group_redis import RedisGroups

        def group_lease_active(generation):
            with LOCK:
                return any(value[0] == generation for value in LIVE.values())

        COMBAT_GROUPS = RedisGroups(
            STORE,
            redis.Redis.from_url(
                os.environ["WAKFU_REDIS_URL"],
                socket_connect_timeout=2,
                socket_timeout=2,
            ),
            recover=True,
            lease_active=group_lease_active,
            flush_interval=1200,
        )
    else:
        COMBAT_GROUPS = PersistentGroups(STORE, recover=True)
    TEST_GROUP_KEY = getattr(COMBAT_GROUPS, "register_seed", COMBAT_GROUPS.register)(
        1134, 0, 200, TEST_MONSTERS
    )
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
        with self.write_lock:
            self.socket.sendall(data)


def write_records(rows):
    # One lock/open per request batch; effect tracing never fsyncs per effect.
    with LOCK:
        with (RUNTIME / "logs/game-server.jsonl").open("a") as log:
            log.writelines(json.dumps(row) + "\n" for row in rows)


def record(**fields):
    active = current_request()
    event = fields.get("event", "")
    if active is not None and (event.endswith("_rejected") or event.endswith("_failed")):
        active.rejection(event, fields.get("reason", fields.get("detail", "")))
        fields["state_at_rejection"] = safe_snapshot(active.snapshot)
    row = redact({"time": datetime.now(timezone.utc).isoformat(),
                  **request_context(), **fields})
    if active is not None and not active.closed:
        active.append(row)
        if event == "unexpected_request_exception":
            active.flush()
    else:
        write_records([row])


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
    record(service=service, direction="out", opcode=opcode, bytes=len(body),
           target_connection_id=getattr(connection, "trace_id", None))


WORLD = World(
    lambda character: wire.spawn_player(PLAYER_TEMPLATE, character),
    wire.remove_player,
    lambda peer, opcode, body: send(peer, "world", opcode, body),
)


def send_planting_context(connection, character):
    from wakfu_server.planting_cells import position_context

    try:
        packet = position_context(character, open_test_policy=OPEN_PLANTING)
        send(connection, "world", *packet)
    except ValueError as error:
        record(
            event="planting_context_unavailable",
            actor_id=character["id"],
            map_id=character["map_id"],
            reason=str(error),
        )


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
    send_planting_context(connection, character)
    for packet in PLANTINGS.snapshots(character["map_id"], character["instance_id"]):
        send(connection, "world", *packet)
    if not COMBAT_TEST:
        WORLD.join(generation, connection, character)
        return
    from wakfu_server.combat_monster_world import spawn_group

    # Snapshot and publishes use the same lock as group claims.
    with COMBAT_GROUPS.lock:
        WORLD.join(generation, connection, character)
        for group in COMBAT_GROUPS.available(
            character["map_id"], character["instance_id"]
        ):
            send(
                connection,
                "world",
                12608,
                spawn_group(group["members"], group_id=group["key"][2]),
            )


def release_groups(generation):
    if not COMBAT_TEST or generation is None:
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


def replay(connection, start, end, account_id, character=None):
    for frame in FRAMES[start:end]:
        if frame["direction"] == "in":
            if frame["opcode"] == 12789:
                # Ecology comes from the current native region and our own
                # population, never the account used to record the fixture.
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
            original = base64.b64decode(frame["body_base64"])
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
            owned = (
                STORE.characters(account_id)
                if frame["opcode"] == 13873 and original[:8] == struct.pack(">II", 2, 0)
                else None
            )
            social_body = social.adapt(
                frame["opcode"], original, account_id, character, owned
            )
            if social_body is not None:
                send(connection, "world", frame["opcode"], social_body)
                continue
            if frame["opcode"] == 13078 and character is None:
                # Account equipment inventories precede character selection.
                # Only seed owned characters from the known Pekebu inventory.
                if struct.unpack(">q", original[:8])[0] == wire.TEMPLATE_CHARACTER:
                    for owned in STORE.characters(account_id):
                        send(
                            connection,
                            "world",
                            13078,
                            wire.adapt(13078, original, account_id, owned),
                        )
                continue
            if frame["opcode"] == 23548:
                body = wire.character_list(
                    CHARACTERS, account_id, STORE.characters(account_id)
                )
            elif frame["opcode"] == 12393:
                body = wire.attribute_sheets(original, STORE.characters(account_id))
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
    group = combat_group_for_target(COMBAT_GROUPS, character, target)
    member = next(m for m in group["members"] if m["id"] == target)
    return dict(member, instance_id=group["key"][1])


def session(raw, peer, service, context):
    selected = loaded = False
    account_id = generation = character = None
    bag_session = None
    fight = None
    active_request = None
    connection_trace_id = uuid.uuid4().hex
    fight_messages = None
    fight_started_at = None
    group_lease = None
    # Each session binds its own claimed roster; globals only register defaults.
    TEST_MONSTERS = ()
    TEST_MONSTERS_BY_ID = {}
    TEST_GROUP_KEY = None
    checkpoint_revision = checkpoint_id = None
    checkpoint_terminal = False
    connected_at = time.monotonic()
    last_chat = 0
    last_health_tick = 0
    last_session_renewal = 0
    position = {"x": -12, "y": -8, "z": -1}
    console_session = None

    def checkpoint_fight(status=None):
        nonlocal checkpoint_revision, checkpoint_id, checkpoint_terminal
        if fight is None:
            return
        if checkpoint_id != fight.id:
            checkpoint_id = fight.id
            checkpoint_revision = None
            checkpoint_terminal = False
        if checkpoint_terminal:
            return
        checkpoint_started = time.monotonic()
        try:
            record(event="persistence_stage", domain="fight_checkpoint",
                   stage="save_started", fight_id=fight.id)
            checkpoint_revision = CHECKPOINTS.save(
                account_id,
                generation,
                fight,
                expected_revision=checkpoint_revision,
                runtime=fight_messages,
            )
            record(event="persistence_stage", domain="fight_checkpoint",
                   stage="save_committed", fight_id=fight.id, revision=checkpoint_revision)
            if status is not None:
                checkpoint_revision = CHECKPOINTS.end(
                    account_id,
                    generation,
                    fight.id,
                    expected_revision=checkpoint_revision,
                    status=status,
                )
                checkpoint_terminal = True
            record(event="combat_checkpoint_timing", fight_id=fight.id,
                   elapsed_ms=round((time.monotonic() - checkpoint_started) * 1000, 3))
        except ValueError as error:
            # A replaced login cannot overwrite the current generation's state.
            record(
                event="combat_checkpoint_rejected", fight_id=fight.id, reason=str(error)
            )

    def complete_test_fight():
        checkpoint_fight("ended")
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_lifecycle import prepare_finish

        for actor in fight.actors.values():
            if actor.hp == 0 and actor.id not in getattr(
                fight_messages, "_reported_deaths", set()
            ):
                for message_id, payload in death_messages(fight_messages, actor.id):
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
        result = prepare_finish(
            STORE,
            account_id,
            generation,
            character,
            fight_messages,
            metadata,
            duration_ms=int((time.monotonic() - fight_started_at) * 1000),
            fight_instance_id=fight.id,
        )
        character.update(
            {key: result["character"][key] for key in ("xp", "kamas", "level")}
        )
        if fight.winner == fight.actors[character["id"]].team:
            COMBAT_GROUPS.finish(group_lease, defeated=True)
        for message_id, payload in result["packets"]:
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

    def pass_test_monster_turn():
        # A bounded local policy: approach, one audited attack, then end turn.
        if (
            fight is not None
            and fight.current is not None
            and not fight.current.controlled
            and fight_messages.awaiting_ack is None
        ):
            from wakfu_server.combat_movement_runtime import apply_ai
            from wakfu_server.combat_actor import actual_monster_actor_stats

            monster = TEST_MONSTERS_BY_ID[fight.current.id]
            packets, plan = apply_ai(
                fight_messages,
                lambda actor: actual_monster_actor_stats(
                    monster, actor, fight.id, wp_current=0, wp_maximum=0, direction=3
                ),
                direction=3,
            )
            for message_id, payload in packets:
                send(connection, service, message_id, payload)
            if packets:
                record(event="combat_monster_movement", fight_id=fight.id, plan=plan)
            from wakfu_server.combat_npc_attack import execute as npc_attack
            from wakfu_server.combat_wire import actor_state

            try:
                result = npc_attack(
                    monster,
                    character,
                    fight,
                    character["id"],
                    action_id=fight_messages.action_id + 1,
                    effect_uid=secrets.randbelow(2**60) + 1,
                    player_wp_current=live_wp(fight, character["id"])[0],
                    player_wp_maximum=live_wp(fight, character["id"])[1],
                    critical_chance=0,
                    caster_running_effects=(),
                    target_running_effects=(),
                    caster_bonuses={},
                    target_bonuses={},
                    mitigate=lambda damage, element, source, target, state: damage,
                )
                for message_id, payload in result["packets"]:
                    send(
                        connection,
                        service,
                        message_id,
                        fight_messages._prefix() + payload[12:],
                    )
                send(connection, service, *fight_messages._flush())
                for actor_id, stats in result["snapshots"].items():
                    send(
                        connection,
                        service,
                        12873,
                        actor_state(12873, fight.id, actor_id, stats),
                    )
                send(connection, service, *fight_messages._flush())
                record(
                    event="combat_monster_attack",
                    fight_id=fight.id,
                    damage=result["damage"],
                )
            except ValueError as error:
                record(
                    event="combat_monster_attack_rejected",
                    fight_id=fight.id,
                    reason=str(error),
                )
            if fight.phase == "finished":
                complete_test_fight()
                return
            record(
                event="combat_test_monster_passed",
                fight_id=fight.id,
                actor_id=fight.current.id,
            )
            for message_id, payload in fight_messages.end_server_turn(
                fight.current.id, fight.turn_id
            ):
                send(connection, service, message_id, payload)

    def execute_test_command(text):
        nonlocal character, position, movement_state
        from wakfu_server.test_console import execute

        failure = None
        try:
            command = text.split()[0].lower()
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
            )
            if result["action"] == "tp":
                WORLD.leave(character["id"], generation)
                character = result["character"]
                POSITIONS.attach(account_id, generation, character)
                position = {key: character[key] for key in ("x", "y", "z")}
                movement_state = Movement(position)
                for message_id, message_body in native_transports.bootstrap(character):
                    send(connection, service, message_id, message_body)
                join_world(generation, connection, character)
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
        except ValueError as error:
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

    def idle():
        if STOPPING.is_set():
            return False
        nonlocal last_health_tick, last_session_renewal, console_session
        if account_id is not None:
            now = time.monotonic()
            renew = now - last_session_renewal >= 10
            valid = (
                STORE.heartbeat(account_id, generation)
                if renew
                else STORE.current_session(account_id, generation)
            )
            if not valid:
                return False
            if renew:
                last_session_renewal = now
            if fight_messages is not None and fight is not None:
                expired_packets = fight_messages.expire_current_once()
                for message_id, payload in expired_packets:
                    send(connection, service, message_id, payload)
                if expired_packets:
                    checkpoint_fight()
                    record(
                        event="combat_turn_expired",
                        fight_id=fight.id,
                        actor_id=character["id"],
                    )
            if (
                loaded
                and character is not None
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
                    sink=record, opcode=opcode, service=service,
                    connection_id=connection_trace_id,
                    snapshot=lambda: state_summary(character, fight, fight_messages),
                    effect_scope=combat_diagnostic_scope(record)
                    if fight is not None or opcode in (13130, 12523, 13260) else None,
                    flush=write_records,
                )
                record(
                    service=service,
                    direction="in",
                    opcode=opcode,
                    route=route,
                    bytes=len(body),
                )
                # All transactional actions/DB refreshes see the last approved
                # outside-world position; own-bag moves remain session-only.
                if character is not None and opcode != 13331:
                    flush_positions(
                        account_id=account_id,
                        generation=generation,
                        character_id=character["id"],
                    )
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
                    record(
                        event="combat_world_action_rejected",
                        actor_id=character["id"],
                        opcode=opcode,
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
                        for message_id, message_body in native_transports.bootstrap(
                            character
                        ):
                            send(connection, service, message_id, message_body)
                    else:
                        replay(connection, 119, 131, account_id, character)
                    join_world(generation, connection, character)
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
                        with POSITIONS.lock:
                            flush_positions(account_id=account_id)
                            generation = STORE.begin_session(account_id)
                            with LOCK:
                                previous = LIVE.pop(account_id, None)
                        if previous:
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
                    replay(connection, 24, 44, account_id)
                    send(
                        connection,
                        service,
                        13873,
                        wire.account_kamas(STORE.account_kamas(account_id)),
                    )
                elif opcode == 13488:
                    if account_id is None or body != b"\x00":
                        raise ValueError("Invalid character selection request")
                    from wakfu_server.combat_health import persist_aborted_fight

                    checkpoint_fight(
                        "ended"
                        if fight is not None and fight.phase == "finished"
                        else "aborted"
                    )
                    persist_aborted_fight(
                        STORE, account_id, generation, character, fight
                    )
                    release_groups(generation)
                    group_lease = None
                    fight = fight_messages = None
                    if character is not None:
                        POSITIONS.release(account_id, generation, character["id"])
                    STORE.clear_character(account_id, generation)
                    if character is not None:
                        WORLD.leave(character["id"], generation)
                    selected = loaded = False
                    character = None
                    movement_state = None
                    bag_session = None
                    replay(connection, 31, 44, account_id)
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
                        replay(connection, 45, 114, account_id, character)
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
                elif opcode == 23664:
                    request = decode_body("out", opcode, body)
                    if account_id is None or selected:
                        raise ValueError(
                            "Authentication required or character already selected"
                        )
                    character = STORE.select_character(
                        account_id, generation, request["character_id"]
                    )
                    if request["character_name"] != character["name"]:
                        raise ValueError("Character name mismatch")
                    character = health_store.initialize(
                        STORE, account_id, generation, character["id"], coefficient=1
                    )
                    POSITIONS.attach(account_id, generation, character)
                    position = {k: character[k] for k in ("x", "y", "z")}
                    movement_state = Movement(position)
                    selected = True
                    replay(connection, 45, 114, account_id, character)
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
                elif opcode == 13220 and loaded:
                    from wakfu_server.planting_cells import authorize
                    from wakfu_server.combat_terrain import map_geometry

                    try:
                        if fight is not None or bag_session is not None:
                            raise ValueError(
                                "Sal del combate o del merkasaco para plantar"
                            )

                        def authorize_planting(current, request, seed, resource):
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
                    from wakfu_server.monster_collect import decode_request, action
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
                                quantity=1,
                                cooldown_seconds=0,
                            )
                        send(connection, service, *packet)
                        record(
                            event="monster_harvest_started",
                            actor_id=character["id"],
                            monster_id=monster["id"],
                            action_id=rule["action_id"],
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
                elif opcode == 13429 and loaded and COMBAT_TEST:
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
                                    send(connection, service, message_id, payload)
                            if result["applied"]:
                                character = result["character"]
                                send_planting_context(connection, character)
                            record(
                                event="planting_completed",
                                actor_id=character["id"],
                                applied=result["applied"],
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
                elif opcode == 13130 and loaded and COMBAT_TEST:
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    from wakfu_server.combat_bootstrap import create_placement
                    from wakfu_server.combat_terrain import local_arena

                    target, x, y, z, auto_lock = struct.unpack(">qiihB", body)
                    if fight is not None or bag_session is not None:
                        record(
                            event="combat_test_attack_rejected",
                            actor_id=character["id"],
                        )
                        continue
                    try:
                        with COMBAT_GROUPS.lock:
                            selected_group = combat_group_for_target(
                                COMBAT_GROUPS, character, target
                            )
                        TEST_GROUP_KEY = selected_group["key"]
                        TEST_MONSTERS = tuple(selected_group["members"])
                        TEST_MONSTERS_BY_ID = {m["id"]: m for m in TEST_MONSTERS}
                        arena = local_arena(
                            character["map_id"],
                            character["id"],
                            (character["x"], character["y"], character["z"]),
                            [(m["x"], m["y"], m["z"]) for m in TEST_MONSTERS],
                        )
                        from wakfu_server.equipment_stats import combat_resources

                        resources = combat_resources(character, wp=COMBAT_TEST_WP)
                        candidate, packets = create_placement(
                            character,
                            TEST_MONSTERS,
                            arena,
                            fight_id=secrets.randbelow(2**30) + 1,
                            player_ap=resources["ap"],
                            player_mp=resources["mp"],
                            player_wp=resources["wp"],
                            player_initiative=resources["initiative"],
                            terrain_effect_id=46,
                            terrain_instance_id=secrets.randbelow(2**60) + 1,
                        )
                        from wakfu_server.combat_actor_snapshot import (
                            initialize_fight_snapshots,
                        )

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
                        )
                        # Match the directions published by placement actor serializers.
                        for participant in candidate.actors.values():
                            participant.direction = 0 if participant.controlled else 3
                        from wakfu_server.combat_monster_world import remove_message

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
                        fight = candidate
                        fight_started_at = time.monotonic()
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
                        record(
                            event="combat_test_placement_started",
                            actor_id=character["id"],
                            fight_id=fight.id,
                        )
                    except ValueError as error:
                        if fight is None and group_lease is not None:
                            release_groups(generation)
                            group_lease = None
                        record(
                            event="combat_test_attack_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12806 and fight is not None:
                    from wakfu_server.combat_bootstrap import placement_positions

                    actor_id, x, y, z = struct.unpack(">qiih", body)
                    try:
                        fight.place(account_id, actor_id, (x, y, z))
                        send(connection, service, 13652, placement_positions(fight))
                    except ValueError as error:
                        record(
                            event="combat_test_placement_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12523 and fight is not None:
                    from wakfu_server.combat_runtime_messages import RuntimeMessages
                    from wakfu_server.combat_bootstrap import player_payload
                    from wakfu_server.combat_actor import (
                        monster_actor_stats,
                        actor_effects,
                    )

                    try:
                        if len(body) != 1 or body[0] not in (0, 1):
                            raise ValueError("Invalid placement readiness")
                        if fight.phase == "placement":
                            from wakfu_server.combat_actor import (
                                actual_actor_stats,
                                actual_monster_actor_stats,
                            )

                            def current_combat_stats(actor):
                                if actor.effect_stats is not None:
                                    if (
                                        actor.effect_maxima is None
                                        or 4 not in actor.effect_stats
                                        or 4 not in actor.effect_maxima
                                    ):
                                        raise ValueError(
                                            "Missing authoritative combat WP snapshot"
                                        )
                                    wp_current = actor.effect_stats[4]
                                    wp_maximum = actor.effect_maxima[4]
                                else:
                                    raise ValueError(
                                        "Missing authoritative combat WP snapshot"
                                    )
                                if actor.controlled:
                                    return actual_actor_stats(
                                        character,
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

                            from wakfu_server.combat_ready import prepare_ready
                            from wakfu_server.combat_server_spell import (
                                prepare_server_initialization,
                            )
                            from wakfu_server.spells import default_deck

                            stored_deck = (
                                character.get("builds", {}).get(0, {}).get("deck")
                            )
                            deck = (
                                bytes.fromhex(stored_deck)
                                if stored_deck
                                else default_deck(character)
                            )
                            candidate, candidate_messages, packets = prepare_ready(
                                fight,
                                account_id,
                                bool(body[0]),
                                initialize=lambda preview, action_id: prepare_server_initialization(
                                    character,
                                    TEST_MONSTERS_BY_ID,
                                    preview,
                                    account_id,
                                    deck,
                                    action_id=action_id,
                                ),
                                stats_serializer=current_combat_stats,
                                effects_serializer=actor_effects,
                            )
                            fight = candidate
                            if candidate_messages is None:
                                continue
                            fight_messages = candidate_messages
                            for message_id, payload in packets:
                                send(connection, service, message_id, payload)
                            record(
                                event="combat_test_active",
                                actor_id=character["id"],
                                fight_id=fight.id,
                            )
                            pass_test_monster_turn()
                    except ValueError as error:
                        record(
                            event="combat_test_ready_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13260 and fight_messages is not None:
                    from wakfu_server.combat_execute import execute_adjacent_cast
                    from wakfu_server.combat_wire import actor_state
                    from wakfu_server.combat_death import death_messages
                    from wakfu_server.combat_results import finish_messages
                    from wakfu_server.spells import default_deck

                    try:
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
                            # Existing test environment chooses the normal cast branch.
                            # Native critical roll remains a separate pending requirement.
                            critical=COMBAT_TEST_CRITICAL_BRANCH == "critical",
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
                                actor
                            ),
                        )
                        cast_commit_finished = time.monotonic()
                        fight = transaction.fight
                        for message_id, payload in packets:
                            send(connection, service, message_id, payload)
                        record(
                            event="combat_cast",
                            dispatch_ms=round((cast_prepare_started - request_received_at) * 1000, 3),
                            prepare_ms=round((cast_prepare_finished - cast_prepare_started) * 1000, 3),
                            commit_ms=round((cast_commit_finished - cast_prepare_finished) * 1000, 3),
                            send_ms=round((time.monotonic() - cast_commit_finished) * 1000, 3),
                            actor_id=character["id"],
                            spell_id=transaction.plan["spell_id"],
                            outcomes=transaction.outcomes,
                        )
                        result = {"events": transaction.events}
                        for event in result["events"]:
                            if event["kind"] == "death":
                                for message_id, payload in death_messages(
                                    fight_messages, event["actor_id"]
                                ):
                                    send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                    except ValueError as error:
                        record(
                            event="combat_cast_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12889 and fight_messages is not None:
                    from wakfu_server.combat_melee import execute_unarmed
                    from wakfu_server.combat_wire import actor_state
                    from wakfu_server.combat_death import death_messages

                    try:
                        if fight_messages.awaiting_ack is not None:
                            raise ValueError("Previous turn is not synchronized")
                        # Owned equipment is empty; build validation rejects unowned item IDs.
                        result = execute_unarmed(
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
                        for message_id, payload in result["packets"]:
                            send(
                                connection,
                                service,
                                message_id,
                                fight_messages._prefix() + payload[12:],
                            )
                        send(connection, service, *fight_messages._flush())
                        for actor_id, stats in result["snapshots"].items():
                            send(
                                connection,
                                service,
                                12873,
                                actor_state(12873, fight.id, actor_id, stats),
                            )
                        send(connection, service, *fight_messages._flush())
                        record(
                            event="combat_melee",
                            actor_id=character["id"],
                            damage=result["damage"],
                        )
                        for event in result["events"]:
                            if event["kind"] == "death":
                                for message_id, payload in death_messages(
                                    fight_messages, event["actor_id"]
                                ):
                                    send(connection, service, message_id, payload)
                        if fight.phase == "finished":
                            complete_test_fight()
                    except ValueError as error:
                        record(
                            event="combat_melee_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13952 and fight_messages is not None:
                    from wakfu_server.combat_abandon import prepare as prepare_abandon

                    try:
                        abandoned = prepare_abandon(
                            STORE,
                            account_id,
                            generation,
                            character,
                            fight_messages,
                            body,
                        )
                        character.update(abandoned["character"])
                        if abandoned["applied"]:
                            checkpoint_fight("aborted")
                        for message_id, payload in abandoned["packets"]:
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
                elif opcode == 12925 and fight_messages is not None:
                    from wakfu_server.combat_lifecycle import return_to_world
                    from wakfu_server.combat_death import despawn_monster

                    try:
                        abandoned = (
                            getattr(fight_messages, "abandon_owner", None) is not None
                        )
                        if abandoned:
                            from wakfu_server.combat_abandon import (
                                return_to_world as return_abandon,
                            )

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
                        if not abandoned:
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
                        for message_id, payload in native_transports.bootstrap(
                            character
                        ):
                            send(connection, service, message_id, payload)
                        from wakfu_server.combat_monster_world import spawn_group

                        if group_lease is not None:
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
                        join_world(generation, connection, character)
                        checkpoint_fight("aborted" if abandoned else "ended")
                        record(
                            event="combat_return_to_world",
                            actor_id=character["id"],
                            fight_id=fight.id,
                            abandoned=abandoned,
                        )
                        group_lease = None
                        fight = fight_messages = None
                    except ValueError as error:
                        record(
                            event="combat_return_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13655 and fight_messages is not None:
                    from wakfu_server.combat_orientation import apply as orient_actor

                    try:
                        oriented = orient_actor(fight_messages, account_id, body)
                        for message_id, payload in oriented["packets"]:
                            send(connection, service, message_id, payload)
                        checkpoint_fight()
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

                    try:
                        packets, event = apply_client(
                            fight_messages,
                            account_id,
                            body,
                            lambda actor: actual_actor_stats(
                                character,
                                actor,
                                fight.id,
                                wp_current=live_wp(fight, character["id"])[0],
                                wp_maximum=live_wp(fight, character["id"])[1],
                            ),
                            direction=3,
                        )
                        for message_id, payload in packets:
                            send(connection, service, message_id, payload)
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
                    try:
                        actor_id, actor_turn = struct.unpack(">qh", body)
                        for message_id, payload in fight_messages.end_turn(
                            account_id, actor_id, actor_turn
                        ):
                            send(connection, service, message_id, payload)
                    except ValueError as error:
                        record(
                            event="combat_test_end_turn_rejected",
                            actor_id=character["id"],
                            reason=str(error),
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
                    except ValueError as error:
                        record(
                            event="combat_recovery_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 13510 and fight_messages is not None:
                    try:
                        for message_id, payload in fight_messages.acknowledge_turn(
                            body
                        ):
                            send(connection, service, message_id, payload)
                        pass_test_monster_turn()
                    except ValueError as error:
                        record(
                            event="combat_test_turn_ack_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 14689 and loaded:
                    if character["instance_id"] == 0:
                        for message_body in world_static.snapshots(character["map_id"]):
                            send(connection, service, 13984, message_body)
                    record(
                        event="transport_objects_initialized",
                        actor_id=character["id"],
                        map_id=character["map_id"],
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
                    from wakfu_server.inventory_move import synchronization

                    try:
                        operation = equip if opcode == 12656 else remove
                        result = operation(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
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
                        message_id, message_body = synchronization(character)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_bag_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12659 and loaded:
                    from wakfu_server.inventory_consumables import use
                    from wakfu_server.inventory_move import synchronization

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
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
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
                        saved = STORE.character(account_id, character["id"])
                        message_id, message_body = synchronization(saved)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_food_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12490 and loaded:
                    from wakfu_server.inventory_actions import destroy
                    from wakfu_server.inventory_move import synchronization

                    try:
                        result = destroy(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
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
                        saved = STORE.character(account_id, character["id"])
                        message_id, message_body = synchronization(saved)
                        send(connection, service, message_id, message_body)
                        record(
                            event="inventory_destroy_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                elif opcode == 12804 and loaded:
                    from wakfu_server.inventory_move import transfer, synchronization

                    try:
                        result = transfer(
                            STORE, account_id, generation, character["id"], body
                        )
                        saved = result["character"]
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
                        record(event="inventory_item_moved", actor_id=character["id"])
                        from wakfu_server.inventory_items import equipment_inventory

                        send(connection, service, *equipment_inventory(character))
                    except ValueError as error:
                        saved = STORE.character(account_id, character["id"])
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
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
                        WORLD.leave(character["id"], generation)
                        character = saved
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        for message_id, message_body in native_transports.bootstrap(
                            character
                        ):
                            send(connection, service, message_id, message_body)
                        join_world(generation, connection, character)
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
                            wire.adapt(13974, fixture(13974), account_id, character),
                        )
                    else:
                        WORLD.leave(character["id"], generation)
                        character = saved
                        POSITIONS.attach(account_id, generation, character)
                        position = {key: character[key] for key in ("x", "y", "z")}
                        movement_state = Movement(position)
                        messages = (
                            native_transports.bootstrap(
                                character, direction=destination_route["direction"]
                            )
                            if generic_route
                            else transports.bootstrap(character, destination_route)
                        )
                        for message_id, message_body in messages:
                            send(connection, service, message_id, message_body)
                        join_world(generation, connection, character)
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
                elif opcode == 12772 and loaded:
                    request_id, index, blobs = builds.decode(body)
                    if request_id != character["id"]:
                        raise ValueError(
                            "Build character does not belong to this session"
                        )
                    try:
                        record(event="persistence_stage", domain="build",
                               stage="save_started", build_index=index,
                               backend="redis" if STORE.build_journal is not None else "sqlite")
                        saved = STORE.save_build(
                            account_id, generation, request_id, index, blobs
                        )
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
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
                        record(event="persistence_stage", domain="build",
                               stage="journal_committed" if STORE.build_journal is not None else "sqlite_committed",
                               build_index=index)
                        character = (
                            bag_session.refresh(character, saved)
                            if bag_session is not None and bag_session.owns(character)
                            else saved
                        )
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
                        for message_id, message_body in builds.response_messages(
                            character, index, wp=COMBAT_TEST_WP
                        ):
                            send(connection, service, message_id, message_body)
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
                    if target_id != 0 or character["map_id"] == 9:
                        send(
                            connection,
                            service,
                            13307,
                            entry_result(success=False, own=target_id == 0),
                        )
                        continue
                    bag_session = HavenBagSession(character)
                    WORLD.leave(character["id"], generation)
                    character = dict(bag_session.inside)
                    position = {key: character[key] for key in ("x", "y", "z")}
                    movement_state = Movement(position)
                    for message_id, message_body in entry_messages(
                        fixture(13974), character
                    ):
                        send(connection, service, message_id, message_body)
                    join_world(generation, connection, character)
                    record(
                        event="haven_bag_entered",
                        actor_id=character["id"],
                        position=position,
                    )
                elif opcode in (12870, 12363) and loaded:
                    from wakfu_server.haven_bag_store import (
                        save as save_haven_bag,
                        edit_furniture,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if opcode == 12870 and character["map_id"] != 9:
                        try:
                            interaction = world_static.interaction(character, body)
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
                    if bag_session is None or not bag_session.owns(character):
                        continue
                    try:
                        furniture = edit_furniture(character["haven_bag"], opcode, body)
                        saved = save_haven_bag(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            furniture=furniture,
                        )
                        character = bag_session.refresh(character, saved)
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
                    send(connection, service, 12187, own_bag(character))
                elif opcode == 13826 and loaded:
                    from wakfu_server.haven_bag_store import (
                        save as save_haven_bag,
                        deploy_furniture,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if bag_session is None or not bag_session.owns(character):
                        continue
                    try:
                        furniture = deploy_furniture(character["haven_bag"], body)
                        saved = save_haven_bag(
                            STORE,
                            account_id,
                            generation,
                            character["id"],
                            furniture=furniture,
                        )
                        character = bag_session.refresh(character, saved)
                        record(
                            event="haven_bag_furniture_saved", actor_id=character["id"]
                        )
                    except ValueError as error:
                        record(
                            event="haven_bag_furniture_rejected",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                    send(connection, service, 12187, own_bag(character))
                elif opcode == 12580 and loaded:
                    from wakfu_server.haven_bag_store import save as save_haven_bag
                    from wakfu_server.haven_bag import (
                        decode_permissions,
                        permission_payload,
                    )

                    if bag_session is None or not bag_session.owns(character):
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
                elif opcode == 13210 and loaded:
                    from wakfu_server.haven_bag_store import (
                        save as save_haven_bag,
                        rearrange_rooms,
                    )
                    from wakfu_server.haven_bag import own_bag

                    if bag_session is None or not bag_session.owns(character):
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
                        for message_id, message_body in leave_messages(
                            fixture(13974), character
                        ):
                            send(connection, service, message_id, message_body)
                        record(
                            event="haven_bag_leave_repaired", actor_id=character["id"]
                        )
                        continue
                    WORLD.leave(character["id"], generation)
                    character = bag_session.leave(character)
                    bag_session = None
                    position = {key: character[key] for key in ("x", "y", "z")}
                    movement_state = Movement(position)
                    for message_id, message_body in leave_messages(
                        fixture(13974), character
                    ):
                        send(connection, service, message_id, message_body)
                    join_world(generation, connection, character)
                    record(
                        event="haven_bag_left",
                        actor_id=character["id"],
                        position=position,
                    )
                elif opcode == 13331 and loaded:
                    PLANTINGS.cancel(character["id"], generation)
                    HARVESTS.cancel(character["id"], generation=generation)
                    movement = decode_body("out", opcode, body)
                    if not movement["steps"]:
                        continue
                    start = movement["start_position"]
                    end = movement["end_position"]
                    try:
                        approved = movement_state.validate(movement)
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
                            account_id, generation, character["id"], position, end
                        )
                        character.update(
                            {key: buffered[key] for key in ("x", "y", "z")}
                        )
                    movement_state.commit(approved)
                    position = end
                    # The owner already follows this path locally. Rebuilding
                    # an endpoint path on it interrupts redirects and stairs.
                    # Other clients receive every packed step and its height.
                    response = wire.movement_path(character["id"], body)
                    WORLD.update(
                        generation, character, 13852, response, include_sender=False
                    )
                    if bag_session is None:
                        send_planting_context(connection, character)
                    record(
                        event="movement",
                        actor_id=character["id"],
                        account_id=account_id,
                        start=start,
                        end=end,
                        steps=movement["step_count"],
                    )
                elif opcode == 12366 and loaded:
                    text = decode_body("out", opcode, body)["text"].strip()
                    if (
                        text.startswith("!")
                        and os.environ.get("WAKFU_TEST_CONSOLE", "1") == "1"
                    ):
                        try:
                            execute_test_command(text)
                        except ValueError:
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
                checkpoint_fight()
                active_request.finish()
                active_request = None
    except (EOFError, OSError, ValueError) as error:
        record(
            event="disconnected",
            connection_id=connection_trace_id,
            service=service,
            error=type(error).__name__,
            detail=str(error),
        )
    except Exception as error:
        record(event="unexpected_request_exception", service=service,
               connection_id=connection_trace_id,
               exception_type=type(error).__name__, traceback=exception_frames(error),
               state_at_failure=safe_snapshot(lambda: state_summary(character, fight, fight_messages)))
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
        if service == "world":
            checkpoint_fight(
                "ended"
                if fight is not None and fight.phase == "finished"
                else "aborted"
            )
            if (
                fight is not None
                and fight.phase == "finished"
                and character is not None
                and fight.winner == fight.actors[character["id"]].team
            ):
                COMBAT_GROUPS.finish(group_lease, defeated=True)
            release_groups(generation)
        if service == "world" and account_id is not None:
            if character is not None:
                # Do not delete its lease or pending position when SQLite is
                # temporarily unavailable. Keep the worker alive for retry.
                while True:
                    try:
                        flush_positions(
                            account_id=account_id,
                            generation=generation,
                            character_id=character["id"],
                        )
                        break
                    except Exception as error:
                        record(
                            event="logout_position_flush_failed",
                            actor_id=character["id"],
                            reason=str(error),
                        )
                        try:
                            STORE.heartbeat(account_id, generation)
                        except Exception:
                            pass
                        time.sleep(1)
                POSITIONS.release(account_id, generation, character["id"])
                from wakfu_server.combat_health import persist_aborted_fight

                exited = persist_aborted_fight(
                    STORE, account_id, generation, character, fight
                )
                if exited is not None and exited["applied"]:
                    record(
                        event="combat_disconnected_health_saved",
                        actor_id=character["id"],
                        fight_id=fight.id,
                        hp=exited["character"]["hp"],
                    )
                WORLD.leave(character["id"], generation)
            with LOCK:
                if LIVE.get(account_id, (None,))[0] == generation:
                    LIVE.pop(account_id, None)
            STORE.end_session(account_id, generation)


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

                for result in PLANTINGS.mature(
                    COMBAT_GROUPS, authorize_spawn=free_spawn
                ):
                    for packet in result["packets"]:
                        WORLD.emit_location(
                            result["map_id"], result["instance_id"], *packet
                        )
                    record(
                        event="planted_resource_grown",
                        map_id=result["map_id"],
                        instance_id=result["instance_id"],
                        resource_uid=result["resource_uid"],
                    )
        except Exception as error:
            record(event="plant_growth_error", reason=str(error))


def wander_monsters():
    from wakfu_server.monster_wander import wander_location, point
    from wakfu_server.combat_terrain import map_geometry

    radius = int(os.environ.get("WAKFU_MONSTER_WANDER_RADIUS", "20"))
    if radius <= 0:
        raise ValueError("Invalid monster wander radius")
    while not STOPPING.wait(random.uniform(3, 6)):
        try:
            players = WORLD.snapshot()
            locations = {(p["map_id"], p["instance_id"]) for p in players}
            with COMBAT_GROUPS.lock, HARVESTS.lock:
                states = COMBAT_GROUPS.snapshot()
                harvesting = set(HARVESTS.targets)
                for map_id, instance_id in locations:
                    local = [g for g in states if g["key"][:2] == (map_id, instance_id)]
                    blocked = {
                        point(m)
                        for g in local
                        for m in g["members"]
                        if g["status"] == "fighting"
                        or any(member["id"] in harvesting for member in g["members"])
                    }
                    geometry = map_geometry(map_id)
                    moved = wander_location(
                        COMBAT_GROUPS,
                        map_id,
                        instance_id,
                        players,
                        geometry["edges"],
                        lambda opcode, body: WORLD.emit_location(
                            map_id, instance_id, opcode, body
                        ),
                        occupied=blocked,
                        radius=radius,
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


def respawn_monsters():
    from wakfu_server.combat_monster_world import spawn_group

    while True:
        time.sleep(1)
        try:
            with COMBAT_GROUPS.lock:
                for group in COMBAT_GROUPS.respawn_due(MONSTER_RESPAWN_SECONDS):
                    map_id, instance_id, group_id = group["key"]
                    WORLD.emit_location(
                        map_id,
                        instance_id,
                        12608,
                        spawn_group(group["members"], group_id=group_id),
                    )
                    record(
                        event="monster_group_respawned",
                        map_id=map_id,
                        instance_id=instance_id,
                        group_id=group_id,
                    )
        except Exception as error:
            record(event="monster_respawn_error", reason=str(error))


def main():
    if COMBAT_TEST:
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
        started = time.monotonic()
        static_info = prewarm_runtime_catalogs()
        record(event="combat_catalogs_ready", elapsed_ms=round(
            (time.monotonic() - started) * 1000, 3), **static_info)
    record(
        event="position_backend_ready",
        backend="redis" if POSITION_RECOVERY is not None else "memory",
        recovery=POSITION_RECOVERY,
    )

    def stop(signum, frame):
        try:
            flush_positions()
            if STORE.build_journal is not None:
                STORE.build_journal.flush()
            if COMBAT_TEST and hasattr(COMBAT_GROUPS, "flush"):
                COMBAT_GROUPS.flush()
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
            if STORE.build_journal is not None:
                STORE.build_journal.close()
            if COMBAT_TEST and hasattr(COMBAT_GROUPS, "flush"):
                COMBAT_GROUPS.flush()
        except Exception as error:
            record(event="shutdown_position_flush_failed", reason=str(error))
            return
        if any(
            worker.name == "wakfu-client-session" and worker.is_alive()
            for worker in threading.enumerate()
        ):
            record(event="shutdown_waiting_for_session_cleanup")
            return
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    external_scheduler = os.environ.get("WAKFU_EXTERNAL_SCHEDULER", "0") == "1"
    from wakfu_server.global_tasks import GlobalTasks

    callbacks = {"positions_flush": flush_positions}
    if STORE.build_journal is not None:
        callbacks["builds_flush"] = STORE.build_journal.flush
    if COMBAT_TEST and hasattr(COMBAT_GROUPS, "flush"):
        callbacks["groups_flush"] = COMBAT_GROUPS.flush
    global_tasks = GlobalTasks(callbacks)
    if not external_scheduler:
        threading.Thread(
            target=flush_position_batches, name="wakfu-position-flusher", daemon=True
        ).start()
    if STORE.build_journal is not None and not external_scheduler:

        def flush_build_batches():
            while not STOPPING.wait(1):
                try:
                    count = STORE.build_journal.flush_due()
                    if count:
                        record(event="build_batch_flushed", characters=count)
                except Exception as error:
                    record(event="build_batch_flush_failed", reason=str(error))

        threading.Thread(
            target=flush_build_batches, name="wakfu-build-flusher", daemon=True
        ).start()
    if COMBAT_TEST and hasattr(COMBAT_GROUPS, "flush_due") and not external_scheduler:

        def flush_group_batches():
            while not STOPPING.wait(1):
                try:
                    count = COMBAT_GROUPS.flush_due()
                    if count:
                        record(event="monster_group_batch_flushed", groups=count)
                except Exception as error:
                    record(event="monster_group_batch_flush_failed", reason=str(error))

        threading.Thread(
            target=flush_group_batches, name="wakfu-group-flusher", daemon=True
        ).start()
    if COMBAT_TEST and MONSTER_RESPAWN_SECONDS > 0:
        threading.Thread(target=respawn_monsters, daemon=True).start()
    if COMBAT_TEST:
        threading.Thread(
            target=grow_planted_resources, name="wakfu-plant-growth", daemon=True
        ).start()
    if COMBAT_TEST and hasattr(COMBAT_GROUPS, "move_members"):
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
