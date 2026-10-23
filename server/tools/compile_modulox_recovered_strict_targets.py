"""Compile additive recovered aliases against existing strict final-boss contracts.

Historical migrations and immutable dungeon plans are never regenerated.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

if __package__:
    from .compile_modulox_native_boss_targets import digest, insert
    from .compile_modulox_targets import POLICY, literal
else:
    from compile_modulox_native_boss_targets import digest, insert
    from compile_modulox_targets import POLICY, literal

POOL = "wakemu.daily-hunter50-modulox64-v1"
BASE_POOL = "wakemu.daily-hunter50-modulox62-v1"
EXPECTED = {4475, 4793}


def compile_sources(manifest, existing, configs, monsters, originals):
    known = {row["definition_id"] for row in existing["qualified"]}
    revisions = {row["native_catalog_revision"] for row in existing["qualified"]}
    documents = {row["monsters_sha256"] for row in existing["qualified"]}
    if len(revisions) != 1 or len(documents) != 1:
        raise ValueError("Existing native Modulox cohort has inconsistent source pins")
    actors = {row["ref"]: row for row in monsters["monsters"]}
    originals = {row["id"]: row for row in originals}
    configured = {
        (row["route_key"], int(row["policy_version"])): row
        for row in configs["configs"]
    }
    if len(configured) != len(configs["configs"]):
        raise ValueError("Duplicate immutable prepared route version")
    qualified = []
    children = []
    seen = set()
    for source in manifest["rows"]:
        identity = source["definition_id"]
        definition = source["native_definition"]
        boss = source["boss_reference"]
        if (
            identity in seen
            or identity in known
            or identity != definition["definition_id"]
        ):
            raise ValueError(
                "Recovered strict final-boss delta overlaps an existing or duplicate contract"
            )
        seen.add(identity)
        actor = source["native_monster"]
        if (
            source["native_boss_property"] != 43
            or actor != actors[boss]
            or 43 not in actor["raw_visual_arrays"]["csc"]
            or not source["native_world_property_authority"]
        ):
            raise ValueError("Target lacks its actual original native BOSS43 authority")
        original = source["original_aKU"]
        if (
            original != originals[source["dungeon_definition_id"]]
            or boss not in original["cno"]
        ):
            raise ValueError(
                "Native target differs from original dungeon species identity"
            )
        active = [route for route in source["routes"] if route["active"]]
        if len(active) != 1:
            raise ValueError(
                "Recovered strict final-boss delta requires one positively prepared active source context"
            )
        route = active[0]
        config = configured[(route["route_key"], route["policy_version"])]
        if (
            config["rooms"] != route["rooms"]
            or config["route"] != route["route"]
            or config["source_sha256"] != route["source_sha256"]
            or config["document_sha256"] != route["document_sha256"]
            or config["route"]["definition_id"] != original["id"]
            or config["route"]["start_map_id"] not in original["aHA"]
        ):
            raise ValueError("Native BOSS43 immutable route/room context changed")
        final = max(config["rooms"], key=lambda row: row["order"])
        actual = [
            dict(
                room_order=final["order"],
                monster_index=index,
                is_final=True,
                role=row["role"],
                count=row["count"],
            )
            for index, row in enumerate(final["monsters"])
            if row["ref_id"] == boss
        ]
        if (
            final["order"] != route["final_room_order"]
            or not actual
            or {r["ref_id"] for r in final["monsters"] if r["role"] == "boss"} != {boss}
            or actual != [row for row in route["target_occurrences"] if row["is_final"]]
            or any(
                row["role"] != "boss"
                or type(row["count"]) is not int
                or row["count"] <= 0
                for row in actual
            )
        ):
            raise ValueError(
                "Native target final-room occurrence/count/role source changed"
            )
        objectives = definition["objectives"]
        if (
            len(objectives) != 1
            or objectives[0]["native_class"] != "aJN"
            or any(objectives[0][key] for key in ("ckc", "ckd", "cke", "ckf"))
        ):
            raise ValueError("Native Modulox objective program changed")
        oid = objectives[0]["d"]
        texts = source["objective_localizations"]
        if set(texts) != {"en", "fr", "es"} or any(
            set(t) != {str(oid)} for t in texts.values()
        ):
            raise ValueError("Missing exact trilingual original objective identity")
        target = re.fullmatch(r"Complete .+ at level ([0-9]+)", texts["en"][str(oid)])
        if target is None or not 1 <= int(target[1]) <= 245:
            raise ValueError("Missing original objective adjusted level")
        offer = source["offer_category"]
        category = definition["category_id"]
        offer_match = re.fullmatch(
            r"GetRealLevel\(\) >= ([0-9]+)\s+and GetAchievementCategoryRunningCount\(([0-9]+)\) < 1\s+and GetAchievementCategoryCount\(\2\) == GetAchievementCategoryCanBeResetCount\(\2\)",
            offer["offer_criterion"],
        )
        minimum = re.fullmatch(
            r"GetRealLevel\(\) >= ([0-9]+)", definition["eligibility_criteria"]
        )
        if (
            offer_match is None
            or minimum is None
            or int(offer_match[2]) != category
            or offer["category_id"] != category
            or int(offer_match[1]) != offer["offer_minimum_level"]
            or offer["offer_node_id"] != 3972
            or definition["activation_criteria"] != f"IsAchievementRunning({identity})"
            or definition["calendar_period_seconds"] != 86400
            or definition["cooldown_seconds"] != 0
            or definition["repeatable"] is not True
            or definition["native_is_quest"] is not True
        ):
            raise ValueError("Original Modulox recurrence/category/offer gates changed")
        rewards = definition["rewards"]
        if (
            len(rewards) != 2
            or {row["type_id"] for row in rewards} != {5, 17}
            or any(
                type(row["raw_flag_ckk"]) is not bool
                or len(row["parameters"]) != (2 if row["type_id"] == 5 else 1)
                or any(
                    type(p) is not int or not 0 < p < 2**31 for p in row["parameters"]
                )
                for row in rewards
            )
        ):
            raise ValueError(
                "Original Modulox native5/17 reward identity/parameters changed"
            )
        provenance = dict(
            source_identity_kind=source["source_identity_kind"],
            original_aKU=original,
            original_definition=definition,
            objective_localizations=texts,
            original_offer=offer,
            native_monster=actor,
            native_boss_property=43,
            native_world_property_authority=source["native_world_property_authority"],
            frozen_route=route,
            immutable_plan_sha256=config["evidence_hashes"]["plan"],
            interpretation="Explicit Wakemu original-objective alias recovery with existing strict final-room boss role",
        )
        row = dict(
            definition_id=identity,
            version=1,
            objective_id=oid,
            minimum_level=max(int(minimum[1]), offer["offer_minimum_level"]),
            required_distinct=1,
            anchor_ms=definition["calendar_anchor_milliseconds"],
            period_ms=86400000,
            cooldown_ms=0,
            interpretation_policy=POLICY,
            boss_reference=boss,
            derived_variable_name=f"wakemu.modulox.boss.{boss}",
            dungeon_definition_id=original["id"],
            route_key=route["route_key"],
            route_policy_version=route["policy_version"],
            final_room_order=final["order"],
            category_id=category,
            minimum_level_authority="native-definition+original-node3972-offer-maximum",
            native_catalog_revision=next(iter(revisions)),
            monsters_path="monsters.json",
            monsters_sha256=next(iter(documents)),
            plan_sha256=config["evidence_hashes"]["plan"],
            reward_policy="native17-frozen-real-level-no-subscription",
            native_reward_order=[r["reward_id"] for r in rewards],
            target_effective_level=int(target[1]),
            offer_node_id=3972,
            offer_choice_id=offer["offer_choice_id"],
            offer_criterion=offer["offer_criterion"],
            offer_source_sha256=offer["offer_source_sha256"],
            public_corroborated=False,
            source_authority="explicit-Wakemu-native-objective+original-aKU+immutable-strict-final-boss",
            original_activation_criterion=definition["activation_criteria"],
            original_eligibility_criterion=definition["eligibility_criteria"],
            original_objective_en=texts["en"][str(oid)],
            original_native_rewards=rewards,
        )
        qualified.append(row)
        children.append(
            dict(
                definition_id=identity,
                version=1,
                boss_reference=boss,
                native_property_id=43,
                source_authority=row["source_authority"],
                proof_sha256=digest(provenance),
                provenance=provenance,
            )
        )
    if seen != EXPECTED:
        raise ValueError("Recovered strict final-boss additive source cohort changed")
    return dict(
        qualified=sorted(qualified, key=lambda row: row["definition_id"]),
        strict_source_proofs=children,
    )


def sql_seed(result, schema, existing_daily, existing_modulox):
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
    for row in result["qualified"]:
        out.append(insert("recurring_hunter_contracts", {k: row[k] for k in fields}))
        out.append(
            insert(
                "recurring_hunter_targets",
                dict(
                    definition_id=row["definition_id"],
                    version=1,
                    boss_reference=row["boss_reference"],
                    variable_name=row["derived_variable_name"],
                ),
            )
        )
        for reward in row["original_native_rewards"]:
            p = reward["parameters"]
            kind = reward["type_id"]
            out.append(
                insert(
                    "recurring_hunter_rewards",
                    dict(
                        definition_id=row["definition_id"],
                        version=1,
                        reward_id=reward["reward_id"],
                        native_type=kind,
                        reference=p[0] if kind == 5 else None,
                        amount=p[1] if kind == 5 else p[0],
                        native_flag=reward["raw_flag_ckk"],
                    ),
                )
            )
        out.append(
            insert("recurring_modulox_authority", {k: row[k] for k in authority})
        )
    out.extend(
        "-- Strict source proof "
        + str(row["definition_id"])
        + ": "
        + row["proof_sha256"]
        for row in result["strict_source_proofs"]
    )
    members = sorted(
        (row["category_id"], row["definition_id"], row["version"])
        for row in [*existing_daily, *existing_modulox, *result["qualified"]]
    )
    if (
        len(members) != 114
        or len({m[1] for m in members}) != 114
        or len({m[0] for m in members}) != 20
    ):
        raise ValueError("Combined daily50/Modulox64 source pool changed")
    out.append(
        insert(
            "recurring_hunter_daily_pools",
            dict(
                pool_version=POOL,
                interpretation_policy="wakemu.daily-hunter-utc-sorted-rotation-v1",
                source_sha256=digest(members),
                sealed=False,
            ),
        )
    )
    out.append(
        "INSERT INTO recurring_hunter_daily_members SELECT "
        + literal(POOL)
        + ",category_id,definition_id,version FROM recurring_hunter_daily_members WHERE pool_version="
        + literal(BASE_POOL)
        + ";"
    )
    for row in result["qualified"]:
        out.append(
            insert(
                "recurring_hunter_daily_members",
                dict(
                    pool_version=POOL,
                    category_id=row["category_id"],
                    definition_id=row["definition_id"],
                    version=1,
                ),
            )
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
    for name in (
        "manifest",
        "existing_modulox",
        "existing_daily",
        "configs",
        "monsters",
        "originals",
        "output",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text())
    source = load(args.manifest)
    for path, expected in source["source_sha256"].items():
        if sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("Strict recovered source SHA changed: " + path)
    existing = load(args.existing_modulox)
    if {r["monsters_sha256"] for r in existing["qualified"]} != {
        sha256(args.monsters.read_bytes()).hexdigest()
    }:
        raise ValueError(
            "Actor document differs from the existing qualified native catalog"
        )
    result = compile_sources(
        source, existing, load(args.configs), load(args.monsters), load(args.originals)
    )
    result["counts"] = dict(
        additional=2, total_modulox=64, combined_daily_members=114, categories=20
    )
    result["source_sha256"] = source["source_sha256"]
    header = (
        "-- Additive recovered strict bosses; no NPC acceptance or policy activation.\n"
    )
    header += (
        "-- Immutable source manifest SHA256: "
        + sha256(args.manifest.read_bytes()).hexdigest()
        + "\n"
    )
    args.output.write_text(
        sql_seed(
            result,
            header,
            load(args.existing_daily)["qualified"],
            existing["qualified"],
        )
    )
    args.output.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
