import os, sys, random, uuid, traceback, time, json, struct
from pathlib import Path

# The wrapper uses this exact PID plus Linux process start time to stop only
# this private worker on timeout, interruption, or failed host execution.
worker_stat = Path("/proc/self/stat").read_text().split()
worker_pid = os.getpid()
(Path(os.environ["WAKIA_PROBE_DIR"]) / "worker-identity.json").write_text(
    json.dumps({"pid": worker_pid, "start": worker_stat[21]})
)

from wakia_native_probe import readonly_providers, load_bridge

readonly_providers()
load_bridge(os.environ["WAKIA_PROBE_DIR"] + "/wakfu_ai")
from wakfu_server.storage.store import Store
from wakfu_server.equipment_stats import effective_character, combat_resources, bonuses
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
from wakfu_server.spells import default_deck
from wakfu_server.combat_attachment_authority import for_characters

try:
    store = Store(os.environ["WAKFU_DATABASE_URL"])
    with store.connection() as db:
        rows = db.execute(
            "SELECT id,account_id FROM characters WHERE lower(name)=lower(%s) AND deleted_at IS NULL",
            (os.environ["WAKIA_CHARACTER_NAME"],),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("Character lookup is not unique")
        identity, account = rows[0]["id"], rows[0]["account_id"]
        source = store.character(account, identity, db)
    character = effective_character(source)
    resources = combat_resources(character)
    index = character.get("active_build_index", 0)
    builds = character.get("builds", {})
    build = builds.get(index, builds.get(str(index), {}))
    raw = build.get("deck") if isinstance(build, dict) else None
    deck = bytes.fromhex(raw) if raw else default_deck(character)
    pos = (character["x"], character["y"], character["z"])
    npc_pos = (pos[0] + 1, pos[1], pos[2])
    mid = -7
    monster_level = int(os.environ.get("WAKIA_MONSTER_LEVEL") or character["level"])
    monster_ref = int(os.environ.get("WAKIA_MONSTER_REF") or 1)
    if not 1 <= monster_level <= 230:
        raise ValueError("Invalid monster level")
    if not 1 <= monster_ref < 2**31:
        raise ValueError("Invalid monster reference")
    monster = owned_instance(
        monster_ref,
        monster_level,
        mid,
        map_id=character["map_id"],
        x=npc_pos[0],
        y=npc_pos[1],
        z=npc_pos[2],
        team=1,
        instance_id=character.get("instance_id", 0),
    )
    monsters = {mid: monster}
    arena = local_arena(
        character["map_id"],
        character.get("instance_id", 0),
        pos,
        npc_pos,
        relocate_monsters=True,
        variation_seed=17,
    )
    fight, _ = create_placement(
        character,
        monster,
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
        characters={identity: character},
        monsters=monsters,
        wp_resources={
            identity: (resources["wp"], resources["wp"]),
            mid: (monster["wp"], monster["wp"]),
        },
        running_effects={key: () for key in fight.actors},
        initial_effect_uid=1,
    )
    fight.ready(account)
    attachments = for_characters(store, {identity: character})
    fight, _ = prepare_server_initialization(
        character,
        monsters,
        fight,
        account,
        deck,
        action_id=1,
        rng=random.Random(17),
        fight_start=True,
        player_characters={identity: character},
        deck_blobs={identity: deck},
        attachment_authority=attachments,
    )
    runtime = RuntimeMessages(fight)
    runtime.action_id = 1
    runtime.tactical_encounter_id = uuid.uuid4().hex
    oracle = NativeOracle(
        runtime,
        characters={identity: character},
        monsters=monsters,
        decks={identity: deck},
        excluded_decks={identity: frozenset()},
        viewer_id=identity,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    from wakfu_server.combat_ai_control import set_native_ai_control
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from pathlib import Path

    player = fight.actors[identity]
    set_native_ai_control(player, True)
    # Mirror the headless duel bot's controller authority so its summons
    # receive AI turns without changing their native ownership flags.
    fight.native_friendly_duel_ai_character_id = identity
    if not effective_server_controlled(fight, player):
        raise ValueError("Private AI control unavailable")
    provider = OwnedExpirationFactory(
        characters={identity: character},
        monsters=monsters,
        decks={identity: deck},
        actor_id=identity,
        fight_start=True,
        area_callbacks=True,
    )
    runtime.expiration_runtime_factory = provider
    runtime.turn_start_provider = provider.turn_start
    runtime.turn_end_provider = provider.turn_end
    serializer = NativeStats(
        characters={identity: character},
        monsters=monsters,
        fight_id=fight.id,
        map_id=character["map_id"],
    )
    root = Path(os.environ["WAKIA_PROBE_DIR"])

    class FileTransport:
        def __init__(self):
            self.count = 0

        def request(self, path, request, *, deadline):
            self.count += 1
            n = self.count
            p = root / ("request-%d.json" % n)
            tmp = root / ("request-%d.tmp" % n)
            reply = root / ("response-%d.json" % n)
            tmp.write_text(json.dumps(request, separators=(",", ":")))
            tmp.replace(p)
            while not reply.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("planner response deadline")
                time.sleep(0.02)
            answer = json.loads(reply.read_text())
            return answer["status"], answer["response"]

        def close(self):
            pass

    transport = FileTransport()
    started = time.monotonic()
    log = []
    acks = 0
    print(
        "PROFILE",
        json.dumps(
            dict(
                level=character["level"],
                breed=character["breed"],
                hp=character["hp"],
                maxHp=character["max_hp"],
                equipmentCount=len(bonuses(source)["equipped_uids"]),
                deckBytes=len(deck),
                monsterLevel=monster_level,
                monsterRef=monster_ref,
                initializedHp=player.hp,
                initializedMaxHp=player.max_hp,
            )
        ),
        flush=True,
    )
    for turn in range(50):
        if runtime.fight.phase != "active":
            break
        actor = runtime.fight.current
        if actor is None:
            raise ValueError("Missing fight actor")
        player_turn = actor.id == identity
        player_side = actor.team == player.team
        if not effective_server_controlled(runtime.fight, actor):
            raise ValueError("Actor is not AI controlled")
        if player_turn:
            print(
                "PLAYER_OWNED_SPELLS",
                len(oracle.owned_spells(runtime.fight)),
                flush=True,
            )
        records = list(
            run_prepared_turn(
                runtime,
                oracle,
                serializer,
                transport,
                deadline=time.monotonic() + 60,
                max_actions=6,
            )
        )
        actions = [r["action"] for _, r in records]
        if not actions:
            raise ValueError("AI produced no actions")
        log.append(
            dict(
                side="player"
                if player_turn
                else "summon"
                if player_side
                else "monster",
                actions=[
                    dict(type=a.get("type"), spellId=a.get("spellId")) for a in actions
                ],
            )
        )
        if runtime.awaiting_ack is not None:
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            acks += 1
        print(
            "TURN",
            turn,
            "side",
            "player" if player_turn else "summon" if player_side else "monster",
            "playerHp",
            runtime.fight.actors[identity].hp,
            "monsterHp",
            runtime.fight.actors[mid].hp,
            "actions",
            [a.get("type") for a in actions],
            "ack",
            runtime.awaiting_ack is None,
            flush=True,
        )
    result = dict(
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
        or result["awaitingAck"] is not None
        or result["pendingCount"]
    ):
        raise ValueError("Fight did not finish with cleared acknowledgments")
except Exception as e:
    print("FAIL", type(e).__name__, str(e), flush=True)
    raise SystemExit(1)
