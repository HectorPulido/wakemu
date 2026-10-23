#!/usr/bin/env python3
"""Reconcile immutable item inventory with current source and a read-only local snapshot."""
import argparse
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "agents_docs/reports/item-actions-inventory-20261019"
PRIVATE = ROOT / ".runtime/item-inventory-reconciliation-20261020"
SNAPSHOT = PRIVATE / "local-catalog-snapshot.json"
INPUTS = {}
QUALIFICATIONS = {}


def current_presentation(row):
    """Keep historical findings explicit; current columns describe this snapshot."""
    for key in (
        "implementation_status",
        "implementation_notes",
        "route",
        "evidence",
        "downstream_limits",
    ):
        row.setdefault("baseline_" + key, row.get(key, ""))
    row["implementation_status"] = row["source_status"]
    row["implementation_notes"] = row["current_evidence"]
    row["downstream_limits"] = row["limitation"]
    row["evidence"] = row["current_evidence"]
    if (
        not row.get("route")
        and row.get("use_action_id")
        and row["source_status"]
        in ("implemented", "implemented_contextual", "implemented_limited")
    ):
        row[
            "route"
        ] = "13220 native inventory action; subsequent domain protocol where applicable"
    return row


def read_json(path):
    path = ROOT / path
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def record_file(path):
    path = ROOT / path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    INPUTS[str(path.relative_to(ROOT))] = digest
    return digest


def passing_unittest_log(raw):
    # stdout audit data can flush after unittest's stderr summary. Require the
    # real nonempty summaries to pass, rather than requiring OK as the last
    # line or accepting an arbitrary printed OK token.
    summaries = re.findall(
        r"^Ran (\d+) tests? in [0-9.]+s\r?\n\r?\n([^\r\n]+)(?:\r?\n|$)",
        raw,
        flags=re.MULTILINE,
    )
    return bool(summaries) and all(
        int(count) > 0 and outcome == "OK" for count, outcome in summaries
    )


def qualification(name, timestamps, source_files):
    paths = [
        timestamp
        if "/" in timestamp
        else f".runtime/consumable-effects-20261019/tests-20261020T{timestamp}Z.log"
        for timestamp in timestamps
    ]
    qualification_receipts(name, paths, source_files)


def qualification_receipts(name, paths, source_files, test_files=()):
    receipts = []
    for path in paths:
        raw = (ROOT / path).read_text()
        if not passing_unittest_log(raw):
            raise ValueError(f"Qualification receipt is not passing: {path}")
        receipts.append(dict(path=path, sha256=record_file(path)))
    sources = {path: record_file(path) for path in source_files}
    tests = {path: record_file(path) for path in test_files}
    QUALIFICATIONS[name] = dict(
        receipts=receipts, current_source_sha256=sources, current_test_sha256=tests
    )


def release_delivery(release):
    """Locate the immutable delivery bundle identified by a release tag."""
    matches = []
    for path in (ROOT / ".runtime").rglob("activation.json"):
        try:
            if json.loads(path.read_text()).get("release") == release:
                matches.append(path.parent)
        except (OSError, ValueError):
            continue
    if not matches:
        raise ValueError(f"No immutable delivery activation found for {release}")
    return max(matches, key=lambda path: path.stat().st_mtime)


def release_audit(activation, *, current_image=None):
    release = activation["release"]
    directory = release_delivery(release)
    build_path = directory / "build-receipt.json"
    verify_path = directory / "image-verification.json"
    probe_path = directory / "character-selection-result.json"
    build = read_json(str(build_path.relative_to(ROOT)))
    verification = read_json(str(verify_path.relative_to(ROOT)))
    probe = read_json(str(probe_path.relative_to(ROOT)))
    world = activation["services"]["world"]
    expected_image = verification["reports"]["world"]["expected"]["/app"]
    observed_image = verification["reports"]["world"]["image_id"]
    if observed_image != world["id"] or verification.get("qualified") is not True:
        raise ValueError(f"Image verification does not match activation for {release}")
    if build.get("release") != release or build.get("source_stable") is not True:
        raise ValueError(f"Complete source build is not stable for {release}")
    probe_checks = {
        "qualified": probe.get("qualified") is True,
        "account_authenticated": probe.get("account_authenticated") is True,
        "character_selected": probe.get("character_selected") is True,
        "native_actor_snapshot": probe.get("selected_actor_in_12666") is True,
        "inventory_registry": probe.get("selected_inventory_registry_seen") is True,
        "inventory_format4": 4 in probe.get("inventory_formats_seen", []),
        "inventory_request_after_selection": probe.get(
            "sent12851_after_selection_without_format10"
        )
        is True,
        "journal_after_selection": probe.get("journal_reply") is True,
        "socket_alive_after_journal": probe.get("socket_alive_after_journal") is True,
        "company_packet_matches_owned_database": probe.get(
            "company_packet_matches_owned_database"
        )
        is True,
    }
    if not all(probe_checks.values()):
        raise ValueError(
            f"Native selection probe is incomplete for {release}: {probe_checks}"
        )
    current_source = {
        path: digest for path, digest in activation.get("verified_source", {}).items()
    }
    inventory = build.get("input_files_after", {})
    if not inventory:
        raise ValueError(f"Complete source inventory is missing for {release}")
    return {
        "release": release,
        "world_image_tag": world["image"],
        "world_image_id": world["id"],
        "current_image_match": current_image == world["id"] if current_image else None,
        "schema_version": activation.get("schema_version"),
        "build_inventory_sha256": activation.get("build_inventory_sha256"),
        "complete_build_input_count": len(inventory),
        "activation_verified_source_count": len(current_source),
        "build_source_stable": build["source_stable"],
        "image_files_verified": len(expected_image),
        "image_verification_qualified": verification["qualified"],
        "character_selection_probe": probe_checks,
        "character_selection_result_path": str(probe_path.relative_to(ROOT)),
        "activation_path": str((directory / "activation.json").relative_to(ROOT)),
        "build_receipt_path": str(build_path.relative_to(ROOT)),
        "image_verification_path": str(verify_path.relative_to(ROOT)),
    }


def psql(sql):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'exec psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1',
        ],
        input="BEGIN READ ONLY;\n" + sql + "\nROLLBACK;\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=True,
    )
    return [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]


def capture_local():
    tables = {
        "native_simple_item_actions": ["item_ref", "available", "unavailable_reason"],
        "native_random_item_actions": ["item_ref", "available", "unavailable_reasons"],
        "native_consumable_actions": ["item_ref", "available", "unsupported_reason"],
        "native_book_item_actions": ["item_ref"],
        "native_pet_xp_actions": ["item_ref"],
        "native_emote_item_actions": ["item_ref"],
        "native_script_item_actions": ["item_ref"],
        "native_conversion_item_actions": ["item_ref"],
        "native_reading_scenario_item_actions": ["item_ref"],
        "native_pet_feeding_food_policy": ["item_ref", "effect_kind"],
        "native_pet_hibernation_food_policy": ["item_ref"],
        "native_pet_models": ["reference", "model_id"],
        "native_neutrality_item_actions": ["item_ref"],
        "native_captain_map_item_actions": ["item_ref"],
        "native_journal_part_item_actions": ["item_ref"],
        "native_world_marker_item_actions": ["item_ref"],
        "native_achievement_item_actions": [
            "item_ref",
            "action_id",
            "definition_id",
            "minimum_real_level",
            "positional_suffix",
            "consumes_source",
            "source_sha256",
            "descriptor",
        ],
    }
    header = psql(
        "SELECT jsonb_build_object('schema_version',(SELECT max(version) FROM schema_migrations),'catalog_revision',(SELECT revision FROM native_catalog_active WHERE id=1),'guild_policy',(SELECT value FROM settings WHERE name='guild_policy'),'present_tables',(SELECT jsonb_agg(tablename) FROM pg_tables WHERE schemaname=current_schema()));"
    )[0]
    selects = []
    for table, columns in tables.items():
        if table in header["present_tables"]:
            selects.append(
                "SELECT jsonb_build_object('table','"
                + table
                + "','rows',COALESCE((SELECT jsonb_agg(t) FROM (SELECT "
                + ",".join(columns)
                + " FROM "
                + table
                + ") t),'[]'::jsonb));"
            )
    records = psql("\n".join(selects))
    header["tables"] = {entry["table"]: entry["rows"] for entry in records}
    header["captured_at"] = datetime.now(timezone.utc).isoformat()
    world_id = subprocess.check_output(
        ["docker", "compose", "ps", "-q", "world"], cwd=ROOT, text=True
    ).strip()
    header["world_image"] = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.Image}}", world_id], text=True
    ).strip()
    data_program = (
        "import hashlib,json; from pathlib import Path; "
        "paths=['wakfu_server/items/native_ranch_creatures.json','wakfu_server/items/native_binding_assembly_contract.json','wakfu_server/items/native_empty_equipment_effects.json']; "
        "print(json.dumps({p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in paths if (Path('/app')/p).exists()}))"
    )
    header["deployed_native_data_sha256"] = json.loads(
        subprocess.check_output(
            ["docker", "compose", "exec", "-T", "world", "python", "-c", data_program],
            cwd=ROOT,
            text=True,
        )
    )
    PRIVATE.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(header, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-local",
        action="store_true",
        help="Read catalog tables only; never mutate DB or services",
    )
    args = parser.parse_args()
    if args.refresh_local:
        capture_local()
    local = read_json(str(SNAPSHOT.relative_to(ROOT)))
    activation = read_json(
        ".runtime/consumable-effects-20261019/expansion-activation.json"
    )
    runtime_verified = local["world_image"] == activation["services"]["world"]["id"]
    current_release = release_audit(activation, current_image=local["world_image"])
    current_directory = release_delivery(activation["release"])
    previous_path = current_directory / "previous-activation.json"
    if not previous_path.exists():
        previous_pins = read_json(
            str((current_directory / "previous-image-pins.json").relative_to(ROOT))
        )
        previous_world_tag = previous_pins.get("WAKFU_WORLD_IMAGE")
        if not isinstance(previous_world_tag, str) or ":" not in previous_world_tag:
            raise ValueError("Previous release lacks an actual pinned World image")
        previous_path = (
            release_delivery(previous_world_tag.rsplit(":", 1)[1]) / "activation.json"
        )
    previous_activation = read_json(str(previous_path.relative_to(ROOT)))
    previous_release = release_audit(previous_activation)
    release_history = {"current": current_release, "previous": previous_release}
    QUALIFICATIONS["local_release_native_selection"] = {
        "current": current_release,
        "previous": previous_release,
    }
    current_image_files = read_json(current_release["image_verification_path"])[
        "reports"
    ]["world"]["expected"]["/app"]

    def source_is_deployed(path, digest):
        explicit = activation.get("verified_source", {}).get(
            path.removeprefix("server/"),
            activation.get("verified_source", {}).get(path),
        )
        if explicit == digest:
            return True
        image_path = path.removeprefix("server/")
        return current_image_files.get(image_path) == digest

    baseline_path = REPORT / "consumables-and-actions.csv"
    INPUTS[str(baseline_path.relative_to(ROOT))] = hashlib.sha256(
        baseline_path.read_bytes()
    ).hexdigest()
    baseline = list(csv.DictReader(baseline_path.open()))
    if len(baseline) != 6645 or len({row["reference"] for row in baseline}) != 6645:
        raise ValueError(
            "Historical primary inventory no longer contains 6645 unique references"
        )
    rows = {}
    for original in baseline:
        row = dict(original)
        implemented = row["implementation_status"] == "implemented"
        row.update(
            baseline_status=row["implementation_status"],
            user_scope="excluded_legacy_set"
            if row["use_action_class"] == "bIl"
            else "active",
            source_status="implemented" if implemented else "missing",
            local_status=(
                "loaded_baseline" if runtime_verified else "baseline_route_unverified"
            )
            if implemented
            else "not_loaded",
            qualification="historical_route_catalog_audit"
            if implemented
            else "not_qualified",
            current_evidence="Historical catalog/route baseline; not individual GUI acceptance",
            limitation=row.get("downstream_limits", ""),
            blocker_kind="" if implemented else "implementation_missing",
            source_migration="",
            secondary_contexts="[]",
            delivery_note="",
        )
        if row["implementation_status"] == "code_present_disabled":
            row.update(
                source_status="disabled",
                local_status="disabled",
                blocker_kind="disabled_policy",
            )
        if row["user_scope"] == "excluded_legacy_set":
            row.update(
                source_status="excluded",
                local_status="excluded",
                qualification="excluded_by_user",
                blocker_kind="excluded_by_user",
            )
        rows[int(row["reference"])] = row

    achievement_action_path = (
        "server/wakfu_server/items/native_achievement_item_actions.json"
    )
    achievement_actions = read_json(achievement_action_path)["actions"]
    achievement_actions_by_ref = {
        item["item_ref"]: item for item in achievement_actions
    }
    achievement_descriptor_sha256 = hashlib.sha256(
        (ROOT / achievement_action_path).read_bytes()
    ).hexdigest()

    def loaded(table, reference):
        records = local["tables"].get(table, [])
        if table == "native_achievement_item_actions":
            expected = achievement_actions_by_ref.get(reference)
            return expected is not None and any(
                item.get("item_ref") == reference
                and item.get("descriptor") == expected
                and item.get("source_sha256") == achievement_descriptor_sha256
                and item.get("action_id") == expected["action_id"]
                and item.get("definition_id") == expected["definition_id"]
                and item.get("minimum_real_level") == expected["minimum_real_level"]
                and item.get("positional_suffix") is expected["positional_suffix"]
                and item.get("consumes_source") is False
                for item in records
            )
        return any(
            item.get("item_ref") == reference and item.get("available", True)
            for item in records
        )

    def mark(
        reference,
        evidence,
        *,
        table=None,
        migration=None,
        status="implemented",
        qualification="source_and_focused_cohort",
        limitation="",
        blocker="",
        runtime_source=None,
        deployed_source_digest=None,
    ):
        if reference not in rows:
            return  # Contextual pet foods/resources are reported separately, not double-counted.
        row = rows[reference]
        is_loaded = (
            loaded(table, reference)
            if table
            else (migration is not None and local["schema_version"] >= migration)
        )
        if runtime_source:
            digest = deployed_source_digest or record_file(runtime_source)
            # Routes without a new migration need their actual delivered module.
            is_loaded = source_is_deployed(runtime_source, digest) and (
                is_loaded if table or migration else True
            )
        row.update(
            source_status=status,
            local_status=(
                "loaded" if runtime_verified else "catalog_present_runtime_unverified"
            )
            if is_loaded
            else "not_loaded",
            qualification=qualification,
            current_evidence=evidence,
            source_migration=migration or "",
            limitation="; ".join(
                filter(None, (row.get("downstream_limits", ""), limitation))
            ),
            blocker_kind=blocker,
        )

    def secondary_context(
        reference, *, name, evidence, migration, runtime_source, table, qualification
    ):
        """Record a qualified secondary behavior without changing primary totals."""
        digest = record_file(runtime_source)
        deployed = source_is_deployed(runtime_source, digest)
        is_loaded = (
            runtime_verified
            and local["schema_version"] >= migration
            and loaded(table, reference)
            and deployed
        )
        row = rows[reference]
        contexts = json.loads(row["secondary_contexts"])
        contexts.append(
            dict(
                name=name,
                source_status="implemented_contextual",
                local_status="loaded" if is_loaded else "not_loaded",
                qualification=qualification,
                evidence=evidence,
                source_migration=migration,
                runtime_source=runtime_source,
                runtime_source_sha256=digest,
            )
        )
        row["secondary_contexts"] = json.dumps(
            contexts, sort_keys=True, separators=(",", ":")
        )

    # Historical learning coverage did not prove that its preset could be selected.
    selection_sources = (
        "server/wakfu_server/characters/cosmetics.py",
        "server/wakfu_server/items/equipment_appearance.py",
        "server/wakfu_server/combat/combat_cosmetic_conditions.py",
    )
    qualification("pet_direct_cosmetic_selection", ["170908755909"], selection_sources)
    selection_hashes = QUALIFICATIONS["pet_direct_cosmetic_selection"][
        "current_source_sha256"
    ]
    selection_loaded = runtime_verified and all(
        activation.get("verified_source", {}).get(path.removeprefix("server/"))
        == digest
        for path, digest in selection_hashes.items()
    )
    selection_count = 0
    for row in rows.values():
        if row["use_action_class"] == "bIt" and row.get("cosmetic_category") in (
            "2",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
        ):
            selection_count += 1
            row["limitation"] = (
                "Selection and reconnect source-qualified; loaded locally; rendered acceptance pending"
                if selection_loaded
                else "Selection and reconnect source-qualified; not yet verified in local image"
            )
            row["qualification"] += ";pet_direct_cosmetic_selection"
            row[
                "current_evidence"
            ] += "; native selection/pet/equipment projection and real learning transactions pass focused cohort"
    if selection_count != 283:
        raise ValueError("Unexpected pet/direct cosmetic selection reference count")

    qualification(
        "standard_equipment_wp_reduction",
        ["173348326414", "173504717361"],
        ("server/wakfu_server/items/equipment_stats.py",),
    )
    qualification(
        "ordered_equipment_scalar_reductions",
        ["191024303293"],
        [
            "server/wakfu_server/items/equipment_characteristics.py",
            "server/wakfu_server/items/equipment_stats.py",
            "server/wakfu_server/items/shard_bonuses.py",
            "server/wakfu_server/items/consumable_characteristics.py",
            "server/wakfu_server/characters/companion_equipment.py",
            "server/wakfu_server/combat/combat_companions.py",
        ],
    )
    qualification(
        "equipment_getcharac_reconciliation",
        ["194110875618", "194159962309", "194240964176"],
        [
            "server/wakfu_server/items/equipment_eligibility.py",
            "server/wakfu_server/items/equipment.py",
            "server/wakfu_server/items/equipment_conditions.py",
            "server/wakfu_server/items/equipment_characteristics.py",
            "server/wakfu_server/items/equipment_stats.py",
            "server/wakfu_server/items/builds.py",
            "server/wakfu_server/characters/companion_equipment.py",
            "server/wakfu_server/combat/combat_characteristic_conditions.py",
        ],
    )
    qualification(
        "equipment_addition_order_search",
        ["195145050337", "195031020350", "195127437006"],
        ["server/wakfu_server/items/equipment_eligibility.py"],
    )
    qualification(
        "equipment_dynamic_scalar_and_static_roles",
        [
            "200051295970",
            "200055917097",
            "200114811605",
            "201203655247",
            "201554426917",
            "201617851847",
            "201638773167",
        ],
        [
            "server/wakfu_server/items/equipment_stats.py",
            "server/wakfu_server/items/equipment_eligibility.py",
            "server/wakfu_server/combat/combat_equipment_passive_completeness.py",
            "server/wakfu_server/combat/combat_equipment_snapshot_roles.py",
        ],
    )
    qualification(
        "equipment_reactive_trigger_5886",
        ["214547005812"],
        [
            "server/wakfu_server/combat/combat_equipment_reactive_trigger_contract.py",
            "server/wakfu_server/combat/combat_operation_registry.py",
            "server/wakfu_server/combat/combat_owned_equipment.py",
            "server/wakfu_server/combat/combat_equipment_snapshot_roles.py",
        ],
    )
    qualification(
        "simple_native_use_context_and_reusable_source",
        ["213707142890"],
        [
            "server/wakfu_server/items/simple_item_actions.py",
            "server/wakfu_server/items/native_simple_item_use_contexts.json",
        ],
    )
    qualification(
        "guild_identity_cost_custody",
        ["214502691903"],
        ["server/wakfu_server/characters/guild_service.py"],
    )
    qualification(
        "equipment_cosmetic_flag17",
        ["220655396847"],
        ["server/wakfu_server/combat/combat_equipment_null_carrier_contract.py"],
    )
    qualification(
        "equipment_profession_modifiers",
        ["221233796101", "220938090524"],
        [
            "server/wakfu_server/storage/profession_equipment_modifiers.py",
            "server/wakfu_server/storage/profession_equipment_effects.json",
            "server/wakfu_server/storage/profession_consumable_modifiers.py",
        ],
    )
    qualification(
        "equipment_resource_maximum_and_actor_hydration",
        ["220856061509", "221635165900", "221940291546", "222638427147"],
        [
            "server/wakfu_server/items/equipment_resource_projection.py",
            "server/wakfu_server/items/equipment_resource_bonuses.py",
            "server/wakfu_server/items/equipment_context.py",
            "server/wakfu_server/items/equipment_eligibility.py",
            "server/wakfu_server/items/equipment_conditions.py",
            "server/wakfu_server/items/equipment.py",
            "server/wakfu_server/items/equipment_stats.py",
        ],
    )
    qualification(
        "equipment_persisted_context_and_ecology_publication",
        ["220658690024"],
        [
            "server/wakfu_server/characters/equipment_persisted_context.py",
            "server/wakfu_server/wire.py",
        ],
    )
    qualification(
        "equipment_start_characteristic_2636",
        ["204849526316", "210536269836"],
        [
            "server/wakfu_server/combat/combat_equipment_start_characteristic_contract.py",
            "server/wakfu_server/combat/combat_owned_equipment.py",
            "server/wakfu_server/combat/combat_equipment_initialization.py",
            "server/wakfu_server/combat/combat_equipment_snapshot_roles.py",
            "server/wakfu_server/items/equipment_eligibility.py",
        ],
    )
    qualification(
        "bound_conversion_capacity_and_hero_expiry_publication",
        ["205013682758"],
        [
            "server/wakfu_server/items/item_action_delivery.py",
            "server/wakfu_server/items/consumable_world_lifecycle.py",
            "server/wakfu_server/items/consumable_world_publication.py",
            "server/local_game_server.py",
        ],
    )
    qualification(
        "recustomization_stack_receipt_history",
        ["203606661389", "203622291844", "203755715367"],
        [
            "server/wakfu_server/characters/character_recustomization.py",
            "server/migrations/226_recustomization_receipt_history.sql",
        ],
    )
    qualification(
        "mount_transferred_owner_receipt_fence",
        ["204124057989"],
        ["server/wakfu_server/items/mount_feeding.py"],
    )
    qualification(
        "consumable_company_membership_clocks",
        ["204426415198"],
        [
            "server/wakfu_server/characters/heroes.py",
            "server/wakfu_server/items/consumable_world_lifecycle.py",
        ],
    )
    qualification(
        "native_random_use_admission",
        ["204236966061", "204341484763"],
        [
            "server/wakfu_server/items/random_item_actions.py",
            "server/migrations/227_native_random_item_use_criteria.sql",
            "server/protocol/native-random-item-use-criteria.json",
        ],
    )
    qualification(
        "shushu_healing_and_known_recipe_crafting",
        ["181203783482", "181859337575", "182559956223", "182157380517"],
        (
            "server/wakfu_server/combat/combat_weapon.py",
            "server/wakfu_server/items/crafting.py",
        ),
    )

    simple = read_json("server/protocol/native-simple-item-actions.json")["actions"]
    for item in simple:
        if item["available"]:
            mark(
                item["item_ref"],
                "Native simple action descriptor; phase1 automated/local delivery",
                table="native_simple_item_actions",
                migration=197,
            )
        else:
            mark(
                item["item_ref"],
                item["unavailable_reason"],
                status="native_data_unavailable",
                qualification="explicit_native_gap",
                blocker="missing_native_output_or_consumption_rule",
            )
    fragment_policy_path = ".runtime/random-native-reassessment-20261021/fragment-policy-qualification.json"
    fragment_policy = read_json(fragment_policy_path)
    fragment = next(
        item
        for item in simple
        if item["item_ref"] == fragment_policy["native_item_ref"]
    )
    if (
        fragment_policy["native_item_ref"] != 15931
        or fragment["action_id"] != fragment_policy["native_action_id"]
        or fragment["required_quantity"] != fragment_policy["native_count"]
        or fragment["output_ref"] != fragment_policy["output_ref"]
        or fragment_policy["required_quantity"] != 1
        or fragment_policy["output_quantity"] != 1
        or fragment_policy["descriptor_migration_197_unchanged"] is not True
    ):
        raise ValueError(
            "Zero-count fragment policy must retain original quantity0 descriptor"
        )
    fragment_source = fragment_policy["source_file"]
    fragment_digest = record_file(fragment_source)
    fragment_receipts = []
    for receipt in fragment_policy["receipts"]:
        fragment_receipts.append(
            dict(
                path=receipt["path"],
                sha256=record_file(receipt["path"]),
                claim=receipt["claim"],
            )
        )
    fragment_present = any(
        row["item_ref"] == 15931
        and row.get("available") is False
        and row.get("unavailable_reason") == fragment["unavailable_reason"]
        for row in local["tables"].get("native_simple_item_actions", [])
    )
    mark(
        15931,
        "General Wakemu zero-count/native-consumes-source policy requires1owned unit;all105 positive merge counts unchanged;output15934x1 and reallevel100;rawSQL197 staysquantity0",
        migration=197,
        runtime_source=fragment_source,
        qualification="qualified_zero_count_consuming_fragment_policy",
        limitation="Item action only; no invented full quest progression or XP",
    )
    if not fragment_present or not source_is_deployed(fragment_source, fragment_digest):
        rows[15931]["local_status"] = "not_loaded"
        rows[15931][
            "delivery_note"
        ] = "Qualified zero-count fragment policy is source-present; matching helper is not deployed; original descriptor intentionally remainsquantity0"
    QUALIFICATIONS["zero_count_fragment_policy"] = dict(
        policy_path=fragment_policy_path,
        original_descriptor_quantity=0,
        runtime_required_quantity=1,
        tested_source_sha256=fragment_policy["source_sha256"],
        observed_source_sha256=fragment_digest,
        qualified_current_source=fragment_digest == fragment_policy["source_sha256"]
        or fragment_digest
        == read_json(".runtime/item-haven-world-criteria-20261021/qualification.json")[
            "current_hashes"
        ].get(fragment_source),
        final_context_qualification=".runtime/item-haven-world-criteria-20261021/qualification.json",
        source_deployed=source_is_deployed(fragment_source, fragment_digest),
        descriptor_present=fragment_present,
        receipts=fragment_receipts,
        qualification="Three new cases passed in a mixed process, one corrected capacity control passed separately; native descriptor not rewritten",
        full_quest_lifecycle=False,
    )
    random = read_json("server/protocol/native-random-item-actions.json")["actions"]
    extension = read_json("server/protocol/native-random-item-extensions.json")
    extended = {item["item_ref"] for item in extension["actions"]}
    for item in random:
        if item["available"] or item["item_ref"] in extended:
            mark(
                item["item_ref"],
                "Native random descriptor and atomic typed delivery; extension214 tests3/3 for10 Rift boxes"
                if item["item_ref"] in extended
                else "Native random descriptor; baseline random tests9/9",
                table="native_random_item_actions",
                migration=214 if item["item_ref"] in extended else 200,
                limitation="Explicit documented weighted server draw policy; original server draw engine unavailable",
            )
        else:
            mark(
                item["item_ref"],
                "Native random descriptor rejects: "
                + ",".join(item["unavailable_reasons"]),
                status="native_data_unavailable",
                qualification="explicit_native_gap",
                blocker="missing_native_"
                + (
                    "table"
                    if "missing_table" in item["unavailable_reasons"]
                    else "item"
                ),
            )
    food = read_json("server/protocol/native-consumable-actions.json")["items"]
    anti_ko_refs = {10657, 15980, 20471, 24265}
    transform_freeze_path = (
        ROOT
        / ".runtime/item-action-readiness-20261020/transformations/source-freeze.json"
    )
    transforms_qualified = False
    if transform_freeze_path.exists():
        freeze = read_json(transform_freeze_path)
        transforms_qualified = (
            freeze.get("exit_code") == 0
            and freeze.get("tests_passed") == 14
            and (ROOT / freeze["visual_oracle"]).exists()
            and all(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == checksum
                for path, checksum in freeze["source_hashes"].items()
            )
        )
    for item in food:
        transformation = rows.get(item["item_ref"], {}).get("family") == "type:738"
        if item["available"]:
            mark(
                item["item_ref"],
                "Current native consumable plan and actual shared runtime",
                table="native_consumable_actions",
                migration=212
                if transformation
                else (209 if item["item_ref"] == 18422 else 198),
                status="integration_wip"
                if transformation and not transforms_qualified
                else "implemented",
                qualification=(
                    "native_oracle_and_14_focused_tests"
                    if transforms_qualified
                    else "descriptor_available_runtime_qualification_pending"
                )
                if transformation
                else "source_and_focused_cohort",
                limitation="Official-client rendered appearance/particles acceptance remains pending"
                if transformation
                else "",
                blocker="native_HMI_runtime_qualification"
                if transformation and not transforms_qualified
                else "",
            )
        else:
            reason = item.get(
                "unsupported_reason", "native effect composition unresolved"
            )
            mark(
                item["item_ref"],
                reason,
                status="native_data_unavailable"
                if "no_native_action_or_effect" in reason
                else "missing",
                qualification="explicit_native_gap"
                if "no_native_action_or_effect" in reason
                else "native_semantics_pending",
                blocker="no_native_payload"
                if "no_native_action_or_effect" in reason
                else "native_state_lifecycle_unimplemented",
            )
    # Entire small native families are already partitioned uniquely by the baseline.
    family_routes = {
        "bHU": (
            "native_book_item_actions",
            203,
            "Original reusable book route;160 qualified",
        ),
        "bHY": (
            "native_emote_item_actions",
            204,
            "Original target-aware single-use emote route;8 qualified",
        ),
        "bHX": (
            "native_pet_xp_actions",
            204,
            "Original pet-level food/feeding route;3 qualified",
        ),
        "bIb": (None, 201, "Identity-preserving dressing room entitlement;4 qualified"),
        "bHT": (
            None,
            207,
            "Original three-UID fusion;typed custody and appearance persistence",
        ),
    }
    for reference, row in rows.items():
        if row["use_action_class"] in family_routes:
            table, migration, evidence = family_routes[row["use_action_class"]]
            mark(reference, evidence, table=table, migration=migration)
    teleports = read_json("server/wakfu_server/items/native_item_teleports.json")[
        "items"
    ]
    for item in teleports:
        mark(
            item["item_ref"],
            "Native teleport/recall authority; full company/position transition",
            migration=202,
            limitation="Recall temporarily uses Astrub by explicit user policy"
            if item["item_ref"] == 14306
            else "Documented destination arrival policy",
        )
    scripts = read_json("server/wakfu_server/items/native_item_scripts.json")["items"]
    for item in scripts:
        mark(
            item["item_ref"],
            "Original native visual script descriptor;41 qualified;postcommit World publication tested",
            table="native_script_item_actions",
            migration=211,
        )
    if (ROOT / "server/wakfu_server/items/native_item_conversions.json").exists():
        conversions = read_json(
            "server/wakfu_server/items/native_item_conversions.json"
        )["items"]
        identified = set()
        socket_sources = set()
        policy_deployed = False
        policy_receipt_path = "agents_docs/reports/conversion-enhanced-20261020/lossless-policy-qualification.json"
        if (ROOT / policy_receipt_path).exists():
            policy = read_json(
                "agents_docs/reports/conversion-enhanced-20261020/identified-policy-capabilities.json"
            )
            receipt = read_json(policy_receipt_path)
            identified = set(policy["source_refs"])
            socket_sources = set(policy["shard_preservation"]["source_refs"])
            no_sockets = set(policy["no_source_socket_template_refs"])
            if (
                policy["official_inheritance_recovered"] is not False
                or policy["catalog_revision"] != activation["catalog_revision"]
                or len(identified) != 104
                or len(socket_sources) != 108
                or len(no_sockets) != 5
                or socket_sources & no_sockets
                or (socket_sources & identified) | no_sockets != identified
                or len(socket_sources - identified) != 9
                or socket_sources != set(policy["source_socket_template_refs"])
                or policy["source_sha256"] != receipt["source_sha256"]
                or len(receipt["source_sha256"]) != 5
                or set(policy["observation_preservation"]["source_refs"])
                != {
                    item["item_ref"]
                    for item in conversions
                    if item["main_reference"] > 0
                }
                or policy["observation_preservation"]["count"] != 116
            ):
                raise ValueError("Conflicting lossless conversion policy capabilities")
            sources, tests, logs = {}, {}, []
            for path, digest in receipt["source_sha256"].items():
                if record_file(path) != digest:
                    raise ValueError(f"Stale lossless conversion policy source: {path}")
                sources[path] = digest
            for path, digest in receipt["test_sha256"].items():
                if record_file(path) != digest:
                    raise ValueError(f"Stale lossless conversion policy test: {path}")
                tests[path] = digest
            for path, digest in receipt["logs_sha256"].items():
                if record_file(path) != digest:
                    raise ValueError(
                        f"Changed lossless conversion policy receipt: {path}"
                    )
                logs.append(dict(path=path, sha256=digest))
            historical = receipt["historical_lossless_qualification"]
            for path, digest in historical["logs_sha256"].items():
                if record_file(path) != digest:
                    raise ValueError(f"Changed historical conversion receipt: {path}")
            initial, corrected = (
                historical["initial_cohort"],
                historical["corrected_selector"],
            )
            initial_raw = (ROOT / initial["log"]).read_text()
            corrected_raw = (ROOT / corrected["log"]).read_text()
            if (
                historical["distinct_methods_qualified"] != 16
                or (initial["methods"], initial["passed"], initial["errors"])
                != (16, 15, 1)
                or not re.search(
                    r"^Ran 16 tests in [0-9.]+s\n\nFAILED \(errors=1\)",
                    initial_raw,
                    re.MULTILINE,
                )
                or (corrected["methods"], corrected["passed"], corrected["normal_exit"])
                != (1, 1, 0)
                or not passing_unittest_log(corrected_raw)
                or not re.search(r"^Ran 1 test in ", corrected_raw, re.MULTILINE)
            ):
                raise ValueError(
                    "Lossless conversion qualification lacks its honest fixture-corrected outcome"
                )
            # Mixed receipts may contain unrelated failures. Qualify only the
            # exact named conversion methods whose unittest outcome is ok.
            qualified_selectors = []
            for cohort in receipt["current_cohorts"]:
                raw = (ROOT / cohort["log"]).read_text()
                for selector in cohort["qualified_selectors"]:
                    pattern = (
                        r"^test_\w+ \("
                        + re.escape(selector)
                        + r"\) \.\.\. (.*?)(?=^test_\w+ \(|^={10,}|^Ran |\Z)"
                    )
                    match = re.search(pattern, raw, re.MULTILINE | re.DOTALL)
                    if match is None or not re.search(
                        r"(?:^|\n)ok\s*$|^ok\s*$", match[1].strip(), re.MULTILINE
                    ):
                        raise ValueError(
                            f"Conversion selector did not pass: {selector}"
                        )
                    qualified_selectors.append(selector)
                if len(cohort["qualified_selectors"]) != cohort["qualified_methods"]:
                    raise ValueError("Conflicting conversion selector count")
            if len(set(qualified_selectors)) != 8:
                raise ValueError(
                    "Conversion current qualification must retain eight distinct methods"
                )
            policy_deployed = all(
                source_is_deployed(path, digest) for path, digest in sources.items()
            )
            QUALIFICATIONS["lossless_conversion_preservation_policy"] = dict(
                qualified_unique_methods=8,
                current_cohorts=receipt["current_cohorts"],
                historical_lossless_qualification=historical,
                receipts=logs,
                current_source_sha256=sources,
                current_test_sha256=tests,
                all_five_sources_deployed=policy_deployed,
                deployed_activation_paths={
                    path.removeprefix("server/"): activation.get(
                        "verified_source", {}
                    ).get(
                        path.removeprefix("server/"),
                        activation.get("verified_source", {}).get(path),
                    )
                    for path in sources
                },
                historical_qualification=historical["historical_qualification"],
                qualification_scope=receipt["scope"],
            )
        closure_path = "agents_docs/reports/item-route-closure-20261021/CONVERSION-ROUTE-CAPABILITIES.json"
        closure = read_json(closure_path)
        closure_rows = {row["source"]: row for row in closure["routes"]}
        if (
            closure["catalog_revision"] != activation["catalog_revision"]
            or closure["source_sha256"] != sources
            or set(closure_rows) != {item["item_ref"] for item in conversions}
            or closure["counts"] != {"implemented": 127, "implemented_limited": 2}
        ):
            raise ValueError("Conflicting reachable conversion route census")
        for path, digest in closure["input_sha256"].items():
            # The activation receipt advances independently of catalog/source
            # compatibility. Its original hash remains recorded in the census.
            if path.endswith("/expansion-activation.json"):
                continue
            if record_file(path) != digest:
                raise ValueError(f"Stale reachable conversion route input: {path}")
        QUALIFICATIONS["lossless_conversion_preservation_policy"][
            "reachable_route_census"
        ] = dict(
            path=closure_path,
            sha256=record_file(closure_path),
            counts=closure["counts"],
            structural_dimensions=closure["structural_dimensions"],
            original_activation=closure["release"],
        )
        for item in conversions:
            selected = item["item_ref"] in identified
            evidence = "Exact native conversion products;source route and migration218"
            limitation = ""
            classification = closure_rows[item["item_ref"]]
            if classification["route_status"] == "implemented_limited":
                limitation = "Native EPIC source can carry a special sublimation that the COMMON destination forbids;conversion refuses atomically instead of deleting the attachment"
            if selected:
                evidence += ";explicit Wakemu policy preserves valid singleton elemental choices on the designated main output only"
            if item["item_ref"] in socket_sources:
                evidence += ";native source/main socket contracts match;complete accepted shard carrier preserved byte-for-byte"
                evidence += ";unknown/foreign carrier fields remain safe refusals, not active producer coverage"
            else:
                evidence += ";native source has no socket-identification route"
            if item["item_ref"] in set(
                policy["observation_preservation"]["source_refs"]
            ):
                evidence += ";exact nullable recycling observations preserved on compatible designated main"
            else:
                evidence += ";refund-only source has no equipment enhancement domain"
            evidence += ";appearance preservation is conditional on native source/main/override type and level validators"
            if (
                classification["dimensions"]["appearance"]
                == "supported_all_source_valid_donors"
            ):
                evidence += ";native source/main contracts accept all source-valid appearance donors (exact78-pair census)"
            else:
                evidence += ";source is not a native appearance-fusion target"
            mark(
                item["item_ref"],
                evidence,
                table="native_conversion_item_actions",
                migration=218,
                status=classification["route_status"],
                qualification="lossless_conversion_preservation_policy",
                limitation=limitation,
                runtime_source="server/wakfu_server/items/conversion_item_actions.py",
            )
            if not policy_deployed and item["item_ref"] in rows:
                rows[item["item_ref"]]["local_status"] = "not_loaded"
    mark(
        30723,
        "Original reusable diary scenario;private13411 event;domain/World tests pass",
        table="native_reading_scenario_item_actions",
        migration=216,
    )
    mark(
        13346,
        "Original universal ordinary pet food membership;210 feeding tests",
        table="native_pet_feeding_food_policy",
        migration=210,
    )
    mark(
        12228,
        "Original one-week pet hibernation membership;215 lifecycle tests11",
        table="native_pet_hibernation_food_policy",
        migration=215,
    )
    for reference in range(26555, 26560):
        mark(
            reference,
            "Gemlevolver native machine211/offers6846–6850;actual catalog PostgreSQL tests3/3",
            migration=206,
            status="implemented_contextual",
            qualification="actual_native_exchange_postgres_verified",
            limitation="Use the Gemlevolver machine, not direct self-use;no claim of pet XP transfer semantics",
        )
    companions = read_json(
        "server/wakfu_server/characters/native_companion_items.json"
    )["items"]
    for item in companions:
        mark(
            item["item_ref"],
            "Qualified native collection/admission/control/reconnect/equipment/capped progression;150% owner combat XP, full post-fight HP and native loot participation",
            migration=217,
            status="implemented_limited",
            qualification="native_lifecycle_equipment_progression_and_combat_focused_cohorts",
            limitation="Environmental-quest XP integration unavailable;Native GetEquipmentNPC*/GetEquipment/GmN/GfN predicates are qualified through actual NPC sheet;17 selected-element rings have real selection/save/projection/retrieval acceptance;generic supported NPC-owned sources now include the qualified two-NPC13574 Ready/checkpoint route; other native conditions and full source shapes remain limited;other conditions remain rejected without consumption;client acceptance remains pending",
            blocker="environmental_quest_xp_and_remaining_conditional_equipment",
        )
    if (ROOT / "server/wakfu_server/items/restat_item_actions.py").exists():
        mark(
            20691,
            "Native all-characteristics-pages reset; exact request and three PostgreSQL cases qualified",
            migration=218,
            qualification="native_confirmation_and_all_sheets_health_atomicity_tests",
            limitation="Resets all owned aptitude pages while preserving their levels, gear, decks and wounds",
        )
    mark(
        26347,
        "Retained account-quest inventory possession grants common active5623 at level130;native base/conditional casts2/2, canonical ownership2/2, World publication15/15 and read-only PostgreSQL provider1/1 (tests-20261020T081445050559Z.log)",
        migration=218,
        status="implemented_contextual",
        qualification="actual_native_common_spell_cast_ownership_and_publication",
        limitation="Not consumed;account-quest possession required;manual spellbook acceptance pending",
    )
    if 20447 in rows:
        rows[20447].update(
            current_evidence="Existing free aptitude reset via native build save12772 is PostgreSQL-qualified;this token has no proven charge/use contract",
            limitation="Feature works without consuming20447;no token debit or invented restriction implemented",
            blocker_kind="missing_native_token_use_contract",
        )
    qualification(
        "neutrality219",
        ["084646142135"],
        [
            "server/wakfu_server/items/neutrality_item_actions.py",
            "server/migrations/219_native_neutrality_items.sql",
        ],
    )
    for item in read_json("server/wakfu_server/items/native_neutrality_items.json")[
        "items"
    ]:
        mark(
            item["item_ref"],
            "Original neutrality scenario2318/event19332;four focused tests pass",
            table="native_neutrality_item_actions",
            migration=219,
            limitation="Current real PvP balance authority is native zero;no nonzero PvP balance reset provider exists",
        )
    qualification(
        "developer_dummy220",
        ["083714769180", "084610913373"],
        [
            "server/wakfu_server/items/item_test_spawns.py",
            "server/migrations/220_developer_item_test_groups.sql",
        ],
    )
    mark(
        30532,
        "Original reusable test item;finite native breed5518;administrator-only Wakemu policy qualified",
        migration=220,
        status="implemented_limited",
        qualification="native_spawn_and_ecological_population_guards",
        limitation="Explicit administrator-only policy;one live group per main;ten-minute unused TTL;no rewards or ecological population",
        blocker="developer_only_access_policy",
    )
    qualification(
        "anti_ko221",
        ["092851881241", "092902735783"],
        [
            "server/migrations/221_native_consumable_anti_ko.sql",
            "server/protocol/native-consumable-actions.json",
            "server/wakfu_server/items/consumable_buffs.py",
            "server/wakfu_server/combat/combat_external_retained_state.py",
            "server/wakfu_server/items/inventory_consumable_effects.py",
        ],
    )
    for reference in anti_ko_refs:
        mark(
            reference,
            "Original state989 subtracts one retained981 level;actual native-origin backend and serialization qualified",
            table="native_consumable_actions",
            migration=221,
            status="implemented_contextual",
            qualification="native_origin_state_and_one_level_removal_focused_cohorts",
            limitation="Requires actual authorized retained981;automatic application on ordinary defeat is unavailable;no invented death-state producer",
        )
    qualification(
        "captain_and_journals222_223",
        ["091803618070"],
        [
            "server/wakfu_server/items/captain_map_item_actions.py",
            "server/wakfu_server/items/journal_part_item_actions.py",
            "server/migrations/222_native_captain_map_items.sql",
            "server/migrations/223_native_journal_part_items.sql",
        ],
    )
    for item in read_json("server/wakfu_server/items/native_captain_map_items.json")[
        "items"
    ]:
        mark(
            item["item_ref"],
            "Complete original16-part Captain map assembly and typed output;seven shared assembly tests pass",
            table="native_captain_map_item_actions",
            migration=222,
            qualification="native_set_assembly_and_atomicity_policy_qualified",
            limitation="Explicit supported-inference Wakemu policy:one encyclopedia per complete native set;not recovered original server callback code",
        )
    qualification(
        "native_mission_activation_wire",
        ["184518691179"],
        ["server/wakfu_server/achievements/wire.py"],
    )
    mission_activation_qualification = read_json(
        ".runtime/item-unreviewed-20261020/mission-initial-activation-228-qualification.json"
    )
    mission_activation_receipts = []
    for path, digest in mission_activation_qualification["receipts_sha256"].items():
        observed = record_file(path)
        if observed != digest:
            raise ValueError(f"Mission activation receipt changed: {path}")
        mission_activation_receipts.append(dict(path=path, sha256=observed))
    mission_activation_sources = {}
    for path, digest in mission_activation_qualification["source_sha256"].items():
        observed = record_file(path)
        if observed != digest:
            raise ValueError(
                f"Mission activation source changed after qualification: {path}"
            )
        mission_activation_sources[path] = observed
    if (
        mission_activation_qualification.get("unique_methods") != 6
        or mission_activation_qualification.get("qualified_methods") != 6
        or mission_activation_qualification.get("initial_cohort", {}).get("passed") != 5
        or mission_activation_qualification.get("initial_cohort", {}).get(
            "fixture_errors"
        )
        != 1
        or mission_activation_qualification.get("corrected_method", {}).get("passed")
        != 1
        or not mission_activation_qualification.get("corrected_method", {}).get(
            "fixture_fix_only"
        )
        or mission_activation_qualification.get("runtime_changes") is not False
    ):
        raise ValueError(
            "Initial-only mission activation qualification is incomplete or not fixture-corrected"
        )
    QUALIFICATIONS["native_mission_initial_activation_228"] = dict(
        qualified_unique_methods=6,
        initial_cohort=dict(
            passed=5,
            fixture_errors=1,
            explanation="One assertion read a raw DB alias; gameplay had completed, and that method passed after the fixture switched to the public achievement_section projection.",
        ),
        corrected_method=dict(passed=1, receipt=mission_activation_receipts[1]),
        receipts=mission_activation_receipts,
        current_source_sha256=mission_activation_sources,
        qualification_scope=mission_activation_qualification["qualification_scope"],
    )
    qualification_receipts(
        "neo_level_group_equipment",
        [".runtime/consumable-effects-20261019/tests-20261021T004357873277Z.log"],
        [
            "server/wakfu_server/items/equipment_level_groups.py",
            "server/wakfu_server/items/equipment_stats.py",
            "server/wakfu_server/items/equipment_eligibility.py",
        ],
        [
            "server/tests/test_equipment_level_groups.py",
            "server/tests/test_equipment_level_groups_postgres.py",
        ],
    )
    QUALIFICATIONS["native_end_resource_equipment_32617_32618"] = dict(
        receipt_path=".runtime/consumable-effects-20261019/end-resource-qualification-receipt.txt",
        receipt_sha256=record_file(
            ".runtime/consumable-effects-20261019/end-resource-qualification-receipt.txt"
        ),
        qualification_kind="direct_unittest_stdout_receipt_not_raw_log",
        results=dict(
            combined_focused_methods="3/3",
            final_mp_selector="1/1",
            corrected_ap_selector="1/1",
        ),
        current_source_sha256={
            path: record_file(path)
            for path in (
                "server/wakfu_server/combat/combat_equipment_end_resource_contract.py",
                "server/wakfu_server/combat/combat_owned_equipment.py",
                "server/wakfu_server/combat/combat_maximum_resource.py",
                "server/wakfu_server/combat/combat_server_spell.py",
                "server/wakfu_server/combat/combat_movement_runtime.py",
            )
        },
        current_test_sha256={
            path: record_file(path)
            for path in (
                "server/tests/test_equipment_null_carrier_pipeline.py",
                "server/tests/test_equipment_end_resource_mp.py",
            )
        },
    )
    QUALIFICATIONS["native_chest_12038_multitab_expansion"] = dict(
        receipt_path=".runtime/consumable-effects-20261019/chest-native-12038-qualification-receipt.txt",
        receipt_sha256=record_file(
            ".runtime/consumable-effects-20261019/chest-native-12038-qualification-receipt.txt"
        ),
        qualification_kind="direct_unittest_stdout_receipt_not_raw_log",
        focused_methods="3/3",
        current_source_sha256={
            path: record_file(path)
            for path in (
                "server/wakfu_server/items/haven_chest.py",
                "server/local_game_server.py",
            )
        },
        current_test_sha256={
            "server/tests/test_haven_chest_store.py": record_file(
                "server/tests/test_haven_chest_store.py"
            )
        },
    )
    qualification(
        "journal_running_mission_progress",
        ["183732413483", "183818141046", "183723432051", "183744946725"],
        [
            "server/wakfu_server/achievements/mission_assembly.py",
            "server/wakfu_server/items/item_set_assembly.py",
            "server/local_game_server.py",
        ],
    )
    for group in read_json("server/wakfu_server/items/native_journal_part_items.json")[
        "groups"
    ]:
        for item in group["items"]:
            mark(
                item["item_ref"],
                "Original journal assembly plus receipt-driven objectives and once-only native XP for already-running2907;atomicity and World publication qualified",
                table="native_journal_part_item_actions",
                migration=223,
                status="implemented_limited",
                qualification="native_journal_part_assembly_and_running_mission_progress_qualified",
                limitation="Supported-inference native journal assembly;qualified2907 completion requires already-running mission at real178+;initial activation remains unavailable",
                blocker="mission2907_initial_activation_unavailable",
            )
    qualification(
        "BenKO9247",
        ["084804263451", "085434003439", "090502135341"],
        ["server/wakfu_server/characters/world_resurrection.py"],
    )
    mark(
        9247,
        "Original contextual12239 world-death/company resurrection;atomic source use and live-session publication qualified",
        status="implemented_contextual",
        qualification="actual_company_resurrection_and_native_world_packets",
        runtime_source="server/wakfu_server/characters/world_resurrection.py",
        limitation="Native eligibility/custody/packets;recovered1HP is explicit existing Wakemu policy,not original heal percentage",
    )
    qualification(
        "Neo32701_32702",
        ["084309359707", "085455953083", "092154985222", "092302061844"],
        ["server/wakfu_server/items/neo_regeneration.py"],
    )
    for reference in (32701, 32702):
        mark(
            reference,
            "Actual original item rejects ordinary use;native descriptions grant start/end fullHP over the Neo-server period",
            status="implemented_contextual",
            qualification="native_unusable_item_possession_and_actual_health_admission_cohorts",
            runtime_source="server/wakfu_server/items/neo_regeneration.py",
            limitation=(
                "Actual personal ordinary-bag possession only"
                if reference == 32701
                else "Actual account-quest possession covers all owned characters"
            )
            + ";trusted Neo mode and original Battlefield exclusion;not full Neo-server support",
        )
    qualification(
        "phoenix224",
        ["145714324243"],
        [
            "server/wakfu_server/items/item_scenario_teleports.py",
            "server/migrations/224_native_saved_phoenix.sql",
        ],
    )
    for reference in (19020, 19022):
        mark(
            reference,
            "Saved-Phoenix binding/company return and nation teleport;three PostgreSQL plus one World route test pass",
            migration=224,
            runtime_source="server/wakfu_server/items/item_scenario_teleports.py",
            qualification="native_phoenix_binding_company_and_nation_four_focused_tests",
            limitation="Original native RespawnPoint destination authority;walkable-neighbor arrival policy;exact original server nation arrival coordinate unavailable",
        )
    qualification(
        "guild_compass_secondary225",
        ["163016393620", "163304512070"],
        [
            "server/wakfu_server/items/world_marker_item_actions.py",
            "server/wakfu_server/items/native_world_marker_items.json",
            "server/migrations/225_native_world_marker_items.sql",
            "server/tests/test_world_marker_item_actions.py",
        ],
    )
    qualification_receipts(
        "account_chest_bulk_deposit_all",
        [".runtime/simple-item-actions-20261019/chest-depositall-final.log"],
        [
            "server/local_game_server.py",
            "server/wakfu_server/items/haven_chest.py",
            "server/wakfu_server/storage/command_permissions.py",
        ],
        [
            "server/tests/test_haven_chest_store.py",
            "server/tests/test_chat_command_routing.py",
            "server/tests/test_command_permissions.py",
        ],
    )
    qualification_receipts(
        "complete_item_custody_exchange",
        [
            ".runtime/simple-item-actions-20261019/trade-metadata-capacity-final.log",
            ".runtime/consumable-effects-20261019/tests-20261021T000519742856Z.log",
            ".runtime/consumable-effects-20261019/tests-20261020T235816985012Z.log",
            ".runtime/consumable-effects-20261019/tests-20261020T235918542486Z.log",
        ],
        [
            "server/wakfu_server/items/item_custody_metadata.py",
            "server/wakfu_server/items/exchange_transfer.py",
            "server/wakfu_server/items/player_exchanges.py",
            "server/wakfu_server/items/haven_chest.py",
        ],
        [
            "server/tests/test_player_exchanges.py",
            "server/tests/test_haven_chest_store.py",
        ],
    )
    mixed = ".runtime/consumable-effects-20261019/tests-20261020T163156288014Z.log"
    QUALIFICATIONS["guild_compass_secondary225"]["initial_mixed_receipt"] = dict(
        path=mixed,
        sha256=record_file(mixed),
        passed_methods=3,
        fixture_failures=1,
        corrected_method_receipt="163304512070",
    )
    guild_primary_enabled = False
    guild_enable_path = ".runtime/guild-primary-enable-20261021/activation.json"
    priority_policy_path = (
        ".runtime/item-whole-routes-20261021/delivery/priority-guild-policy-78.json"
    )
    priority_activation_path = (
        ".runtime/item-whole-routes-20261021/delivery/"
        + activation["release"]
        + "/guild-policy-activation.private.json"
    )
    if not (ROOT / priority_activation_path).exists():
        # Policy remains active across unchanged game releases; follow actual
        # immutable predecessor pins until its latest activation receipt.
        policy_release = previous_activation["release"]
        visited_policy_releases = set()
        while policy_release not in visited_policy_releases:
            visited_policy_releases.add(policy_release)
            policy_directory = release_delivery(policy_release)
            previous_policy_receipt = (
                policy_directory / "guild-policy-activation.private.json"
            )
            if previous_policy_receipt.exists():
                priority_activation_path = str(
                    previous_policy_receipt.relative_to(ROOT)
                )
                break
            policy_previous_path = policy_directory / "previous-activation.json"
            if policy_previous_path.exists():
                policy_release = read_json(str(policy_previous_path.relative_to(ROOT)))[
                    "release"
                ]
                continue
            policy_pins_path = policy_directory / "previous-image-pins.json"
            if not policy_pins_path.exists():
                break
            policy_tag = read_json(str(policy_pins_path.relative_to(ROOT))).get(
                "WAKFU_WORLD_IMAGE", ""
            )
            if ":" not in policy_tag:
                break
            policy_release = policy_tag.rsplit(":", 1)[1]
    priority_policy_recorded = (ROOT / priority_policy_path).exists() and (
        ROOT / priority_activation_path
    ).exists()
    if (ROOT / guild_enable_path).exists() and not priority_policy_recorded:
        guild_enable = read_json(guild_enable_path)
        candidate_path = (
            ".runtime/guild-primary-enable-20261021/candidate-enabled-policy.json"
        )
        candidate = read_json(candidate_path)
        candidate_sha = record_file(candidate_path)
        sys.path.insert(0, str(ROOT / "server"))

        guild_sources = (
            "guild_primary_policy.py",
            "guild_service.py",
            "guild_wire.py",
            "guild_dispatch.py",
            "guild_model.py",
            "guild_machine_context.py",
            "native_guild_machines.json",
            "guild_native_validators.py",
            "native_guild_identity_catalog.json",
        )
        workspace_guild_hashes = {
            "server/wakfu_server/characters/"
            + name: record_file("server/wakfu_server/characters/" + name)
            for name in guild_sources
        }
        # Workspace work can move ahead while a qualified older image remains
        # live. Read only these actual deployed modules, not mutable workspace
        # hashes, when deciding whether the activated policy is still loaded.
        guild_live_program = (
            "import hashlib,json,pathlib; "
            "from wakfu_server.guild_primary_policy import policy; "
            + "paths="
            + repr(tuple(workspace_guild_hashes))
            + "; "
            + "print(json.dumps(dict(source_sha256={p:hashlib.sha256((pathlib.Path('/app')/p.removeprefix('server/')).read_bytes()).hexdigest() for p in paths},constructor=policy(enabled=True))))"
        )
        guild_live = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "world",
                    "python",
                    "-c",
                    guild_live_program,
                ],
                cwd=ROOT,
                text=True,
            )
        )
        guild_hashes = guild_live["source_sha256"]
        guild_test_path = (
            ".runtime/consumable-effects-20261019/tests-20261021T064659099414Z.log"
        )
        guild_test_raw = (ROOT / guild_test_path).read_text()
        # A policy activation survives a game release when its exact original
        # implementation and enabled policy remain deployed unchanged.
        guild_activation_source = read_json(guild_enable["source_parity_receipt"])
        original_guild_hashes = guild_activation_source.get("verified_source", {})
        guild_checks = dict(
            runtime_image_matches=runtime_verified,
            receipt_release_matches=guild_activation_source.get("release")
            == guild_enable.get("code_release", guild_enable.get("release")),
            implementation_unchanged_since_activation=all(
                original_guild_hashes.get(
                    path.removeprefix("server/"), original_guild_hashes.get(path)
                )
                == digest
                for path, digest in guild_hashes.items()
            ),
            activation_recorded=guild_enable.get("activated") is True,
            candidate_hash_matches=guild_enable.get("policy_sha256") == candidate_sha,
            candidate_matches_constructor=candidate == guild_live["constructor"],
            live_policy_matches=local.get("guild_policy") == candidate,
            guild_sources_deployed=all(
                source_is_deployed(path, digest)
                for path, digest in guild_hashes.items()
            ),
            focused_cohort_passed=passing_unittest_log(guild_test_raw),
        )
        guild_primary_enabled = all(guild_checks.values())
        QUALIFICATIONS["guild_primary_identity_activation"] = dict(
            checks=guild_checks,
            qualified_and_loaded=guild_primary_enabled,
            receipt_path=guild_enable_path,
            candidate_policy_sha256=candidate_sha,
            policy_activation_code_release=guild_enable.get(
                "code_release", guild_enable.get("release")
            ),
            current_code_release=activation["release"],
            compatible_policy_source_receipt=guild_enable["source_parity_receipt"],
            focused_receipt=dict(
                path=guild_test_path,
                sha256=record_file(guild_test_path),
                passed_methods=10,
                scope="Machine cells, three success codecs, dispatch success/refusal and isolated PostgreSQL create/rename/blazon/reload",
            ),
            deployed_source_sha256=guild_hashes,
            workspace_source_sha256=workspace_guild_hashes,
            scope="Three identity operations only; actual account ownership and disabled-economy projections are explicit Wakemu policy",
        )
    if priority_policy_recorded:
        priority_policy = read_json(priority_policy_path)
        priority_activation = read_json(priority_activation_path)
        guild_paths = [
            path
            for path in activation["verified_source"]
            if path.startswith("wakfu_server/characters/guild_")
            and path.endswith(".py")
        ]
        guild_hashes = {
            "server/" + path: activation["verified_source"][path]
            for path in guild_paths
        }
        guild_checks = dict(
            runtime_image_matches=runtime_verified,
            live_policy_matches=local.get("guild_policy") == priority_policy,
            activation_policy_matches=priority_activation.get("current")
            == priority_policy,
            primary_enabled=priority_policy.get("enabled") is True,
            management_enabled=priority_policy.get("management_enabled") is True,
            storage_enabled=priority_policy.get("chest", {}).get("enabled") is True,
            treasury_enabled=priority_policy.get("economy", {}).get("treasury_enabled")
            is True,
            progression_enabled=priority_policy.get("economy", {}).get(
                "progression_enabled"
            )
            is True,
            haven_world_enabled=priority_policy.get("haven_world", {}).get("enabled")
            is True,
            native_bonus_count=len(
                priority_policy.get("economy", {}).get("bonus_catalog", {})
            )
            == 78,
            weekly_and_world_contracts_enabled=all(
                str(ref) in priority_policy.get("economy", {}).get("bonus_catalog", {})
                for ref in (42, 84)
            ),
            original_catalog_present="42"
            in priority_policy.get("economy", {}).get("bonus_catalog", {}),
            guild_sources_deployed=bool(guild_hashes)
            and all(
                source_is_deployed(path, digest)
                for path, digest in guild_hashes.items()
            ),
        )
        guild_primary_enabled = all(guild_checks.values())
        QUALIFICATIONS["guild_primary_identity_activation"] = dict(
            checks=guild_checks,
            qualified_and_loaded=guild_primary_enabled,
            current_code_release=activation["release"],
            policy_path=priority_policy_path,
            actual_policy_receipt=priority_activation_path,
            deployed_source_sha256=guild_hashes,
            scope="Identity, management, storage, treasury, progression and all78 native bonus descriptors enabled; weekly42 and native HavenWorld84 provisioning qualified",
        )
    for reference in (16942, 25100, 25101):
        if rows[reference]["source_status"] != "disabled":
            raise ValueError(
                "Guild navigation must not enable primary guild operations"
            )
        rows[reference][
            "limitation"
        ] = "Advertised guild creation or identity-change operation remains policy-disabled;secondary native compass support is reported separately"
        rows[reference][
            "current_evidence"
        ] = "Primary guild operation remains disabled by guild_policy101;nonconsuming native compass action is a separate secondary context"
        if guild_primary_enabled:
            mark(
                reference,
                "Actual enabled guild policy matches the live setting, deployed source and activation receipt",
                status="implemented"
                if priority_policy_recorded
                else "implemented_limited",
                qualification="guild_primary_identity_activation",
                runtime_source="server/wakfu_server/characters/guild_service.py",
                deployed_source_digest=guild_hashes[
                    "server/wakfu_server/characters/guild_service.py"
                ],
                limitation=(
                    "Identity/management/storage/treasury/points and78 native bonuses enabled; graphical manual acceptance remains separate"
                    if priority_policy_recorded
                    else "Identity-only policy; independent guild systems unavailable"
                ),
                blocker=""
                if priority_policy_recorded
                else "unqualified_guild_management_and_economy",
            )
        secondary_context(
            reference,
            name="native_guild_machine_compass",
            evidence="Original client-local GuildMachine27023 compass;map527(71,-13,0);native criteria and source custody;no consumption or guild operation",
            migration=225,
            table="native_world_marker_item_actions",
            runtime_source="server/wakfu_server/items/world_marker_item_actions.py",
            qualification="guild_compass_secondary225",
        )
    # Learning a native plan is not evidence that its construction target exists.
    # Preserve all native sources in scope; missing definitions are not obsolete.
    ranch_actions_path = ".runtime/tina-ranch-learning-20261018/native-actions.json"
    ranch_catalog_path = (
        "server/wakfu_server/items/native_ranch_building_definitions.json"
    )
    ranch_actions = read_json(ranch_actions_path)
    ranch_definitions = {
        entry["p"] for entry in read_json(ranch_catalog_path)["definitions"]
    }
    missing_ranch_targets = []
    for action in ranch_actions:
        missing = sorted(set(action["kdp"]) - ranch_definitions)
        if not missing:
            continue
        row = rows[action["item_ref"]]
        row.update(
            source_status="implemented_limited",
            qualification="native_learning_target_definition_missing",
            blocker_kind="native_ranch_building_definition_missing",
            limitation="Native learning target has no installed construction definition: "
            + ",".join(map(str, missing)),
            current_evidence="Original bIA plan exists, but the complete112-definition original aMR catalog lacks its target; retained in active scope, not excluded as obsolete",
        )
        missing_ranch_targets.append(
            dict(source_ref=action["item_ref"], missing_building_refs=missing)
        )
    QUALIFICATIONS["ranch_learning_target_reachability"] = dict(
        action_evidence=ranch_actions_path,
        definition_evidence=ranch_catalog_path,
        learning_source_count=len(ranch_actions),
        native_definition_count=len(ranch_definitions),
        missing_targets=missing_ranch_targets,
        scope="Source classification only. Existing loaded descriptor status does not prove successful construction; guard/build qualification and next activation remain separate.",
    )
    herd_catalog_path = "server/wakfu_server/items/native_ranch_creatures.json"
    herd_catalog = read_json(herd_catalog_path)
    herd_actions = herd_catalog["actions"]
    herd_definitions = {entry["reference"] for entry in herd_catalog["definitions"]}
    if (
        len(herd_actions) != 36
        or len(herd_definitions) != 125
        or len({entry["item_ref"] for entry in herd_actions}) != 36
        or any(
            not entry["candidate_refs"]
            or entry["suffix_bytes"] != 0
            or entry["action_criterion"] != ""
            or not set(entry["candidate_refs"]) <= herd_definitions
            for entry in herd_actions
        )
    ):
        raise ValueError("Incomplete native Ranch acquisition catalog")
    herd_paths = (
        "server/wakfu_server/items/haven_ranch_herd.py",
        "server/wakfu_server/items/haven_ranch_herd_wire.py",
        "server/wakfu_server/items/haven_ranch_building_knowledge.py",
        "server/wakfu_server/items/haven_ranch_furniture_wire.py",
        "server/wakfu_server/items/ranch_native_paddocks.py",
        herd_catalog_path,
        "server/local_game_server.py",
    )
    herd_hashes = {path: record_file(path) for path in herd_paths}

    def herd_source_deployed(path, digest):
        return source_is_deployed(path, digest) or (
            runtime_verified
            and local.get("deployed_native_data_sha256", {}).get(
                path.removeprefix("server/")
            )
            == digest
        )

    herd_world_proof_path = (
        ".runtime/ranch-building-route-20261021/world-refresh-qualification.json"
    )
    herd_world_proof = read_json(herd_world_proof_path)
    herd_world_qualified = (
        herd_world_proof.get("result") == "OK"
        and herd_world_proof.get("tests") == 19
        and herd_world_proof.get("exit_code") == 0
        and herd_world_proof["sha256"]["server/local_game_server.py"]
        == herd_hashes["server/local_game_server.py"]
    )
    herd_composition_path = ".runtime/ranch-building-route-20261021/world-binding-router-composition-200504.json"
    if not herd_world_qualified and (ROOT / herd_composition_path).exists():
        composed = read_json(herd_composition_path)
        current_world_text = (ROOT / "server/local_game_server.py").read_text()
        delta = composed["delta"]
        reverse_world = current_world_text.replace(
            delta["import_line_added"], ""
        ).replace(delta["router_loop_new"], delta["router_loop_previous"])
        herd_world_qualified = (
            composed.get("exact_reverse_matches") is True
            and composed["current_world_sha256"]
            == herd_hashes["server/local_game_server.py"]
            and hashlib.sha256(reverse_world.encode()).hexdigest()
            == composed["previous_qualified_world_sha256"]
            and composed["previous_qualified_world_sha256"]
            == herd_world_proof["sha256"]["server/local_game_server.py"]
        )
    # Later qualified herd revisions carry their own immutable release cohort.
    # The nine AST methods cover the current mutation/publication adapter; do
    # not relabel the historical19-method run as having tested this revision.
    herd_release_qualification = None
    herd_release_qualification_path = current_directory / "qualification.json"
    if herd_release_qualification_path.exists():
        current_adapter_receipt = read_json(
            str(herd_release_qualification_path.relative_to(ROOT))
        )
        previous_world_digest = previous_activation.get("verified_source", {}).get(
            "local_game_server.py"
        )
        previous_adapter_receipt = (
            release_delivery(previous_activation["release"]) / "qualification.json"
        )
        if (
            current_adapter_receipt.get("policy")
            != "wakemu_ranch_deployed_cycle_rewards_v1"
            and previous_world_digest == herd_hashes["server/local_game_server.py"]
            and previous_adapter_receipt.exists()
        ):
            previous_adapter = read_json(
                str(previous_adapter_receipt.relative_to(ROOT))
            )
            if (
                previous_adapter.get("policy")
                == "wakemu_ranch_deployed_cycle_rewards_v1"
            ):
                herd_release_qualification_path = previous_adapter_receipt
    if local["schema_version"] >= 239 and herd_release_qualification_path.exists():
        release_qualification = read_json(
            str(herd_release_qualification_path.relative_to(ROOT))
        )
        cohorts = release_qualification.get("cohorts", [])
        dispatch_log = (
            ".runtime/consumable-effects-20261019/tests-20261021T204346903870Z.log"
        )
        domain_log = (
            ".runtime/consumable-effects-20261019/tests-20261021T204440745534Z.log"
        )
        release_cohort_matches = any(
            entry.get("log") == dispatch_log and entry.get("passed") == 9
            for entry in cohorts
        ) and any(
            entry.get("log") == domain_log and entry.get("passed") == 1
            for entry in cohorts
        )
        if release_cohort_matches:
            dispatch_raw = (ROOT / dispatch_log).read_text()
            domain_raw = (ROOT / domain_log).read_text()
            world_methods = re.findall(
                r"^test_[^\n]*\(test_haven_ranch_herd_dispatch[^\n]*\) \.{3} ok$",
                dispatch_raw,
                re.MULTILINE,
            )
            herd_world_qualified = (
                len(world_methods) == 9
                and passing_unittest_log(domain_raw)
                and source_is_deployed(
                    "server/local_game_server.py",
                    herd_hashes["server/local_game_server.py"],
                )
            )
            herd_release_qualification = dict(
                path=str(herd_release_qualification_path.relative_to(ROOT)),
                dispatch_log=dispatch_log,
                dispatch_methods_passed=len(world_methods),
                mixed_process_not_all_green=True,
                corrected_domain_log=domain_log,
                world_source_sha256=herd_hashes["server/local_game_server.py"],
            )
    if local["schema_version"] >= 240 and herd_release_qualification_path.exists():
        production_qualification = read_json(
            str(herd_release_qualification_path.relative_to(ROOT))
        )
        production_final_log = (
            ".runtime/consumable-effects-20261019/tests-20261021T212205182872Z.log"
        )
        if (
            production_qualification.get("policy")
            == "wakemu_ranch_deployed_cycle_rewards_v1"
            and any(
                entry.get("log") == production_final_log and entry.get("passed") == 1
                for entry in production_qualification.get("cohorts", [])
            )
            and passing_unittest_log((ROOT / production_final_log).read_text())
            and source_is_deployed(
                "server/local_game_server.py",
                herd_hashes["server/local_game_server.py"],
            )
        ):
            herd_world_qualified = True
            herd_release_qualification = dict(
                path=str(herd_release_qualification_path.relative_to(ROOT)),
                scope="Current cycle/pickup/release revision composed with retained native World/publication qualification; not a rerun of historical19tests",
                final_queue_pg=production_final_log,
                world_source_sha256=herd_hashes["server/local_game_server.py"],
            )
    companion_world_proof_path = ".runtime/item-inventory-reconciliation-20261020/world-companion-admission-221423-proof.json"
    if not herd_world_qualified and (ROOT / companion_world_proof_path).exists():
        scoped = read_json(companion_world_proof_path)
        world_text = (ROOT / "server/local_game_server.py").read_text()
        reverse = world_text.replace(scoped["removed_added_block"], "", 1).replace(
            scoped["removed_added_argument"], "", 1
        )
        old_ranch = read_json(scoped["composed_ranch_qualification"])
        if (
            scoped["current_world_sha256"] == herd_hashes["server/local_game_server.py"]
            and hashlib.sha256(reverse.encode()).hexdigest()
            == scoped["previous_world_sha256"]
            == scoped["reverse_sha256"]
            and old_ranch.get("policy") == "wakemu_ranch_deployed_cycle_rewards_v1"
        ):
            herd_world_qualified = True
            herd_release_qualification = dict(
                scoped_unchanged_ranch_world_proof=companion_world_proof_path,
                composed_production_qualification=scoped[
                    "composed_ranch_qualification"
                ],
                scope="Exact reverse whole-file equality: only companion13191 preflight changes; no historical test is relabeled as a current World run",
            )
    herd_loaded = (
        runtime_verified
        and herd_world_qualified
        and local["schema_version"] >= 237
        and all(
            herd_source_deployed(path, digest) for path, digest in herd_hashes.items()
        )
    )
    for action in herd_actions:
        mark(
            action["item_ref"],
            "General36-action native acquisition and account herd custody; explicit Wakemu seeded list-slot sampling and original constructor baseline; owned enclosure deployment, rename, repack and reconnect",
            migration=237,
            runtime_source=herd_paths[0],
            qualification="ranch_seeded_herd237_source_route",
            limitation="Explicit Wakemu initial-generation policy; native genetics, breeding, growth, production and lifecycle rewards are not implemented",
        )
        row = rows[action["item_ref"]]
        row["local_status"] = "loaded" if herd_loaded else "not_loaded"
        if not herd_loaded:
            row[
                "delivery_note"
            ] = "Whole herd source route present; requires schema237 and exact domain, catalog, component18/scene and World source deployment"
        # The historical baseline described a missing herd. Preserve that
        # historical column, but do not append its obsolete limitation here.
        row[
            "limitation"
        ] = "Explicit Wakemu seeded constructor baseline; no native genetics, breeding, growth, production or lifecycle rewards"
    QUALIFICATIONS["ranch_seeded_herd237_source_route"] = dict(
        source_sha256=herd_hashes,
        source_migration=237,
        world_publication_qualification=herd_world_proof_path,
        composed_world_qualification=herd_composition_path
        if (ROOT / herd_composition_path).exists()
        else None,
        world_publication_qualified=herd_world_qualified,
        current_herd_revision_qualification=herd_release_qualification,
        actual_world_image=local["world_image"],
        directly_verified_static_data_sha256=local.get(
            "deployed_native_data_sha256", {}
        ),
        static_data_scope="Only explicitly listed pinned data files; not verification of all JSON",
        qualified_and_loaded=herd_loaded,
        policy="wakemu_native_seeded_herd_v1",
        native_action_count=36,
        native_creature_definition_count=125,
        scope="Complete acquisition/custody route under explicit policy; final focused domain and World publication receipts remain separate; no native genetics or breeding claim",
    )
    # Remaining mechanisms have data, but need system integration rather than invented direct effects.
    reasons = {
        "bHz": (
            "ranch_creature_inventory_and_breeding",
            "Native profession/minimum/list data exists;Ranch creature inventory/generation/breeding missing",
        ),
        "bHQ": (
            "haven_world_permissions_and_ecosystem_bombs",
            "Native radius/coordinates exist;requires owned Haven World/guild permissions",
        ),
        "bIg": (
            "native_treasure_engine",
            "Native operation/timer data exists;treasure lifecycle missing",
        ),
        "bHw": (
            "native_achievement_authority_mapping",
            "Native IDs652/1197 exported;achievement/objective authority integration missing",
        ),
        "bHx": (
            "native_restat_entitlement",
            "Restat item exists;durable native entitlement workflow missing",
        ),
        "bIn": (
            "native_scenario_lifecycle",
            "Original scenario IDs/events exist;only30723 self-contained reading scenario qualified",
        ),
    }
    for row in rows.values():
        if row["source_status"] == "missing" and row["use_action_class"] in reasons:
            row["blocker_kind"], row["current_evidence"] = reasons[
                row["use_action_class"]
            ]

    for item in achievement_actions:
        mark(
            item["item_ref"],
            "Native initial mission activation only; six distinct focused methods qualified with one corrected fixture assertion; no objective completion or reward grant",
            table="native_achievement_item_actions",
            migration=228,
            status="implemented_limited",
            qualification="native_achievement_initial_activation_only_228",
            limitation="Initial activation and persistent running-state publication only; mission objectives, completion and rewards remain unavailable",
            blocker="native_mission_objective_completion_and_rewards_unavailable",
            runtime_source="server/wakfu_server/items/achievement_item_actions.py",
        )

    binding_contract_path = (
        "server/wakfu_server/items/native_binding_assembly_contract.json"
    )
    binding_contract = read_json(binding_contract_path)
    if (
        binding_contract.get("policy")
        != "wakemu_reconstructed_native_binding_assembly_v1"
        or binding_contract.get("item_ref") != 20440
        or binding_contract.get("minimum_real_level") != 178
        or binding_contract.get("definition_id") != 2909
        or binding_contract.get("required_objectives") != [5914, 5915, 5916, 5917, 5918]
    ):
        raise ValueError(
            "Binding assembly reporting differs from its qualified contract"
        )
    binding_runtime_path = "server/wakfu_server/items/binding_kit_item_actions.py"
    binding_log_path = (
        ".runtime/consumable-effects-20261019/tests-20261021T200359786472Z.log"
    )
    binding_log = (ROOT / binding_log_path).read_text()
    if not passing_unittest_log(binding_log):
        raise ValueError(
            "Configured material assembly focused qualification did not pass"
        )
    QUALIFICATIONS["binding_material_assembly238"] = dict(
        receipt=dict(
            path=binding_log_path, sha256=record_file(binding_log_path), passed=2
        ),
        source_sha256={
            path: record_file(path)
            for path in (
                binding_runtime_path,
                binding_contract_path,
                "server/wakfu_server/items/item_set_assembly.py",
            )
        },
        scope="Explicit Wakemu material minima debit13, retained kit, inferred20441x1; actualnative2909 objective5919 and200M XP; no initial activation or2910",
    )
    mark(
        20440,
        "Qualified generic material assembly for already-running2909 with actual objectives5914–5918; explicitWakemu13materialdebits,retainedkit,20441x1; native200M XPonce",
        migration=238,
        status="implemented_limited",
        qualification="binding_material_assembly238",
        runtime_source=binding_runtime_path,
        limitation="Requires already-running2909 at real178+ and native prerequisite objectives; initial quest activation and2910 remain unavailable",
        blocker="mission2909_initial_activation_unavailable",
    )
    binding_data_deployed = local.get("deployed_native_data_sha256", {}).get(
        binding_contract_path.removeprefix("server/")
    ) == record_file(binding_contract_path)
    if not binding_data_deployed:
        rows[20440]["local_status"] = "not_loaded"
        rows[20440][
            "delivery_note"
        ] = "Source-qualified configured material assembly; requires238, actualmodule and exactpinnedstaticcontract deployment"

    # Scope policy only: preserve every native/runtime reward table unchanged.
    exclusion_path = "agents_docs/reports/item-external-authority-20261021/missing-output-exclusion-evidence.json"
    exclusion_evidence = read_json(exclusion_path)
    if exclusion_evidence.get("schema") != "missing-native-item-exclusion-evidence-v1":
        raise ValueError("Unqualified missing-output scope exclusion evidence")
    for path, expected in exclusion_evidence["source_sha256"].items():
        if record_file(path) != expected:
            raise ValueError("Missing-output scope evidence source changed: " + path)
    excluded_outputs = [
        entry
        for entry in exclusion_evidence["rows"]
        if entry["eligible_missing_output_exclusion"] is True
    ]
    if len(excluded_outputs) != 8 or any(
        not entry["native_missing_output_refs"] for entry in excluded_outputs
    ):
        raise ValueError(
            "Missing-output scope must contain exactly eight attested source routes"
        )
    for entry in excluded_outputs:
        row = rows[entry["source_ref"]]
        row.update(
            user_scope="excluded_missing_native_output",
            source_status="excluded",
            local_status="excluded",
            qualification="excluded_by_user",
            blocker_kind="excluded_missing_native_output",
            current_evidence="User excludes routes referencing absent native output templates: "
            + ",".join(map(str, entry["native_missing_output_refs"]))
            + "; evidence: "
            + exclusion_path,
            limitation="Scope exclusion only; native output tables and mixed valid outcomes are unchanged",
        )
    QUALIFICATIONS["missing_native_output_scope_exclusion"] = dict(
        policy="User excludes source routes referencing items absent from the native catalog",
        evidence_path=exclusion_path,
        source_refs=sorted(entry["source_ref"] for entry in excluded_outputs),
        runtime_filtering=False,
        native_reward_tables_changed=False,
    )

    def current_mechanism(name, paths, receipts, scope):
        source_hashes = {path: record_file(path) for path in paths}
        # This mechanism describes the active immutable release. A later
        # workspace patch is recorded separately and does not invalidate that
        # release's qualified route or claim that the patch was delivered.
        qualified_route_hashes = {}
        workspace_ahead = {}
        for path, digest in source_hashes.items():
            actual = activation["verified_source"].get(
                path.removeprefix("server/"),
                current_image_files.get(path.removeprefix("server/")),
            )
            if actual is not None:
                qualified_route_hashes[path] = actual
                if actual != digest:
                    workspace_ahead[path] = dict(
                        workspace=digest,
                        deployed=actual,
                        authority="Current immutable build/image verification and scoped route receipts",
                    )
        QUALIFICATIONS[name] = dict(
            observed_workspace_source_sha256=source_hashes,
            qualified_route_source_sha256=qualified_route_hashes,
            workspace_ahead_of_qualified_live_route=workspace_ahead,
            all_sources_deployed=len(qualified_route_hashes) == len(paths)
            and all(
                source_is_deployed(path, digest)
                for path, digest in qualified_route_hashes.items()
            ),
            receipts=[
                dict(path=path, sha256=record_file(path), scope=claim)
                for path, claim in receipts
            ],
            scope=scope,
            current_release=activation["release"],
        )

    if local["schema_version"] >= 240:
        current_mechanism(
            "ranch_cycle_partial_production240",
            [
                "server/wakfu_server/items/ranch_cycle_rewards.py",
                "server/wakfu_server/items/ranch_reward_retrieval.py",
                "server/wakfu_server/items/native_ranch_rewards.json",
            ],
            [
                (
                    ".runtime/consumable-effects-20261019/tests-20261021T212127442076Z.log",
                    "Five pure controls and ordinaryPG pass; mixed7process has one new fixture assertion failure",
                ),
                (
                    ".runtime/consumable-effects-20261019/tests-20261021T212205182872Z.log",
                    "Corrected actual11cycle chronology/backlog PG passes1of1",
                ),
                (
                    ".runtime/consumable-effects-20261019/tests-20261021T211827636230Z.log",
                    "Actual native pickup capacity rollback passes1of1",
                ),
            ],
            "Loaded explicitWakemu deployed86400second cycle policy, chronological earnedintervals and atomic native12068/12320 pickup; no nativegenetics/growth/breeding/age/death simulation. No new primaryreferences/families or globalcompletionclaim.",
        )
    current_mechanism(
        "companion_generic_owned_passive221423",
        [
            "server/wakfu_server/combat/combat_companion_owned_equipment_adapter.py",
            "server/wakfu_server/combat/combat_server_spell.py",
            "server/wakfu_server/combat/combat_equipment_dynamic_levels.py",
            "server/wakfu_server/characters/companion_equipment.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T221437980213Z.log",
                "Final2of2: two real distinct NPCs own separate13574 sources; native custody/preflight, Ready, full root67259 pin, checkpoint/retrieve; native999 custody-facts positive/negative controls",
            )
        ],
        "General supported source adapter with actual type5/non-eHP and no player inheritance; no blanket passive/condition support or environmental-quest XP; family remains limited",
    )
    current_mechanism(
        "equipment_native_eWO_resource_dispatch240",
        ["server/wakfu_server/items/equipment_stats.py"],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T213641796756Z.log",
                "Two general AP/MP/WP reduction-route and native HP21 controls pass",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T214115875576Z.log",
                "Actual NPC9434 resource receipt and6583HP save/reload/removal passes1of1; earlier assertion used wrong virtual-emblem baseline, runtime unchanged",
            ),
        ],
        "Shared eWO dispatch HP21 versus resource56/57/192; same item UID and restoration; no new family closure or staged passive-adapter claim",
    )
    current_mechanism(
        "companion_native_physical_slot_predicates238",
        [
            "server/wakfu_server/items/equipment_conditions.py",
            "server/wakfu_server/characters/companion_equipment.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T195823611965Z.log",
                "Seven focused native NPC physical-slot predicate and actual emblem equip/refusal/retrieval methods pass",
            )
        ],
        "Actual NPC inventory/equipment predicates use its own physical slots; no inherited player profession/guild context; environmentalXP and remaining passive contracts remain limited",
    )
    current_mechanism(
        "portable_bag_and_furniture_custody232",
        [
            "server/wakfu_server/items/portable_item_custody.py",
            "server/wakfu_server/items/inventory_bags.py",
            "server/wakfu_server/items/haven_bag_furniture_transfer.py",
            "server/wakfu_server/items/haven_bag_store.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170743656929Z.log",
                "Eight cases pass; unrelated/stale assertions remain mixed and are not counted green",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170923770052Z.log",
                "Corrected binary-length bag control passes",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T171030034416Z.log",
                "Actual character-binding guard passes",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T165347124534Z.log",
                "Native background learning/placement passes",
            ),
        ],
        "General portable9-sidecar custody and native background placement; retired merchant sale service excluded; not112Ranch construction/progression",
    )
    current_mechanism(
        "guild_storage_native_gates_and_treasury",
        [
            "server/wakfu_server/characters/guild_storage_policy.py",
            "server/wakfu_server/characters/guild_chest.py",
            "server/wakfu_server/characters/guild_chest_dispatch.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170743656929Z.log",
                "Two storage PG cases pass in mixed process",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170957541097Z.log",
                "Corrected native custody case passes",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180749198708Z.log",
                "Final native all4 gates: learned11 opens only compartment0; deposit passes",
            ),
        ],
        "All4 compartments require actual learned native bonuses; original13994 treasury route; no free base compartment",
    )
    current_mechanism(
        "guild_daily_point_sources",
        ["server/wakfu_server/characters/guild_daily_quests.py"],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180341312329Z.log",
                "Two daily methods pass in mixed process; unrelated cases fail",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180516388324Z.log",
                "One actual craft daily selector passes; other passing selector is HW travel, not a second daily",
            ),
        ],
        "Three distinct daily methods: native activation/cycle, kill+boss thresholds and real crafted-item-level completion; actual15/15/20point bases; no arbitrary PvE points",
    )
    current_mechanism(
        "haven_world_complete_entry_bombs_return",
        [
            "server/wakfu_server/characters/guild_haven_world.py",
            "server/wakfu_server/characters/haven_world_travel.py",
            "server/wakfu_server/maps/haven_world_native.py",
            "server/wakfu_server/maps/haven_world_terrain.py",
            "server/wakfu_server/items/haven_world_bombs.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170302482912Z.log",
                "Two domain cases pass; one radius fixture assertion fails",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T170326363927Z.log",
                "Corrected radius case passes, no runtime change",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180516388324Z.log",
                "Final complete entry/pending/reconnect/NPC/return selector passes",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180530996300Z.log",
                "Five final signed-world/item-criteria selectors pass",
            ),
        ],
        "Owned negative guild-world identity, real native terrain, company/pending transition, bombs and return; native84 owned-world provision qualified separately; no official construction/auction claim",
    )
    current_mechanism(
        "guild_progression_and78_bonus_scope",
        [
            "server/wakfu_server/characters/guild_progression.py",
            "server/wakfu_server/characters/guild_member_effects.py",
            "server/wakfu_server/characters/guild_bonus_authority.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T173651648665Z.log",
                "Two original27-bonus progression/outbox PG cases pass",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T175806805551Z.log",
                "Six pure member/profession-domain selectors pass",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T180341312329Z.log",
                "MemberHP/reconnect, foodclear/profession and temporary ready/expiry/renewal selectors pass; whole14-method process has unrelated failures",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T183017020406Z.log",
                "Final42 weekly SET1500 and84 real owned world provision, rollback/replay/adoption/entry:4of4 pass",
            ),
        ],
        "78 enabled native descriptors through shared typed policy/projection; final42/84 focused4of4; not78 individual graphical tests",
    )
    current_mechanism(
        "craft_upgrade_rich_precursor_and_observation",
        [
            "server/wakfu_server/items/craft_upgrade_policy.py",
            "server/wakfu_server/items/crafting.py",
            "server/wakfu_server/items/craft_planner.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T043324955227Z.log",
                "Historical20-method mixed-domain green:4 rich-upgrade PG+1craft nonce; other15 are independent effect controls",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T165114109705Z.log",
                "Supplemental nullable recycling observation preservation case passes1of1",
            ),
        ],
        "General native precursor mapping, fresh per-unit compatible output, batchN, exact accepted metadata and rollback; current deployment hashes separate from historical test source basis; not3326 individually executed recipes",
    )
    current_mechanism(
        "shushu_and_paid_weapon_representatives",
        [
            "server/wakfu_server/combat/combat_weapon.py",
            "server/wakfu_server/items/equipment_stats.py",
        ],
        [
            (
                ".runtime/consumable-effects-20261019/tests-20261021T164653387793Z.log",
                "All30 native Shushu passive projections pass; other selector had a fixture failure",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T164929064814Z.log",
                "Actual equipped Pinchus Ready/normal+critical healing selector passes",
            ),
            (
                ".runtime/consumable-effects-20261019/tests-20261021T165611037317Z.log",
                "Actual paid normal+critical damage for two native representatives passes",
            ),
        ],
        "Existing qualified general weapon/provider routes carried by the current full build; no invented killXP evolution; no clean mixed-cohort claim",
    )
    if priority_policy_recorded:
        for reference in (17551, 17592, 17593):
            mark(
                reference,
                "Complete ownedHavenWorld native terrain/entry/signed publication/bomb/population/return route qualified",
                migration=231,
                runtime_source="server/wakfu_server/items/haven_world_bombs.py",
                status="implemented_contextual",
                qualification="haven_world_complete_entry_bombs_return",
                limitation="Requires actual owned assigned HavenWorld, enabled policy and native permission512; no public-world bomb",
            )
            if not guild_primary_enabled:
                rows[reference]["local_status"] = "not_loaded"
                rows[reference][
                    "delivery_note"
                ] = "HavenWorld source exists but full enabled actual policy did not verify"

    retired_path = "agents_docs/reports/item-route-closure-20261021/RETIRED-IKIAKIT-EXCLUSIONS.json"
    retired = read_json(retired_path)
    if (
        retired.get("schema") != "retired-ikiakit-scope-exclusion-v1"
        or record_file(retired["original_jar"]) != retired["original_jar_sha256"]
        or {entry["reference"] for entry in retired["rows"]}
        != {11080, 11081, 11082, 11083}
        or any(
            "no longer functional" not in entry["description"]
            for entry in retired["rows"]
        )
    ):
        raise ValueError("Retired Ikiakit exclusion lacks explicit original authority")
    for entry in retired["rows"]:
        rows[entry["reference"]].update(
            user_scope="excluded_retired_native_function",
            source_status="excluded",
            local_status="excluded",
            qualification="excluded_by_user",
            blocker_kind="excluded_retired_native_function",
            current_evidence="Original description explicitly retires the original function; refund conversion remains available: "
            + retired_path,
            limitation="Task-scope exclusion only; no runtime conversion or native table removed",
        )
    QUALIFICATIONS["retired_native_ikiakit_scope_exclusion"] = dict(
        evidence_path=retired_path,
        source_refs=sorted(entry["reference"] for entry in retired["rows"]),
        original_jar_sha256=retired["original_jar_sha256"],
        runtime_changed=False,
    )

    # The new shared assembly fixes a concrete deployed import regression.
    # Descriptor presence alone cannot accredit the old executable route.
    assembly_path = "server/wakfu_server/items/item_set_assembly.py"
    assembly_digest = record_file(assembly_path)
    assembly_refs = {
        item["item_ref"]
        for item in read_json(
            "server/wakfu_server/items/native_captain_map_items.json"
        )["items"]
    }
    assembly_refs.update(
        item["item_ref"]
        for group in read_json(
            "server/wakfu_server/items/native_journal_part_items.json"
        )["groups"]
        for item in group["items"]
    )
    if len(assembly_refs) != 31:
        raise ValueError("Shared assembly route census must contain31 sources")
    assembly_deployed = source_is_deployed(assembly_path, assembly_digest)
    assembly_final_log = (
        ".runtime/consumable-effects-20261019/tests-20261021T172758125919Z.log"
    )
    assembly_final_raw = (ROOT / assembly_final_log).read_text()
    if not passing_unittest_log(assembly_final_raw) or not re.search(
        r"^Ran 1 test in ", assembly_final_raw, re.MULTILINE
    ):
        raise ValueError("Final shared assembly selector did not pass")
    assembly_final_qualified = (
        assembly_digest
        == "62def34f541c650fa7bca4bff1bfef33744e9c2db58499bd4f72c67f23d0e00f"
    )
    assembly_238_composed = (
        passing_unittest_log(binding_log)
        and "test_assembly_accepts_empty_metadata_and_rejects_unqualified_appearance_or_shard"
        in binding_log
        and QUALIFICATIONS["binding_material_assembly238"]["source_sha256"][
            assembly_path
        ]
        == assembly_digest
    )
    assembly_final_qualified = assembly_final_qualified or assembly_238_composed
    for reference in assembly_refs:
        row = rows[reference]
        if not assembly_deployed:
            row["local_status"] = "not_loaded"
            row[
                "delivery_note"
            ] = "Current shared assembly repair is source-present; current deployed engine has a known import regression. Final62def34f metadata selector passed; await matching deployment."
        row["qualification"] = (
            "shared_assembly_final_source_qualified"
            if assembly_final_qualified
            else "shared_assembly_source_changed_since_qualification"
        )
        row["current_evidence"] += (
            ";shared assembly repair: MISSION-JOURNAL-SHARED-ROUTES.md; source SHA256 "
            + assembly_digest
        )
    historical_journal = QUALIFICATIONS.get("journal_running_mission_progress", {})
    if "current_source_sha256" in historical_journal:
        historical_journal["observed_workspace_source_sha256"] = historical_journal.pop(
            "current_source_sha256"
        )
    historical_journal["historical_receipts_only"] = True
    historical_journal[
        "current_source_qualification"
    ] = "See shared_assembly31_current_source_delivery; historical receipts are not final-hash accreditation"
    QUALIFICATIONS["shared_assembly31_current_source_delivery"] = dict(
        source_path=assembly_path,
        current_source_sha256=assembly_digest,
        source_refs=sorted(assembly_refs),
        source_deployed=assembly_deployed,
        evidence_path="agents_docs/reports/item-route-closure-20261021/MISSION-JOURNAL-SHARED-ROUTES.md",
        qualified_current_source=assembly_final_qualified,
        historical_final_hash_receipt=dict(
            path=assembly_final_log,
            sha256=record_file(assembly_final_log),
            methods=1,
            passed=1,
        ),
        current_common_adapter_composed_qualification=assembly_238_composed,
        current_common_adapter_receipt=binding_log_path
        if assembly_238_composed
        else None,
        prior_semantic_controls=dict(
            log=".runtime/consumable-effects-20261019/tests-20261021T165331749625Z.log",
            source_hash_prefix="7a1f0752",
            passed=3,
            methods=3,
            scope="Before the final canonical import spelling only",
        ),
        qualification="Historical15-trigger/reward controls, corrected3of3 and62def34f1of1 retained;238currentadapter has actualordinaryjournal metadata regression pluskit2of2 composed qualification, not31new executions",
        official_mission_initial_activation=False,
    )

    result = sorted(
        (current_presentation(row) for row in rows.values()),
        key=lambda row: int(row["reference"]),
    )
    if len(result) != 6645:
        raise ValueError("Reconciliation lost or duplicated primary item references")
    columns = list(result[0])
    with (REPORT / "current-status-20261020.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result)
    source_pending = [
        row
        for row in result
        if row["user_scope"] == "active"
        and row["source_status"] not in ("implemented", "implemented_contextual")
    ]
    delivery_pending = [
        row
        for row in result
        if row["user_scope"] == "active"
        and row["local_status"] not in ("loaded", "loaded_baseline")
    ]
    pending = [
        row
        for row in result
        if row["user_scope"] == "active"
        and (
            row["source_status"] not in ("implemented", "implemented_contextual")
            or row["local_status"] not in ("loaded", "loaded_baseline")
        )
    ]
    with (REPORT / "current-pending-20261020.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(pending)
    source_counts = collections.Counter(row["source_status"] for row in result)
    local_counts = collections.Counter(row["local_status"] for row in result)
    families = collections.defaultdict(collections.Counter)
    for row in result:
        families[row["family"]][row["source_status"]] += 1
    summary = dict(
        total=6645,
        unique_references=len(rows),
        source_counts=dict(source_counts),
        local_counts=dict(local_counts),
        in_scope_pending=len(pending),
        in_scope_source_pending=len(source_pending),
        in_scope_delivery_pending=len(delivery_pending),
        shared_assembly_source_not_loaded=len(assembly_refs)
        if not assembly_deployed
        else 0,
        source_repairs_not_loaded=sum(bool(row["delivery_note"]) for row in result),
        retired_native_function_excluded=len(retired["rows"]),
        legacy_excluded=353,
        missing_native_output_excluded=len(excluded_outputs),
        total_excluded=source_counts.get("excluded", 0),
        local_schema=local["schema_version"],
        local_image=local["world_image"],
        snapshot_at=local["captured_at"],
        runtime_receipt_matches_image=runtime_verified,
        local_release_history=release_history,
        secondary_contexts={
            row["reference"]: json.loads(row["secondary_contexts"])
            for row in result
            if row["secondary_contexts"] != "[]"
        },
        source_qualification=QUALIFICATIONS,
        families={key: dict(value) for key, value in sorted(families.items())},
        input_sha256=INPUTS,
    )
    active_families = collections.defaultdict(list)
    for row in result:
        if row["user_scope"] == "active":
            active_families[row["family"]].append(row)
    available_families = sorted(
        name
        for name, group in active_families.items()
        if all(
            row["source_status"] in ("implemented", "implemented_contextual")
            and row["local_status"] in ("loaded", "loaded_baseline")
            for row in group
        )
    )
    summary["family_route_availability"] = dict(
        available=len(available_families),
        in_scope=len(active_families),
        percent=round(100 * len(available_families) / len(active_families), 1),
        available_families=available_families,
        definition="Every active reference in the family is source implemented/contextual and actually loaded; excludes limited/missing/authority-gap rows. Not whole-goal acceptance or graphical coverage.",
    )
    summary["descriptor_coverage"] = dict(
        loaded_primary_references=local_counts.get("loaded", 0)
        + local_counts.get("loaded_baseline", 0),
        in_scope_primary_references=6645 - source_counts.get("excluded", 0),
    )
    summary["excluded_service_contexts"] = [
        dict(
            service="haven_bag_merchant_listing_and_purchase",
            status="excluded_retired_native_service",
            evidence="agents_docs/reports/item-route-closure-20261021/HAVEN-BAG-MERCHANT-NATIVE-ENTRY.md",
            furniture_scope="Do not exclude decorative placement/rendering merely because listing/purchase is retired",
        )
    ]
    summary["overall_system_completion"] = dict(
        status="not_measured",
        scope="No verified whole-goal acceptance denominator; report source, qualification and deployment separately.",
    )
    (REPORT / "current-summary-20261020.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    lines = [
        "# Current item-action reconciliation — 2026-10-21",
        "",
        "This replaces only the mutable current tracker. Historical inventory CSVs and their20,229-item/6,645-primary-reference baseline remain unchanged. Each primary reference occurs once, even when it also serves pet feeding, crafting or contextual exchanges. Production deployment and individual graphical acceptance are not inferred.",
        "",
        f"Local catalog snapshot: schema**{local['schema_version']}**, captured`{local['captured_at']}`. World image`{local['world_image']}`. Receipt/image match:**{runtime_verified}**. Last verified local delivery receipt:`{activation['release']}`. Source availability, focused qualification and loaded local authority are separate columns in the CSV.",
        "",
        f"Measured family-route availability: **{len(available_families)}/{len(active_families)} ({summary['family_route_availability']['percent']}%)**. A family counts only when every active reference is implemented/contextual and loaded. This is not a global whole-goal or graphical-acceptance percentage. Exact source, qualification and deployment counts follow.",
        "",
        "## Local release identity",
        "",
        "| Release | World image | Schema | Complete build inputs | Activation-verified source hashes | Image files verified | Real QA selection probe |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for label in ("current", "previous"):
        release = release_history[label]
        probe_ok = all(release["character_selection_probe"].values())
        lines.append(
            f"| {release['release']} ({label}) | `{release['world_image_id']}` | {release['schema_version']} | {release['complete_build_input_count']} | {release['activation_verified_source_count']} | {release['image_files_verified']} | {'pass' if probe_ok else 'fail'} |"
        )
    lines += [
        "",
        "These are local Compose releases only. The current release receipt and source-stable image verification are linked in `current-summary-20261020.json`; this status does not claim production deployment.",
        "",
        "## Source implementation status",
        "",
        "| Status | Unique primary references |",
        "|---|---:|",
    ]
    lines += [f"| {key} | {value} |" for key, value in sorted(source_counts.items())]
    lines += [
        "",
        "## Loaded local status",
        "",
        "| Status | Unique primary references |",
        "|---|---:|",
    ]
    lines += [f"| {key} | {value} |" for key, value in sorted(local_counts.items())]
    lines += [
        "",
        f"The actual local release loads **{local_counts.get('loaded',0)+local_counts.get('loaded_baseline',0):,}** unique primary references. **{local_counts.get('not_loaded',0)}** are not loaded: {summary['source_repairs_not_loaded']} have source repairs awaiting matching deployment; the remainder lack a source route or native authority. Separately, **{source_counts.get('implemented_limited',0)}** supported references have the explicit limitations listed in the CSV; **{source_counts.get('disabled',0)}** remain policy-disabled. The pending CSV contains **{len(pending)}** distinct rows: **{len(source_pending)}** source-limited/missing-authority rows and **{len(delivery_pending)}** delivery-pending rows with overlap. They are not all missing implementations.",
    ]
    lines += [
        "",
        "## Newly qualified primary references",
        "",
        "Items14539 and16471 now support their original initial mission activation only. The six-method qualification is counted honestly as five passes in the initial cohort plus one corrected fixture-only rerun. Objectives, mission completion and rewards remain unavailable. Each item is marked `loaded` only when the refreshed local snapshot contains its exact migration228 descriptor and the current release activation verifies the matching `achievement_item_actions.py` source hash.",
    ]
    lines += [
        "",
        "Current CSV presentation keeps historical catalog findings only under baseline-prefixed implementation/route/evidence/limits columns. Unprefixed fields describe the current snapshot. See [nine remaining families and exact dependencies](../item-route-closure-20261021/CURRENT-REMAINING-BLOCKERS.md).",
    ]
    lines += [
        "",
        "**Loaded** means an enabled descriptor is present in the actual local catalog with the delivered route, or a baseline route retained by the complete local release. **Source only** is not a local/prod deployment claim. Companion collection/combat/equipment/progression is qualified, with environmental-quest XP and remaining unqualified equipment conditions unavailable; qualified NPC predicates, paired swords and capped-level gear are supported. Transformation source qualification uses the frozen native-oracle/focused-test receipt; rendered client acceptance remains pending. Legacy353set containers remain excluded.",
        "",
        "## Focused mechanism qualifications outside the primary count",
        "",
        "These checks qualify reusable inventory behavior and do not add references to the 6,645-item primary inventory.",
        "",
        "| Mechanism | Result | Focused receipts |",
        "|---|---|---|",
        "| Haven Chest bulk deposit | Existing command path 5/5 plus native12038 multitab expansion 3/3; rich metadata, one-tab scope, replay, equipped/QUEST exclusions and capacity rollback covered | `.runtime/simple-item-actions-20261019/chest-depositall-final.log`; `.runtime/consumable-effects-20261019/chest-native-12038-qualification-receipt.txt` |",
        "| Native equipment end-boundary resources | Focused AP/MP carrier lifecycle qualified: combined3/3, corrected AP1/1, final MP1/1; current resource unchanged, maximum +1, native timer and state702 exclusion | `.runtime/consumable-effects-20261019/end-resource-qualification-receipt.txt` (direct unittest stdout receipt, not a raw test log) |",
        "| Neo equipment level groups | 3/3 focused PostgreSQL methods: four real native sources, level/mode authority, sibling bonuses, Ready snapshot ownership, and removal | `.runtime/consumable-effects-20261019/tests-20261021T004357873277Z.log` |",
        "| Item custody across exchange/trade | 9/9 pass across four focused receipts: full/partial transfer, rich metadata and nonce preservation, merge/split, replay, binding controls, and capacity rollback | `.runtime/simple-item-actions-20261019/trade-metadata-capacity-final.log`; `.runtime/consumable-effects-20261019/tests-20261021T000519742856Z.log`; `.runtime/consumable-effects-20261019/tests-20261020T235816985012Z.log`; `.runtime/consumable-effects-20261019/tests-20261020T235918542486Z.log` |",
        "",
        "[Full current CSV](current-status-20261020.csv) · [In-scope pending/limited/WIP](current-pending-20261020.csv) · [Counts and input hashes](current-summary-20261020.json)",
        "",
        "## Every original family",
        "",
        "| Family | Baseline total | Implemented source | Contextual | Limited | WIP | Missing | Native data unavailable | Disabled | Excluded | Loaded locally |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for family, counts in sorted(families.items()):
        loaded_count = sum(
            row["local_status"] in ("loaded", "loaded_baseline")
            for row in result
            if row["family"] == family
        )
        values = (
            [sum(counts.values())]
            + [
                counts[k]
                for k in (
                    "implemented",
                    "implemented_contextual",
                    "implemented_limited",
                    "integration_wip",
                    "missing",
                    "native_data_unavailable",
                    "disabled",
                    "excluded",
                )
            ]
            + [loaded_count]
        )
        lines.append("| " + family + " | " + " | ".join(map(str, values)) + " |")
    if summary["secondary_contexts"]:
        lines += [
            "",
            "## Secondary contexts outside primary support totals",
            "",
            "These behaviors do not implement the item’s advertised primary operation and do not increase the supported-primary-reference count. A disabled guild operation may still have an independently qualified compass action.",
            "",
            "| Reference | Secondary behavior | Source status | Local status | Primary operation |",
            "|---|---|---|---|---|",
        ]
        for reference, contexts in summary["secondary_contexts"].items():
            for context in contexts:
                lines.append(
                    f"| {reference} | {context['name']} | {context['source_status']} | {context['local_status']} | {rows[int(reference)]['source_status']} |"
                )
        lines += [
            "",
            (
                "The three guild items also retain their original nonconsuming local compass marker to GuildMachine27023, map527 at(71,-13,0). Their separately verified primary identity operations and current enabled management/economy/storage policy are recorded above; the compass is not counted as another primary reference."
                if guild_primary_enabled
                else "The three guild items only provide their original nonconsuming local compass marker to GuildMachine27023, map527 at(71,-13,0), subject to their original native conditions. Guild creation, guild-name changes, and guild-emblem changes remain policy-disabled; compass support does not enable those operations."
            ),
        ]
    lines += [
        "",
        "## Remaining in-scope route checklist",
        "",
        "| Family | References | Source status | Local status | Remaining boundary |",
        "|---|---:|---|---|---|",
    ]
    groups = collections.defaultdict(list)
    for row in pending:
        groups[
            (
                row["family"],
                row["source_status"],
                row["local_status"],
                row["delivery_note"] or row["blocker_kind"] or row["limitation"],
            )
        ].append(row)
    for (family, status, local_status, blocker), items in sorted(groups.items()):
        lines.append(
            f"| {family} | {len(items)} | {status} | {local_status} | {blocker} |"
        )
    lines += [
        "",
        "## Context and limits",
        "",
        "- Retained item26347 grants common active5623 contextually from actual account-quest possession and level130;no source consumption. Reset token20447 remains distinct from the existing qualified free aptitude-reset feature.",
        "- Five evolution stones26555–26559 are already supported inputs to native Gemlevolver machine211. All five real offers pass PostgreSQL purchase tests; they are not direct consumables.",
        "- Legacy Kiteas are material refunds, not chest-capacity upgrades. Explicit Wakemu conversion policy preserves compatible singleton elemental choices, complete accepted socket carriers for108 catalog-qualified source/main pairs (including9 socket-only pairs), and exact nullable recycling observations on116 compatible mains and appearances accepted by native source/main/override validators. A complete exact78-pair appearance census now proves native source/main type/level compatibility. Reachable contracts classify127 routes implemented and2 limited only by real EPIC-to-COMMON special-sublimation incompatibility;those attached sources reject atomically. Animal/companion/cursor and unknown extension guards protect foreign or unqualified state;zero native source/product model/action intersections do not count as129 missing enhancements. Current qualification records6 observation/default-path methods and2 socket-only methods with their actual source bases and mixed-process outcomes; historical15/16 plus corrected1/1 remains separate, not relabeled as current-source verification.",
        "- Pet feeding extends to ordinary resource references outside the6,645-primary-item scope. They are secondary contexts and must not inflate the primary totals. Current descriptors include126pet models;source migration210 carries156XP-food references plus3heals, with feeding policies shared across models.",
        f"- Learning remains distinct from downstream selection:283pet/direct-equipment appearances now have qualified selection routes; local selection delivery verified:{selection_loaded}. Rendered client acceptance remains pending. Existing absent emote/recipe output caveats remain in partial-usability.csv.",
        "- Companion collection, admission, control, reconnect, native default/accepted gear, capped level progression,150% combat XP, post-fight recovery and loot are qualified. Environmental-quest XP is unavailable;Native NPC equipped-item predicates are qualified, but 17 selected-element rings have real selection/save/projection/retrieval acceptance;remaining conditions and passives remain limited;conditional gear remains limited. These16references remain explicitly limited rather than WIP.",
        "- New migration219–227 routes, BenKO9247, Neo32701/32702, chest bulk deposit and full item-custody exchange have focused mechanism-level qualifications. These do not increase the 6,645-reference primary inventory. No-migration routes require their exact module hash in the actual activation receipt before loaded status. Phoenix224 scenarios have four focused passing tests;their loaded status also requires the delivered route module hash.",
        "- User exclusions comprise353 legacy set containers,8 routes with absent native output templates and4 Ikiakit sources explicitly declared nonfunctional by original item descriptions. The four mixed random tables retain their original valid, missing and no-grant outcomes: this is an inventory-scope exclusion, not runtime filtering. Fragment15931 now has a qualified source consumption policy;its original SQLquantity0 descriptor is retained and matching source deployment is tracked separately. Missing tables, zero merge quantities and empty payloads remain separate unresolved authority.",
        "",
        "## Reproduction",
        "",
        "`python3 tools/reconcile-item-action-status.py` rebuilds these artifacts from frozen inputs and the recorded local catalog snapshot. Add`--refresh-local` to refresh catalog-only SQL and image metadata in read-only transactions. No character/account rows, inventory contents, secrets, services or production are read or mutated by this tool.",
    ]
    lines += [
        "",
        "## Service context excluded from the active goal",
        "",
        "The original Haven Bag flea-stand listing/purchase service is retired: its native controller explicitly rejects deposits and exposes removal-only callbacks. This does not exclude furniture that still has valid decorative placement/rendering. The primary item count is unchanged by excluding that service context; no furniture row is counted as a working merchant sale merely because its decoration can be displayed. See [native entry evidence](../item-route-closure-20261021/HAVEN-BAG-MERCHANT-NATIVE-ENTRY.md).",
    ]
    (REPORT / "CURRENT-STATUS-20261020.md").write_text("\n".join(lines) + "\n")
    readme_path = REPORT / "README.md"
    readme = readme_path.read_text()
    tracker = (
        f"**Current tracker (2026-10-21):** [{summary['descriptor_coverage']['loaded_primary_references']:,} primary references loaded locally](CURRENT-STATUS-20261020.md); "
        f"{summary['descriptor_coverage']['in_scope_primary_references']:,} in active scope. Source: "
        f"{source_counts.get('implemented',0):,} implemented, {source_counts.get('implemented_contextual',0)} contextual, "
        f"{source_counts.get('implemented_limited',0)} limited, {source_counts.get('missing',0)} missing and "
        f"{source_counts.get('native_data_unavailable',0)} native-data gaps. "
        f"{local_counts.get('not_loaded',0)} are not loaded, including {summary['source_repairs_not_loaded']} source repairs awaiting matching delivery. "
        f"Exclusions: {source_counts.get('excluded',0)} references (353 legacy sets, eight absent-output routes and four explicitly retired Ikiakits). "
        f"Current verified release `{activation['release']}`, schema {local['schema_version']}. "
        "Source availability, focused qualification, deployment and rendered acceptance are separate; no global completion percentage is claimed."
    )
    readme = re.sub(r"^\*\*Current tracker[^\n]*", tracker, readme, flags=re.MULTILINE)
    readme_path.write_text(readme)

    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "total",
                    "source_counts",
                    "local_counts",
                    "in_scope_pending",
                    "local_schema",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
