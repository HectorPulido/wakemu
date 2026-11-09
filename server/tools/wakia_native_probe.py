"""Exercise a prepared WakIA service against an in-memory native encounter.

This tool is intended to run as a separate process in the local World
container. It uses a read-only catalogue connection, never opens a player
session, and does not publish its synthetic fight to the game registry.
"""
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import sys
import time
import uuid
from contextlib import contextmanager
from types import SimpleNamespace


def readonly_providers():
    """Enforce PostgreSQL read-only mode and disable Redis writes in-process."""
    options = os.environ.get("PGOPTIONS", "")
    if options:
        options += " "
    os.environ["PGOPTIONS"] = options + "-c default_transaction_read_only=on"
    import redis

    original_command = redis.Redis.execute_command
    original_pipeline = redis.client.Pipeline.execute
    reads = {"GET", "MGET", "PING"}

    def require_read(args):
        if not args or str(args[0]).upper() not in reads:
            raise PermissionError("WakIA probe forbids Redis writes")

    def command(client, *args, **kwargs):
        require_read(args)
        return original_command(client, *args, **kwargs)

    def guard_pipeline_method(original):
        def guarded(client, *args, **kwargs):
            require_read(args)
            return original(client, *args, **kwargs)

        return guarded

    def pipeline(client, *args, **kwargs):
        for args_and_options in client.command_stack:
            operation = args_and_options[0]
            require_read(operation)
        return original_pipeline(client, *args, **kwargs)

    redis.Redis.execute_command = command
    # Pipeline overrides Redis.execute_command. In WATCH mode it sends
    # commands immediately, without ever calling Pipeline.execute; direct
    # immediate/queue methods must be guarded as well.
    for name in (
        "execute_command",
        "immediate_execute_command",
        "pipeline_execute_command",
    ):
        setattr(
            redis.client.Pipeline,
            name,
            guard_pipeline_method(getattr(redis.client.Pipeline, name)),
        )
    redis.client.Pipeline.execute = pipeline
    from wakfu_server.native_catalog import _database

    with _database().connection() as connection:
        row = connection.execute("SHOW transaction_read_only").fetchone()
        value = next(iter(row.values())) if isinstance(row, dict) else row[0]
        if value != "on":
            raise RuntimeError("WakIA probe requires read-only PostgreSQL")


def load_bridge(directory):
    """Load the selected bridge in isolation without editing the live SDK."""
    import wakfu_server.wakia_bridge

    directory = Path(directory).resolve()
    spec = importlib.util.spec_from_file_location(
        "wakfu_server.wakia_bridge.wakfu_ai",
        directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    if spec is None or spec.loader is None:
        raise ValueError("WakIA bridge package is unavailable")
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)


def fixture(*, extra_ally=False):
    """Create a Jalato/character fight entirely in memory using native Ready."""
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import combat_resources, effective_character
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck

    npc_position, pc_position = (-8, -3, -1), (-10, -3, -1)
    hp = maximum(15, 50)
    character = effective_character(
        dict(
            id=7,
            account_id=3,
            map_id=1134,
            instance_id=0,
            breed=15,
            level=50,
            hp=hp,
            max_hp=hp,
            active_build_index=0,
            x=pc_position[0],
            y=pc_position[1],
            z=pc_position[2],
            builds={},
            inventory_items=[],
        )
    )
    resources = combat_resources(character)
    monster = owned_instance(
        1,
        10,
        -7,
        map_id=1134,
        x=npc_position[0],
        y=npc_position[1],
        z=npc_position[2],
        team=1,
        instance_id=0,
    )
    monsters = {-7: monster}
    if extra_ally:
        monsters[-8] = owned_instance(
            3856, 100, -8, map_id=1134, x=-9, y=-4, z=-1, team=1, instance_id=0
        )
    arena = local_arena(
        1134, 1, pc_position, npc_position, relocate_monsters=False, variation_seed=17
    )
    fight, _ = create_placement(
        character,
        list(monsters.values()),
        arena,
        fight_id=1,
        player_ap=resources["ap"],
        player_mp=resources["mp"],
        player_wp=resources["wp"],
        player_initiative=resources["initiative"],
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    initialize_fight_snapshots(
        fight,
        characters={7: character},
        monsters=monsters,
        wp_resources={
            7: (resources["wp"], resources["wp"]),
            **{i: (m["wp"], m["wp"]) for i, m in monsters.items()},
        },
        running_effects={key: () for key in fight.actors},
        initial_effect_uid=1,
    )
    fight.ready(character["account_id"])
    deck = default_deck(character)
    fight, _ = prepare_server_initialization(
        character,
        monsters,
        fight,
        character["account_id"],
        deck,
        action_id=1,
        rng=random.Random(17),
        fight_start=True,
        player_characters={7: character},
        deck_blobs={7: deck},
    )
    fight.order, fight.turn_index = [-7, 7] + ([-8] if extra_ally else []), 0
    fight.current.turn_count = 1
    if not effective_server_controlled(fight, fight.current):
        raise ValueError("Fixture monster lacks native server control")
    runtime = RuntimeMessages(fight)
    runtime.action_id = 1
    runtime.tactical_encounter_id = uuid.uuid4().hex
    return (
        runtime,
        {7: character},
        monsters,
        {7: deck},
        {7: frozenset()},
        SimpleNamespace(pc=fight.actors[7], character=character),
    )


def run(endpoint):
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.wakia_bridge.wakfu_ai.transport.framed import FramedClient

    runtime, characters, monsters, decks, excluded, description = fixture()
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks=excluded,
        viewer_id=description.pc.id,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    serializer = NativeStats(
        characters=characters,
        monsters=monsters,
        fight_id=runtime.fight.id,
        map_id=description.character["map_id"],
    )
    before_hp = description.pc.hp
    channel = FramedClient(*tcp_address(endpoint), timeout=20)
    started = time.monotonic()
    try:
        deliveries = list(
            run_prepared_turn(
                runtime,
                oracle,
                serializer,
                channel,
                deadline=started + 20,
                max_actions=4,
            )
        )
    finally:
        channel.close()
    actions = [diagnostic["action"] for _, diagnostic in deliveries]
    pending = runtime.awaiting_ack
    if pending is not None:
        runtime.acknowledge_turn(struct.pack(">i", pending))
    checks = dict(
        moved=any(action.get("type") == "move" for action in actions),
        cast=any(action.get("type") == "cast" for action in actions),
        damaged=runtime.fight.actors[description.pc.id].hp < before_hp,
        ended=any(action.get("type") == "end_turn" for action in actions),
        packets=any(packets for packets, _ in deliveries),
        ackCleared=pending is not None and runtime.awaiting_ack is None,
    )
    return dict(
        passed=all(checks.values()),
        checks=checks,
        actions=actions,
        damage=before_hp - runtime.fight.actors[description.pc.id].hp,
        elapsedMs=round((time.monotonic() - started) * 1000, 3),
        scope="native in-memory fixture; excludes client and full fight startup",
    )


def run_dispatched(endpoint):
    """Exercise the non-shared World dispatcher with in-memory authorities."""
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.backend_selection import endpoint_for
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.world_entry import run_npc_turn

    if endpoint != endpoint_for("jondo"):
        raise ValueError("Dispatched probe requires the configured WakIA endpoint")
    runtime, characters, monsters, _, _, description = fixture()

    class MemoryStore:
        @contextmanager
        def connection(self):
            class Transaction:
                def execute(self, statement):
                    if (
                        statement
                        != "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                    ):
                        raise ValueError("Unexpected memory store statement")

            yield Transaction()

        def character(self, account_id, character_id, _db):
            character = characters[character_id]
            if character["account_id"] != account_id:
                raise ValueError("Unexpected fixture account")
            return character

    before_hp = description.pc.hp
    sent, records = [], []
    bindings = dict(
        STORE=MemoryStore(),
        character=description.character,
        TEST_MONSTERS_BY_ID=monsters,
        connection=object(),
        service=object(),
        send=lambda _connection, _service, opcode, body: sent.append((opcode, body)),
        record=lambda **event: records.append(event),
        complete_test_fight=lambda: None,
    )
    started = time.monotonic()
    deliveries = list(
        run_npc_turn(runtime, world_context=dict(globals=bindings, scopes=[]))
    )
    actions = [diagnostic["action"] for _, diagnostic in deliveries]
    pending = runtime.awaiting_ack
    if pending is not None:
        runtime.acknowledge_turn(struct.pack(">i", pending))
    checks = dict(
        wakiaPinned=getattr(runtime, "native_ai_backend_pin", {}).get("backend")
        == "jondo",
        moved=any(action.get("type") == "move" for action in actions),
        cast=any(action.get("type") == "cast" for action in actions),
        damaged=runtime.fight.actors[description.pc.id].hp < before_hp,
        ended=any(action.get("type") == "end_turn" for action in actions),
        packets=bool(sent),
        ackCleared=pending is not None and runtime.awaiting_ack is None,
    )
    return dict(
        passed=all(checks.values()),
        checks=checks,
        actions=actions,
        damage=before_hp - runtime.fight.actors[description.pc.id].hp,
        elapsedMs=round((time.monotonic() - started) * 1000, 3),
        scope="non-shared World dispatch and native in-memory fixture; excludes client",
    )


def run_shared(endpoint):
    """Exercise actual shared Registry publication with a private in-memory fight."""
    from wakfu_server.combat_shared import Registry, Session
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.backend_selection import endpoint_for
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.world_shared import run_shared_turn
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_commit_capability import (
        _WORLD_NATIVE_RUNNER,
    )
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.wakia_bridge.wakfu_ai.transport.framed import FramedClient

    if endpoint != endpoint_for("jondo"):
        raise ValueError("Shared probe requires the configured WakIA endpoint")
    runtime, characters, monsters, decks, excluded, description = fixture()
    session = Session(3, 7, "probe", 1134, 0)
    registry = Registry(lambda candidate: candidate == session)
    shared = registry.register(runtime.fight, session, runtime=runtime)
    adapter = SimpleNamespace(registry=registry)
    before_hp = description.pc.hp

    def runner(candidate):
        oracle = NativeOracle(
            candidate,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=7,
            flags=dict(native_area_callbacks=True, native_start_events=True),
        )
        serializer = NativeStats(
            characters=characters,
            monsters=monsters,
            fight_id=candidate.fight.id,
            map_id=1134,
        )
        channel = FramedClient(*tcp_address(endpoint), timeout=20)
        try:
            yield from run_prepared_turn(
                candidate,
                oracle,
                serializer,
                channel,
                deadline=time.monotonic() + 20,
                max_actions=4,
            )
        finally:
            channel.close()

    started = time.monotonic()
    deliveries = list(
        run_shared_turn(
            runtime,
            adapter,
            session,
            runner,
            native_runner_authority=_WORLD_NATIVE_RUNNER,
        )
    )
    actions = [diagnostic["action"] for _, diagnostic in deliveries]
    batches = list(registry.drain(shared.fight.id, session))
    checks = dict(
        moved=any(action.get("type") == "move" for action in actions),
        cast=any(action.get("type") == "cast" for action in actions),
        damaged=shared.fight.actors[7].hp < before_hp,
        ended=any(action.get("type") == "end_turn" for action in actions),
        publication=shared.sequence >= 3
        and len(batches) >= 3
        and all(batch.packets for batch in batches),
        ackArmed=shared.runtime.awaiting_ack is not None
        and shared.ack.turn == shared.runtime.awaiting_ack,
    )
    return dict(
        passed=all(checks.values()),
        checks=checks,
        actions=actions,
        damage=before_hp - shared.fight.actors[7].hp,
        elapsedMs=round((time.monotonic() - started) * 1000, 3),
        scope="shared Registry publication, in-memory encounter and synthetic participant; excludes client ACK",
    )


def forbid_legacy_sdk():
    """Fail the dispatch probe if it opens or lists the legacy SDK tree."""
    root = "/app/ai-service"
    violations = []

    def guard(event, args):
        if event not in ("open", "os.listdir", "os.scandir") or not args:
            return
        try:
            path = os.path.abspath(os.fsdecode(os.fspath(args[0])))
        except (TypeError, ValueError):
            return
        if path == root or path.startswith(root + "/"):
            violations.append(event)
            raise PermissionError("Legacy AI access blocked: " + event)

    sys.addaudithook(guard)
    return violations


def main():
    endpoint = os.environ["WAKIA_PROBE_ENDPOINT"]
    dispatch = os.environ.get("WAKIA_PROBE_DISPATCH") == "1"
    violations = forbid_legacy_sdk() if dispatch else None
    readonly_providers()
    load_bridge(os.environ["WAKIA_PROBE_BRIDGE"])
    result = (
        run_shared(endpoint)
        if os.environ.get("WAKIA_PROBE_SHARED") == "1"
        else (run_dispatched(endpoint) if dispatch else run(endpoint))
    )
    if dispatch:
        result["checks"]["noLegacyAccess"] = not violations
        result["passed"] = result["passed"] and not violations
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
