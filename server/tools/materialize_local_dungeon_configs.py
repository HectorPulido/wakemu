"""Materialize explicit local roster drafts separately from guide evidence.

This command emits configuration JSON only. It never changes original evidence,
activates a database policy, or restarts world.
"""
import argparse
import copy
import json
from pathlib import Path

from wakfu_server.maps.dungeon_runtime_config import (
    canonical_hash,
    prepare_configuration,
)
from wakfu_server.dungeon_instances import _load_routes


POLICY = "generated_native_species_policy"


def materialize(batch, routes, topologies, native_monsters, *, version):
    if batch.get("policy_mode") != POLICY or batch.get("official") is not False:
        raise ValueError("Explicit non-official local roster policy required")
    from wakfu_server.dungeon_monster_admission import current_policy, require

    admission_policy = current_policy()
    from wakfu_server.dungeon_local_roster_policy import BOSS_PROPERTIES

    native = {row["ref"]: row for row in native_monsters}
    configurations, coverage = [], []
    for draft in batch["drafts"]:
        slug = draft["slug"]
        reasons = []
        if (
            draft.get("official") is not False
            or draft.get("reviewed_official") is not False
            or draft.get("policy_mode") != POLICY
        ):
            raise ValueError("Draft misrepresents generated local policy")
        matching = [
            route
            for route in routes
            if route["definition_id"] == draft["definition_id"]
        ]
        legacy = draft.get("identity_policy") == "local_legacy_map_registry"
        if legacy and matching:
            if any(
                route.get("registration_policy") != "local_legacy_map_registry"
                for route in matching
            ):
                raise ValueError("Legacy identity cannot use a native definition route")
            # Explicit local selection among independently verified native variants.
            matching = [
                min(
                    matching,
                    key=lambda r: (
                        r["destination_id"],
                        r["entry_map_id"],
                        r["entry_object_id"],
                    ),
                )
            ]
        if len(matching) != 1:
            reasons.append("missing_or_ambiguous_native_route")
        topology = topologies.get(slug)
        if topology is None:
            reasons.append("missing_native_topology")
        rooms = []
        for room in draft["rooms"]:
            monsters = []
            for monster in room["monsters"]:
                reference = native.get(monster["ref_id"])
                if reference is None or (
                    monster["native_min_level"],
                    monster["native_max_level"],
                ) != (reference["min_level"], reference["max_level"]):
                    raise ValueError("Local roster contradicts native monster bounds")
                if room["policy_applied"] and monster["ref_id"] not in (
                    draft["species_pool"] if legacy else draft["native_species_pool"]
                ):
                    raise ValueError(
                        "Generated monster leaves native dungeon species pool"
                    )
                properties = reference.get("raw_visual_arrays", {}).get("csc", [])
                if (
                    room["policy_applied"]
                    and set(properties) & BOSS_PROPERTIES
                    and monster.get("role") != "boss"
                ):
                    raise ValueError(
                        "Generated ordinary slots cannot contain native boss actors; explicit encounter composition required"
                    )
                require(
                    admission_policy,
                    monster["ref_id"],
                    reference["min_level"],
                    reference["max_level"],
                    native=reference,
                )
                monsters.append(copy.deepcopy(monster))
            rooms.append(dict(order=room["order"], monsters=monsters, diagnostics=[]))
        if reasons:
            coverage.append(dict(slug=slug, configuration_ready=False, reasons=reasons))
            continue
        route = matching[0]
        _load_routes([route])
        original = draft["original_plan"]
        plan = dict(
            slug=slug,
            source_url=original["source_url"],
            source_sha256=original["source_sha256"],
            document_sha256=canonical_hash(draft),
            definition_id=route["definition_id"],
            template_id=route["template_id"],
            asset_map_id=route["start_map_id"],
            rooms=rooms,
            diagnostics=[],
            roster_ready=True,
            policy_mode=POLICY,
            official=False,
            reviewed_official=False,
            original_guide_document_sha256=original["document_sha256"],
            local_policy=copy.deepcopy(draft["policy"]),
            generated_fields=[
                dict(
                    order=r["order"],
                    policy_applied=r["policy_applied"],
                    fields=r["generated_fields"],
                )
                for r in draft["rooms"]
            ],
        )
        if legacy:
            plan["identity_policy"] = "local_legacy_map_registry"
            plan["native_definition_id"] = None
            plan["species_pool_provenance"] = draft["species_pool_provenance"]
            plan[
                "entry_route_selection_policy"
            ] = "local_lowest_verified_destination_id"
        try:
            config = prepare_configuration(
                plan,
                topology,
                route,
                version=version,
                provenance="Explicit local generated_native_species_policy; official=false; native species and statistics, local room/count policy.",
            )
        except ValueError as error:
            reasons.append(str(error))
        else:
            configurations.append(config)
        coverage.append(
            dict(slug=slug, configuration_ready=not reasons, reasons=reasons)
        )
    coverage.extend(
        dict(slug=row["slug"], configuration_ready=False, reasons=[row["reason"]])
        for row in batch.get("excluded", [])
    )
    return dict(schema_version=1, configurations=configurations), dict(
        schema_version=1,
        official=False,
        runtime_imported=False,
        policy_mode=POLICY,
        summary=dict(dungeons=len(coverage), configuration_ready=len(configurations)),
        coverage=coverage,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("drafts", "routes", "topologies", "native_monsters", "output"):
        parser.add_argument("--" + field.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--legacy-routes", type=Path)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text())
    routes = read(args.routes)
    if args.legacy_routes:
        routes.extend(read(args.legacy_routes)["routes"])
    bundle, coverage = materialize(
        read(args.drafts),
        routes,
        read(args.topologies),
        read(args.native_monsters)["monsters"],
        version=args.version,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, value in [
        ("configurations.json", bundle),
        ("coverage.json", coverage),
    ]:
        (args.output / filename).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        )
    print(json.dumps(coverage["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
