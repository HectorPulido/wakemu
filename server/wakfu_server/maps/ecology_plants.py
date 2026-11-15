"""World-owned validation, growth commits, and bounded native publication."""

from datetime import datetime
import math
import json
import time

from wakfu_server import planting

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


MAX_BIRTH_BATCH = 64
MAX_BIRTH_BATCH_BYTES = 224 * 1024


_SEED_LOG_STATES = {}


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
