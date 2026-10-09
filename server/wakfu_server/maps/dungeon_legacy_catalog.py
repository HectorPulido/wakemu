"""Explicit local registry for native dungeon maps without an aKU definition.

Map localization and transport records remain native evidence. Runtime identity
and guide-derived species membership are local registration policy.
"""
import copy
import hashlib
import json

POLICY_MODE = "local_legacy_map_registry"
LOCAL_ID_NAMESPACE = 1_000_000


def register(
    evidence, document, native_sources, native_monsters, *, native_definition_ids=()
):
    """Validate primary map/route evidence and return a non-native runtime entry."""
    map_id = evidence.get("asset_map_id")
    if type(map_id) is not int or not 0 < map_id <= 32767:
        raise ValueError("Invalid native asset map identity")
    if evidence.get("native_dungeon_definition_id") is not None:
        raise ValueError("Legacy registration cannot claim a native dungeon definition")
    if evidence.get("native_localization_key") != f"content.77.{map_id}":
        raise ValueError("Native map localization key does not identify this map")
    if (
        not isinstance(evidence.get("native_localization_value"), str)
        or not evidence["native_localization_value"].strip()
    ):
        raise ValueError("Missing native map localization value")
    slug = document.get("dungeon", {}).get("slug")
    if not slug or evidence.get("guide_slug") != slug:
        raise ValueError("Guide identity differs from map evidence")
    runtime_id = LOCAL_ID_NAMESPACE + map_id
    if runtime_id in native_definition_ids:
        raise ValueError("Local runtime identity conflicts with native definition")
    sources = {source["id"]: source for source in native_sources}
    routes = evidence.get("incoming_native_routes", [])
    if not routes:
        raise ValueError("Legacy dungeon requires a native entry route")
    approved = []
    for route in routes:
        source = sources.get(route.get("source_id"))
        destination = route.get("destination")
        if (
            source is None
            or source["map_id"] != route.get("source_map_id")
            or source["map_id"] == map_id
            or not isinstance(destination, dict)
            or destination.get("map_id") != map_id
            or destination not in source.get("destinations", [])
        ):
            raise ValueError("Legacy entry route differs from native catalog")
        approved.append(copy.deepcopy(route))
    catalog = {monster["ref"]: monster for monster in native_monsters}
    pool = sorted(
        {
            monster["ref_id"]
            for room in document.get("rooms", [])
            for monster in room.get("monsters", [])
            if monster.get("ref_id") is not None
        }
    )
    if not pool or any(
        type(ref) is not int or ref <= 0 or ref not in catalog for ref in pool
    ):
        raise ValueError("Guide-derived species pool has unresolved native references")
    for ref in pool:
        row = catalog[ref]
        if (
            type(row.get("min_level")) is not int
            or type(row.get("max_level")) is not int
            or not 0 < row["min_level"] <= row["max_level"]
        ):
            raise ValueError("Guide-derived species has invalid native grade bounds")
    canonical = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return {
        "schema_version": 1,
        "policy_mode": POLICY_MODE,
        "runtime_definition_id": runtime_id,
        "native_definition_id": None,
        "identity_namespace": "local_legacy_native_map",
        "asset_map_id": map_id,
        "slug": slug,
        "name": evidence["native_localization_value"],
        "native_localization_key": evidence["native_localization_key"],
        "identity_evidence_sha256": hashlib.sha256(canonical).hexdigest(),
        "identity_evidence": copy.deepcopy(evidence),
        "entry_routes": approved,
        "species_pool": pool,
        "species_pool_provenance": "guide_verified_native_references",
        "official_native_definition": False,
        "runtime_imported": False,
        "route_criteria_policy": "Preserve and evaluate native criterion, seasonal dates, achievement gates, cyZ, and item requirements.",
    }


def policy_definition(entry):
    """Adapter for local roster drafting, without a raw_cno native-pool claim."""
    if (
        entry.get("policy_mode") != POLICY_MODE
        or entry.get("native_definition_id") is not None
    ):
        raise ValueError("Invalid legacy registry entry")
    return {
        "id": entry["runtime_definition_id"],
        "type": "LOCAL_LEGACY_MAP",
        "name_fr": entry["name"],
        "raw_aHA": [entry["asset_map_id"]],
        "local_species_pool": list(entry["species_pool"]),
        "species_pool_provenance": entry["species_pool_provenance"],
        "native_definition_id": None,
        "policy_mode": POLICY_MODE,
    }


def validate_legacy_route(raw, native_sources):
    """Return core route fields after validating explicit local registration."""
    core = {
        "key",
        "template_id",
        "definition_id",
        "entry_map_id",
        "entry_object_id",
        "destination_id",
        "start_map_id",
        "criterion",
    }
    metadata = {
        "registration_policy",
        "native_definition_id",
        "native_template_id",
        "native_localization_key",
    }
    if not isinstance(raw, dict) or set(raw) != core | metadata:
        raise ValueError("Invalid legacy route configuration fields")
    if (
        raw["registration_policy"] != POLICY_MODE
        or raw["native_definition_id"] is not None
    ):
        raise ValueError("Invalid legacy route provenance")
    for field in core - {"key", "criterion"}:
        if type(raw[field]) is not int or raw[field] <= 0:
            raise ValueError("Invalid legacy route numeric field")
    map_id = raw["start_map_id"]
    if (
        map_id > 32767
        or raw["definition_id"] != LOCAL_ID_NAMESPACE + map_id
        or raw["template_id"] != LOCAL_ID_NAMESPACE + map_id
    ):
        raise ValueError("Legacy runtime identity does not belong to its asset map")
    if raw["native_localization_key"] != f"content.77.{map_id}":
        raise ValueError("Legacy localization key does not belong to its asset map")
    if (
        not isinstance(raw["key"], str)
        or not raw["key"]
        or not isinstance(raw["criterion"], str)
    ):
        raise ValueError("Malformed legacy route key or criterion")
    if type(raw["native_template_id"]) is not int:
        raise ValueError("Malformed native legacy template identity")
    if isinstance(native_sources, dict):
        source = native_sources.get((raw["entry_map_id"], raw["entry_object_id"]))
    else:
        source = next(
            (
                s
                for s in native_sources
                if s["map_id"] == raw["entry_map_id"]
                and s["id"] == raw["entry_object_id"]
            ),
            None,
        )
    destination = (
        None
        if source is None
        else next(
            (
                d
                for d in source["destinations"]
                if d["destination_id"] == raw["destination_id"]
            ),
            None,
        )
    )
    if (
        destination is None
        or destination["map_id"] != map_id
        or destination["criterion"] != raw["criterion"]
        or destination["cyZ"] != raw["native_template_id"]
        or raw["entry_map_id"] == map_id
    ):
        raise ValueError(
            "Legacy route differs from native transport map, criterion, or template"
        )
    return {field: raw[field] for field in core}


def registered_routes(entry):
    """Expose exact native routes with explicit local runtime identities."""
    routes = []
    for incoming in entry["entry_routes"]:
        destination = incoming["destination"]
        routes.append(
            {
                "key": f"legacy-map-{entry['asset_map_id']}-{incoming['source_id']}-{destination['destination_id']}",
                "definition_id": entry["runtime_definition_id"],
                "template_id": entry["runtime_definition_id"],
                "entry_map_id": incoming["source_map_id"],
                "entry_object_id": incoming["source_id"],
                "destination_id": destination["destination_id"],
                "start_map_id": entry["asset_map_id"],
                "criterion": destination["criterion"],
                "registration_policy": POLICY_MODE,
                "native_definition_id": None,
                "native_template_id": destination["cyZ"],
                "native_localization_key": entry["native_localization_key"],
            }
        )
    return routes
