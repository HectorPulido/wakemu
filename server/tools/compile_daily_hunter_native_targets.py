"""Compile additive original-objective daily hunter target authority.

No public URL is invented and no immutable route, roster, role or old contract
is changed. Native category minima remain an explicit Wakemu interpretation.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

POLICY = "wakemu.daily-hunter-native-objective-final-room-v1"
MINIMUM_AUTHORITY = "wakemu-reconstruction:original-native-category-bracket-minimum"
REWARD_POLICY = "fixed-native-parameter-no-booster"
BASE_POOL = "wakemu.daily-hunter50-modulox64-v1"
POOL = "wakemu.daily-hunter65-modulox64-v1"
EXPECTED = {
    4142,
    4448,
    4153,
    4225,
    5113,
    5114,
    4981,
    4185,
    4191,
    4195,
    4196,
    4459,
    4217,
    4219,
    4151,
}


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def literal(value):
    if value is None:
        return "NULL"
    if type(value) is bool:
        return str(value).lower()
    if type(value) is int:
        return str(value)
    return "E'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def compile_sources(
    manifest, existing, configurations, monsters, originals, definitions, categories
):
    known = {r["definition_id"] for r in existing["qualified"]}
    if len(known) != 50 or known & EXPECTED:
        raise ValueError("Daily native delta overlaps or changes original50")
    pins = {
        (r["native_catalog_revision"], r["monsters_path"], r["monsters_sha256"])
        for r in existing["qualified"]
    }
    if len(pins) != 1:
        raise ValueError("Inconsistent original daily catalog source")
    revision, monster_path, monster_sha = next(iter(pins))
    configs = {
        (c["route_key"], c["policy_version"]): c for c in configurations["configs"]
    }
    actors = {m["ref"]: m for m in monsters["monsters"]}
    originals = {o["id"]: o for o in originals}
    definitions = {d["definition_id"]: d for d in definitions["definitions"]}
    categories = {c["id"]: c for c in categories["categories"]}
    result = []
    seen = set()
    for source in manifest["rows"]:
        identity = source["definition_id"]
        if identity in seen or identity not in EXPECTED:
            raise ValueError("Duplicate or unexpected original daily source")
        seen.add(identity)
        definition = source["native_definition"]
        if (
            definition != definitions[identity]
            or definition["definition_id"] != identity
        ):
            raise ValueError("Original daily definition source changed")
        if (
            definition["activation_criteria"]
            or definition["eligibility_criteria"]
            or definition["repeatable"] is not True
            or definition["native_is_quest"] is not True
            or definition["calendar_period_seconds"] != 86400
            or definition["cooldown_seconds"] != 0
        ):
            raise ValueError("Original daily lifecycle or eligibility changed")
        objectives = definition["objectives"]
        if (
            len(objectives) != 1
            or objectives[0]["native_class"] != "aJN"
            or any(objectives[0][key] for key in ("ckc", "ckd", "cke", "ckf"))
        ):
            raise ValueError("Original daily objective program changed")
        objective = objectives[0]["d"]
        localizations = source["original_localizations"]
        if set(localizations) != {"en", "fr", "es"} or any(
            set(localizations[language]["objectives"]) != {str(objective)}
            or not localizations[language]["objectives"][str(objective)]
            for language in localizations
        ):
            raise ValueError("Missing original native objective localization")
        if not localizations["en"]["objectives"][str(objective)].startswith(
            "Defeat "
        ) or not localizations["fr"]["objectives"][str(objective)].startswith(
            "Vaincre "
        ):
            raise ValueError("Unsupported original native daily goal")
        category = source["original_category"]
        if (
            category != categories[definition["category_id"]]
            or category["parent_id"] != 517
        ):
            raise ValueError("Original daily category changed")
        bracket = re.fullmatch(
            r"Boss Hunt \[(\d{3})-(\d{3})\]", category["labels"]["en"]
        )
        if (
            bracket is None
            or source["minimum_level"] != int(bracket[1])
            or not 1 <= int(bracket[1]) <= int(bracket[2]) <= 245
            or source["minimum_level_authority"] != MINIMUM_AUTHORITY
        ):
            raise ValueError(
                "Daily minimum lacks its declared native-category authority"
            )
        boss, dungeon = source["boss_reference"], source["dungeon_definition_id"]
        actor = source["native_monster"]
        if (
            actor != actors[boss]
            or source["original_aKU"] != originals[dungeon]
            or boss not in originals[dungeon]["cno"]
            or [o["id"] for o in originals.values() if boss in o["cno"]] != [dungeon]
            or 43 not in actor["raw_visual_arrays"]["csc"]
        ):
            raise ValueError(
                "Daily target lacks unique original dungeon/native BOSS43 identity"
            )
        configuration = configs[(source["route_key"], source["route_policy_version"])]
        route = configuration["route"]
        final = max(configuration["rooms"], key=lambda room: room["order"])
        occurrences = [
            dict(monster_index=i, planned_role=m["role"], count=m["count"])
            for i, m in enumerate(final["monsters"])
            if m["ref_id"] == boss
        ]
        if (
            configuration["active"] is not True
            or route != source["route"]
            or route["definition_id"] != dungeon
            or route["start_map_id"] not in originals[dungeon]["aHA"]
            or final != source["final_room"]
            or final["order"] != source["final_room_order"]
            or occurrences != source["occurrences"]
            or not occurrences
            or any(
                o["planned_role"] not in ("boss", "monster", "unknown")
                or type(o["count"]) is not int
                or o["count"] <= 0
                for o in occurrences
            )
            or configuration["source_sha256"] != source["configuration_sha256"]
            or configuration["document_sha256"] != source["document_sha256"]
            or configuration["evidence_hashes"]["plan"] != source["plan_sha256"]
        ):
            raise ValueError("Immutable daily final-room/occurrence source changed")
        if (
            source["native_catalog_revision"],
            source["monsters_path"],
            source["monsters_sha256"],
        ) != (revision, monster_path, monster_sha):
            raise ValueError("Daily native catalog source differs from existing50")
        strict = {m["ref_id"] for m in final["monsters"] if m["role"] == "boss"} == {
            boss
        }
        if source["target_authority_kind"] != (
            "strict_final_boss" if strict else "native_BOSS43_final_occurrence"
        ):
            raise ValueError("Daily native target interpretation changed")
        rewards = definition["rewards"]
        if (
            len(rewards) != 2
            or {r["type_id"] for r in rewards} != {5, 6}
            or any(
                type(r["raw_flag_ckk"]) is not bool
                or len(r["parameters"]) != (2 if r["type_id"] == 5 else 1)
                or any(
                    type(p) is not int or not 0 < p < 2**63 for p in r["parameters"]
                )
                for r in rewards
            )
        ):
            raise ValueError("Original daily native5/6 rewards changed")
        provenance = dict(source)
        result.append(
            dict(
                definition_id=identity,
                version=1,
                objective_id=objective,
                minimum_level=source["minimum_level"],
                required_distinct=1,
                anchor_ms=definition["calendar_anchor_milliseconds"],
                period_ms=86400000,
                cooldown_ms=0,
                interpretation_policy=POLICY,
                boss_reference=boss,
                derived_variable_name="wakemu.daily.boss." + str(boss),
                dungeon_definition_id=dungeon,
                route_key=source["route_key"],
                route_policy_version=source["route_policy_version"],
                final_room_order=source["final_room_order"],
                category_id=category["id"],
                minimum_level_authority=MINIMUM_AUTHORITY,
                native_catalog_revision=revision,
                monsters_path=monster_path,
                monsters_sha256=monster_sha,
                plan_sha256=source["plan_sha256"],
                reward_policy=REWARD_POLICY,
                native_reward_order=[r["reward_id"] for r in rewards],
                original_native_rewards=rewards,
                native_property_id=43,
                source_authority=source["native_world_property_authority"],
                proof_sha256=digest(provenance),
                provenance=provenance,
                occurrences=occurrences,
            )
        )
    if seen != EXPECTED:
        raise ValueError("Native daily delta requires all15 original contracts")
    return dict(
        qualified=sorted(result, key=lambda r: r["definition_id"]),
        counts=dict(
            contracts=15, strict_final_boss=7, native_BOSS43_final_occurrence=8
        ),
        base_pool=BASE_POOL,
        pool_version=POOL,
        runtime_acceptance_active=False,
    )


def sql_seed(result, schema):
    out = [schema]
    contract_fields = (
        "definition_id",
        "version",
        "objective_id",
        "minimum_level",
        "required_distinct",
        "anchor_ms",
        "period_ms",
        "cooldown_ms",
        "interpretation_policy",
    )
    authority_fields = (
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
        "native_property_id",
        "source_authority",
        "proof_sha256",
    )
    for row in result["qualified"]:
        source = (
            "Wakemu-original-native-goal+named-boss+frozen-final-room:"
            + row["proof_sha256"]
        )
        out.append(
            "INSERT INTO recurring_hunter_contracts VALUES("
            + ",".join(literal(row[k]) for k in contract_fields)
            + ","
            + literal(source)
            + ");"
        )
        out.append(
            "INSERT INTO recurring_hunter_targets VALUES("
            + ",".join(
                map(
                    literal,
                    (
                        row["definition_id"],
                        row["version"],
                        row["boss_reference"],
                        row["derived_variable_name"],
                    ),
                )
            )
            + ");"
        )
        for reward in row["original_native_rewards"]:
            kind, parameters = reward["type_id"], reward["parameters"]
            values = (
                row["definition_id"],
                row["version"],
                reward["reward_id"],
                kind,
                parameters[0] if kind == 5 else None,
                parameters[1] if kind == 5 else parameters[0],
                reward["raw_flag_ckk"],
            )
            out.append(
                "INSERT INTO recurring_hunter_rewards VALUES("
                + ",".join(map(literal, values))
                + ");"
            )
        columns = ",".join(authority_fields) + ",native_reward_order,provenance"
        values = ",".join(literal(row[k]) for k in authority_fields)
        values += ",ARRAY[" + ",".join(map(str, row["native_reward_order"])) + "]"
        values += (
            ","
            + literal(
                json.dumps(
                    row["provenance"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
            )
            + "::jsonb"
        )
        out.append(
            "INSERT INTO recurring_hunter_native_target_authority ("
            + columns
            + ") VALUES("
            + values
            + ");"
        )
        for o in row["occurrences"]:
            values = (
                row["definition_id"],
                row["version"],
                o["monster_index"],
                o["planned_role"],
                o["count"],
            )
            out.append(
                "INSERT INTO recurring_hunter_native_target_occurrences VALUES("
                + ",".join(map(literal, values))
                + ");"
            )
    out.append(
        "INSERT INTO recurring_hunter_daily_pools VALUES("
        + ",".join(
            map(
                literal,
                (
                    POOL,
                    "wakemu.daily-hunter-utc-sorted-rotation-v1",
                    digest(result["qualified"]),
                    False,
                ),
            )
        )
        + ");"
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
            "INSERT INTO recurring_hunter_daily_members VALUES("
            + ",".join(
                map(
                    literal,
                    (POOL, row["category_id"], row["definition_id"], row["version"]),
                )
            )
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
    for name in (
        "manifest",
        "existing",
        "configurations",
        "monsters",
        "originals",
        "definitions",
        "categories",
        "schema",
        "output",
        "sql",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    load = lambda name: json.loads(getattr(args, name).read_text())
    result = compile_sources(
        *(
            load(n)
            for n in (
                "manifest",
                "existing",
                "configurations",
                "monsters",
                "originals",
                "definitions",
                "categories",
            )
        )
    )
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    args.sql.write_text(sql_seed(result, args.schema.read_text()))
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
