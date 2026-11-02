"""Attested native scene replay for graphics owned separately from Door views."""
from functools import lru_cache
from pathlib import Path
import hashlib
import json

SOURCE_SHA256 = "cebdc42441d0457336948d1ec914307e6d52b9ba5b3bcb95436b36d409a7f5d5"


@lru_cache(maxsize=1)
def _rules():
    data = Path(__file__).with_name("dungeon_gate_presentation_rules.json").read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Native gate presentation source changed")
    return json.loads(data)["rules"]


def validate(topology):
    """Only an exact reviewed native Door can opt into its original script."""
    selected = []
    for door in topology.get("physical_doors", ()):
        key = door.get("presentation_rule")
        if key is None:
            continue
        matches = [r for r in _rules() if r["key"] == key]
        if len(matches) != 1:
            raise ValueError("Unknown native gate presentation binding")
        rule = matches[0]
        if (
            topology.get("asset_map_id") != rule["map_id"]
            or door.get("source_id") != rule["source_id"]
            or door.get("position") != rule["position"]
            or door.get("destination_room") != rule["destination_room"]
        ):
            raise ValueError("Native gate presentation contradicts its physical Door")
        if rule["source_id"] in {r["source_id"] for r in selected}:
            raise ValueError("Duplicate native gate presentation binding")
        selected.append(rule)
    return tuple(selected)


def packets(topology, *, opened_source_ids):
    """Replay after ordinary Door state on victory and map/reconnect bootstrap.

    The original script performs an idempotent picto fade; it does not change
    actors, collision, quests, room progress, items, or another instance.
    """
    from wakfu_server.dungeon_main_completion import presentation_packet

    opened = frozenset(opened_source_ids)
    return tuple(
        presentation_packet(rule["presentation"])
        for rule in validate(topology)
        if rule["source_id"] in opened
    )


def project_configuration(config, *, validated_pin=False):
    """Bind an attested older pin at read time without modifying earned progress.

    validated_pin is reserved for the immediate result of pinned_configuration,
    which already rehashes plan, topology and route. Its small remaining fields
    are still compared exactly; the default checks the entire configuration.
    Only the complete reviewed immutable configuration is accepted. A changed
    version, route, geometry, roster, or level policy gets no compatibility
    projection. The published configuration and all its hashes remain intact.
    """
    from wakfu_server.dungeon_runtime_config import canonical_hash

    if type(validated_pin) is not bool:
        raise ValueError("Native gate compatibility requires explicit pin validation")
    for rule in _rules():
        pin = rule.get("compatible_configuration")
        if (
            pin is None
            or config.get("route", {}).get("key") != pin["route_key"]
            or config.get("version") != pin["version"]
            or config.get("topology", {}).get("asset_map_id") != rule["map_id"]
        ):
            continue
        if validated_pin:
            remaining = {
                k: v
                for k, v in config.items()
                if k not in ("compiled_plan", "topology", "route")
            }
            if (
                config.get("evidence_hashes") != pin["validated_evidence_hashes"]
                or config.get("route") != pin["validated_route"]
                or remaining != pin["remaining_configuration"]
            ):
                continue
        elif canonical_hash(config) != pin["canonical_sha256"]:
            continue
        topology = config["topology"]
        projected = dict(
            topology,
            physical_doors=[
                dict(door, presentation_rule=rule["key"])
                if door["source_id"] == rule["source_id"]
                else dict(door)
                for door in topology["physical_doors"]
            ],
        )
        validate(projected)
        return dict(config, topology=projected)
    return config
