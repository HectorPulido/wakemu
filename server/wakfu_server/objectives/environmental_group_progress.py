"""Durable secondary entity counts for source-qualified group challenge UI.

These counts never create objective progress, completion, or reward authority.
The contribution caller owns the authenticated gameplay transaction and scope.
"""
from hashlib import sha256
import json


def _transaction(db):
    from .environmental_storage import _transaction as require_transaction

    require_transaction(db)


def _policy(db, event, profile=None):
    row = db.execute(
        "SELECT u.*,p.family,p.mode,p.sealed,p.enabled FROM environmental_profile_group_ui u "
        "JOIN environmental_runtime_profiles p USING(profile_key,version) "
        "JOIN environmental_native_scenarios n ON n.source_key=u.source_key "
        "AND n.scenario_id=u.native_scenario_id "
        "WHERE u.profile_key=%s AND u.version=%s AND n.native_type IN (6,7,8)",
        (event["profile_key"], event["version"]),
    ).fetchone()
    if row is None:
        return None
    if (
        not row["sealed"]
        or row["family"] not in ("monster_defeat", "group_defeat")
        or row["mode"] not in ("solo", "collaborative", "race", "competitive")
        or not isinstance(row["authority"], str)
        or not row["authority"].strip()
    ):
        raise ValueError("Invalid qualified environmental group UI policy")
    if profile is not None and any(
        profile[key] != row[key]
        for key in ("profile_key", "version", "native_scenario_id", "family", "mode")
    ):
        raise ValueError("Environmental group UI profile changed")
    return row


def _owned(db, event, fact, membership):
    actual = db.execute(
        "SELECT * FROM environmental_event_memberships WHERE instance_id=%s "
        "AND entity_kind=%s AND entity_id=%s",
        (event["instance_id"], fact.entity_kind, fact.entity_id),
    ).fetchone()
    if actual is None or not actual["spawn_owned"]:
        return None
    fields = (
        "instance_id",
        "entity_kind",
        "entity_id",
        "reference",
        "source_key",
        "spawn_owned",
    )
    if (
        membership is None
        or any(actual[key] != membership.get(key) for key in fields)
        or actual["reference"] != fact.reference
    ):
        raise ValueError("Environmental secondary count membership changed")
    if fact.entity_kind == "group":
        owned = db.execute(
            "SELECT * FROM environmental_owned_groups WHERE instance_id=%s AND group_id=%s",
            (event["instance_id"], fact.entity_id),
        ).fetchone()
        expected_source = None if owned is None else owned["source_key"]
        expected_reference = None if owned is None else owned["group_reference"]
    else:
        owned = db.execute(
            "SELECT g.*,m.monster_reference FROM environmental_owned_group_members m "
            "JOIN environmental_owned_groups g USING(instance_id,group_ordinal) "
            "WHERE m.instance_id=%s AND m.monster_id=%s",
            (event["instance_id"], fact.entity_id),
        ).fetchone()
        expected_source = (
            None if owned is None else owned["source_key"] + ":" + str(fact.entity_id)
        )
        expected_reference = None if owned is None else owned["monster_reference"]
    if (
        owned is None
        or owned["map_id"] != fact.map_id
        or owned["world_instance_id"] != fact.instance_id
        or actual["source_key"] != expected_source
        or fact.reference != expected_reference
        or owned["spawned_at_ms"] > fact.occurred_at_ms
    ):
        raise ValueError("Environmental secondary count lacks its exact owned spawn")
    return actual, owned


def _receipt(db, fact, owned):
    key = "fight:" + str(fact.fight_id)
    expected = (
        key if fact.entity_kind == "monster" else key + ":group:" + str(fact.entity_id)
    )
    if fact.receipt_key != expected:
        raise ValueError("Environmental secondary count receipt identity changed")
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (fact.character_id, key),
    ).fetchone()
    if row is None or row["payload"].get("fight_id") != fact.fight_id:
        raise ValueError(
            "Environmental secondary count lacks its committed fight receipt"
        )
    roster = row["payload"].get("original_monsters")
    if type(roster) is not list or any(
        type(member) is not list
        or len(member) != 2
        or any(type(value) is not int for value in member)
        for member in roster
    ):
        raise ValueError("Malformed original environmental fight roster")
    killed = {tuple(member) for member in roster}
    if len(killed) != len(roster):
        raise ValueError("Duplicate original environmental fight member")
    if fact.entity_kind == "monster":
        required = {(fact.entity_id, fact.reference)}
    else:
        required = {
            (row["monster_id"], row["monster_reference"])
            for row in db.execute(
                "SELECT monster_id,monster_reference FROM environmental_owned_group_members "
                "WHERE instance_id=%s AND group_ordinal=%s",
                (owned["instance_id"], owned["group_ordinal"]),
            ).fetchall()
        }
    if not required or not required.issubset(killed):
        raise ValueError(
            "Environmental secondary count is not an original defeated member"
        )


def record(db, event, profile, fact, membership):
    """Record one real owned entity once per recipient, before objective filtering."""
    from .environmental_gameplay import GameplayFact
    from .environmental_runtime import fact_values

    _transaction(db)
    if type(fact) is not GameplayFact:
        raise ValueError("Environmental secondary counts require a typed gameplay fact")
    if fact.kind not in ("monster_defeated", "group_defeated"):
        return False
    if _policy(db, event, profile) is None:
        return False
    fresh = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (event["instance_id"],),
    ).fetchone()
    if (
        fresh is None
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
        or fresh["state"] != "active"
        or fact.map_id != fresh["map_id"]
        or fact.instance_id != fresh["world_instance_id"]
        or fact.region_id != fresh["region_id"]
        or not fresh["started_at_ms"] <= fact.occurred_at_ms < fresh["deadline_ms"]
    ):
        raise ValueError("Environmental secondary count leaves its active scope")
    participant = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
        (event["instance_id"], fact.character_id),
    ).fetchone()
    if (
        participant is None
        or participant["account_id"] != fact.account_id
        or not participant["eligible"]
        or participant["completed_at_ms"] is not None
        or participant["joined_at_ms"] > fact.occurred_at_ms
    ):
        raise ValueError(
            "Environmental secondary count lacks its eligible owned participant"
        )
    source = _owned(db, fresh, fact, membership)
    if source is None:
        return False
    actual, owned = source
    _receipt(db, fact, owned)
    values = fact_values(fact)
    digest = sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    physical = {
        key: value
        for key, value in values.items()
        if key not in ("account_id", "character_id", "occurred_at_ms")
    }
    physical_digest = sha256(
        json.dumps(physical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    identity = (
        event["instance_id"],
        fact.character_id,
        fact.entity_kind,
        fact.entity_id,
    )
    previous = db.execute(
        "SELECT fact_digest FROM environmental_group_progress_facts WHERE instance_id=%s "
        "AND character_id=%s AND entity_kind=%s AND entity_id=%s",
        identity,
    ).fetchone()
    if previous is not None:
        if previous["fact_digest"] != digest:
            raise ValueError("Environmental secondary entity replay changed")
        return False
    existing = db.execute(
        "SELECT physical_digest FROM environmental_group_progress_facts WHERE instance_id=%s "
        "AND entity_kind=%s AND entity_id=%s LIMIT 1",
        (event["instance_id"], fact.entity_kind, fact.entity_id),
    ).fetchone()
    if existing is not None and existing["physical_digest"] != physical_digest:
        raise ValueError("Environmental secondary entity changed across recipients")
    db.execute(
        "INSERT INTO environmental_group_progress_facts(instance_id,character_id,account_id,"
        "entity_kind,entity_id,reference,source_key,fact_kind,receipt_key,fight_id,occurred_at_ms,"
        "fact_digest,physical_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *identity[:2],
            fact.account_id,
            *identity[2:],
            fact.reference,
            actual["source_key"],
            fact.kind,
            fact.receipt_key,
            fact.fight_id,
            fact.occurred_at_ms,
            digest,
            physical_digest,
        ),
    )
    return True


def counters(db, event, participant, entity_kind):
    """Return personal and globally distinct physical counts, never player sums."""
    _transaction(db)
    if entity_kind not in ("monster", "group") or _policy(db, event) is None:
        raise ValueError("Missing qualified environmental entity count policy")
    actual = db.execute(
        "SELECT account_id FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
        (event["instance_id"], participant["character_id"]),
    ).fetchone()
    if (
        actual is None
        or actual["account_id"] != participant["account_id"]
        or participant["instance_id"] != event["instance_id"]
    ):
        raise ValueError("Foreign environmental secondary count participant")
    row = db.execute(
        "SELECT count(*) FILTER (WHERE character_id=%s) AS personal,"
        "count(DISTINCT entity_id) AS global FROM environmental_group_progress_facts "
        "WHERE instance_id=%s AND entity_kind=%s",
        (participant["character_id"], event["instance_id"], entity_kind),
    ).fetchone()
    return row["personal"], row["global"]
