"""Offer the native join modal to nearby real party members during placement.

Native cvh (13599) carries an actor ID. ciu resolves that world actor and opens
fight.join.request; accepting sends coK (12197), whose acceptance is normalized to normal join admission.
This notification does not admit participants or change their hero selection.
"""
import struct


def packet(actor_id):
    if type(actor_id) is not int or not 0 < actor_id < 2**63:
        raise ValueError("Invalid party combat invitation actor")
    return 13599, struct.pack(">q", actor_id)


def notify(store, world, sessions, shared, starter_id):
    """Publish best-effort prompts after the complete fight was registered.

    Distance is a local policy of 25 horizontal cells. Session and combat
    admission are checked again by their authoritative handlers on acceptance.
    Never hold shared/world locks while querying SQL or writing to a socket.
    """
    with shared.lock:
        fight = shared.fight
        actor = fight.actors.get(starter_id)
        if (
            fight.phase != "placement"
            or shared.auto_locked
            or getattr(shared, "is_duel", False)
            or actor is None
            or not actor.controlled
            or actor.hp <= 0
        ):
            return 0
        location = (shared.map_id, shared.instance_id)
        occupied = {a.position for a in fight.actors.values() if a.hp > 0}
        if not (fight.placement[actor.team] - occupied):
            return 0
        participant_ids = {
            member.character_id for member in shared.participants.values()
        }
    starter = world.live_identity(character_id=starter_id)
    if starter is None:
        return 0
    starter_character = starter[1]
    if (
        starter_character["map_id"],
        starter_character.get("instance_id", 0),
    ) != location:
        return 0
    with store.connection() as db:
        members = db.execute(
            "SELECT m.character_id FROM player_party_members m "
            "JOIN player_party_members source ON source.party_id=m.party_id "
            "WHERE source.character_id=%s AND m.character_id<>%s "
            "AND NOT EXISTS (SELECT 1 FROM combat_fight_participants p "
            "JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=m.character_id "
            "AND f.status IN ('placement','active')) ORDER BY m.character_id",
            (starter_id, starter_id),
        ).fetchall()
    delivered = 0
    for row in members:
        character_id = row["character_id"]
        if character_id in participant_ids or sessions.lookup_character(character_id):
            continue
        identity = world.live_identity(character_id=character_id)
        if identity is None:
            continue
        generation, character = identity
        if (
            (character["map_id"], character.get("instance_id", 0)) != location
            or character.get("hp", 0) <= 0
            or character.get("health_dead", False)
            or character["account_id"] == starter_character["account_id"]
            or max(
                abs(character["x"] - starter_character["x"]),
                abs(character["y"] - starter_character["y"]),
            )
            > 25
            or not store.current_character_session(
                character["account_id"], generation, character_id
            )
        ):
            continue
        delivered += bool(world.send_to(character_id, generation, *packet(starter_id)))
    return delivered


def accepted_join_request(body):
    """Convert coK12197 acceptance into coU13241; refusal/timeout is a no-op.

    ciu bootstrap callbacks 22/23/24 call np/no/nn: respectively true/false/
    false. The coK boolean is acceptance, unlike coU's autoLock boolean.
    """
    if len(body) != 9:
        raise ValueError("Invalid party fight answer length")
    target_id, accepted = struct.unpack(">qB", body)
    if target_id <= 0 or accepted not in (0, 1):
        raise ValueError("Invalid party fight answer")
    return struct.pack(">qB", target_id, 0) if accepted else None
