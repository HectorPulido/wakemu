"""Read-only ecology growth planning and bounded world-side authoritative apply."""
from datetime import datetime
import math

from wakfu_server import planting
from wakfu_server.planting_runtime import monster_growth_member

RESOURCE_KEYS = (
    "resource_uid",
    "map_id",
    "instance_id",
    "x",
    "y",
    "z",
    "resource_reference",
    "stage",
    "creation_time",
)


# Advisory read cursors only: restarting them cannot replay a durable mutation.
_CURSORS = {}


def prepare(store, snapshot, *, limit=16):
    """Read-only fair bounded plans; final authority stays in world apply."""
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid ecology growth batch")
    epoch, now_ms = snapshot.get("world_epoch"), snapshot.get("now_ms")
    delay = snapshot.get("growth_seconds", 30)
    tick = snapshot.get("planning_tick", 0)
    if (
        not isinstance(epoch, str)
        or not epoch
        or type(now_ms) is not int
        or type(tick) is not int
        or tick < 0
    ):
        raise ValueError("Invalid ecology world snapshot")
    if type(delay) not in (int, float) or not math.isfinite(delay) or delay <= 0:
        raise ValueError("Invalid ecology seed growth delay")
    if epoch not in _CURSORS:
        if len(_CURSORS) >= 8:
            _CURSORS.pop(next(iter(_CURSORS)))
        _CURSORS[epoch] = {}
    cursors = _CURSORS[epoch]
    refs = [
        ref
        for ref, definition in planting.RESOURCES.items()
        if definition["monster_resource"]
    ]
    from wakfu_server.resource_domains import is_fixed_resource

    fixed_refs = [ref for ref in planting.RESOURCES if is_fixed_resource(ref)]
    occupied = {
        (p["map_id"], p.get("instance_id", 0), p["x"], p["y"], p["z"])
        for p in snapshot.get("players", ())
    }
    queries = {
        "monster": (
            "SELECT p.* FROM planted_resources p WHERE p.stage=1 "
            "AND p.creation_time<=%s AND p.resource_reference=ANY(%s) ",
            (now_ms - int(delay * 1000), refs),
            "p.resource_uid",
        ),
        "flora": (
            "SELECT p.*,t.to_stage,t.delay_ms,t.probability FROM planted_resources p "
            "JOIN resource_growth_transitions t ON t.resource_reference=p.resource_reference "
            "AND t.from_stage=p.stage WHERE p.creation_time+t.delay_ms<=%s "
            "AND NOT (p.resource_reference=ANY(%s)) AND NOT EXISTS "
            "(SELECT 1 FROM resource_growth_decisions d WHERE d.resource_uid=p.resource_uid "
            "AND d.from_stage=p.stage) ",
            (now_ms, refs + fixed_refs),
            "p.resource_uid",
        ),
        "mineral": (
            "SELECT resource_uid,available_at FROM mining_vein_slots "
            "WHERE enabled AND NOT active AND available_at<=%s ",
            (store.now(),),
            "resource_uid",
        ),
        "fishing": (
            "SELECT resource_uid,available_at FROM fishing_spot_slots "
            "WHERE enabled AND NOT active AND available_at<=%s ",
            (store.now(),),
            "resource_uid",
        ),
        "publication": (
            "SELECT resource_uid FROM planting_growth_outbox WHERE NOT published ",
            (),
            "resource_uid",
        ),
    }
    categories = list(queries)
    categories = (
        categories[tick % len(categories) :] + categories[: tick % len(categories)]
    )
    from wakfu_server.ecology_planting_intents import prepare_intents

    plans = prepare_intents(store, snapshot, limit=min(4, limit))
    growth_limit = limit - len(plans)
    with store.connection() as db:
        for index, category in enumerate(categories):
            quota = growth_limit // len(categories) + (
                index < growth_limit % len(categories)
            )
            if not quota:
                continue
            query, params, column = queries[category]
            after = cursors.get(category, 0)
            rows = db.execute(
                query + f"AND {column}>%s ORDER BY {column} LIMIT %s",
                params + (after, quota),
            ).fetchall()
            if not rows and after:
                rows = db.execute(
                    query + f"ORDER BY {column} LIMIT %s", params + (quota,)
                ).fetchall()
            if rows:
                cursors[category] = rows[-1]["resource_uid"]
            if category in ("mineral", "fishing"):
                plans.extend(
                    dict(
                        kind=category + "_refill",
                        world_epoch=epoch,
                        resource_uid=r["resource_uid"],
                        available_at=r["available_at"].isoformat(),
                    )
                    for r in rows
                )
            elif category == "publication":
                plans.extend(
                    dict(
                        kind="growth_publish",
                        world_epoch=epoch,
                        resource_uid=r["resource_uid"],
                    )
                    for r in rows
                )
            else:
                for row in rows:
                    resource = {key: row[key] for key in RESOURCE_KEYS}
                    definition = planting.RESOURCES[resource["resource_reference"]]
                    transition, member = None, None
                    if category == "monster":
                        if (
                            tuple(
                                resource[k]
                                for k in ("map_id", "instance_id", "x", "y", "z")
                            )
                            in occupied
                        ):
                            continue
                        member = monster_growth_member(resource, definition)
                    else:
                        if row["to_stage"] not in definition["stages"]:
                            raise ValueError(
                                "Growth stage absent from native definition"
                            )
                        transition = [
                            row["to_stage"],
                            row["delay_ms"],
                            row["probability"],
                        ]
                    plans.append(
                        dict(
                            kind="resource_growth",
                            world_epoch=epoch,
                            expected=resource,
                            transition=transition,
                            member=member,
                        )
                    )
    return plans


def apply(plantings, groups, proposal, *, authorize_spawn, publish):
    """Commit one plan under caller's live fence; never scan all due resources."""
    if not isinstance(proposal, dict):
        raise ValueError("Invalid ecology growth proposal")
    epoch = proposal.get("world_epoch")
    if not isinstance(epoch, str) or not epoch:
        raise ValueError("Missing ecology world epoch")
    current_epoch = getattr(plantings, "ecology_world_epoch", epoch)
    if epoch != current_epoch:
        return dict(applied=False, reason="stale_world_epoch", publications=[])
    if proposal.get("kind") == "growth_publish":
        uid = proposal.get("resource_uid")
        if type(uid) is not int or not 0 < uid < 2**63:
            raise ValueError("Invalid ecology publication identity")
        deliveries = plantings.publish_growth(
            groups, publish=publish, resource_uid=uid, limit=1
        )
        return dict(applied=bool(deliveries), publications=deliveries)
    if proposal.get("kind") in ("mineral_refill", "fishing_refill"):
        if proposal["kind"] == "fishing_refill":
            from wakfu_server.fishing_spots import refill
        else:
            from wakfu_server.mining_veins import refill

        uid = proposal["resource_uid"]
        if type(uid) is not int or not 0 < uid < 2**63:
            raise ValueError("Invalid ecology mineral identity")
        expected = datetime.fromisoformat(proposal["available_at"])
        if expected.tzinfo is None:
            raise ValueError("Mineral deadline must include timezone")
        with plantings.publisher_lock:
            restored = refill(
                plantings.store,
                limit=1,
                resource_uid=uid,
                expected_available_at=expected,
            )
        deliveries = plantings.publish_growth(
            groups, publish=publish, resource_uid=uid, limit=1
        )
        return dict(applied=bool(restored), publications=deliveries)
    if proposal.get("kind") != "resource_growth":
        raise ValueError("Unknown ecology growth proposal")
    resource = proposal.get("expected")
    if (
        not isinstance(resource, dict)
        or set(resource) != set(RESOURCE_KEYS)
        or any(type(resource[key]) is not int for key in RESOURCE_KEYS)
        or not 0 < resource["resource_uid"] < 2**63
    ):
        raise ValueError("Invalid ecology expected resource")
    definition = planting.RESOURCES.get(resource["resource_reference"])
    if definition is None or resource["stage"] not in definition["stages"]:
        raise ValueError("Unknown ecology native resource")
    transition = proposal.get("transition")
    members = None
    if definition["monster_resource"]:
        if transition is not None or resource["stage"] != 1:
            raise ValueError("Invalid ecology monster transition")
        if not authorize_spawn(resource):
            return dict(applied=False, reason="occupied", publications=[])
        if int(plantings.store.clock() * 1000) < (
            resource["creation_time"] + plantings.growth_seconds * 1000
        ):
            return dict(applied=False, reason="not_due", publications=[])
        member = proposal.get("member")
        if not isinstance(member, dict) or any(
            member.get(key) != resource[key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Ecology monster location differs")
        from wakfu_server.monsters import reference
        from wakfu_server.combat_monster_world import spawn_group

        if (
            reference(member["ref"])["family_id"]
            not in definition["monster_family_ids"]
        ):
            raise ValueError("Ecology monster family differs")
        spawn_group([member], group_id=abs(member["id"]))
        members = {resource["resource_uid"]: member}
    else:
        if (
            not isinstance(transition, (list, tuple))
            or len(transition) != 3
            or type(transition[0]) is not int
            or type(transition[1]) is not int
            or transition[1] < 0
            or transition[0] not in definition["stages"]
            or type(transition[2]) not in (int, float)
            or not math.isfinite(transition[2])
            or not 0 <= transition[2] <= 1
        ):
            raise ValueError("Invalid ecology flora transition")
        if (
            int(plantings.store.clock() * 1000)
            < resource["creation_time"] + transition[1]
        ):
            return dict(applied=False, reason="not_due", publications=[])
        transition = tuple(transition)
    # The complete row, live harvest occupation and current transition policy
    # are compared again inside the existing atomic mutation transaction.
    plantings.apply_growth_candidates(
        [(resource, definition, transition)], prepared_members=members
    )
    deliveries = plantings.publish_growth(
        groups, publish=publish, resource_uid=resource["resource_uid"], limit=1
    )
    return dict(applied=bool(deliveries), publications=deliveries)
