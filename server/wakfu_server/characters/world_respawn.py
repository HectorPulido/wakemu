"""Owned native13932 world respawn; selected-PC recovery and travel are atomic.

One HP and the unbound Phoenix arrival choices are explicit Wakemu policies.
The native empty request proves neither a healing percentage nor a destination.
"""
from wakfu_server.phoenix_points import point_destination, saved_identity, points
from wakfu_server.nation_state import nation_id
from wakfu_server.item_scenario_teleports import NATION_MAPS
from wakfu_server.world_resurrection import _outside, occupation_packet

LOCATION = ("map_id", "instance_id", "x", "y", "z", "direction")
NEUTRAL_PHOENIX_ID = 31371
INTENT = "world_respawn"


def destination(character):
    identity = saved_identity(character)
    if identity:
        return point_destination(identity), "saved_phoenix"
    map_id = NATION_MAPS.get(nation_id(character))
    if map_id is None:
        return point_destination(NEUTRAL_PHOENIX_ID), "wakemu_unbound_astrub_phoenix"
    candidates = [point for point in points().values() if point["map_id"] == map_id]
    if len(candidates) != 1:
        raise ValueError("La nación no tiene un fénix nativo único disponible")
    return point_destination(candidates[0]["id"]), "wakemu_unbound_nation_phoenix"


def request(
    store,
    positions,
    account_id,
    generation,
    character_id,
    body,
    *,
    source,
    validate_live,
    in_fight=False
):
    """Commit one selected casualty; retain the normal transition until delivery."""
    from wakfu_server import health, health_policy
    from wakfu_server import rift_transition_delivery as delivery
    from wakfu_server.heroes import load_roster

    if not isinstance(body, bytes) or body:
        raise ValueError("Invalid native Phoenix respawn request")
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Termina el regreso del combate antes de volver al fénix")
    if (
        not callable(validate_live)
        or source.get("instance_id") != 0
        or any(type(source.get(key)) is not int for key in LOCATION)
    ):
        raise ValueError("El regreso al fénix requiere la escena pública actual")
    with positions.account_barrier(account_id, blocking=False):
        if validate_live() is not True:
            raise ValueError("La escena del personaje cambió antes de volver al fénix")
        pending = delivery.pending(account_id, generation, character_id)
        if pending is not None:
            metadata = pending.get(INTENT)
            if not isinstance(metadata, dict) or metadata.get("source") != {
                key: source[key] for key in LOCATION
            }:
                raise ValueError(
                    "Completa el traslado pendiente antes de volver al fénix"
                )
            with store.connection() as db:
                store.lock_character(db, account_id, generation, character_id)
                current = store.character(account_id, character_id, db)
                if (
                    current["health_dead"]
                    or current["hp"] <= 0
                    or any(current[key] != pending[key] for key in LOCATION[:-1])
                ):
                    raise ValueError("El regreso confirmado al fénix cambió")
            return dict(character=current, destination=pending, replayed=True)
        positions.flush(
            account_id=account_id, generation=generation, character_id=character_id
        )
        with store.connection() as db:
            store.lock_character(db, account_id, generation, character_id)
            current = store.character(account_id, character_id, db)
            if any(current[key] != source[key] for key in LOCATION):
                raise ValueError(
                    "La posición del personaje cambió antes de volver al fénix"
                )
            if current["health_dead"] is not True or current["hp"] != 0:
                raise ValueError("El personaje ya está vivo")
            roster = load_roster(db, store, account_id, character_id)
            company = (roster["leader"], *roster["heroes"])
            identities = [row["id"] for row in company]
            if any(
                (row["map_id"], row["instance_id"])
                != (current["map_id"], current["instance_id"])
                or not _outside(db, row["id"])
                for row in company
            ):
                raise ValueError(
                    "La compañía aún tiene un regreso de combate pendiente"
                )
            if (
                db.execute(
                    "SELECT 1 FROM dungeon_instance_members m JOIN dungeon_instances i "
                    "ON i.instance_id=m.instance_id WHERE m.character_id=ANY(%s) "
                    "AND m.status='active' AND i.status IN('active','completed') LIMIT 1",
                    (identities,),
                ).fetchone()
                or db.execute(
                    "SELECT 1 FROM rift_instances WHERE status IN('entered','running') "
                    "AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(members) member "
                    "WHERE member::bigint=ANY(%s)) LIMIT 1",
                    (identities,),
                ).fetchone()
            ):
                raise ValueError(
                    "Sal de la instancia de la compañía antes de volver al fénix"
                )
            target, policy = destination(current)
            damage, dead = health_policy.recover_finished_return(
                current["max_hp"], current["hp_damage"], current["health_dead"]
            )
            hp = health_policy.apply_damage(db, current, damage, dead)
            coefficient = health.exploration_coefficient(current["max_hp"], hp)
            now = store.now()
            db.execute(
                "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
                "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                "coefficient=excluded.coefficient,last_at=excluded.last_at",
                (character_id, hp, now, coefficient, now),
            )
            moved = store.transition_map_in_transaction(
                db, account_id, generation, character_id, current, target
            )
            if validate_live() is not True:
                raise ValueError(
                    "La escena del personaje cambió durante su regreso al fénix"
                )
        # A marked normal transition survives transport/position-journal failure.
        # Only the caller's own selected-PC intent can authorize an alive retry.
        target = dict(
            target,
            **{
                INTENT: dict(
                    source={key: source[key] for key in LOCATION},
                    policy=policy,
                    position_released=False,
                    occupation_published=False,
                )
            }
        )
        delivery.queue(
            [dict(account_id=account_id, generation=generation, id=character_id)],
            target,
        )
        return dict(character=moved, destination=target, replayed=False)


def release_position(
    store, positions, account_id, generation, character_id, destination
):
    """Retain exact normal Redis revision ACKs before any native scene handoff."""
    metadata = destination.get(INTENT)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("source"), dict):
        raise ValueError("Missing committed Phoenix transition authority")
    positions.release_committed_transition(
        account_id, generation, character_id, metadata["source"], destination
    )


def publication(character):
    from wakfu_server import health

    return (
        (
            12436,
            health.packet(
                character["id"],
                character["hp"],
                health.exploration_coefficient(character["max_hp"], character["hp"]),
            ),
        ),
        occupation_packet(character["id"], dead=False),
    )
