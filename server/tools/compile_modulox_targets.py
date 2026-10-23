#!/usr/bin/env python3
"""Compile all uniquely native-bound Modulox objectives; public evidence is optional."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / ".runtime/parallel-readiness-20261021/recurring-acceptance"
POLICY = "wakemu.modulox-native-adjusted-final-room-v1"
POOL = "wakemu.daily-hunter45-modulox54-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(value):
    if type(value) is bool:
        return str(value).lower()
    if type(value) is int:
        return str(value)
    if value is None:
        return "NULL"
    # Preserve original CRLF predicates under the migration reader's universal
    # newline handling, rather than writing physical carriage-return bytes.
    return (
        "E'"
        + value.replace("\\", "\\\\")
        .replace("'", "''")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        + "'"
    )


def compile_sources(
    definitions, corroboration, configs, originals, offer_document, monsters
):
    if configs["revision"] != monsters["revision"]:
        raise ValueError("Modulox plan/native catalog revisions differ")
    indexed = {r["definition_id"]: r for r in definitions}
    if len(indexed) != len(definitions):
        raise ValueError("Duplicate original definition")
    original_by_id = {r["id"]: r for r in originals}
    config_by_key = {r["route_key"]: r for r in configs["configs"]}
    offers = {}
    for choice in offer_document["original_node3972"]["choices"]:
        match = re.fullmatch(
            r"GetRealLevel\(\) >= (\d+)\s+and GetAchievementCategoryRunningCount\((\d+)\) < 1\s+and GetAchievementCategoryCount\(\2\) == GetAchievementCategoryCanBeResetCount\(\2\)",
            choice["criteria"],
        )
        if match:
            minimum, category = map(int, match.groups())
            if choice["type"] != 5 or category in offers:
                raise ValueError("Ambiguous original Modulox offer")
            offers[category] = (minimum, choice)
    if set(offers) != {684, 685, 686, 687, 810}:
        raise ValueError("Incomplete original five-category offer")
    category_members = []
    for source in corroboration["rows"]:
        definition = indexed[source["definition_id"]]
        minimum = re.fullmatch(
            r"GetRealLevel\(\) >= (\d+)", definition["eligibility_criteria"]
        )
        if minimum is None or int(definition["calendar_period_seconds"]) != 86400:
            raise ValueError("Unqualified original category membership")
        category_members.append(
            dict(
                definition_id=source["definition_id"],
                category_id=int(definition["category_id"]),
                anchor_ms=int(definition["calendar_anchor_ms"]),
                period_ms=86400000,
                original_minimum_level=int(minimum[1]),
            )
        )
    category_sources = [
        dict(
            category_id=category,
            expected_members=sum(
                m["category_id"] == category for m in category_members
            ),
            offer_node_id=3972,
            offer_choice_id=choice["id"],
            offer_minimum_level=minimum,
            offer_criterion=choice["criteria"],
            offer_source_sha256=offer_document["document_sha256"],
        )
        for category, (minimum, choice) in sorted(offers.items())
    ]
    qualified, pending = [], []
    seen = set()
    for source in corroboration["rows"]:
        identity = source["definition_id"]
        if identity in seen:
            raise ValueError("Duplicate corroboration definition")
        seen.add(identity)
        routes = source["positive_native_routes"]
        if len(routes) != 1:
            pending.append(
                dict(definition_id=identity, reason="native_route_not_unique_positive")
            )
            continue
        definition = indexed[identity]
        route = routes[0]
        config = config_by_key[route["route"]]
        original = original_by_id[route["dungeon_definition"]]
        boss = route["boss_reference"]
        final = max(config["rooms"], key=lambda r: r["order"])
        if (
            config["route"]["definition_id"] != original["id"]
            or boss not in original["cno"]
            or config["route"]["start_map_id"] not in original["aHA"]
            or {r["ref_id"] for r in final["monsters"] if r["role"] == "boss"} != {boss}
            or boss not in source["bilingual_candidates"]
            or not any(route["literal_dungeon_name_in_objective"].values())
        ):
            raise ValueError("Changed original/final-room numeric binding")
        objective = json.loads(definition["objectives"])
        if (
            len(objective) != 1
            or objective[0]["native_class"] != "aJN"
            or objective[0]["d"] != source["objective_id"]
            or any(objective[0][key] for key in ("ckc", "ckd", "cke", "ckf"))
        ):
            raise ValueError("Original Modulox objective program changed")
        target = source["adjusted_level"]
        match = re.fullmatch(
            r"Complete .+ at level (\d+)", source["native_objectives"]["en"]
        )
        if (
            type(target) is not int
            or target <= 0
            or match is None
            or int(match[1]) != target
        ):
            raise ValueError("Original objective effective level changed")
        category = int(definition["category_id"])
        offer_minimum, choice = offers[category]
        eligibility = re.fullmatch(
            r"GetRealLevel\(\) >= (\d+)", definition["eligibility_criteria"]
        )
        if (
            eligibility is None
            or definition["activation_criteria"] != f"IsAchievementRunning({identity})"
        ):
            raise ValueError("Unqualified original definition gate")
        rewards = json.loads(definition["rewards"])
        if len(rewards) != 2 or {r["type_id"] for r in rewards} != {5, 17}:
            raise ValueError("Changed native Modulox reward family")
        for reward in rewards:
            params = reward["parameters"]
            kind = reward["type_id"]
            if (
                type(reward["raw_flag_ckk"]) is not bool
                or len(params) != (2 if kind == 5 else 1)
                or any(type(p) is not int or not 0 < p < 2**31 for p in params)
            ):
                raise ValueError("Changed native Modulox reward parameter")
        if (
            int(definition["calendar_period_seconds"]) != 86400
            or int(definition["cooldown_seconds"]) != 0
        ):
            raise ValueError("Unsupported original Modulox period")
        minimum = max(int(eligibility[1]), offer_minimum)
        qualified.append(
            dict(
                definition_id=identity,
                version=1,
                objective_id=source["objective_id"],
                minimum_level=minimum,
                required_distinct=1,
                anchor_ms=int(definition["calendar_anchor_ms"]),
                period_ms=86400000,
                cooldown_ms=0,
                interpretation_policy=POLICY,
                boss_reference=boss,
                derived_variable_name=f"wakemu.modulox.boss.{boss}",
                dungeon_definition_id=original["id"],
                route_key=config["route_key"],
                route_policy_version=config["policy_version"],
                final_room_order=final["order"],
                category_id=category,
                minimum_level_authority="native-definition+original-node3972-offer-maximum",
                native_catalog_revision=configs["revision"],
                monsters_path="monsters.json",
                monsters_sha256=monsters["document"]["sha256"],
                plan_sha256=config["evidence_hashes"]["plan"],
                reward_policy="native17-frozen-real-level-no-subscription",
                native_reward_order=[r["reward_id"] for r in rewards],
                target_effective_level=target,
                offer_node_id=3972,
                offer_choice_id=choice["id"],
                offer_criterion=choice["criteria"],
                offer_source_sha256=offer_document["document_sha256"],
                public_corroborated=source["public_objective_exact"],
                source_authority="explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room",
                original_activation_criterion=definition["activation_criteria"],
                original_eligibility_criterion=definition["eligibility_criteria"],
                original_objective_en=source["native_objectives"]["en"],
                original_native_rewards=rewards,
            )
        )
    return dict(
        qualified=sorted(qualified, key=lambda r: r["definition_id"]),
        pending=pending,
        category_members=category_members,
        category_sources=category_sources,
        counts=dict(
            native_candidates=len(corroboration["rows"]),
            qualified=len(qualified),
            pending=len(pending),
        ),
    )


def sql_seed(result, schema):
    rows = result["qualified"]
    fields = (
        "definition_id",
        "version",
        "objective_id",
        "minimum_level",
        "required_distinct",
        "anchor_ms",
        "period_ms",
        "cooldown_ms",
        "interpretation_policy",
        "source_authority",
    )
    authority = (
        "definition_id",
        "version",
        "boss_reference",
        "dungeon_definition_id",
        "route_key",
        "route_policy_version",
        "final_room_order",
        "category_id",
        "minimum_level",
        "minimum_level_authority",
        "native_catalog_revision",
        "monsters_path",
        "monsters_sha256",
        "plan_sha256",
        "interpretation_policy",
        "reward_policy",
        "native_reward_order",
        "target_effective_level",
        "offer_node_id",
        "offer_choice_id",
        "offer_criterion",
        "offer_source_sha256",
        "public_corroborated",
        "source_authority",
        "original_activation_criterion",
        "original_eligibility_criterion",
        "original_objective_en",
    )
    out = [schema]
    for row in result["category_sources"]:
        fields_source = (
            "category_id",
            "expected_members",
            "offer_node_id",
            "offer_choice_id",
            "offer_minimum_level",
            "offer_criterion",
            "offer_source_sha256",
        )
        out.append(
            "INSERT INTO recurring_modulox_category_sources VALUES("
            + ",".join(literal(row[k]) for k in fields_source)
            + ");"
        )
    for row in sorted(result["category_members"], key=lambda r: r["definition_id"]):
        fields_member = (
            "definition_id",
            "category_id",
            "anchor_ms",
            "period_ms",
            "original_minimum_level",
        )
        out.append(
            "INSERT INTO recurring_modulox_category_members VALUES("
            + ",".join(literal(row[k]) for k in fields_member)
            + ");"
        )
    for row in rows:
        out.append(
            "INSERT INTO recurring_hunter_contracts VALUES("
            + ",".join(literal(row[k]) for k in fields)
            + ");"
        )
        out.append(
            "INSERT INTO recurring_hunter_targets VALUES("
            + ",".join(
                literal(v)
                for v in (
                    row["definition_id"],
                    1,
                    row["boss_reference"],
                    row["derived_variable_name"],
                )
            )
            + ");"
        )
        for reward in row["original_native_rewards"]:
            p = reward["parameters"]
            kind = reward["type_id"]
            values = (
                row["definition_id"],
                1,
                reward["reward_id"],
                kind,
                p[0] if kind == 5 else None,
                p[1] if kind == 5 else p[0],
                reward["raw_flag_ckk"],
            )
            out.append(
                "INSERT INTO recurring_hunter_rewards VALUES("
                + ",".join(literal(v) for v in values)
                + ");"
            )
        out.append(
            "INSERT INTO recurring_modulox_authority VALUES("
            + ",".join(
                "ARRAY[" + ",".join(map(str, row[k])) + "]"
                if k == "native_reward_order"
                else literal(row[k])
                for k in authority
            )
            + ");"
        )
    membership = [(r["category_id"], r["definition_id"], r["version"]) for r in rows]
    all_members = sorted(
        membership
        + [
            (r["category_id"], r["definition_id"], r["version"])
            for r in result["existing_daily_members"]
        ]
    )
    if len(all_members) != 99 or len({r[0] for r in all_members}) != 20:
        raise ValueError("Combined qualified daily pool changed")
    poolsha = hashlib.sha256(
        json.dumps(all_members, separators=(",", ":")).encode()
    ).hexdigest()
    out.append(
        "INSERT INTO recurring_hunter_daily_pools VALUES("
        + ",".join(
            literal(v)
            for v in (
                POOL,
                "wakemu.daily-hunter-utc-sorted-rotation-v1",
                poolsha,
                False,
            )
        )
        + ");"
    )
    out.append(
        "INSERT INTO recurring_hunter_daily_members SELECT "
        + literal(POOL)
        + ",category_id,definition_id,version FROM recurring_hunter_daily_members WHERE pool_version="
        + literal("wakemu.daily-hunter-qualified45-v1")
        + ";"
    )
    for category, identity, version in membership:
        out.append(
            "INSERT INTO recurring_hunter_daily_members VALUES("
            + ",".join(literal(v) for v in (POOL, category, identity, version))
            + ");"
        )
    out.append(
        "UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version="
        + literal(POOL)
        + ";"
    )
    out.append(
        "UPDATE recurring_hunter_daily_active SET pool_version="
        + literal(POOL)
        + ",enabled=false WHERE singleton;"
    )
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    path = (
        ROOT
        / "agents_docs/reports/parallel-readiness-20261021/recurring-native-definitions.csv"
    )
    with path.open() as stream:
        definitions = [
            dict(r, definition_id=int(r["definition_id"]))
            for r in csv.DictReader(stream)
        ]
    load = lambda path: json.loads(path.read_text())
    result = compile_sources(
        definitions,
        load(EVIDENCE / "modulox102-public-target-corroboration.json"),
        load(EVIDENCE / "web/current-final-room-boss-metadata.json"),
        load(EVIDENCE / "native-dungeon-qa/original-aKU-definitions.json"),
        load(EVIDENCE / "modulox102-original-dialogue-criterion-audit.json"),
        load(EVIDENCE / "web/current-native-boss-scalar-records.json"),
    )
    if result["counts"] != {"native_candidates": 102, "qualified": 54, "pending": 48}:
        raise ValueError("Expected attested cohort changed")
    result["existing_daily_members"] = load(
        EVIDENCE / "daily45-source-derived-targets.json"
    )["qualified"]
    result["source_hashes"] = {
        str(p.relative_to(ROOT)): sha(p)
        for p in (
            path,
            EVIDENCE / "modulox102-public-target-corroboration.json",
            EVIDENCE / "modulox102-original-dialogue-criterion-audit.json",
            EVIDENCE / "native-dungeon-qa/original-aKU-definitions.json",
            EVIDENCE / "web/current-final-room-boss-metadata.json",
            EVIDENCE / "web/current-native-boss-scalar-records.json",
            EVIDENCE / "daily45-source-derived-targets.json",
        )
    }
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    args.sql.write_text(sql_seed(result, args.schema.read_text()))
    fields = (
        "definition_id",
        "objective_id",
        "category_id",
        "minimum_level",
        "target_effective_level",
        "boss_reference",
        "dungeon_definition_id",
        "route_key",
        "route_policy_version",
        "public_corroborated",
    )
    with args.csv.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["qualified"])
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
