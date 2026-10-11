#!/usr/bin/env python3
"""Plan explicit local fishing distribution; never install or claim official spawns."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import random
import math
from pathlib import Path


def stable_uid(map_id, x, y, z):
    digest = hashlib.sha256(
        f"wakemu:fishing-slot:v1:{map_id}:{x}:{y}:{z}".encode()
    ).digest()
    return (int.from_bytes(digest[:8], "big") & ((1 << 61) - 1)) | (1 << 61)


def plan(
    catalog,
    evidence,
    *,
    surface,
    geometry,
    max_per_map=8,
    spacing=4,
    source_sha256,
    policy=None,
    suitable=None,
    navigation=None,
    supports_action=None,
):
    if (
        type(max_per_map) is not int
        or max_per_map < 0
        or type(spacing) is not int
        or spacing < 0
    ):
        raise ValueError("Invalid fishing density or spacing")
    policy = dict(
        policy
        or dict(
            seed=20261010,
            density_basis_points=7500,
            max_per_map=16,
            minimum_spacing=4,
            level_scale=50,
            level_power=2,
            precious_weight_basis_points=200,
        )
    )
    max_per_map = policy.get("max_per_map", max_per_map)
    spacing = policy.get("minimum_spacing", spacing)
    full = policy.get("coverage_mode") == "all_accessible"
    expected = {
        "seed",
        "density_basis_points",
        "max_per_map",
        "minimum_spacing",
        "level_scale",
        "level_power",
        "precious_weight_basis_points",
    }
    if full:
        expected |= {
            "coverage_mode",
            "minimum_per_species",
            "allow_species_ground_fallback",
        }
    if (
        set(policy) != expected
        or type(policy["seed"]) is not int
        or type(policy["density_basis_points"]) is not int
        or not 0 <= policy["density_basis_points"] <= 10000
        or type(max_per_map) is not int
        or max_per_map < (0 if full else 1)
        or type(spacing) is not int
        or spacing < 0
        or type(policy["precious_weight_basis_points"]) is not int
        or not 0 <= policy["precious_weight_basis_points"] <= 10000
        or type(policy["level_scale"]) not in (int, float)
        or policy["level_scale"] <= 0
        or not math.isfinite(policy["level_scale"])
        or type(policy["level_power"]) not in (int, float)
        or policy["level_power"] <= 0
    ):
        raise ValueError("Invalid explicit fishing distribution policy")
    if not math.isfinite(policy["level_power"]):
        raise ValueError("Invalid fishing level power")
    if full and (
        max_per_map != 0
        or spacing != 0
        or policy["density_basis_points"] != 10000
        or type(policy["minimum_per_species"]) is not int
        or policy["minimum_per_species"] < 1
        or type(policy["allow_species_ground_fallback"]) is not bool
        or navigation is None
    ):
        raise ValueError("Full fishing coverage requires uncapped native navigation")
    rng = random.Random(policy["seed"])
    definitions = {}
    variants = {}
    for resource in catalog:
        if resource.get("monster_resource", False):
            continue
        stages = [
            (stage["stage_id"], action)
            for stage in resource["stage_definitions"]
            for action in stage["actions"]
            if action["profession_id"] == 75
            and (
                (
                    supports_action(action)
                    if supports_action is not None
                    else action["item_reference"] > 0
                    and not action["criteria"].strip()
                    and action["raw_getters"]["cvF"] == 0
                )
            )
        ]
        if stages:
            variants[resource["resource_reference"]] = sorted(
                stages,
                key=lambda entry: (
                    entry[0] != 1,
                    entry[1]["minimum_level"],
                    entry[0],
                    entry[1]["action_id"],
                ),
            )
            definitions[resource["resource_reference"]] = (
                resource,
                min(
                    stages,
                    key=lambda entry: (
                        entry[0] != 1,
                        entry[1]["minimum_level"],
                        entry[0],
                        entry[1]["action_id"],
                    ),
                ),
            )
    candidates = evidence["candidate_surfaces"]
    xy = defaultdict(set)
    for row in candidates:
        xy[(row["map_id"], row["x"], row["y"])].add(row["z"])
    incoming, excluded, valid = {}, Counter(), []
    map_errors = {}
    for row in sorted(candidates, key=lambda r: (r["map_id"], r["y"], r["x"], r["z"])):
        mid = row["map_id"]
        position = tuple(row[k] for k in ("x", "y", "z"))
        if len(xy[(mid, *position[:2])]) != 1:
            excluded["ambiguous_height_at_same_xy"] += 1
            continue
        if mid not in incoming:
            try:
                incoming[mid] = (
                    navigation(mid)
                    if navigation is not None
                    else {
                        tuple(b)
                        for a, b in geometry(mid)["edges"]
                        if tuple(a) != tuple(b)
                    }
                )
            except (ValueError, KeyError, FileNotFoundError) as error:
                incoming[mid] = None
                map_errors[str(mid)] = str(error)
        if incoming[mid] is None:
            excluded["unknown_server_geometry"] += 1
            continue
        if position not in incoming[mid]:
            excluded["no_exact_incoming_edge"] += 1
            continue
        if navigation is not None and not incoming[mid][position]["approaches"]:
            excluded["no_native_resource_approach"] += 1
            continue
        try:
            ground = (
                incoming[mid][position]
                if navigation is not None
                else surface(mid, *position)
            )
        except (ValueError, KeyError, FileNotFoundError):
            excluded["unknown_server_planting_surface"] += 1
            continue
        if ground["ground_id"] != row["ground_id"]:
            excluded["ground_provenance_mismatch"] += 1
            continue
        refs = []
        for ref in row["eligible_resource_references"]:
            if ref not in definitions:
                continue
            resource = definitions[ref][0]
            # Evidence has native suitability; server surface must agree exactly.
            if navigation is not None and ref not in ground["eligible_refs"]:
                continue
            if (
                navigation is None
                and suitable is not None
                and suitable(ground["ground_id"], resource) <= 0
            ):
                continue
            refs.append(ref)
        if not refs:
            excluded["no_supported_common_harvest"] += 1
            continue
        valid.append((row, sorted(set(refs))))
    selected, map_counts, ref_counts, used_xy = [], Counter(), Counter(), set()
    assets = {asset["map_id"]: asset for asset in evidence["assets"]}

    def available(row):
        mid = row["map_id"]
        return (
            (full or map_counts[mid] < max_per_map)
            and (mid, row["x"], row["y"]) not in used_xy
            and (
                spacing == 0
                or all(
                    abs(row["x"] - old["x"]) + abs(row["y"] - old["y"]) >= spacing
                    for old in selected
                    if old["map_id"] == mid
                )
            )
        )

    def choose(row, ref, *, fallback=False):
        common = definitions[ref][1]
        options = variants[ref]
        weighted = [
            1.0 if option == common else policy["precious_weight_basis_points"] / 10000
            for option in options
        ]
        if full:
            alternates = [option for option in options if option != common]
            stage, action = (
                rng.choice(alternates)
                if alternates
                and rng.randrange(10000) < policy["precious_weight_basis_points"]
                else common
            )
        else:
            stage, action = rng.choices(options, weights=weighted, k=1)[0]
        placement = {key: row[key] for key in ("map_id", "x", "y", "z")}
        placement.update(
            resource_uid=stable_uid(**placement),
            instance_id=0,
            resource_reference=ref,
            stage=stage,
            respawn_seconds=None,
            provenance=dict(
                distribution="local-native-terrain",
                official_spawn=False,
                generator_version=1,
                source_evidence_sha256=source_sha256,
                native_ground_id=row["ground_id"],
                native_chunk=row["chunk"],
                environment_chunk_sha256=row["environment_chunk_sha256"],
                asset=assets[row["map_id"]],
                eligible_resource_references=row["eligible_resource_references"],
                minimum_profession_level=action["minimum_level"],
                action_id=action["action_id"],
                variant_rule="local_common_vs_alternate_stage_not_native_rarity",
                common_stage=common[0],
                selected_alternate=(stage, action) != common,
            ),
        )
        placement["provenance"]["species_ground_policy"] = (
            "local-fishing-ground-fallback" if fallback else "native-compatible"
        )
        selected.append(placement)
        map_counts[row["map_id"]] += 1
        ref_counts[ref] += 1
        used_xy.add((row["map_id"], row["x"], row["y"]))

    # Reserve native-compatible slots for every species before weighted filling.
    if full:
        by_ref = {
            ref: [(row, refs) for row, refs in valid if ref in refs]
            for ref in definitions
        }
        for ref in sorted(definitions, key=lambda ref: (len(by_ref[ref]), ref)):
            for _ in range(policy["minimum_per_species"]):
                choices = [row for row, refs in by_ref[ref] if available(row)]
                fallback = False
                if not choices and policy["allow_species_ground_fallback"]:
                    choices = [
                        row
                        for row, refs in valid
                        if available(row) and row["ground_id"] > 0 and refs
                    ]
                    fallback = True
                if choices:
                    choose(rng.choice(choices), ref, fallback=fallback)
                else:
                    excluded["species_minimum_unavailable"] += 1
    # A seeded local policy, rather than a claim about official population.
    for row, refs in sorted(
        valid,
        key=lambda pair: (
            len(pair[1]) != 1,
            pair[0]["map_id"],
            pair[0]["y"],
            pair[0]["x"],
        ),
    ):
        if not available(row):
            continue
        weights = [
            (1 + definitions[ref][1][1]["minimum_level"] / policy["level_scale"])
            ** -policy["level_power"]
            for ref in refs
        ]
        ref = rng.choices(refs, weights=weights, k=1)[0]
        level_weight = (
            1 + definitions[ref][1][1]["minimum_level"] / policy["level_scale"]
        ) ** -policy["level_power"]
        if (
            not full
            and rng.random() * 10000 >= policy["density_basis_points"] * level_weight
        ):
            excluded["density_and_level_probability"] += 1
            continue
        choose(row, ref)
    return dict(
        schema_version=1,
        distribution="local-native-terrain",
        official_distribution=False,
        applied=False,
        max_per_map=max_per_map,
        spacing=spacing,
        policy_snapshot=policy,
        distribution_policy=policy,
        evidence_kind="local_generated_from_native_terrain",
        placements=sorted(selected, key=lambda p: (p["map_id"], p["y"], p["x"])),
        selected_species=sorted(ref_counts),
        species_counts={str(ref): ref_counts[ref] for ref in sorted(definitions)},
        minimum_species_failures=[
            ref
            for ref in sorted(definitions)
            if full and ref_counts[ref] < policy["minimum_per_species"]
        ],
        accessible_candidate_slots=len(valid),
        allocated_slots=len(selected),
        eligible_surfaces_by_minimum_level=dict(
            Counter(
                min(definitions[ref][1][1]["minimum_level"] for ref in refs)
                for row, refs in valid
            )
        ),
        eligible_species_surface_counts=dict(
            Counter(ref for row, refs in valid for ref in refs)
        ),
        stage_audit=[
            dict(
                resource_reference=ref,
                common_stage=definitions[ref][1][0],
                variants=[
                    dict(
                        stage=stage,
                        action_id=action["action_id"],
                        item_reference=action["item_reference"],
                        minimum_level=action["minimum_level"],
                        native_terminal_stage=action["raw_getters"]["cvF"],
                    )
                    for stage, action in options
                ],
                native_rare_label_verified=False,
            )
            for ref, options in sorted(variants.items())
        ],
        excluded_species=sorted(set(definitions) - set(ref_counts)),
        exclusions=dict(excluded),
        geometry_errors=map_errors,
        unsupported_asset_chunks=evidence.get("errors", []),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--navigation-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.fishing_navigation import _incoming
    from wakfu_server.fishing_products import supports_action

    policy = json.loads(args.policy.read_text())
    indexes = {}

    def navigation(map_id):
        if map_id not in indexes:
            indexes[map_id] = _incoming(
                json.loads((args.navigation_dir / f"{map_id}.json").read_text()), map_id
            )
        return indexes[map_id]

    data = args.candidates.read_bytes()
    evidence = json.loads(data)
    with native_catalog._database().connection() as db:
        occupied = set(
            tuple(row[key] for key in ("map_id", "x", "y"))
            for row in db.execute(
                "SELECT map_id,x,y FROM planted_resources UNION SELECT map_id,x,y FROM mining_vein_slots WHERE enabled"
            ).fetchall()
        )
    original_count = len(evidence["candidate_surfaces"])
    evidence["candidate_surfaces"] = [
        row
        for row in evidence["candidate_surfaces"]
        if (row["map_id"], row["x"], row["y"]) not in occupied
    ]
    result = plan(
        native_catalog.load(DATA_ROOT / "plant-resources.json"),
        evidence,
        surface=None,
        geometry=None,
        source_sha256=hashlib.sha256(data).hexdigest(),
        policy=policy,
        navigation=navigation,
        supports_action=supports_action,
    )
    result["catalog_revision"] = native_catalog.release()
    result["excluded_existing_resource_positions"] = original_count - len(
        evidence["candidate_surfaces"]
    )
    native_catalog._database().close()
    try:
        native_catalog._redis().close()
    except KeyError:
        pass
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "allocated_slots",
                    "selected_species",
                    "minimum_species_failures",
                    "exclusions",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
