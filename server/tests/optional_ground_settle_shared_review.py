"""Disposable-schema full Fight and fight_store.settle_shared optional lifecycle."""
from wakfu_server import (
    dungeon_fight_binding,
    dungeon_progression,
    fight_store,
    monsters,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_terrain import map_geometry


def exercise(ctx):
    store, groups = ctx["store"], ctx["groups"]
    instance_id = 11
    available = groups.available(910, instance_id)
    row = available[0]
    key, members = row["key"], row["members"]
    if len(members) < 6:
        raise AssertionError(
            f"expected six native NPCs in optional group, got {len(members)}"
        )

    # Only settlement's real withdrawal/checkpoint relations are absent from
    # the deliberately minimal disposable PG schema.
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS combat_pve_withdrawals(fight_id integer,character_id bigint,PRIMARY KEY(fight_id,character_id))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS fight_checkpoints(fight_id integer PRIMARY KEY,account_id bigint,generation text,revision bigint,status text,snapshot jsonb,updated_at timestamptz)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS fight_health_exits(fight_id integer,character_id bigint,reason text,return_acknowledged_at timestamptz)"
        )
        db.execute(
            "ALTER TABLE objectives_challenge_runs ADD COLUMN IF NOT EXISTS fight_id integer"
        )
        db.execute(
            "INSERT INTO dungeon_difficulty_selections(instance_id,stasis_level,competitive,competitive_max_level) VALUES(%s,2,false,0) ON CONFLICT DO NOTHING",
            (instance_id,),
        )

    def lock_character(db, account_id, generation, character_id):
        row = db.execute(
            "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
            (character_id, account_id),
        ).fetchone()
        if row is None:
            raise ValueError("shared participant character unavailable")

    store.lock_character = lock_character

    geometry = map_geometry(910)
    walkable = {tuple(cell) for cell in geometry["cells"]}
    edges = {tuple(map(tuple, edge)) for edge in geometry["edges"]}
    player = Actor(76, 0, (21, 51, 0), 100, 6, 3, 10, 60, 54, True, max_hp=100)
    opponents = []
    for member in members:
        source = monsters.owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            map_id=910,
            instance_id=instance_id,
            x=member["x"],
            y=member["y"],
            z=member["z"],
            team=1,
        )
        opponents.append(
            Actor(
                source["id"],
                1,
                (source["x"], source["y"], source["z"]),
                source["hp"],
                source["ap"],
                source["mp"],
                source["initiative"],
                source["level"],
                max_hp=source["max_hp"],
            )
        )
    occupied = {player.position} | {actor.position for actor in opponents}
    hero_position = min(
        (cell for cell in walkable if cell not in occupied),
        key=lambda cell: (
            abs(cell[0] - player.position[0]) + abs(cell[1] - player.position[1]),
            cell,
        ),
    )
    hero = Actor(77, 0, hero_position, 90, 6, 3, 9, 60, 54, True, max_hp=90)
    if player.position in {actor.position for actor in opponents}:
        raise AssertionError("native group overlaps player position")
    with store.connection() as db:
        db.execute(
            "INSERT INTO characters(id,account_id,map_id,instance_id,x,y,z,deleted_at) VALUES(77,54,910,%s,%s,%s,%s,NULL)",
            (instance_id, *hero_position),
        )
    check = ctx["check"]

    def new_fight(fight_id):
        return Fight(
            fight_id,
            [player, hero, *opponents],
            walkable,
            {0: walkable, 1: walkable},
            edges,
        )

    def begin_fight(fight_id):
        lease, claimed = groups.claim(key, ctx["generation"], fight_id)
        if claimed != members:
            raise AssertionError("claimed native roster changed")
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) VALUES(%s,'active')", (fight_id,)
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,76,54,0,'lease')",
                (fight_id,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,77,54,0,'lease')",
                (fight_id,),
            )
            bound = dungeon_fight_binding.bind_room_group(
                db, key, 76, fight_id, player_team=0, expected_selection_revision=1
            )
        if bound is None or bound.get("encounter_scope") != "optional":
            raise AssertionError("Fight did not bind the optional encounter")
        return lease, new_fight(fight_id)

    def snapshot():
        with store.connection() as db:
            return {
                "main": dict(
                    db.execute(
                        "SELECT current_room,status,revision FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()
                ),
                "access": dict(
                    db.execute(
                        "SELECT status,revision FROM dungeon_optional_access WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()
                ),
                "encounters": [
                    dict(row)
                    for row in db.execute(
                        "SELECT fight_id,status,result FROM dungeon_room_encounters WHERE instance_id=%s ORDER BY fight_id",
                        (instance_id,),
                    ).fetchall()
                ],
                "group": dict(
                    db.execute(
                        "SELECT status,revision FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                        key,
                    ).fetchone()
                ),
            }

    baseline = snapshot()
    check(
        "two same-account controlled actors and six native NPCs construct a Fight on map910",
        len(opponents) >= 6
        and len([actor for actor in new_fight(799).actors.values() if actor.controlled])
        == 2,
    )
    check(
        "Fight roster uses native room positions and actors",
        all(actor.position in walkable for actor in opponents)
        and player.position in walkable
        and hero.position in walkable,
    )

    lease, defeated_fight = begin_fight(800)
    defeated_fight.phase, defeated_fight.winner = "finished", 1
    with store.connection() as db:
        fight_store.finish(store, db, 54, "lease", 76, 800)

    def settle_defeat(db, participant_rows, current):
        dungeon_progression.lock_encounter_run(db, current.id)
        groups.finish(lease, defeated=False, db=db)
        return dungeon_progression.settle_encounter(db, current)

    defeat_result = fight_store.settle_shared(
        store, 54, "lease", 76, defeated_fight, settle_defeat
    )
    after_defeat = snapshot()
    check(
        "actual shared Fight loss frees optional group and slot",
        defeat_result
        and after_defeat["group"]["status"] == "available"
        and after_defeat["access"]["status"] == "available"
        and after_defeat["encounters"][0]["status"] == "defeat",
    )
    check(
        "loss through settle_shared preserves completed main frontier",
        after_defeat["main"]
        == baseline["main"]
        == {"current_room": 3, "status": "completed", "revision": 4},
    )
    with store.connection() as db:
        checkpoint = db.execute(
            "SELECT status,snapshot->>'phase' AS phase FROM fight_checkpoints WHERE fight_id=800"
        ).fetchone()
    check(
        "shared settlement persisted terminal fight checkpoint",
        checkpoint == {"status": "ended", "phase": "finished"},
    )

    abort_lease, _ = begin_fight(801)
    with store.connection() as db:
        applied = fight_store.abort(
            store,
            54,
            76,
            801,
            expected_generation="lease",
            db=db,
            on_aborted=lambda tx, identity: (
                groups.finish(abort_lease, defeated=False, db=tx),
                dungeon_fight_binding.abort_room_encounter(tx, identity),
            ),
        )
    after_abort = snapshot()
    check(
        "public abort releases same optional group for retry",
        applied
        and after_abort["group"]["status"] == "available"
        and after_abort["access"]["status"] == "available"
        and any(
            row["fight_id"] == 801 and row["status"] == "aborted"
            for row in after_abort["encounters"]
        ),
    )
    check(
        "abort preserves completed main frontier",
        after_abort["main"] == baseline["main"],
    )

    victory_lease, victory_fight = begin_fight(802)
    victory_fight.phase, victory_fight.winner = "finished", 0
    with store.connection() as db:
        fight_store.finish(store, db, 54, "lease", 76, 802)

    def settle_victory(db, participant_rows, current):
        dungeon_progression.lock_encounter_run(db, current.id)
        groups.finish(victory_lease, defeated=True, db=db)
        return dungeon_progression.settle_encounter(db, current)

    victory_result = fight_store.settle_shared(
        store, 54, "lease", 76, victory_fight, settle_victory
    )
    final_state = snapshot()
    replay = fight_store.settle_shared(
        store, 54, "lease", 76, victory_fight, settle_victory
    )
    with store.connection() as db:
        stele_count = db.execute(
            "SELECT count(*) AS n FROM dungeon_stele_encounters"
        ).fetchone()["n"]
        old_rewards = db.execute(
            "SELECT fight_id,character_id,marker FROM fight_reward_awards ORDER BY fight_id"
        ).fetchall()
    check(
        "shared victory permanently closes optional slot and group",
        victory_result
        and final_state["group"]["status"] == "defeated"
        and final_state["access"]["status"] == "victory",
    )
    check(
        "shared victory replay preserves optional and main receipts",
        snapshot() == final_state and final_state["main"] == baseline["main"],
    )
    try:
        groups.claim(key, ctx["generation"], 803)
    except ValueError:
        unavailable = True
    else:
        unavailable = False
    check("permanent optional victory cannot be reclaimed", unavailable)
    check(
        "optional fights add no main-boss stele or rewrite old rewards",
        stele_count == 0
        and old_rewards
        == [
            {
                "fight_id": 507,
                "character_id": 76,
                "marker": "earned-main-boss-reward-unchanged",
            }
        ],
    )
