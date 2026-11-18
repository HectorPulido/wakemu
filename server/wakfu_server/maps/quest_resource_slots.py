"""Profile-pinned public story resources using ordinary harvest occupations.

Native resource/action metadata supplies duration, criteria and depletion. Exact
placements and replenishment are explicit reviewed server reconstruction. Quest
progress still comes only from the trusted committed action event.
"""
from copy import deepcopy
from hashlib import sha256
import json

from psycopg.types.json import Jsonb


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def ready(db):
    return db.execute(
        "SELECT to_regclass('quest_resource_slots') IS NOT NULL AS ready"
    ).fetchone()["ready"]


def validate(profile, definitions, geometry):
    from wakfu_server.planting import RESOURCES
    from wakfu_server.achievements.mission_toolkit_contract import definitions_by_id

    if (
        type(profile) is not dict
        or set(profile) - {"owned_story", "loot_tables"}
        != {
            "schema",
            "id",
            "provenance",
            "map_id",
            "quest_id",
            "objective_id",
            "resource_actions",
            "placements",
            "replenishment",
            "geometry_sha256",
        }
        or profile["schema"] != "quest-resource-slots-v1"
    ):
        raise ValueError("Invalid quest resource profile")
    if not all(type(profile[k]) is str and profile[k] for k in ("id", "provenance")):
        raise ValueError("Missing quest resource provenance")
    scope = profile.get("owned_story")
    if scope is not None and (
        not isinstance(scope, dict)
        or set(scope)
        != {"controller_id", "owner_id", "instance_id", "native_sources_sha256"}
        or not isinstance(scope["controller_id"], str)
        or not scope["controller_id"]
        or any(
            type(scope[k]) is not int or scope[k] <= 0
            for k in ("owner_id", "instance_id")
        )
        or not isinstance(scope["native_sources_sha256"], str)
        or len(scope["native_sources_sha256"]) != 64
    ):
        raise ValueError("Quest resource lacks its original private owner source")
    if profile["replenishment"] != "reviewed_immediate_after_native_depletion":
        raise ValueError("Unsupported quest resource replenishment")
    if any(
        type(profile[k]) is not int or profile[k] <= 0
        for k in ("map_id", "quest_id", "objective_id")
    ):
        raise ValueError("Invalid quest resource native identity")
    by_id = definitions_by_id(definitions)
    quest = by_id.get(profile["quest_id"])
    objectives = (
        []
        if quest is None
        else [o for o in quest["cjJ"] if o["d"] == profile["objective_id"]]
    )
    if len(objectives) != 1:
        raise ValueError("Quest resource objective is absent from native definitions")
    if (
        geometry["map_id"] != profile["map_id"]
        or digest(geometry) != profile["geometry_sha256"]
    ):
        raise ValueError("Quest resource native surface pin differs")
    cells = {tuple(p) for p in geometry["cells"]}
    edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    if type(profile["resource_actions"]) is not list or not profile["resource_actions"]:
        raise ValueError("Quest resource actions are absent")
    actions = {}
    for row in profile["resource_actions"]:
        if type(row) is not dict or set(row) - {"native_loot"} != {
            "resource_reference",
            "stage",
            "action_id",
            "resource_sha256",
            "action_sha256",
        }:
            raise ValueError("Invalid pinned quest resource action")
        ref, stage, action = (
            row[k] for k in ("resource_reference", "stage", "action_id")
        )
        if (
            any(type(v) is not int or v <= 0 for v in (ref, stage, action))
            or ref in actions
        ):
            raise ValueError("Invalid or duplicate quest resource action")
        native = RESOURCES.get(ref)
        if (
            native is None
            or native["monster_resource"]
            or digest(native) != row["resource_sha256"]
        ):
            raise ValueError("Quest resource native definition differs")
        raw = next(
            (
                a
                for s in native["stage_definitions"]
                if s["stage_id"] == stage
                for a in s["actions"]
                if a["action_id"] == action
            ),
            None,
        )
        if (
            raw is None
            or digest(raw) != row["action_sha256"]
            or raw["profession_id"] != 0
            or raw["minimum_level"] != 0
            or raw["item_reference"] != 0
            or (raw["product_references"] != [] and "native_loot" not in row)
            or raw["raw_getters"]["cvH"] != 0
            or raw["raw_getters"]["cvF"] != 0
        ):
            raise ValueError(
                "Quest resource requires a native productless zero-cost depletion"
            )
        if "native_loot" in row:
            loot = row["native_loot"]
            tables = profile.get("loot_tables", {})
            table = (
                tables.get(str(loot.get("table_id")))
                if isinstance(loot, dict)
                else None
            )
            if (
                not isinstance(loot, dict)
                or set(loot) != {"table_id", "native_getter", "source_sha256"}
                or loot["native_getter"] != "aNn.csO"
                or type(loot["table_id"]) is not int
                or loot["table_id"] <= 0
                or not isinstance(loot["source_sha256"], str)
                or len(loot["source_sha256"]) != 64
                or not isinstance(table, dict)
                or table.get("d") != loot["table_id"]
                or table.get("native_class") != "fFc"
                or set(raw["product_references"])
                != {p["aAi"] for p in table.get("gBN", ())}
                or not profile.get("owned_story")
            ):
                raise ValueError(
                    "Quest resource loot lacks its original getter and product table"
                )
        actions[ref] = row
    seen, positions = set(), set()
    if type(profile["placements"]) is not list or not profile["placements"]:
        raise ValueError("Quest resource placements are absent")
    for row in profile["placements"]:
        if type(row) is not dict or set(row) != {
            "resource_uid",
            "resource_reference",
            "position",
            "approach",
        }:
            raise ValueError("Invalid quest resource placement")
        uid = row["resource_uid"]
        point, approach = (tuple(row[k]) for k in ("position", "approach"))
        if (
            type(uid) is not int
            or not 0 < uid < 2**63
            or uid in seen
            or row["resource_reference"] not in actions
            or len(point) != 3
            or len(approach) != 3
            or any(type(v) is not int for v in point + approach)
            or point not in cells
            or approach not in cells
            or (point, approach) not in edges
            or (approach, point) not in edges
            or point[:2] in positions
        ):
            raise ValueError("Quest resource placement lacks unique native access")
        seen.add(uid)
        positions.add(point[:2])
    if any(tuple(row["approach"])[:2] in positions for row in profile["placements"]):
        raise ValueError("Quest resource blocks a pinned harvest approach")
    return deepcopy(profile)


def install(db, store, profile, definitions, geometry):
    """Install immutable reviewed slots; never overwrite another resource."""
    profile = validate(profile, definitions, geometry)
    pin = digest(profile)
    from wakfu_server.fixed_resource_slots import restore_resource

    for placement in sorted(profile["placements"], key=lambda p: p["resource_uid"]):
        point = placement["position"]
        slot = dict(
            resource_uid=placement["resource_uid"],
            map_id=profile["map_id"],
            instance_id=profile.get("owned_story", {}).get("instance_id", 0),
            x=point[0],
            y=point[1],
            z=point[2],
            resource_reference=placement["resource_reference"],
            stage=next(
                a["stage"]
                for a in profile["resource_actions"]
                if a["resource_reference"] == placement["resource_reference"]
            ),
        )
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("quest-resource:" + str(slot["resource_uid"]),),
        )
        old = db.execute(
            "SELECT * FROM quest_resource_slots WHERE resource_uid=%s FOR UPDATE",
            (slot["resource_uid"],),
        ).fetchone()
        if old is not None and (
            old["profile_sha256"] != pin or any(old[k] != v for k, v in slot.items())
        ):
            raise ValueError("Cannot replace an installed quest resource slot")
        if old is None:
            if db.execute(
                "SELECT 1 FROM planted_resources WHERE resource_uid=%s OR (map_id=%s AND instance_id=%s AND x=%s AND y=%s)",
                (
                    slot["resource_uid"],
                    slot["map_id"],
                    slot["instance_id"],
                    slot["x"],
                    slot["y"],
                ),
            ).fetchone():
                raise ValueError("Quest resource identity or cell is occupied")
            for table in ("mining_vein_slots", "fishing_spot_slots"):
                if db.execute(
                    "SELECT 1 FROM "
                    + table
                    + " WHERE enabled AND (resource_uid=%s OR (map_id=%s AND instance_id=%s AND x=%s AND y=%s))",
                    (
                        slot["resource_uid"],
                        slot["map_id"],
                        slot["instance_id"],
                        slot["x"],
                        slot["y"],
                    ),
                ).fetchone():
                    raise ValueError("Quest resource identity or cell is reserved")
            db.execute(
                "INSERT INTO quest_resource_slots(resource_uid,profile_id,profile_sha256,policy,map_id,instance_id,x,y,z,resource_reference,stage) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    slot["resource_uid"],
                    profile["id"],
                    pin,
                    Jsonb(profile),
                    *[
                        slot[k]
                        for k in (
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                            "resource_reference",
                            "stage",
                        )
                    ],
                ),
            )
        restore_resource(db, slot, store.now(), spawn_flag="quest_resource_spawn")
    return len(profile["placements"])


def lock_scope(db, resource):
    if not ready(db):
        return False
    row = db.execute(
        "SELECT 1 FROM quest_resource_slots WHERE resource_uid=%s AND enabled",
        (resource["resource_uid"],),
    ).fetchone()
    if row is None:
        return False
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("quest-resource:" + str(resource["resource_uid"]),),
    )
    return True


def owns(db, resource_uid):
    return (
        ready(db)
        and db.execute(
            "SELECT 1 FROM quest_resource_slots WHERE resource_uid=%s", (resource_uid,)
        ).fetchone()
        is not None
    )


def authorize(db, store, account, generation, character, resource, native_action):
    if not lock_scope(db, resource):
        return None
    row = db.execute(
        "SELECT * FROM quest_resource_slots WHERE resource_uid=%s FOR UPDATE",
        (resource["resource_uid"],),
    ).fetchone()
    profile = row["policy"]
    if profile.get("owned_story"):
        from wakfu_server import owned_story_resource_slots

        owned_story_resource_slots.authorize(db, store, character, profile)
    if (
        digest(profile) != row["profile_sha256"]
        or not row["enabled"]
        or any(
            row[k] != resource[k]
            for k in (
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "resource_reference",
                "stage",
            )
        )
        or any(character[k] != row[k] for k in ("map_id", "instance_id"))
    ):
        raise ValueError("Quest resource differs from its pinned source")
    action = next(
        (
            a
            for a in profile["resource_actions"]
            if a["resource_reference"] == resource["resource_reference"]
        ),
        None,
    )
    if action is None or digest(native_action) != action["action_sha256"]:
        raise ValueError("Quest resource action differs from its pinned native action")
    placement = next(
        (
            p
            for p in profile["placements"]
            if p["resource_uid"] == resource["resource_uid"]
        ),
        None,
    )
    nearby = placement is not None and tuple(
        character[k] for k in ("x", "y", "z")
    ) == tuple(placement["approach"])
    if not nearby and placement is not None and profile.get("owned_story"):
        nearby = owned_story_resource_slots.approachable(db, character, placement)
    if not nearby:
        raise ValueError("Quest resource actor is outside its native approach")
    from wakfu_server.achievements import storage
    from wakfu_server import dungeon_criteria, dungeon_achievement_authority

    state = storage.load_locked(db, character["id"])
    if (
        profile["quest_id"] not in state["running"]
        or profile["objective_id"] in state["objectives"]
    ):
        raise ValueError("Quest resource requires its running unfinished objective")
    from wakfu_server.achievements import mission_toolkit

    definitions = mission_toolkit.definitions(
        db,
        {
            "bindings": [{"quest_id": profile["quest_id"]}],
            "links": [],
            "activations": [],
        },
    )
    quest = (
        next(q for q in definitions if q["d"] == profile["quest_id"])
        if isinstance(definitions, list)
        else definitions[profile["quest_id"]]
    )
    objective = next(o for o in quest["cjJ"] if o["d"] == profile["objective_id"])
    queries = dungeon_achievement_authority.queries_from_state(
        state, now_ms=int(store.clock() * 1000)
    )
    if not all(
        dungeon_criteria.evaluate(
            store, criterion, character=character, queries=queries
        )
        for criterion in (
            quest["cjI"],
            objective["ckc"],
            objective["cke"],
            native_action["criteria"],
        )
    ):
        raise ValueError("Quest resource native prerequisite is not earned")
    return dict(
        kind="quest_resource_slot",
        destination_stage=0,
        resource_uid=resource["resource_uid"],
        **(
            {
                "native_loot": action["native_loot"],
                "loot_tables": profile["loot_tables"],
                "native_action_id": action["action_id"],
            }
            if "native_loot" in action
            else {}
        ),
    )


def products(store, db, account, generation, character, authorization):
    """Draw original quest-resource products inside the occupation transaction."""
    if "native_loot" not in authorization:
        return None
    from wakfu_server.random_item_actions import draw_products, PrivateDraw
    from wakfu_server.item_action_delivery import grant_outputs
    from wakfu_server import owned_story_mechanics

    tables = authorization["loot_tables"]
    token = authorization.get("occupation_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Native harvest draw requires its actual occupation token")
    entropy = db.execute(
        "SELECT secret FROM random_item_entropy WHERE singleton=true"
    ).fetchone()
    if entropy is None:
        raise ValueError("Missing private native harvest entropy")
    # A rollback retries this occupation's same private draw. A new genuine
    # timed occupation receives a different server-issued UUID token.
    nonce = int(sha256(token.encode()).hexdigest()[:15], 16)
    rng = PrivateDraw(
        bytes(entropy["secret"]),
        account,
        authorization["native_action_id"],
        authorization["resource_uid"],
        nonce,
    )
    resolved = draw_products(
        authorization["native_loot"]["table_id"],
        lambda ref: tables[str(ref)],
        rng,
        entry_allowed=lambda expression: owned_story_mechanics.allowed(
            db, store, character, expression
        ),
    )
    if not resolved:
        return None
    result = grant_outputs(store, db, account, generation, character, resolved)
    return dict(result, products=resolved)


def apply(db, store, resource, token):
    """Native depletion plus reviewed refill; normal receipt forbids replay."""
    from wakfu_server.fixed_resource_slots import restore_resource

    row = db.execute(
        "SELECT * FROM quest_resource_slots WHERE resource_uid=%s FOR UPDATE",
        (resource["resource_uid"],),
    ).fetchone()
    if row is None or not row["enabled"]:
        raise ValueError("Quest resource slot disappeared during occupation")
    db.execute(
        "DELETE FROM planted_resources WHERE resource_uid=%s",
        (resource["resource_uid"],),
    )
    db.execute(
        "DELETE FROM resource_growth_decisions WHERE resource_uid=%s",
        (resource["resource_uid"],),
    )
    # Preserve native depletion as the immediate World outcome. The established
    # outbox publishes a fresh full resource using the reviewed refill policy.
    if not restore_resource(db, row, store.now(), spawn_flag="quest_resource_spawn"):
        raise ValueError("Quest resource refill could not retain its native cell")
    return dict(resource, stage=0)
