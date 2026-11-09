import os, random, uuid, traceback, json, time
from wakia_native_probe import readonly_providers, load_bridge

readonly_providers()
load_bridge(os.environ["WAKIA_PROBE_DIR"] + "/wakfu_ai")
import importlib.util, sys

spec = importlib.util.spec_from_file_location(
    "wakfu_server.combat_walk_surface_policy",
    os.environ["WAKIA_PROBE_DIR"] + "/combat_walk_surface_policy.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_terrain import local_arena
from wakfu_server.equipment_stats import combat_resources, effective_character
from wakfu_server.health import maximum
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import default_deck
from wakfu_server.combat_state import Actor
from wakfu_server.combat_global_pv_collections import register_global_fighter
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import build_snapshot


def person(i, pos, map_id, level):
    hp = 60
    return effective_character(
        dict(
            id=i,
            account_id=i - 4,
            map_id=map_id,
            instance_id=0,
            breed=15,
            level=level,
            hp=hp,
            max_hp=maximum(15, level),
            active_build_index=0,
            x=pos[0],
            y=pos[1],
            z=pos[2],
            builds={},
            inventory_items=[],
        )
    )


try:
    scenario = os.environ["WAKIA_MAP527_SCENARIO"]
    map_id, player_level, monster_level, actor_mp = 527, 50, 10, None
    if scenario == "455":
        players = [(1, 36, 0), (3, 36, 0)]
        ps = [(1, 40, 0), (0, 41, 0), (3, 40, 0)]
    elif scenario == "456":
        players = [(2, 37, 0), (1, 36, 0)]
        ps = [(-3, 35, 0), (-4, 36, 0), (-5, 36, 0)]
    elif scenario == "custom":
        from pathlib import Path

        data = json.loads(
            (Path(os.environ["WAKIA_PROBE_DIR"]) / "fixture.json").read_text()
        )
        if not isinstance(data, dict) or set(data) - {
            "mapId",
            "players",
            "monsters",
            "playerLevel",
            "monsterLevel",
            "actorMp",
        }:
            raise ValueError(
                "Fixture accepts only map, synthetic positions, levels and actor MP"
            )
        map_id = data.get("mapId")
        player_level = data.get("playerLevel", 50)
        monster_level = data.get("monsterLevel", 10)
        actor_mp = data.get("actorMp")
        players, ps = data.get("players"), data.get("monsters")
        if (
            type(map_id) is not int
            or map_id <= 0
            or type(player_level) is not int
            or not 1 <= player_level <= 230
            or type(monster_level) is not int
            or not 1 <= monster_level <= 230
            or (actor_mp is not None and (type(actor_mp) is not int or actor_mp < 0))
            or not isinstance(players, list)
            or len(players) != 2
            or not isinstance(ps, list)
            or len(ps) != 3
            or any(
                not isinstance(p, list)
                or len(p) != 3
                or any(type(v) is not int for v in p)
                for p in players + ps
            )
        ):
            raise ValueError("Invalid synthetic map fixture")
        players, ps = [tuple(p) for p in players], [tuple(p) for p in ps]
    else:
        raise ValueError("Unsupported synthetic scenario")
    chars = {
        7: person(7, players[0], map_id, player_level),
        8: person(8, players[1], map_id, player_level),
    }
    rs = {i: combat_resources(c) for i, c in chars.items()}
    mons = {
        -7
        - i: owned_instance(
            1,
            monster_level,
            -7 - i,
            map_id=map_id,
            x=x,
            y=y,
            z=z,
            team=1,
            instance_id=0,
        )
        for i, (x, y, z) in enumerate(ps)
    }
    arena = local_arena(
        map_id, 1, players[0], ps, relocate_monsters=False, variation_seed=17
    )
    f, _ = create_placement(
        chars[7],
        list(mons.values()),
        arena,
        fight_id=1,
        player_ap=rs[7]["ap"],
        player_mp=rs[7]["mp"],
        player_wp=rs[7]["wp"],
        player_initiative=rs[7]["initiative"],
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    r = rs[8]
    f.actors[8] = Actor(
        8,
        0,
        players[1],
        chars[8]["hp"],
        r["ap"],
        r["mp"],
        r["initiative"],
        player_level,
        4,
        True,
        max_hp=chars[8]["max_hp"],
    )
    f.actors[8].native_obstacle_id = next(
        i
        for i in range(127)
        if i not in {a.native_obstacle_id for j, a in f.actors.items() if j != 8}
    )
    register_global_fighter(f, 8)
    f.native_qi_fresh_actor_order = tuple(f.actors)
    initialize_fight_snapshots(
        f,
        characters=chars,
        monsters=mons,
        wp_resources={
            **{i: (r["wp"], r["wp"]) for i, r in rs.items()},
            **{i: (m["wp"], m["wp"]) for i, m in mons.items()},
        },
        running_effects={i: () for i in f.actors},
        initial_effect_uid=1,
    )
    f.ready(3)
    f.ready(4)
    decks = {i: default_deck(c) for i, c in chars.items()}
    f, _ = prepare_server_initialization(
        chars[7],
        mons,
        f,
        3,
        decks[7],
        action_id=1,
        rng=random.Random(17),
        fight_start=False,
        player_characters=chars,
        deck_blobs=decks,
    )
    f, _ = prepare_server_initialization(
        chars[8],
        mons,
        f,
        4,
        decks[8],
        action_id=2,
        rng=random.Random(17),
        fight_start=True,
        player_characters=chars,
        deck_blobs=decks,
    )
    f.order = [-7, -8, -9, 7, 8]
    f.turn_index = 0
    f.current.turn_count = 1
    if actor_mp is not None:
        if actor_mp > f.current.mp:
            raise ValueError("Fixture actor MP exceeds its native starting resources")
        from wakfu_server.combat_resource_pa_notifications import shift_resource_current

        shift_resource_current(f, f.current, 3, f.current.mp - actor_mp, subtract=True)
    runtime = RuntimeMessages(f)
    runtime.action_id = 1
    runtime.tactical_encounter_id = uuid.uuid4().hex
    oracle = NativeOracle(
        runtime,
        characters=chars,
        monsters=mons,
        decks=decks,
        excluded_decks={i: frozenset() for i in chars},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
    from wakfu_server.combat_timeline_snapshot import current_wire_turn
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.wakia_bridge.wakfu_ai.transport.framed import FramedClient
    import struct

    provider = OwnedExpirationFactory(
        characters=chars,
        monsters=mons,
        decks=decks,
        actor_id=7,
        fight_start=True,
        area_callbacks=True,
    )
    runtime.expiration_runtime_factory = provider
    runtime.turn_start_provider = provider.turn_start
    runtime.turn_end_provider = provider.turn_end
    serializer = NativeStats(characters=chars, monsters=mons, fight_id=f.id, map_id=527)
    if os.environ.get("WAKIA_PLANNER_TRANSPORT") == "file":
        from pathlib import Path

        root = Path(os.environ["WAKIA_PROBE_DIR"])

        class FileTransport:
            def __init__(self):
                self.count = 0

            def request(self, path, request, *, deadline):
                if path != "/jondo/decide":
                    raise ValueError("Unexpected planner path")
                self.count += 1
                request_file = root / ("request-%d.json" % self.count)
                temporary = root / ("request-%d.tmp" % self.count)
                response_file = root / ("response-%d.json" % self.count)
                temporary.write_text(json.dumps(request, separators=(",", ":")))
                temporary.replace(request_file)
                while not response_file.exists():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Isolated C# planner response deadline")
                    time.sleep(0.02)
                response = json.loads(response_file.read_text())
                return response["status"], response["response"]

            def close(self):
                pass

        client = FileTransport()
    else:
        client = FramedClient(*tcp_address("tcp://wakia:8091"), timeout=30)
    started = time.monotonic()
    log = []
    acks = 0
    try:
        for step in range(100):
            if runtime.fight.phase != "active":
                break
            actor = runtime.fight.current
            if actor is None:
                raise ValueError("No current actor")
            if actor.controlled:
                owner = actor.owner_id
                runtime.end_turn(owner, actor.id, current_wire_turn(runtime.fight))
                log.append(("script_pass", actor.id))
            else:
                deliveries = list(
                    run_prepared_turn(
                        runtime,
                        oracle,
                        serializer,
                        client,
                        deadline=time.monotonic() + 60,
                        max_actions=5,
                    )
                )
                kinds = [r["action"]["type"] for _, r in deliveries]
                log.append(("wakia", actor.id, kinds))
                if not kinds:
                    raise ValueError("WakIA produced no action")
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                acks += 1
            print(
                "TURN",
                step,
                "actor",
                actor.id,
                "phase",
                runtime.fight.phase,
                "hp",
                [(i, x.hp) for i, x in runtime.fight.actors.items()],
                "ack",
                runtime.awaiting_ack is None,
                flush=True,
            )
        result = dict(
            scenario=scenario,
            phase=runtime.fight.phase,
            winner=runtime.fight.winner,
            turns=len(log),
            acks=acks,
            awaitingAck=runtime.awaiting_ack,
            pendingCount=len(runtime.pending),
            elapsedMs=round((time.monotonic() - started) * 1000, 2),
            actions=log,
        )
        print("RESULT", json.dumps(result), flush=True)
        if (
            result["phase"] != "finished"
            or result["winner"] != 1
            or result["awaitingAck"] is not None
            or result["pendingCount"]
            or not any(x[0] == "script_pass" for x in log)
        ):
            raise ValueError(
                "Synthetic fight did not finish with expected winner and cleared ACKs"
            )
    finally:
        client.close()
except Exception as e:
    print("FAIL", repr(e), flush=True)
    traceback.print_exc()
    raise
