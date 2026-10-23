"""Rebuild explicitly nonofficial generated rosters without changing live runs.

This is a new local composition policy, not recovery of mismatched guide-slot
provenance. The published roster bounds the source pool; no new species enter.
"""
import copy

from wakfu_server.dungeon_local_roster_policy import draft
from wakfu_server.dungeon_runtime_config import canonical_hash


def prepare(configuration, native_monsters, admission_policy, *, version):
    original = configuration["compiled_plan"]
    evidence = original.get("roster_policy_evidence", {})
    if (
        original.get("official") is not False
        or original.get("reviewed_official") is not False
        or evidence.get("policy_mode") != "generated_native_species_policy"
        or evidence.get("official") is not False
        or version <= configuration["version"]
    ):
        raise ValueError(
            "Explicit nonofficial generated composition and newer version required"
        )
    rooms = original["rooms"]
    quantities = {
        room["order"]: sum(row["count"] for row in room["monsters"]) for room in rooms
    }
    references = sorted({row["ref_id"] for room in rooms for row in room["monsters"]})
    bosses = evidence.get("boss_references")
    actual_bosses = {
        row["ref_id"]
        for room in rooms
        for row in room["monsters"]
        if row.get("role") == "boss"
    }
    if (
        not bosses
        or set(bosses) != actual_bosses
        or any(
            row.get("role") == "boss" for room in rooms[:-1] for row in room["monsters"]
        )
    ):
        raise ValueError("Published final-boss identity is unresolved")
    source = copy.deepcopy(original)
    source["rooms"] = [
        dict(
            order=room["order"],
            monsters=[],
            diagnostics=["explicit_nonofficial_admitted_roster_rebuild"],
        )
        for room in rooms
    ]
    prepared = draft(
        source,
        dict(id=original["definition_id"], raw_cno=references),
        native_monsters,
        generation_target=max(quantities.values()),
        generation_targets=quantities,
        boss_references=bosses,
        admission_policy=admission_policy,
    )
    plan = copy.deepcopy(original)
    plan["rooms"] = [
        dict(order=room["order"], monsters=room["monsters"], diagnostics=[])
        for room in prepared["rooms"]
    ]
    plan["generated_fields"] = [
        dict(order=room["order"], policy_applied=True, fields=room["generated_fields"])
        for room in prepared["rooms"]
    ]
    plan[
        "local_policy"
    ] = "Explicit nonofficial rebuild of existing ordered rooms using admitted members of the published species pool; preserve room quantities and final-boss identity."
    plan["roster_policy_evidence"] = dict(
        official=False,
        policy_mode="generated_native_species_policy",
        boss_references=bosses,
        species_pool_provenance="previous_immutable_published_roster",
        source_species_pool=references,
        admitted_species_pool=prepared["admitted_species_pool"],
        excluded_unadmitted_references=prepared["excluded_unadmitted_references"],
        admission_policy_sha256=canonical_hash(admission_policy),
        previous_configuration_sha256=canonical_hash(configuration),
        previous_generated_fields_reused=False,
    )
    plan["document_sha256"] = canonical_hash(
        dict(rooms=plan["rooms"], policy=plan["roster_policy_evidence"])
    )
    provenance = "Explicit nonofficial admitted-roster rebuild; existing ordered native topology, room quantities and final boss preserved; mismatched legacy guide-slot annotations superseded."
    # Preserve the already validated topology verbatim. Rebuilding its unrelated
    # transport catalog here would not add roster authority.
    candidate = copy.deepcopy(configuration)
    candidate.update(version=version, compiled_plan=plan, provenance=provenance)
    candidate["evidence_hashes"]["plan"] = canonical_hash(plan)
    # Roster correction does not change level selection or dungeon context rules.
    candidate["level_policy"] = dict(
        configuration["level_policy"], provenance=provenance
    )
    candidate["context_policy"] = dict(
        configuration["context_policy"], policy_version=version, provenance=provenance
    )
    return candidate


def install_candidates(db, candidates, *, apply=False):
    """Review or activate staged candidates inside the caller's transaction.

    The caller owns deployment timing and database backup. This function never
    edits players, instances, frozen runs, historical configurations or rosters.
    All candidates are recomputed against current indexed native authority before
    any version is inserted. Default review performs no writes.
    """
    from wakfu_server.dungeon_runtime_config import (
        install_configuration,
        prepare_configuration,
    )

    revision = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()["revision"]
    records = db.execute(
        "SELECT record_key,payload FROM native_catalog_records WHERE revision=%s "
        "AND path='native-npc-spell-effect-trees.json' AND collection='activation_policy'",
        (revision,),
    ).fetchall()
    policy = {row["record_key"]: row["payload"] for row in records}
    pending, actions, seen = [], [], set()
    for candidate in candidates:
        key = candidate["route"]["key"]
        if key in seen:
            raise ValueError("Duplicate staged dungeon route")
        seen.add(key)
        if apply:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"dungeon_runtime_config:{key}",),
            )
        current = db.execute(
            "SELECT a.policy_version,c.configuration FROM dungeon_runtime_active_configurations a "
            "JOIN dungeon_runtime_configurations c USING(route_key,policy_version) WHERE a.route_key=%s",
            (key,),
        ).fetchone()
        context = db.execute(
            "SELECT policy_version FROM dungeon_context_active_policies WHERE route_key=%s",
            (key,),
        ).fetchone()
        if (
            current is None
            or context is None
            or context["policy_version"] != current["policy_version"]
        ):
            raise ValueError("Dungeon configuration/context active pointers disagree")
        source = current["configuration"]
        if candidate["compiled_plan"]["roster_policy_evidence"][
            "previous_configuration_sha256"
        ] != canonical_hash(source):
            raise ValueError("Staged dungeon source configuration changed")
        references = candidate["compiled_plan"]["roster_policy_evidence"][
            "source_species_pool"
        ]
        native = db.execute(
            "SELECT payload FROM native_catalog_records WHERE revision=%s AND path='monsters.json' "
            "AND collection='monsters' AND record_key=ANY(%s)",
            (revision, [str(ref) for ref in references]),
        ).fetchall()
        expected = prepare(
            source,
            [row["payload"] for row in native],
            policy,
            version=candidate["version"],
        )
        canonical = prepare_configuration(
            candidate["compiled_plan"],
            candidate["topology"],
            candidate["route"],
            version=candidate["version"],
            provenance=candidate["provenance"],
        )
        if candidate != expected or candidate != canonical:
            raise ValueError(
                "Staged dungeon candidate differs from current native policy"
            )
        pending.append(candidate)
        actions.append(
            dict(
                route_key=key,
                previous_version=source["version"],
                candidate_version=candidate["version"],
                source_sha256=canonical_hash(source),
                candidate_sha256=canonical_hash(candidate),
            )
        )
    if apply:
        for candidate in pending:
            install_configuration(db, candidate)
    return dict(
        status="ACTIVATED_FUTURE_RUNS_ONLY" if apply else "READY_NOT_ACTIVATED",
        actions=actions,
        existing_runs_changed=False,
    )
