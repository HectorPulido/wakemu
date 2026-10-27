"""Owned environmental resource interactions under declared catalog_cvF policy.

Original resource/action metadata does not authorize an event. Every operation
requires its current sealed profile, live occupied event and exact owned UID.
"""
from hashlib import sha256
import json

from . import environmental_presence as presence
from . import environmental_storage as storage


def lock_scope(db, resource):
    """Take the event scope before the physical resource row in harvest paths."""
    storage._transaction(db)
    map_id, instance_id = resource["map_id"], resource["instance_id"]
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
    ):
        raise ValueError("Invalid environmental resource scope")
    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        raise ValueError("Environmental resource scope is not occupied")
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        raise ValueError("Environmental resource occupancy changed")
    return occupied


def authorize_action(db, *, store, account_id, generation, character, resource, rule):
    """Recheck in prepare, reservation and completion, never trust a client flag.

    Profession zero is not a learned profession or a global harvest bypass.
    Product-bearing actions remain unqualified. Native level criteria use the
    current owned actor's effective level at each interaction phase.
    """
    occupied = lock_scope(db, resource)
    if (
        type(rule.get("profession_id")) is not int
        or rule["profession_id"] != 0
        or rule.get("item_reference") != 0
        or rule.get("product_references") != []
        or type(rule.get("minimum_level")) is not int
        or rule["minimum_level"] != 0
        or type(rule.get("duration_ms")) is not int
        or rule["duration_ms"] < 0
        or type(rule.get("raw_getters", {}).get("cvF")) is not int
        or rule["raw_getters"]["cvF"] != 0
    ):
        raise ValueError(
            "Environmental resource action requires qualified native authority"
        )
    if any(character[k] != resource[k] for k in ("map_id", "instance_id")):
        raise ValueError("Environmental resource actor is outside its scope")
    now = store.now()
    now_ms = int(now.timestamp() * 1000)
    selected = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s",
        (account_id, generation, now),
    ).fetchone()
    if selected is None:
        raise ValueError("Missing selected environmental owner")
    if selected["character_id"] != character["id"]:
        from .environmental_company import loaded_ids

        if character["id"] not in loaded_ids(db, account_id, selected["character_id"]):
            raise ValueError("Environmental actor is not the current loaded company")
    row = db.execute(
        "SELECT e.instance_id,e.profile_key,e.version,e.region_id,r.native_scenario_id,"
        "r.level_min,r.level_max,r.catalog_revision,pop.source_key,pop.source_authority,"
        "s.catalog_revision AS source_catalog_revision,a.action_sha256,a.original_action,"
        "o.map_id AS owned_map_id,o.world_instance_id AS owned_world_instance_id,"
        "o.x AS owned_x,o.y AS owned_y,o.z AS owned_z,o.reference AS owned_reference,"
        "o.native_step AS owned_step,o.creation_time AS owned_creation_time "
        "FROM environmental_owned_resources o "
        "JOIN environmental_event_memberships m ON "
        "(m.instance_id,m.entity_kind,m.entity_id)=(o.instance_id,o.entity_kind,o.resource_uid) "
        "JOIN environmental_event_instances e ON e.instance_id=o.instance_id "
        "JOIN environmental_runtime_profiles r ON (r.profile_key,r.version)=(e.profile_key,e.version) "
        "JOIN environmental_profile_resource_population pop ON "
        "(pop.profile_key,pop.version)=(r.profile_key,r.version) "
        "JOIN environmental_resource_action_source_versions s ON s.source_key=pop.source_key "
        "JOIN environmental_resolved_resource_actions a ON "
        "(a.source_key,a.scenario_id)=(pop.source_key,r.native_scenario_id) "
        "JOIN environmental_participants p ON p.instance_id=e.instance_id "
        "WHERE o.resource_uid=%s AND o.retired_at_ms IS NULL AND o.entity_kind='resource' "
        "AND o.map_id=%s AND o.world_instance_id=%s AND m.spawn_owned "
        "AND m.reference=o.reference AND a.resource_reference=o.reference "
        "AND a.native_step=o.native_step "
        "AND a.action_id=%s AND r.family='resource_collect' AND r.sealed AND r.enabled "
        "AND pop.placement_policy='declared_native_cells' AND pop.transition_policy='catalog_cvF' "
        "AND r.catalog_revision=s.catalog_revision "
        "AND e.map_id=o.map_id AND e.world_instance_id=o.world_instance_id "
        "AND r.map_id=e.map_id AND r.region_id IS NOT DISTINCT FROM e.region_id "
        "AND e.state='active' AND e.started_at_ms<=%s AND e.deadline_ms>%s "
        "AND p.account_id=%s AND p.character_id=%s AND p.eligible "
        "AND p.completed_at_ms IS NULL AND p.joined_at_ms<=%s "
        "AND EXISTS(SELECT 1 FROM environmental_profile_objectives q WHERE "
        "(q.profile_key,q.version)=(r.profile_key,r.version) AND q.family='resource_collect' "
        "AND q.target_reference=o.reference AND q.resource_step=o.native_step "
        "AND q.action_id=a.action_id) "
        "FOR UPDATE OF e,o,m,p FOR SHARE OF r,pop",
        (
            resource["resource_uid"],
            resource["map_id"],
            resource["instance_id"],
            rule["action_id"],
            now_ms,
            now_ms,
            account_id,
            character["id"],
            now_ms,
        ),
    ).fetchone()
    if row is None:
        raise ValueError("Resource is not an eligible owned environmental interaction")
    from .environmental_gameplay import _native_region

    if row["region_id"] is None or any(
        _native_region(resource["map_id"], entity) != row["region_id"]
        for entity in (character, resource)
    ):
        raise ValueError("Environmental interaction belongs to another native region")
    level = character.get("effective_level")
    if type(level) is not int or not row["level_min"] <= level <= row["level_max"]:
        raise ValueError("Environmental resource actor level is ineligible")
    for own, physical in (
        ("owned_map_id", "map_id"),
        ("owned_world_instance_id", "instance_id"),
        ("owned_x", "x"),
        ("owned_y", "y"),
        ("owned_z", "z"),
        ("owned_reference", "resource_reference"),
        ("owned_step", "stage"),
        ("owned_creation_time", "creation_time"),
    ):
        if row[own] != resource[physical] or type(row[own]) is not type(
            resource[physical]
        ):
            raise ValueError("Environmental owned resource incarnation changed")
    encoded = json.dumps(
        rule, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    if (
        row["original_action"] != rule
        or sha256(encoded).hexdigest() != row["action_sha256"]
    ):
        raise ValueError(
            "Environmental resource action differs from frozen original source"
        )
    from wakfu_server.resource_action_criteria import authorize

    authorize(rule, effective_level=level)
    if not presence.current(occupied, resource["map_id"], resource["instance_id"]):
        raise ValueError(
            "Environmental resource occupancy changed during authorization"
        )
    return dict(
        instance_id=row["instance_id"],
        profile_key=row["profile_key"],
        version=row["version"],
        native_scenario_id=row["native_scenario_id"],
        source_key=row["source_key"],
        source_authority=row["source_authority"],
        transition_policy="catalog_cvF",
        original_action_sha256=row["action_sha256"],
        destination_stage=0,
        region_id=row["region_id"],
    )
