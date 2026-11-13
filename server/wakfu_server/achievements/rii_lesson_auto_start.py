"""Find a server-created, owner-receipted lesson encounter to auto-start."""

KEYS = {
    10574: ("rii-orientation-sack:", "reconstructed_rii_orientation_sack"),
    10575: ("rii-element-sack:", "reconstructed_rii_element_sack"),
    10576: ("rii-distance-sack:", "reconstructed_rii_distance_sack"),
    10608: ("rii-los-sack:", "reconstructed_rii_los_sack"),
    10609: ("rii-area-sack:", "reconstructed_rii_area_sack"),
    10610: ("rii-movement-sack:", "reconstructed_rii_movement_sack"),
    10611: ("rii-states-sack:", "reconstructed_rii_states_sack"),
}


def target(db, groups, owner, objective):
    """Return an available target with an exact durable owner receipt."""
    prefix, kind = KEYS[objective]
    matches = []
    for group in groups.available(1388, 0):
        for actor in group["members"]:
            identity = actor.get("id")
            if type(identity) is not int or identity >= 0 or actor.get("ref") != 5466:
                continue
            row = db.execute(
                "SELECT payload FROM character_achievement_events "
                "WHERE character_id=%s AND event_key=%s",
                (owner, prefix + str(-identity)),
            ).fetchone()
            if row is None:
                continue
            payload = row["payload"]
            if (
                isinstance(payload, dict)
                and payload.get("kind") == kind
                and payload.get("owner") == owner
                and payload.get("actor_id") == identity
                and payload.get("ref") == 5466
            ):
                matches.append((group["key"], actor))
                break
    if len(matches) != 1:
        raise ValueError("Rii lesson requires one available owned encounter")
    return matches[0][1]
