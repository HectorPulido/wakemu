"""Read-only ecology growth planning and bounded world-side authoritative apply."""
from datetime import datetime
import math
import json
import time

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
_SEED_LOG_STATES = {}
MAX_BIRTH_BATCH = 64
MAX_BIRTH_BATCH_BYTES = 224 * 1024


def _prepare_birth_batch(store, snapshot, refs, delay, occupied):
    """One ordered read gathers ready seeds into one bounded durable proposal."""
    from wakfu_server.ecology.protocol import json_bytes

    epoch = snapshot["world_epoch"]
    cursor = _CURSORS.setdefault(epoch, {}).get("monster_bulk", 0)
    with store.connection() as db:
        rows = db.execute(
            "SELECT * FROM planted_resources WHERE stage=1 AND creation_time<=%s "
            "AND resource_reference=ANY(%s) ORDER BY (resource_uid<=%s),resource_uid LIMIT %s",
            (snapshot["now_ms"] - int(delay * 1000), refs, cursor, MAX_BIRTH_BATCH),
        ).fetchall()
    bulk = dict(kind="resource_growth_bulk", world_epoch=epoch, resources=[])
    for row in rows:
        resource = {key: row[key] for key in RESOURCE_KEYS}
        _CURSORS[epoch]["monster_bulk"] = resource["resource_uid"]
        if (
            tuple(resource[k] for k in ("map_id", "instance_id", "x", "y", "z"))
            in occupied
        ):
            continue
        member = monster_growth_member(
            resource,
            planting.RESOURCES[resource["resource_reference"]],
            decision_seed=f"seed-birth:{resource['resource_uid']}:{resource['resource_reference']}:{resource['stage']}",
        )
        candidate = dict(
            kind="resource_growth",
            world_epoch=epoch,
            expected=resource,
            transition=None,
            member=member,
        )
        bulk["resources"].append(candidate)
        try:
            json_bytes(bulk, limit=MAX_BIRTH_BATCH_BYTES)
        except ValueError:
            bulk["resources"].pop()
            break
    return [bulk] if bulk["resources"] else []


def _seed_log(resource, state, **details):
    """Log state transitions immediately; repeat unchanged diagnostics every 30s."""
    identity = resource["resource_uid"]
    now = time.monotonic()
    previous = _SEED_LOG_STATES.get(identity)
    if previous is not None and previous[0] == state and now - previous[1] < 30:
        return
    if len(_SEED_LOG_STATES) >= 1024 and identity not in _SEED_LOG_STATES:
        _SEED_LOG_STATES.pop(next(iter(_SEED_LOG_STATES)))
    _SEED_LOG_STATES[identity] = (state, now)
    print(
        json.dumps(
            dict(
                event="ecology_seed_growth",
                state=state,
                resource_uid=identity,
                map_id=resource["map_id"],
                instance_id=resource["instance_id"],
                position=[resource[key] for key in ("x", "y", "z")],
                **details,
            )
        ),
        flush=True,
    )


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
    if snapshot.get("reserve_monster_births", False):
        return _prepare_birth_batch(store, snapshot, refs, delay, occupied)
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
    if snapshot.get("reserve_monster_births", False):
        queries = {"monster": queries["monster"]}
    elif snapshot.get("skip_monster_births", False):
        queries.pop("monster")
    categories = list(queries)
    categories = (
        categories[tick % len(categories) :] + categories[: tick % len(categories)]
    )
    from wakfu_server.ecology_planting_intents import prepare_intents

    plans = (
        []
        if snapshot.get("skip_interactive", False)
        else prepare_intents(store, snapshot, limit=min(4, limit))
    )
    if not snapshot.get("reserve_monster_births", False) and len(plans) < limit:
        from .ecology_affinity_reconciliation import prepare as prepare_reconciliation

        plans.extend(prepare_reconciliation(store, snapshot, limit=1))
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
                            _seed_log(
                                resource,
                                "blocked",
                                reason="player_occupied",
                                age_ms=now_ms - resource["creation_time"],
                            )
                            continue
                        member = monster_growth_member(resource, definition)
                        _seed_log(
                            resource,
                            "prepared",
                            age_ms=now_ms - resource["creation_time"],
                            offspring_reference=member["ref"],
                        )
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


def apply(plantings, groups, proposal, *, authorize_spawn, publish, _collect=None):
    """Commit one plan under caller's live fence; never scan all due resources."""
    if not isinstance(proposal, dict):
        raise ValueError("Invalid ecology growth proposal")
    epoch = proposal.get("world_epoch")
    if not isinstance(epoch, str) or not epoch:
        raise ValueError("Missing ecology world epoch")
    current_epoch = getattr(plantings, "ecology_world_epoch", epoch)
    if epoch != current_epoch:
        return dict(applied=False, reason="stale_world_epoch", publications=[])
    if proposal.get("kind") == "resource_growth_bulk":
        return _apply_birth_batch(
            plantings,
            groups,
            proposal,
            authorize_spawn=authorize_spawn,
            publish=publish,
        )
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
        if int(plantings.store.clock() * 1000) < (
            resource["creation_time"] + plantings.growth_seconds * 1000
        ):
            _seed_log(resource, "blocked", reason="not_due")
            return dict(
                status="deferred", applied=False, reason="not_due", publications=[]
            )
        if not authorize_spawn(resource):
            _seed_log(resource, "blocked", reason="world_occupied")
            return dict(
                status="deferred",
                applied=False,
                reason="occupied",
                publications=[],
                resource_failures=[resource["resource_uid"]],
            )
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
            return dict(
                status="deferred", applied=False, reason="not_due", publications=[]
            )
        transition = tuple(transition)
    # The complete row, live harvest occupation and current transition policy
    # are compared again inside the existing atomic mutation transaction.
    if _collect is not None:
        if members is None:
            raise ValueError("Bulk birth contains a non-monster resource")
        _collect.append(
            (resource, definition, transition, members[resource["resource_uid"]])
        )
        return dict(applied=False, publications=[])
    if members is not None:
        _seed_log(resource, "committing", offspring_reference=member["ref"])
    growth = plantings.apply_growth_candidates(
        [(resource, definition, transition)], prepared_members=members
    )
    if resource["resource_uid"] in growth.get("capacity_skipped", ()):
        _seed_log(resource, "blocked", reason="capacity")
        return dict(
            status="deferred",
            applied=False,
            reason="capacity",
            publications=[],
            resource_failures=[resource["resource_uid"]],
        )
    if members is not None:
        _seed_log(resource, "commit_checked")
    deliveries = plantings.publish_growth(
        groups, publish=publish, resource_uid=resource["resource_uid"], limit=1
    )
    if members is not None:
        _seed_log(
            resource,
            "published" if deliveries else "publication_pending",
            publications=len(deliveries),
        )
    return dict(applied=bool(deliveries), publications=deliveries)


def _apply_birth_batch(plantings, groups, proposal, *, authorize_spawn, publish):
    """Validate the whole batch before one transactional per-seed CAS pass."""
    from wakfu_server.ecology.protocol import json_bytes

    rows = proposal.get("resources")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BIRTH_BATCH:
        raise ValueError("Invalid ecology birth batch size")
    json_bytes(proposal, limit=MAX_BIRTH_BATCH_BYTES)
    candidates, identities, waiting, failures = [], set(), [], []
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("kind") != "resource_growth"
            or row.get("world_epoch") != proposal["world_epoch"]
        ):
            raise ValueError("Invalid ecology birth batch member")
        resource = row.get("expected")
        uid = resource.get("resource_uid") if isinstance(resource, dict) else None
        if type(uid) is not int or uid in identities:
            raise ValueError("Invalid ecology birth batch identity")
        identities.add(uid)
        result = apply(
            plantings,
            groups,
            row,
            authorize_spawn=authorize_spawn,
            publish=publish,
            _collect=candidates,
        )
        failures.extend(result.get("resource_failures", []))
        if result.get("status") == "deferred":
            waiting.append(result["reason"])
    if not candidates:
        return dict(
            status="deferred",
            applied=False,
            reason=waiting[0] if waiting else "not_due",
            publications=[],
            resource_failures=failures,
        )
    prepared = {
        resource["resource_uid"]: member for resource, _, _, member in candidates
    }
    growth = plantings.apply_growth_candidates(
        [
            (resource, definition, transition)
            for resource, definition, transition, _ in candidates
        ],
        prepared_members=prepared,
    )
    deliveries = plantings.publish_growth(
        groups, publish=publish, resource_uids=sorted(identities), limit=MAX_BIRTH_BATCH
    )
    failures.extend(growth.get("capacity_skipped", ()))
    failures = list(dict.fromkeys(failures))
    if not growth.get("applied") and not deliveries and growth.get("capacity_skipped"):
        return dict(
            status="deferred",
            applied=False,
            reason="capacity",
            publications=[],
            resource_failures=failures,
        )
    return dict(
        applied=bool(growth.get("applied") or deliveries),
        publications=deliveries,
        resource_failures=failures,
    )
