"""Transactional native action3 removal of exact event-owned world members.

The caller owns commit and native publication. This is not combat, harvesting,
health damage or loot. Immutable births remain the provenance authority.
"""
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from . import environmental_storage as storage


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _living_member(member):
    # Explicit current HP is authoritative, including zero. Older world-member
    # records may carry the same native integer HP under stats instead.
    hp = member.get("hp") if "hp" in member else (member.get("stats") or {}).get("HP")
    if type(hp) is not int or hp <= 0:
        raise ValueError("Native destruction requires a living durable world member")
    return hp


def _roster_digest(members):
    return _digest(
        [
            {k: v for k, v in member.items() if k not in ("x", "y", "z")}
            for member in members
        ]
    )


def destroyed_ids(db, instance_id):
    """Exact durable consumed UIDs; original birth memberships remain intact."""
    storage._transaction(db)
    return frozenset(
        row["monster_id"]
        for row in db.execute(
            "SELECT monster_id FROM environmental_monster_destructions WHERE instance_id=%s",
            (instance_id,),
        ).fetchall()
    )


def verify_group_roster(db, owned, group):
    """Verify current members against immutable births minus authorized removals.

    Returns current members. Coordinates may legitimately change by wandering.
    The original birth digest, identities, metadata and member order may not.
    """
    storage._transaction(db)
    key = (owned["instance_id"], owned["group_ordinal"])
    frozen = db.execute(
        "SELECT * FROM environmental_destroy_rosters "
        "WHERE instance_id=%s AND group_ordinal=%s",
        key,
    ).fetchone()
    removals = db.execute(
        "SELECT d.*,m.monster_reference AS original_reference,m.group_ordinal AS original_group "
        "FROM environmental_monster_destructions d JOIN environmental_owned_group_members m "
        "ON m.instance_id=d.instance_id AND m.monster_id=d.monster_id "
        "WHERE d.instance_id=%s AND d.group_ordinal=%s ORDER BY d.group_revision",
        key,
    ).fetchall()
    current = group["members"]
    if not isinstance(current, list):
        raise ValueError("Invalid durable environmental roster")
    if frozen is None:
        if removals or _roster_digest(current) != owned["roster_sha256"]:
            raise ValueError(
                "Environmental birth roster changed without removal authority"
            )
        return tuple(current)
    births = frozen["birth_members"]
    if (
        frozen["roster_sha256"] != owned["roster_sha256"]
        or _roster_digest(births) != owned["roster_sha256"]
    ):
        raise ValueError("Environmental destruction birth snapshot changed")
    birth_ids = [member["id"] for member in births]
    members = db.execute(
        "SELECT monster_id,monster_reference FROM environmental_owned_group_members "
        "WHERE instance_id=%s AND group_ordinal=%s",
        key,
    ).fetchall()
    if len(set(birth_ids)) != len(birth_ids) or {
        member["id"]: member["ref"] for member in births
    } != {member["monster_id"]: member["monster_reference"] for member in members}:
        raise ValueError("Environmental destruction snapshot lost original memberships")
    for row in removals:
        if (
            row["original_group"] != owned["group_ordinal"]
            or row["original_reference"] != row["monster_reference"]
        ):
            raise ValueError(
                "Environmental destruction refers to another original member"
            )
    removed = {row["monster_id"] for row in removals}
    expected = [member for member in births if member["id"] not in removed]
    if _roster_digest(expected) != _roster_digest(current):
        raise ValueError(
            "Environmental remaining roster differs from authorized removals"
        )
    return tuple(current)


def _receipt(row, owned, *, replayed=False):
    monster = row["target_snapshot"]
    expected = dict(
        map_id=owned["map_id"],
        instance_id=owned["world_instance_id"],
        id=row["monster_id"],
        ref=row["monster_reference"],
    )
    if (
        not isinstance(monster, dict)
        or any(monster.get(k) != value for k, value in expected.items())
        or any(
            type(monster.get(k)) is not int
            for k in ("map_id", "instance_id", "id", "ref", "x", "y", "z", "level")
        )
        or monster["level"] <= 0
    ):
        raise ValueError("Native destruction frozen target snapshot changed")
    return dict(
        token=row["token"],
        character_id=row["character_id"],
        account_id=row["account_id"],
        monster_id=row["monster_id"],
        map_id=owned["map_id"],
        instance_id=owned["world_instance_id"],
        event_instance_id=row["instance_id"],
        action_id=row["action_id"],
        monster_reference=row["monster_reference"],
        monster_action_type=3,
        action_kind="destroy",
        destroyed=True,
        quantity=1,
        occurred_at_ms=row["occurred_at_ms"],
        group_revision=row["group_revision"],
        monster=dict(monster),
        replayed=replayed,
    )


def _source(db, event, profile, rule):
    from wakfu_server import native_catalog

    row = db.execute(
        "SELECT s.* FROM environmental_profile_destroy_policy p "
        "JOIN environmental_destroy_sources s USING(source_key,scenario_id,policy_version,monster_reference,action_id) "
        "JOIN environmental_native_scenarios n USING(source_key,scenario_id) "
        "WHERE p.profile_key=%s AND p.version=%s AND p.monster_reference=%s AND p.action_id=%s "
        "AND n.native_type=5 AND n.family='destroy_monster_action'",
        (
            event["profile_key"],
            event["version"],
            rule["monster_reference"],
            rule["action_id"],
        ),
    ).fetchone()
    if (
        row is None
        or profile["family"] != "monster_destroy"
        or not profile["sealed"]
        or profile["native_scenario_id"] != row["scenario_id"]
        or row["catalog_revision"] != native_catalog.release()
        or profile["catalog_revision"] != row["catalog_revision"]
        or row["descriptor_sha256"] != _digest(row["action_descriptor"])
        or row["action_descriptor"] != rule["native"]
    ):
        raise ValueError("Missing exact native environmental destruction source policy")
    configuration = {
        item["normalized_key"]: item["native_value"]
        for item in db.execute(
            "SELECT normalized_key,native_value FROM environmental_native_configuration WHERE source_key=%s AND scenario_id=%s",
            (row["source_key"], row["scenario_id"]),
        ).fetchall()
    }
    if (
        configuration.get("usergrouptemplateid") != str(row["template_reference"])
        or configuration.get("monsteractiontypeid") != "3"
    ):
        raise ValueError("Native destruction template/action configuration changed")
    return row


def commit(
    store,
    db,
    account_id,
    generation,
    character,
    body,
    *,
    groups,
    reachable,
    loaded=False,
    blocked=False,
    location_context=None,
    now_ms,
):
    """Authenticate cnT13222 and atomically remove one event-owned world UID.

    Caller must hold groups.lock BEFORE opening the database transaction, using
    the same Store as groups.store. Never acquire the registry lock after scope
    locks. The transaction must roll back on an exception. Replays authenticate the
    same selected owner and frozen scene before returning the original receipt.
    Publication and contribution consumers run after this returns, in the same
    transaction; socket publication happens only after commit.
    """
    from .environmental_monster_actions import admit_destroy_request, decode_request
    from . import environmental_presence as presence
    from wakfu_server.paid_containers import _leased_owner

    storage._transaction(db)
    if (
        getattr(groups, "store", None) is not store
        or not getattr(getattr(groups, "lock", None), "_is_owned", lambda: False)()
    ):
        raise ValueError(
            "Native destruction requires the same Store and pre-held registry lock"
        )
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid native destruction clock")
    if loaded is not True or blocked is not False or not callable(reachable):
        raise ValueError("Native destruction requires the loaded exploration owner")
    request = decode_request(body)
    _leased_owner(store, db, account_id, generation, character)
    actual = store.character(account_id, character["id"], db)
    if location_context is not None:
        if not callable(location_context):
            raise ValueError("Invalid native destruction location authority")
        actual = location_context(actual)
    if any(
        actual.get(k, 0) != character.get(k, 0)
        for k in ("map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Native destruction owner scene changed")
    scope = (actual["map_id"], actual.get("instance_id", 0))
    occupied = presence.capture(*scope)
    if occupied is None:
        raise ValueError("Native destruction scene is vacant")
    storage._scope_lock(db, *scope)
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"monster-population:{scope[0]}:{scope[1]}",),
    )
    owned = db.execute(
        "SELECT o.* FROM environmental_owned_groups o "
        "JOIN environmental_owned_group_members m USING(instance_id,group_ordinal) "
        "WHERE o.map_id=%s AND o.world_instance_id=%s AND m.monster_id=%s FOR UPDATE OF o",
        (*scope, request["monster_id"]),
    ).fetchall()
    if len(owned) != 1:
        raise ValueError("Native destruction requires one exact event-owned birth")
    owned = owned[0]
    group_membership = db.execute(
        "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind='group' AND entity_id=%s",
        (owned["instance_id"], owned["group_id"]),
    ).fetchone()
    if (
        group_membership is None
        or not group_membership["spawn_owned"]
        or group_membership["source_key"] != owned["source_key"]
        or group_membership["reference"] != owned["group_reference"]
    ):
        raise ValueError("Native destruction lacks its exact owned group membership")
    previous = db.execute(
        "SELECT * FROM environmental_monster_destructions "
        "WHERE instance_id=%s AND monster_id=%s",
        (owned["instance_id"], request["monster_id"]),
    ).fetchone()
    if previous is not None:
        if (
            previous["account_id"] != account_id
            or previous["character_id"] != actual["id"]
            or previous["action_id"] != request["action_id"]
        ):
            raise ValueError(
                "Native destruction receipt belongs to another owner/action"
            )
        if not presence.current(occupied, *scope):
            raise ValueError("Native destruction owner left before replay")
        return _receipt(previous, owned, replayed=True)
    admission = admit_destroy_request(
        store,
        db,
        account_id,
        generation,
        character,
        body,
        groups=groups,
        reachable=reachable,
        loaded=loaded,
        blocked=blocked,
        location_context=location_context,
    )
    event = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (owned["instance_id"],),
    ).fetchone()
    if (
        event is None
        or event["state"] != "active"
        or owned["retired_at_ms"] is not None
        or (event["map_id"], event["world_instance_id"]) != scope
        or not event["started_at_ms"] <= now_ms < event["deadline_ms"]
    ):
        raise ValueError("Native destruction event is not active in this scene")
    participant = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s FOR UPDATE",
        (owned["instance_id"], actual["id"]),
    ).fetchone()
    if (
        participant is None
        or participant["account_id"] != account_id
        or not participant["eligible"]
        or participant["completed_at_ms"] is not None
        or participant["joined_at_ms"] > now_ms
    ):
        raise ValueError(
            "Native destruction requires an admitted eligible selected owner"
        )
    membership = db.execute(
        "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind='monster' AND entity_id=%s",
        (owned["instance_id"], request["monster_id"]),
    ).fetchone()
    if (
        membership is None
        or not membership["spawn_owned"]
        or membership["source_key"]
        != owned["source_key"] + ":" + str(request["monster_id"])
        or membership["reference"] != admission["rule"]["monster_reference"]
    ):
        raise ValueError("Native destruction lacks exact owned monster membership")
    profile = storage._event_profile(db, event)
    source = _source(db, event, profile, admission["rule"])
    key = (*scope, owned["group_id"])
    group = db.execute(
        "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
        "AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if group is None or group["status"] != "available":
        raise ValueError(
            "Native destruction cannot consume an unavailable or fighting group"
        )
    members = list(verify_group_roster(db, owned, group))
    selected = [member for member in members if member["id"] == request["monster_id"]]
    if (
        len(selected) != 1
        or selected[0]["ref"] != admission["rule"]["monster_reference"]
    ):
        raise ValueError("Native destruction target changed before commit")
    _living_member(selected[0])
    target = dict(selected[0], map_id=scope[0], instance_id=scope[1], group_key=key)
    if reachable(admission["character"], target) is not True:
        raise ValueError("Native destruction durable target is no longer reachable")
    db.execute(
        "INSERT INTO environmental_destroy_rosters(instance_id,group_ordinal,birth_members,roster_sha256) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (
            owned["instance_id"],
            owned["group_ordinal"],
            Jsonb(members),
            owned["roster_sha256"],
        ),
    )
    target_snapshot = {
        key: target[key]
        for key in ("map_id", "instance_id", "id", "ref", "x", "y", "z", "level")
    }
    if any(type(value) is not int for value in target_snapshot.values()):
        raise ValueError(
            "Native destruction target snapshot is not an actual native actor"
        )
    revision = group["revision"] + 1
    token = str(
        uuid5(
            NAMESPACE_URL,
            f'wakemu:environmental-destroy:{owned["instance_id"]}:{request["monster_id"]}',
        )
    )
    row = db.execute(
        "INSERT INTO environmental_monster_destructions "
        "(instance_id,monster_id,group_ordinal,account_id,character_id,action_id,monster_reference,policy_version,target_snapshot,token,occurred_at_ms,group_revision) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            owned["instance_id"],
            request["monster_id"],
            owned["group_ordinal"],
            account_id,
            actual["id"],
            request["action_id"],
            target["ref"],
            source["policy_version"],
            Jsonb(target_snapshot),
            token,
            now_ms,
            revision,
        ),
    ).fetchone()
    remaining = [member for member in members if member["id"] != request["monster_id"]]
    db.execute(
        "UPDATE combat_groups SET members=%s,status=%s,revision=%s,generation=NULL,fight_id=NULL,"
        "defeated_at=CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        (
            Jsonb(remaining),
            "available" if remaining else "defeated",
            revision,
            not remaining,
            *key,
        ),
    )
    db.execute(
        "INSERT INTO environmental_destroy_publications "
        "(instance_id,group_ordinal,group_revision,created_at_ms) VALUES(%s,%s,%s,%s)",
        (owned["instance_id"], owned["group_ordinal"], revision, now_ms),
    )
    # Both scene presence and this owner's actual location are final fences.
    final = store.character(account_id, actual["id"], db)
    if location_context is not None:
        final = location_context(final)
    if any(
        final.get(k, 0) != actual.get(k, 0)
        for k in ("map_id", "instance_id", "x", "y", "z")
    ) or not presence.current(occupied, *scope):
        raise ValueError("Native destruction owner left during commit")
    return _receipt(row, owned)


def record(db, event, profile, fact, membership):
    """Record typed eligible main/loaded-hero facts before objective filtering.

    This does not synthesize a group defeat. Group UI counters below require
    all born members, independently of the monster reward threshold.
    """
    from .environmental_gameplay import GameplayFact
    from .environmental_runtime import fact_values
    from .environmental_company import loaded_ids

    storage._transaction(db)
    if type(fact) is not GameplayFact:
        raise ValueError("Native destruction progress requires its typed gameplay fact")
    if fact.kind != "monster_destroyed" or profile["family"] != "monster_destroy":
        return False
    if (
        db.execute(
            "SELECT 1 FROM environmental_profile_destroy_ui WHERE profile_key=%s AND version=%s",
            (profile["profile_key"], profile["version"]),
        ).fetchone()
        is None
    ):
        return False
    fresh = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (event["instance_id"],),
    ).fetchone()
    if (
        fresh is None
        or fresh["state"] != "active"
        or any(
            fresh[key] != event[key]
            for key in (
                "profile_key",
                "version",
                "map_id",
                "world_instance_id",
                "region_id",
            )
        )
        or (fact.map_id, fact.instance_id, fact.region_id)
        != (fresh["map_id"], fresh["world_instance_id"], fresh["region_id"])
        or not fresh["started_at_ms"] <= fact.occurred_at_ms < fresh["deadline_ms"]
    ):
        raise ValueError("Native destruction progress leaves its actual event")
    row = db.execute(
        "SELECT * FROM environmental_monster_destructions "
        "WHERE instance_id=%s AND monster_id=%s",
        (fresh["instance_id"], fact.entity_id),
    ).fetchone()
    if (
        row is None
        or fact.entity_kind != "monster"
        or fact.quantity != 1
        or fact.reference != row["monster_reference"]
        or fact.action_id != row["action_id"]
        or fact.receipt_key != "monster-action:" + row["token"]
        or fact.occurred_at_ms != row["occurred_at_ms"]
        or fact.account_id != row["account_id"]
    ):
        raise ValueError(
            "Native destruction progress lacks its committed action receipt"
        )
    frozen_profile = storage._event_profile(db, fresh)
    if (
        any(
            profile[key] != frozen_profile[key]
            for key in (
                "profile_key",
                "version",
                "native_scenario_id",
                "family",
                "mode",
            )
        )
        or frozen_profile["family"] != "monster_destroy"
    ):
        raise ValueError("Native destruction progress profile changed")
    policy = db.execute(
        "SELECT 1 FROM environmental_profile_destroy_policy WHERE profile_key=%s "
        "AND version=%s AND monster_reference=%s AND action_id=%s AND policy_version=%s",
        (
            fresh["profile_key"],
            fresh["version"],
            row["monster_reference"],
            row["action_id"],
            row["policy_version"],
        ),
    ).fetchone()
    if policy is None:
        raise ValueError("Native destruction progress lacks its frozen source binding")
    owned = db.execute(
        "SELECT g.* FROM environmental_owned_groups g "
        "JOIN environmental_owned_group_members m USING(instance_id,group_ordinal) "
        "WHERE m.instance_id=%s AND m.monster_id=%s",
        (fresh["instance_id"], fact.entity_id),
    ).fetchone()
    actual = db.execute(
        "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind='monster' AND entity_id=%s",
        (fresh["instance_id"], fact.entity_id),
    ).fetchone()
    if (
        actual is None
        or not actual["spawn_owned"]
        or membership is None
        or owned is None
        or actual["source_key"] != owned["source_key"] + ":" + str(fact.entity_id)
        or owned["spawned_at_ms"] > fact.occurred_at_ms
        or any(
            actual[key] != membership.get(key)
            for key in (
                "instance_id",
                "entity_kind",
                "entity_id",
                "reference",
                "source_key",
                "spawn_owned",
            )
        )
        or actual["reference"] != fact.reference
    ):
        raise ValueError("Native destruction progress has foreign birth membership")
    participant = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
        (fresh["instance_id"], fact.character_id),
    ).fetchone()
    if (
        participant is None
        or participant["account_id"] != fact.account_id
        or not participant["eligible"]
        or participant["completed_at_ms"] is not None
        or participant["joined_at_ms"] > fact.occurred_at_ms
    ):
        raise ValueError(
            "Native destruction progress requires its eligible participant"
        )
    digest = _digest(fact_values(fact))
    previous = db.execute(
        "SELECT fact_digest FROM environmental_destroy_progress_facts "
        "WHERE instance_id=%s AND character_id=%s AND monster_id=%s",
        (fresh["instance_id"], fact.character_id, fact.entity_id),
    ).fetchone()
    if previous is not None:
        if previous["fact_digest"] != digest:
            raise ValueError("Native destruction projected receipt replay changed")
        return False
    if fact.character_id != row["character_id"]:
        selected = db.execute(
            "SELECT 1 FROM sessions WHERE account_id=%s AND character_id=%s "
            "AND expires_at>to_timestamp(%s/1000.0)",
            (row["account_id"], row["character_id"], row["occurred_at_ms"]),
        ).fetchone()
        if selected is None or fact.character_id not in loaded_ids(
            db, row["account_id"], row["character_id"]
        ):
            raise ValueError(
                "Native destruction projection requires the actual loaded owned hero"
            )
    db.execute(
        "INSERT INTO environmental_destroy_progress_facts "
        "(instance_id,character_id,account_id,monster_id,receipt_key,occurred_at_ms,fact_digest) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (
            fresh["instance_id"],
            fact.character_id,
            fact.account_id,
            fact.entity_id,
            fact.receipt_key,
            fact.occurred_at_ms,
            digest,
        ),
    )
    return True


def counters(db, event, participant, entity_kind):
    """Declared UI counts: all original members consumed, never combat credit."""
    storage._transaction(db)
    if entity_kind not in ("monster", "group"):
        raise ValueError("Unknown native destruction counter kind")
    actual = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
        (event["instance_id"], participant["character_id"]),
    ).fetchone()
    if (
        actual is None
        or actual["account_id"] != participant["account_id"]
        or participant["instance_id"] != event["instance_id"]
    ):
        raise ValueError("Foreign native destruction counter participant")
    if entity_kind == "monster":
        row = db.execute(
            "SELECT (SELECT count(*) FROM environmental_destroy_progress_facts "
            "WHERE instance_id=%s AND character_id=%s) AS personal,"
            "(SELECT count(*) FROM environmental_monster_destructions WHERE instance_id=%s) AS global",
            (event["instance_id"], participant["character_id"], event["instance_id"]),
        ).fetchone()
    else:
        row = db.execute(
            """SELECT count(*) FILTER (WHERE complete_personal) AS personal,
            count(*) FILTER (WHERE complete_global) AS global FROM (
            SELECT m.group_ordinal,
              bool_and(d.monster_id IS NOT NULL) AS complete_global,
              bool_and(p.monster_id IS NOT NULL) AS complete_personal
            FROM environmental_owned_group_members m
            LEFT JOIN environmental_monster_destructions d
              ON d.instance_id=m.instance_id AND d.monster_id=m.monster_id
            LEFT JOIN environmental_destroy_progress_facts p
              ON p.instance_id=m.instance_id AND p.monster_id=m.monster_id AND p.character_id=%s
            WHERE m.instance_id=%s GROUP BY m.group_ordinal) q""",
            (participant["character_id"], event["instance_id"]),
        ).fetchone()
    return row["personal"], row["global"]


def inventory(db, event):
    """Original births and actual remaining world members for type5 native UI."""
    storage._transaction(db)
    rows = db.execute(
        "SELECT o.*,g.members,g.status AS current_status FROM environmental_owned_groups o "
        "LEFT JOIN combat_groups g ON g.map_id=o.map_id AND g.instance_id=o.world_instance_id "
        "AND g.group_id=o.group_id WHERE o.instance_id=%s ORDER BY o.group_ordinal",
        (event["instance_id"],),
    ).fetchall()
    counts = dict(
        resource=dict(entity_kind="resource", spawned=0, remaining=0, invalid=0),
        group=dict(entity_kind="group", spawned=len(rows), remaining=0, invalid=0),
        monster=dict(entity_kind="monster", spawned=0, remaining=0, invalid=0),
    )
    for owned in rows:
        members = db.execute(
            "SELECT monster_id FROM environmental_owned_group_members "
            "WHERE instance_id=%s AND group_ordinal=%s",
            (event["instance_id"], owned["group_ordinal"]),
        ).fetchall()
        counts["monster"]["spawned"] += len(members)
        cleaned = db.execute(
            "SELECT 1 FROM environmental_cleanup_outbox WHERE instance_id=%s "
            "AND entity_kind='group' AND entity_id=%s AND completed_at_ms IS NOT NULL",
            (event["instance_id"], owned["group_id"]),
        ).fetchone()
        if owned["retired_at_ms"] is not None or cleaned is not None:
            continue
        if owned["current_status"] is None:
            counts["group"]["invalid"] += 1
            counts["monster"]["invalid"] += len(members)
            continue
        current = verify_group_roster(db, owned, dict(members=owned["members"]))
        if owned["current_status"] in ("available", "fighting"):
            if not current:
                raise ValueError(
                    "Active native destruction group has no remaining members"
                )
            counts["group"]["remaining"] += 1
            counts["monster"]["remaining"] += len(current)
    return tuple(counts[kind] for kind in ("resource", "group", "monster"))


def remaining_birth_members(db, owned):
    """Authenticated surviving identities after cleanup; None for legacy births.

    Coordinates are the first-destruction snapshot, not a current position claim.
    Consumers may use returned UIDs for despawn, never to recreate world actors.
    """
    storage._transaction(db)
    key = (owned["instance_id"], owned["group_ordinal"])
    frozen = db.execute(
        "SELECT birth_members FROM environmental_destroy_rosters "
        "WHERE instance_id=%s AND group_ordinal=%s",
        key,
    ).fetchone()
    if frozen is None:
        return None
    removed = {
        row["monster_id"]
        for row in db.execute(
            "SELECT monster_id FROM environmental_monster_destructions WHERE instance_id=%s AND group_ordinal=%s",
            key,
        ).fetchall()
    }
    expected = [
        member for member in frozen["birth_members"] if member["id"] not in removed
    ]
    return verify_group_roster(db, owned, dict(members=expected))
