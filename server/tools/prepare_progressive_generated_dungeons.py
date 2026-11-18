"""Audit every dungeon and stage immutable progressive generated candidates.

This tool reads JSON inputs and writes local artifacts only. It does not connect
to a game server, change selections or runs, or restart any service.
"""

import argparse
import copy
import json
from pathlib import Path

from wakfu_server.dungeon_runtime_config import canonical_hash, level_selector
from wakfu_server.dungeon_optional_rooms import main_room_orders
from tools.prepare_family_linear_dungeons import progressive_family_roster
from tools.extract_dungeon_family_bosses import role_allowed
from wakfu_server.dungeon_monster_admission import admitted, require

GENERATED = "generated_native_species_policy"
POLICY = "progressive_published_native_family_v1"
SOURCE_FAMILY_POLICIES = frozenset(
    (
        "user_authorized_progressive_native_family_encounters",
        "user_authorized_progressive_native_trigger_family_rooms",
        "user_authorized_progressive_native_mixed_family_rooms",
    )
)


def mode(configuration):
    plan = configuration["compiled_plan"]
    return plan.get("roster_policy_evidence", {}).get("policy_mode") or plan.get(
        "policy_mode"
    )


def _audit_projected(configuration, native_monsters):
    """Measure actual configured grades, separately from roster composition."""
    catalog = {row["ref"]: row for row in native_monsters}
    main = main_room_orders(configuration["topology"])
    result = dict(
        route=configuration["route"]["key"],
        version=configuration["version"],
        source_sha256=canonical_hash(configuration),
        policy_mode=mode(configuration),
        level_policy=configuration["level_policy"]["mode"],
        main_room_orders=list(main),
        rooms=[],
    )
    for room in configuration["compiled_plan"]["rooms"]:
        order = room["order"]
        select = level_selector(configuration, room_order=order)
        species_by_key = {}
        for row in room["monsters"]:
            native = catalog[row["ref_id"]]
            level = select(
                native,
                dict(
                    min_level=row["native_min_level"], max_level=row["native_max_level"]
                ),
            )
            key = (row["ref_id"], level, row["role"])
            species_by_key[key] = species_by_key.get(key, 0) + row["count"]
        species = [
            dict(reference=ref, count=count, level=level, role=role)
            for (ref, level, role), count in species_by_key.items()
        ]
        quantity = sum(row["count"] for row in species)
        if quantity <= 0:
            raise ValueError("Encounter has no positive native composition")
        strength = sum(row["count"] * row["level"] for row in species)
        result["rooms"].append(
            dict(
                order=order,
                main=order in main,
                quantity=quantity,
                actual_spawn_level_sum=strength,
                weighted_mean_level=strength / quantity,
                composition=sorted(species, key=lambda row: row["reference"]),
            )
        )
    selected = [row for row in result["rooms"] if row["main"]]
    strengths = [row["actual_spawn_level_sum"] for row in selected]
    counts = [row["quantity"] for row in selected]
    composition = [
        tuple((m["reference"], m["count"]) for m in row["composition"])
        for row in selected
    ]
    result.update(
        strict_strength_increase=all(a < b for a, b in zip(strengths, strengths[1:])),
        strict_count_increase=all(a < b for a, b in zip(counts, counts[1:])),
        equal_counts=len(set(counts)) == 1,
        repeated_adjacent_compositions=[
            selected[i + 1]["order"]
            for i, (a, b) in enumerate(zip(composition, composition[1:]))
            if a == b
        ],
        metric="sum(count * actual configured native spawn level)",
        interpretation="Composition progression proxy, not certification of boss mechanics or overall fight difficulty",
    )
    return result


def audit(configuration, native_monsters):
    """Use the same logical entry-path projections as actual room spawning."""
    from wakfu_server import dungeon_entry_paths

    paths = dungeon_entry_paths.validate_policy(configuration["topology"])
    if not paths or configuration["topology"].get("selected_entry_path") is not None:
        return _audit_projected(configuration, native_monsters)
    qualified = {
        key: path for key, path in paths.items() if path["review_status"] == "qualified"
    }
    if not qualified:
        raise ValueError("No qualified native encounter path is available for audit")
    observations = {
        key: _audit_projected(
            dungeon_entry_paths.project_configuration(configuration, key),
            native_monsters,
        )
        for key in qualified
    }
    return dict(
        route=configuration["route"]["key"],
        version=configuration["version"],
        source_sha256=canonical_hash(configuration),
        policy_mode=mode(configuration),
        level_policy=configuration["level_policy"]["mode"],
        rooms=[],
        paths=observations,
        strict_strength_increase=all(
            row["strict_strength_increase"] for row in observations.values()
        ),
        strict_count_increase=all(
            row["strict_count_increase"] for row in observations.values()
        ),
        equal_counts=all(row["equal_counts"] for row in observations.values()),
        repeated_adjacent_compositions={
            key: row["repeated_adjacent_compositions"]
            for key, row in observations.items()
        },
        metric="sum(count * actual configured native spawn level)",
        interpretation="Separate qualified native entry paths; no flat concatenation of mutually exclusive source nodes",
    )


def prepare_source_recipe(
    configuration, native_monsters, *, version, capacity=None, admission_policy=None
):
    """Resize local encounters using only their published source actors.

    Logical path rank controls ordinary quotas. Special actor multiplicities,
    optional-only nodes, branch geometry and fixed actor identities retain their
    published authority.
    """
    from wakfu_server import dungeon_entry_paths
    from wakfu_server.dungeon_local_roster_policy import generated_quantity
    from wakfu_server.combat_fixed_actor_placement import declarations

    if admission_policy is None:
        raise ValueError("Explicit current native NPC admission policy is required")
    topology = configuration["topology"]
    paths = dungeon_entry_paths.validate_policy(topology)
    if paths:
        if any(path["review_status"] != "qualified" for path in paths.values()):
            raise ValueError(
                "Progression requires qualified encounter recipes for every entrance"
            )
        sequences = [path["main_source_orders"] for path in paths.values()]
    else:
        sequences = [list(main_room_orders(topology))]
    ranks = {}
    for sequence in sequences:
        for rank, order in enumerate(sequence, 1):
            stage = (rank, len(sequence))
            if order in ranks and ranks[order] != stage:
                raise ValueError(
                    "Shared source encounter has conflicting logical progression ranks"
                )
            ranks[order] = stage
    for branch in topology.get("branch_routes", ()):
        if (
            not isinstance(branch, dict)
            or [room["order"] for room in branch.get("rooms", ())] != sequences[0]
            or any("monsters" in room for room in branch["rooms"])
        ):
            raise ValueError(
                "Branch-specific encounter recipes require independent projection"
            )
    original = configuration["compiled_plan"]
    rows = {room["order"]: room for room in original["rooms"]}
    capacity = (
        (10 if max(total for _, total in ranks.values()) >= 4 else 8)
        if capacity is None
        else capacity
    )
    if type(capacity) is not int or not 3 <= capacity <= 10:
        raise ValueError(
            "Generated native formation capacity must be between three and ten"
        )
    catalog = {row["ref"]: row for row in native_monsters}
    plan = copy.deepcopy(original)
    changed = []
    scenes = {
        room["order"]: room.get("encounter_scene", {}) for room in topology["rooms"]
    }
    for room in plan["rooms"]:
        order = room["order"]
        if order not in ranks:
            continue
        rank, total = ranks[order]
        # Keep every source-qualified actor and vary only the same source's
        # ordinary entourage; unknown scripted roles never become bosses.
        target = generated_quantity(rank, total, capacity)
        monsters = room["monsters"]
        available = sum(row["count"] for row in monsters)
        if target == available:
            continue
        fixed = {row["reference"] for row in declarations(scenes.get(order, {}))}
        counts = []
        for row in monsters:
            native = catalog[row["ref_id"]]
            special = (
                row["role"] != "monster"
                or row["ref_id"] in fixed
                or bool(
                    set(native.get("raw_visual_arrays", {}).get("csc", ()))
                    & {13, 43, 115}
                )
            )
            counts.append(row["count"] if special else 0)
        if sum(counts) > target:
            raise ValueError(
                "Stage quota cannot retain its source-qualified encounter actors"
            )
        ordinary = [i for i, row in enumerate(monsters) if counts[i] == 0]
        if sum(counts) < target and not ordinary:
            raise ValueError(
                "Generated minimum cannot add unrelated actors to a scripted-only encounter"
            )
        while sum(counts) < target:
            eligible = ordinary
            # Weighted fair allocation preserves the published proportions and
            # stable row order; no species is imported from another source node.
            index = max(
                eligible, key=lambda i: (monsters[i]["count"] / (counts[i] + 1), -i)
            )
            counts[index] += 1
        room["monsters"] = [
            dict(row, count=count) for row, count in zip(monsters, counts) if count
        ]
        changed.append(order)
    if not changed:
        raise ValueError(
            "Published encounter recipes already fill their permitted progression quotas"
        )
    if "generated_fields" in plan:
        plan["generated_fields"] = [
            row for row in plan["generated_fields"] if row["order"] not in changed
        ]
    plan["roster_policy_evidence"] = dict(
        official=False,
        policy_mode=POLICY,
        previous_configuration_sha256=canonical_hash(configuration),
        previous_policy_mode=mode(configuration),
        species_pool_provenance="unchanged_per_source_encounter_recipe",
        preserved_special_actor_counts=True,
        changed_source_orders=changed,
        quantity_policy="minimum_three_native_ceiling_eight_or_ten_v2",
        admission_policy_sha256=canonical_hash(admission_policy),
    )
    plan["progression_policy"] = dict(
        policy=POLICY,
        allocation="weighted_published_source_recipe",
        capacity=capacity,
        source_stage_ranks={str(order): list(rank) for order, rank in ranks.items()},
        actual_spawn_level_policy=configuration["level_policy"]["mode"],
    )
    candidate = copy.deepcopy(configuration)
    candidate.update(version=version, compiled_plan=plan)
    candidate["context_policy"]["policy_version"] = version
    assessment = audit(candidate, native_monsters)
    if (
        not assessment["strict_strength_increase"]
        or not assessment["strict_count_increase"]
    ):
        raise ValueError(
            "Source-preserving quotas do not produce strictly increasing encounters on every path"
        )
    observations = (
        assessment.get("paths", {}).values() if "paths" in assessment else [assessment]
    )
    for observation in observations:
        for room in observation["rooms"]:
            for monster in room["composition"]:
                require(
                    admission_policy,
                    monster["reference"],
                    monster["level"],
                    monster["level"],
                    native=catalog[monster["reference"]],
                )
    plan["progression_policy"].update(
        metric=assessment["metric"], rooms=assessment["rooms"]
    )
    if "paths" in assessment:
        plan["progression_policy"]["paths"] = assessment["paths"]
    plan["document_sha256"] = canonical_hash(
        dict(
            rooms=plan["rooms"],
            policy=plan["roster_policy_evidence"],
            progression=plan["progression_policy"],
        )
    )
    candidate["evidence_hashes"]["plan"] = canonical_hash(plan)
    if topology.get("optional_vote_access") is not None:
        from wakfu_server.dungeon_optional_votes import rule_for

        # Keep native vote authority; rebind only its immutable plan identity.
        rule_for(configuration)
        candidate["topology"]["optional_vote_access"]["plan_sha256"] = plan[
            "document_sha256"
        ]
        candidate["evidence_hashes"]["topology"] = canonical_hash(candidate["topology"])
        rule_for(candidate)
    return candidate


def prepare_minimum_source_family(
    configuration, native_monsters, *, version, admission_policy
):
    """Fill deficient main encounters from their already-published native family.

    This is an explicit local reconstruction. Consumers with sealed encounter
    actions still need their exact new plan scope and native mechanic proof.
    """
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.combat_mission_allies import DECLARATIONS

    if (
        type(version) is not int
        or version <= configuration["version"]
        or configuration["compiled_plan"].get("official") is not False
        or configuration["compiled_plan"].get("reviewed_official") is not False
    ):
        raise ValueError(
            "New immutable nonofficial source-family reconstruction required"
        )
    if any(
        row["map_id"] == configuration["topology"]["asset_map_id"]
        for row in DECLARATIONS.values()
    ):
        raise ValueError(
            "Mission-owned native encounter recipe must retain its declared actors and quantities"
        )
    catalog = {row["ref"]: row for row in native_monsters}
    original = configuration["compiled_plan"]
    ordinary = {
        row["ref_id"]: row
        for room in original["rooms"]
        for row in room["monsters"]
        if row["role"] == "monster"
    }
    plan = copy.deepcopy(original)
    changes = []
    for room in plan["rooms"]:
        if room["order"] not in main_room_orders(configuration["topology"]):
            continue
        quantity = sum(row["count"] for row in room["monsters"])
        if quantity >= 3:
            continue
        families = {catalog[row["ref_id"]].get("family_id") for row in room["monsters"]}
        select = level_selector(configuration, room_order=room["order"])
        eligible = []
        for ref, row in ordinary.items():
            native = catalog[ref]
            if (
                native.get("family_id") is None
                or native["family_id"] not in families
                or set(native.get("raw_visual_arrays", {}).get("csc", ()))
                & {43, 45, 49, 99, 115}
            ):
                continue
            level = select(
                native,
                dict(
                    min_level=row["native_min_level"], max_level=row["native_max_level"]
                ),
            )
            if admitted(admission_policy, ref, level, level, native=native):
                eligible.append(ref)
        if not eligible:
            raise ValueError(
                "Deficient encounter lacks an already-admitted ordinary source-family actor"
            )
        reference = min(eligible, key=lambda ref: (catalog[ref]["min_level"], ref))
        existing = next(
            (
                row
                for row in room["monsters"]
                if row["ref_id"] == reference and row["role"] == "monster"
            ),
            None,
        )
        if existing is None:
            room["monsters"].append(
                dict(copy.deepcopy(ordinary[reference]), count=3 - quantity)
            )
        else:
            existing["count"] += 3 - quantity
        changes.append(
            dict(
                order=room["order"], added_reference=reference, added_count=3 - quantity
            )
        )
    if not changes:
        raise ValueError(
            "Published source encounters already satisfy the minimum three"
        )
    if "generated_fields" in plan:
        changed = {row["order"] for row in changes}
        plan["generated_fields"] = [
            row for row in plan["generated_fields"] if row["order"] not in changed
        ]
    plan["minimum_quantity_reconstruction"] = dict(
        policy="user_requested_minimum_three_same_native_family_v1",
        previous_configuration_sha256=canonical_hash(configuration),
        previous_document_sha256=original["document_sha256"],
        special_actor_multiplicities_preserved=True,
        changes=changes,
        ordinary_source="previously_published_admitted_route_family",
    )
    plan["document_sha256"] = canonical_hash(
        dict(
            rooms=plan["rooms"], reconstruction=plan["minimum_quantity_reconstruction"]
        )
    )
    topology = copy.deepcopy(configuration["topology"])
    if topology.get("optional_vote_access") is not None:
        from wakfu_server.dungeon_optional_votes import rule_for

        rule_for(configuration)
        topology["optional_vote_access"]["plan_sha256"] = plan["document_sha256"]
    candidate = prepare_configuration(
        plan,
        topology,
        configuration["route"],
        version=version,
        provenance=configuration["provenance"],
        level_policy=configuration["level_policy"],
    )
    assessment = audit(candidate, native_monsters)
    for observation in assessment.get("paths", {"main": assessment}).values():
        for room in observation["rooms"]:
            for monster in room["composition"]:
                require(
                    admission_policy,
                    monster["reference"],
                    monster["level"],
                    monster["level"],
                    native=catalog[monster["reference"]],
                )
    return candidate


def prepare(
    configuration, native_monsters, *, version, capacity=None, admission_policy=None
):
    """Replace only explicitly generated rosters, preserving native topology.

    The existing published species pool bounds generation; no unrelated native
    species, source-qualified event actors or reviewed quantities are guessed.
    """
    original = configuration["compiled_plan"]
    evidence = original.get("roster_policy_evidence", {})
    if (
        mode(configuration) not in ({GENERATED, POLICY} | SOURCE_FAMILY_POLICIES)
        or original.get("official") is not False
        or original.get("reviewed_official") is not False
        or type(version) is not int
        or version <= configuration["version"]
    ):
        raise ValueError(
            "Newer immutable version and explicitly nonofficial generated source required"
        )
    from wakfu_server.combat_mission_allies import DECLARATIONS

    mission_recipes = [
        row
        for row in DECLARATIONS.values()
        if row["map_id"] == configuration["topology"]["asset_map_id"]
    ]
    if mission_recipes:
        raise ValueError(
            "Mission-owned native encounter recipe must retain its declared actors and quantities"
        )
    main = main_room_orders(configuration["topology"])
    orders = [room["order"] for room in original["rooms"]]
    complex_recipe = (
        mode(configuration) in SOURCE_FAMILY_POLICIES
        or orders != list(main)
        or configuration["topology"].get("branch_routes")
        or configuration["topology"].get("entry_path_policy")
        or any(
            room.get("encounter_scene", {}).get("fixed_actor_placements")
            for room in configuration["topology"]["rooms"]
        )
        or not any(
            row.get("role") == "boss"
            for room in original["rooms"]
            for row in room["monsters"]
        )
    )
    if complex_recipe:
        return prepare_source_recipe(
            configuration,
            native_monsters,
            version=version,
            capacity=capacity,
            admission_policy=admission_policy,
        )
    if orders != list(range(1, len(orders) + 1)):
        raise ValueError("Generated room order must follow its logical native stages")
    references = sorted(
        set(evidence.get("source_species_pool", ()))
        | {row["ref_id"] for room in original["rooms"] for row in room["monsters"]}
    )
    catalog = {row["ref"]: row for row in native_monsters}
    actual_bosses = {
        row["ref_id"]
        for room in original["rooms"]
        for row in room["monsters"]
        if row.get("role") == "boss"
    }
    bosses = evidence.get(
        "boss_references", original.get("boss_references", sorted(actual_bosses))
    )
    if not bosses or set(bosses) != actual_bosses:
        raise ValueError("Published final-boss identity is unresolved")
    if any(
        row.get("role") == "boss"
        for room in original["rooms"][:-1]
        for row in room["monsters"]
    ):
        raise ValueError("Generated source has a boss before its final encounter")
    if any(
        set(catalog[ref].get("raw_visual_arrays", {}).get("csc", ())) & {13, 115}
        for ref in references
    ):
        raise ValueError(
            "Source-qualified controller or dominant actors cannot be rebuilt as ordinary generated slots"
        )
    capacity = (10 if len(orders) >= 4 else 8) if capacity is None else capacity
    if type(capacity) is not int or not 3 <= capacity <= 10:
        raise ValueError(
            "Generated native formation capacity must be between three and ten"
        )
    native = dict(
        native_species_pool=[
            dict(
                ref_id=ref,
                name_es=catalog[ref].get("name", str(ref)),
                min_level=catalog[ref]["min_level"],
                max_level=catalog[ref]["max_level"],
            )
            for ref in references
        ]
    )
    if admission_policy is None:
        raise ValueError("Explicit current native NPC admission policy is required")

    def supported(ref):
        native = catalog[ref]
        row = admission_policy.get("enabled_monsters", {}).get(str(ref))
        return row is not None and admitted(
            admission_policy,
            ref,
            native["min_level"],
            native["max_level"],
            native=native,
        )

    eligible = {
        ref
        for ref in references
        if role_allowed(catalog[ref], final_room=True, allowed_boss_references=bosses)
        and supported(ref)
    }
    roster = progressive_family_roster(
        native, len(orders), bosses, capacity=capacity, eligible_refs=eligible
    )
    plan = copy.deepcopy(original)
    plan["rooms"] = [
        dict(order=room["order"], monsters=room["monsters"], diagnostics=[])
        for room in roster["rooms"]
    ]
    # Old guide-slot indices describe a superseded generated composition. They
    # must not be reused as provenance for these explicit new family slots.
    plan.pop("generated_fields", None)
    plan["roster_policy_evidence"] = dict(
        official=False,
        policy_mode=POLICY,
        boss_references=sorted(bosses),
        source_species_pool=references,
        species_pool_provenance="previous_immutable_published_roster",
        previous_configuration_sha256=canonical_hash(configuration),
        previous_policy_mode=mode(configuration),
        previous_generated_fields_reused=False,
        quantity_policy="minimum_three_native_ceiling_eight_or_ten_v2",
    )
    plan["progression_policy"] = copy.deepcopy(roster["progression_policy"])
    plan[
        "local_policy"
    ] = "Explicit progressive generated native-family roster; preserve reviewed topology, native stage-grade selection and final bosses; supersede prior generated composition."
    plan["document_sha256"] = canonical_hash(
        dict(rooms=plan["rooms"], policy=plan["roster_policy_evidence"])
    )
    candidate = copy.deepcopy(configuration)
    candidate.update(version=version, compiled_plan=plan)
    candidate["context_policy"]["policy_version"] = version
    candidate["evidence_hashes"]["plan"] = canonical_hash(plan)
    assessment = audit(candidate, native_monsters)
    if (
        not assessment["strict_strength_increase"]
        or not assessment["strict_count_increase"]
    ):
        raise ValueError(
            "Strict roster quantity and actual native-grade progression do not fit the existing formation ceiling"
        )
    for room in assessment["rooms"]:
        for monster in room["composition"]:
            require(
                admission_policy,
                monster["reference"],
                monster["level"],
                monster["level"],
                native=catalog[monster["reference"]],
            )
    plan["roster_policy_evidence"]["admission_policy_sha256"] = canonical_hash(
        admission_policy
    )
    plan["progression_policy"].update(
        policy=POLICY,
        metric=assessment["metric"],
        actual_spawn_level_policy=configuration["level_policy"]["mode"],
        rooms=assessment["rooms"],
    )
    plan["document_sha256"] = canonical_hash(
        dict(
            rooms=plan["rooms"],
            policy=plan["roster_policy_evidence"],
            progression=plan["progression_policy"],
        )
    )
    candidate["evidence_hashes"]["plan"] = canonical_hash(plan)
    return candidate


def batch(configurations, native_monsters, *, admission_policy=None):
    """Account for every source route, including policies left for review."""
    records, candidates = [], []
    for configuration in configurations:
        record = dict(
            route=configuration["route"]["key"], version=configuration["version"]
        )
        try:
            record["before"] = audit(configuration, native_monsters)
        except (ValueError, KeyError, TypeError) as error:
            record["audit_error"] = str(error)
        observations = (
            record.get("before", {})
            .get("paths", {"main": record.get("before", {})})
            .values()
        )
        source_family_needs_revision = mode(
            configuration
        ) in SOURCE_FAMILY_POLICIES and any(
            any(
                room["quantity"] < 3
                for room in observation.get("rooms", ())
                if room["main"]
            )
            or (
                sum(room["main"] for room in observation.get("rooms", ())) >= 4
                and max(
                    (room["quantity"] for room in observation["rooms"] if room["main"]),
                    default=0,
                )
                < 10
            )
            for observation in observations
        )
        if (
            mode(configuration) not in (GENERATED, POLICY)
            and not source_family_needs_revision
        ):
            record.update(
                status="preserved_custom_or_progressive_policy",
                reason="Existing non-generated mechanics and reviewed encounter composition require separate review",
            )
        else:
            try:
                candidate = prepare(
                    configuration,
                    native_monsters,
                    version=configuration["version"] + 1,
                    admission_policy=admission_policy,
                )
            except (ValueError, KeyError, TypeError) as error:
                if (
                    str(error)
                    == "Published encounter recipes already fill their permitted progression quotas"
                ):
                    record.update(
                        status="already_meets_quantity_policy",
                        reason="Published source encounters already satisfy the native quantity quotas",
                    )
                else:
                    record.update(status="candidate_blocked", reason=str(error))
            else:
                record.update(
                    status="candidate_prepared",
                    after=audit(candidate, native_monsters),
                    candidate_version=candidate["version"],
                    candidate_sha256=canonical_hash(candidate),
                )
                candidates.append(candidate)
        records.append(record)
    return dict(
        schema_version=1,
        records=records,
        candidates=candidates,
        installed=False,
        existing_runs_changed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configurations", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admission-policy", type=Path, required=True)
    args = parser.parse_args()
    configurations = json.loads(args.configurations.read_text())
    monsters = json.loads(args.native_monsters.read_text())
    if isinstance(monsters, dict):
        monsters = monsters["monsters"]
    args.output.write_text(
        json.dumps(
            batch(
                configurations,
                monsters,
                admission_policy=json.loads(args.admission_policy.read_text()),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
