"""Explicit native snapshots for World lifecycle commit fixtures.

Callers supply offspring identities, references and destinations. No ecology
selection, randomness, allocation, clock observation or path search runs here.
"""

from copy import deepcopy
from wakfu_server.monsters import REFERENCES, owned_instance


def prepared_birth(store, ticket, *, destination, actor_id, reference=6):
    with store.connection() as db:
        row = db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s",
            (ticket["map_id"], ticket["instance_id"], ticket["group_id"]),
        ).fetchone()
    members = list(row["members"])
    parent = next(member for member in members if member["id"] == ticket["monster_id"])
    child = owned_instance(
        reference,
        REFERENCES[reference]["min_level"],
        actor_id,
        map_id=ticket["map_id"],
        instance_id=ticket["instance_id"],
        team=parent["team"],
        x=destination[0],
        y=destination[1],
        z=destination[2],
    )
    return dict(
        expected_members=deepcopy(members), destination=list(destination), child=child
    )
