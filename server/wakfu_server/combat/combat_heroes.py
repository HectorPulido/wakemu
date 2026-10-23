"""Atomic admission of actual owned heroes under their main character lease."""

from copy import deepcopy

from wakfu_server.characters.heroes import load_roster
from wakfu_server.fight_store import _require_transaction, _health_baseline
from wakfu_server.combat_join_registration import register_joined_fighter


def frozen_main_sessions(db, store, member_ids):
    """Resolve frozen company members to real selected-main account sessions."""
    identities = tuple(member_ids)
    if not identities or len(set(identities)) != len(identities) or len(identities) > 6:
        raise ValueError("Invalid frozen combat company")
    rows = db.execute(
        "SELECT c.id,c.account_id,s.character_id AS main_id,s.generation "
        "FROM characters c JOIN sessions s ON s.account_id=c.account_id "
        "WHERE c.id=ANY(%s) AND c.deleted_at IS NULL AND s.expires_at>%s "
        "ORDER BY c.account_id,c.id",
        (list(identities), store.now()),
    ).fetchall()
    if {row["id"] for row in rows} != set(identities):
        raise ValueError("Frozen company has an unavailable account session")
    result = []
    for account_id in sorted({row["account_id"] for row in rows}):
        owned = [row for row in rows if row["account_id"] == account_id]
        main = owned[0]["main_id"]
        if main not in {row["id"] for row in owned}:
            raise ValueError("Frozen company omits its selected main")
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, owned[0]["generation"], main)
        db.execute(
            "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (account_id,),
        )
        roster = load_roster(db, store, account_id, main)
        actual = {main} | {hero["id"] for hero in roster["heroes"]}
        if actual != {row["id"] for row in owned}:
            raise ValueError("Frozen company differs from the real owned hero roster")
        result.append(
            {"id": main, "account_id": account_id, "generation": owned[0]["generation"]}
        )
    return tuple(result)


def player_actor(character, team):
    """Build the same native stat snapshot used by an ordinary joining player."""
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_orientation import INITIAL_PLAYER_DIRECTION
    from wakfu_server.combat_actor_snapshot import build_player_snapshot
    from wakfu_server.equipment_stats import combat_resources
    from wakfu_server.builds import effective_sheet_level

    resources = combat_resources(character)
    actor = Actor(
        character["id"],
        team,
        tuple(character[k] for k in ("x", "y", "z")),
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        effective_sheet_level(character, character.get("active_build_index", 0)),
        character["account_id"],
        True,
        max_hp=character["max_hp"],
        direction=INITIAL_PLAYER_DIRECTION,
    )
    build_player_snapshot(
        character,
        actor,
        wp_current=resources["wp"],
        wp_maximum=resources["wp"],
        running_effects=(),
    ).install(actor)
    actor.native_resource_numeric_observers = {4: ()}
    return actor


def admit_owned_heroes(
    db, store, session, fight, *, frozen_members=None, private_scene=None
):
    """Return an unpublished candidate; caller publishes only after DB commit.

    Main membership must already exist in this transaction. Savepoint rollback
    protects callers that catch admission errors without aborting that transaction.
    No hero session is created: all participants retain the real main's generation.
    """
    _require_transaction(db)
    with db.transaction():
        db.execute(
            "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (session.account_id,)
        ).fetchone()
        store.lock_character(
            db, session.account_id, session.generation, session.character_id
        )
        db.execute(
            "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (session.account_id,),
        ).fetchone()
        row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
        ).fetchone()
        main = db.execute(
            "SELECT team,session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (fight.id, session.character_id, session.account_id),
        ).fetchone()
        if (
            row is None
            or row["status"] != "placement"
            or fight.phase != "placement"
            or main is None
            or main["session_generation"] != session.generation
        ):
            raise ValueError(
                "Hero admission requires durable selected-main placement membership"
            )
        team = main["team"]
        leader = fight.actors.get(session.character_id)
        if (
            leader is None
            or not leader.controlled
            or leader.owner_id != session.account_id
            or leader.team != team
        ):
            raise ValueError("Hero admission requires the actual owning main actor")
        roster = load_roster(db, store, session.account_id, session.character_id)
        durable_leader = roster["leader"]
        if private_scene is not None:
            from wakfu_server.haven_ranch import RanchSession

            if not isinstance(private_scene, RanchSession):
                raise ValueError("Combat admission requires a trusted Ranch session")
            private_scene.validate_lease(session.generation)
            live = private_scene.inside
            if (
                live["id"] != session.character_id
                or live["account_id"] != session.account_id
                or (live["map_id"], live["instance_id"])
                != (session.map_id, session.instance_id)
            ):
                raise ValueError(
                    "Ranch combat admission differs from its selected main"
                )
            roster["leader"] = private_scene.refresh(live, durable_leader)
        if (roster["leader"]["map_id"], roster["leader"].get("instance_id", 0)) != (
            session.map_id,
            session.instance_id,
        ):
            raise ValueError("Main character moved outside the admitted world instance")
        from wakfu_server.characters.heroes import follow_main

        companions = (
            follow_main(
                db, store, session.account_id, session.generation, session.character_id
            )
            if private_scene is None
            else roster
        )
        heroes = companions["heroes"]
        if frozen_members is not None:
            expected = {
                row["id"]
                for row in db.execute(
                    "SELECT id FROM characters WHERE account_id=%s AND id=ANY(%s)",
                    (session.account_id, list(frozen_members)),
                ).fetchall()
            }
            if expected != {session.character_id} | {hero["id"] for hero in heroes}:
                raise ValueError(
                    "Frozen combat company differs from the current owned roster"
                )
        occupied = {actor.position for actor in fight.actors.values()}
        cells = sorted(set(fight.placement[team]) - occupied)
        population = sum(actor.team == team for actor in fight.actors.values())
        if population + len(heroes) > 6 or len(cells) < len(heroes):
            raise ValueError("Insufficient team capacity for the complete hero roster")
        candidate = deepcopy(fight) if heroes else fight
        sources, actors = {}, []
        from wakfu_server import territory_bonuses

        for character, position in zip(heroes, cells):
            identity = character["id"]
            context = dict(character)
            context.update(
                {
                    key: roster["leader"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                }
            )
            territory_bonuses.reconcile_owned(
                store,
                session.account_id,
                session.generation,
                context,
                db=db,
                selected_character_id=session.character_id,
            )
            baseline = _health_baseline(db, session.account_id, identity)
            character = store.character(session.account_id, identity, db)
            if baseline[0] <= 0 or baseline[3] or identity in candidate.actors:
                raise ValueError("Hero is dead or already admitted")
            if any(
                character[k] != durable_leader[k] for k in ("map_id", "instance_id")
            ):
                raise ValueError("Hero is outside the main world instance")
            if db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') "
                "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id "
                "AND w.character_id=p.character_id) LIMIT 1",
                (identity,),
            ).fetchone():
                raise ValueError("Hero already has durable combat membership")
            from wakfu_server.characters.starter_decks import (
                initialize as initialize_decks,
            )

            initialize_decks(db, character)
            character = store.character(session.account_id, identity, db)
            # Heroes follow their owner's live exterior position. Their
            # durable coordinates can lag behind a walk within the same map.
            character = {
                **character,
                **{
                    key: roster["leader"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                },
            }
            character = territory_bonuses.attach_character(db, character)
            actor = player_actor(character, team)
            register_joined_fighter(candidate, actor, position)
            sources[identity] = character
            actors.append(actor)
            db.execute(
                "INSERT INTO combat_fight_participants "
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,entry_max_hp,"
                "entry_hp_damage,entry_health_dead) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    fight.id,
                    identity,
                    session.account_id,
                    team,
                    session.generation,
                    *baseline,
                ),
            )
            from .combat_consumable_lifecycle import enter_participant

            enter_participant(
                store, db, identity, fight.id, generation=session.generation
            )
            from wakfu_server.health_store import timestamp

            now = timestamp(int(store.clock() * 1000))
            db.execute(
                "INSERT INTO character_regeneration "
                "(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,0,%s) "
                "ON CONFLICT(character_id) DO UPDATE SET initial_hp=EXCLUDED.initial_hp,"
                "started_at=EXCLUDED.started_at,coefficient=0,last_at=EXCLUDED.last_at",
                (identity, character["hp"], now, now),
            )
        candidate._check_positions()
        return {
            "fight": candidate,
            "characters": sources,
            "actors": tuple(actors),
            "leader": roster["leader"],
            "roster_revision": roster["revision"],
        }
