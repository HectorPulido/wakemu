"""Native roster for ordinary player characters, excluding hero/companion rows.

Account association and portrait sex are taken from authoritative characters.
Effective levels and active-fight identities must be supplied by the caller's
current gameplay state; membership storage does not infer them from captures.
"""
from .party_wire import roster


def packet(snapshot, *, effective_levels, fighting_ids=()):
    if snapshot is None:
        return None
    members = []
    fighting = set(fighting_ids)
    for row in snapshot["members"]:
        if type(row.get("sex")) is not bool or type(row.get("health_dead")) is not bool:
            raise ValueError("Missing authoritative party appearance or death state")
        if row["health_dead"] != (row["hp"] == 0):
            raise ValueError("Party death state disagrees with health")
        if row["id"] not in effective_levels:
            raise ValueError("Missing current party member effective level")
        members.append(
            dict(
                id=row["id"],
                association_id=row["account_id"],
                name=row["name"],
                breed=row["breed"],
                portrait_variant=int(row["sex"]),
                native_identity_flag=False,
                level=row["level"],
                effective_level=effective_levels[row["id"]],
                in_fight=row["id"] in fighting,
                dead=row["health_dead"],
                hp=row["hp"],
                max_hp=row["max_hp"],
            )
        )
    return roster(snapshot["party_id"], snapshot["leader_id"], members)
