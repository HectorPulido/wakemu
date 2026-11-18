"""Publish exact native encounter affiliations through existing immutable tables.

The caller owns the local bundle transaction. This changes no live fights,
player state, ordinary AI or native team criteria.
"""


def validate(document):
    from wakfu_server.combat_encounter_roles import SCHEMA
    from wakfu_server import monsters

    fields = {
        "schema",
        "policy",
        "authority",
        "map_id",
        "monster_references",
        "player_team",
        "npc_team",
    }
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "id", "roles"}
        or document["schema"] != "wakemu-encounter-role-publication-v1"
        or not isinstance(document["id"], str)
        or not document["id"]
        or not isinstance(document["roles"], list)
        or not document["roles"]
    ):
        raise ValueError("Malformed encounter role publication")
    policies, scopes = set(), set()
    for row in document["roles"]:
        if (
            not isinstance(row, dict)
            or set(row) != fields
            or row["schema"] != SCHEMA
            or any(
                not isinstance(row[k], str) or not row[k]
                for k in ("policy", "authority")
            )
            or type(row["map_id"]) is not int
            or row["map_id"] <= 0
            or not isinstance(row["monster_references"], list)
            or not row["monster_references"]
            or any(
                type(ref) is not int or ref <= 0 for ref in row["monster_references"]
            )
            or row["monster_references"] != sorted(row["monster_references"])
            or any(type(row[k]) is not int for k in ("player_team", "npc_team"))
            or {row["player_team"], row["npc_team"]} != {0, 1}
        ):
            raise ValueError("Invalid exact native encounter roles")
        scope = row["map_id"], tuple(row["monster_references"])
        if row["policy"] in policies or scope in scopes:
            raise ValueError("Duplicate encounter role policy or exact scope")
        for reference in row["monster_references"]:
            monsters.reference(reference)
        policies.add(row["policy"])
        scopes.add(scope)
    return document["roles"]


def install(db, document):
    rows = validate(document)
    for row in rows:
        values = tuple(
            row[k]
            for k in (
                "policy",
                "authority",
                "map_id",
                "monster_references",
                "player_team",
                "npc_team",
            )
        )
        db.execute(
            "INSERT INTO encounter_role_versions(policy,authority,map_id,monster_references,player_team,npc_team) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            values,
        )
        actual = db.execute(
            "SELECT policy,authority,map_id,monster_references,player_team,npc_team "
            "FROM encounter_role_versions WHERE policy=%s",
            (row["policy"],),
        ).fetchone()
        if actual is None or dict(actual) != {
            key: row[key] for key in row if key != "schema"
        }:
            raise ValueError("Immutable encounter role version differs from its source")
        db.execute(
            "INSERT INTO encounter_role_active(map_id,monster_references,policy) "
            "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (row["map_id"], row["monster_references"], row["policy"]),
        )
        selected = db.execute(
            "SELECT policy FROM encounter_role_active WHERE map_id=%s AND monster_references=%s::integer[]",
            (row["map_id"], row["monster_references"]),
        ).fetchone()
        if selected is None or selected["policy"] != row["policy"]:
            raise ValueError(
                "Another encounter role version already owns this exact scope"
            )
    return dict(id=document["id"], roles=len(rows))
