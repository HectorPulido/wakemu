#!/usr/bin/env python3
"""Attest public daily quest objectives against current native final-room roles.

This builds declared Wakemu reconstruction data, not recovered original numeric
quest selectors. It never accepts a quest or installs a public gameplay file.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
POLICY = "wakemu.daily-hunter-public-final-room-v1"
REWARD_POLICY = "fixed-native-parameter-no-booster"
PUBLIC_URL = "https://wakfu.wiki.gg/wiki/Guild_of_Hunters"


def norm(value):
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).replace("’", "'"))
        .strip()
        .casefold()
    )


def compile_targets(
    definitions,
    observations,
    translations,
    configurations,
    native_monsters,
    *,
    revision,
    monsters_sha256,
    categories,
    original_dungeons,
    original_dungeon_sha256,
):
    """Pure strict join. Names suggest candidates; independent evidence authorizes data."""
    names = {}
    for language in ("en", "fr"):
        index = defaultdict(set)
        for key, value in translations[language].items():
            matched = re.fullmatch(r"content\.7\.(\d+)", key)
            if matched:
                index[norm(value)].add(int(matched[1]))
        names[language] = index
    native = {r["reference"]: r for r in native_monsters}
    final_roles = defaultdict(list)
    for config in configurations:
        rooms = config["rooms"]
        if not rooms:
            continue
        last = max(rooms, key=lambda r: r["order"])
        bosses = {r["ref_id"] for r in last["monsters"] if r["role"] == "boss"}
        if len(bosses) == 1:
            final_roles[next(iter(bosses))].append((config, last["order"]))
    source_categories = {r["id"]: r for r in categories}
    public = {r["definition_id"]: r for r in observations}
    accepted, pending = [], []
    for definition in definitions:
        identity = int(definition["definition_id"])
        row = public.get(identity)
        reason = None
        if definition["activation_criteria"].strip() == "False":
            continue
        if (
            definition["calendar_period_seconds"] != "86400"
            or definition["repeatable"] != "True"
            or int(definition["cooldown_seconds"]) != 0
            or definition["activation_criteria"]
            or definition["eligibility_criteria"]
        ):
            reason = "daily_lifecycle_or_criteria_unqualified"
        if row is None:
            reason = reason or "public_direct_row_missing"
        facts = (
            []
            if row is None
            else [
                f
                for f in row["public_direct_objective_rows"]
                if f["url"] == PUBLIC_URL
                and norm(f["quest_title"]) == norm(definition["title_en"])
                and norm(f["objective"]) == norm(row["native_objective_en"])
            ]
        )
        if not facts:
            reason = reason or "public_direct_objective_not_corroborated"
        bilingual = set()
        if row is not None:
            en = row["title_en"].split(": ", 1)
            fr = row["title_fr"].split(": ", 1)
            if len(en) == 2 and len(fr) == 2:
                bilingual = names["en"].get(norm(en[1]), set()) & names["fr"].get(
                    norm(fr[1]), set()
                )
        if len(bilingual) == 1:
            # Preserve the already-attested singleton identity path. The
            # original-dungeon uniqueness/map guard below remains mandatory.
            boss = next(iter(bilingual))
            roles = final_roles.get(boss, [])
        else:
            # Duplicate localized boss names can be resolved by an ORIGINAL
            # dungeon name literally present in the objective, its original
            # species roster, and exactly one actual final-room role.
            pairs = set()
            for original in original_dungeons:
                literal = (
                    any(
                        translations[language].get("content.137." + str(original["id"]))
                        and norm(
                            translations[language]["content.137." + str(original["id"])]
                        )
                        in norm(row.get("native_objective_" + language, ""))
                        for language in ("en", "fr")
                    )
                    if row is not None
                    else False
                )
                if literal:
                    pairs.update(
                        (reference, original["id"])
                        for reference in bilingual & set(original["cno"])
                    )
            bound = []
            if len(pairs) == 1:
                reference, dungeon = next(iter(pairs))
                bound = [
                    (reference, config, order)
                    for config, order in final_roles.get(reference, [])
                    if config["route"].get("definition_id") == dungeon
                ]
            boss = bound[0][0] if len(bound) == 1 else None
            roles = [(bound[0][1], bound[0][2])] if len(bound) == 1 else []
            if len(bound) != 1:
                reason = reason or "original_dungeon_bilingual_pair_not_unique"
        if len(roles) != 1:
            reason = reason or "active_single_final_boss_role_missing_or_ambiguous"
        record = native.get(boss)
        if (
            record is None
            or record.get("record_key") != str(boss)
            or record.get("name_es") != translations["es"].get("content.7." + str(boss))
        ):
            reason = reason or "current_catalog_native_identity_not_corroborated"
        levels = {f["minimum_level"] for f in facts}
        category = source_categories.get(int(definition["category_id"]))
        category_bracket = (
            None
            if category is None
            else re.fullmatch(
                r"Boss Hunt \[(\d{3})-(\d{3})\]", category["labels"]["en"]
            )
        )
        if (
            len(levels) != 1
            or any(type(v) is not int or v <= 0 for v in levels)
            or category_bracket is None
            or next(iter(levels)) != int(category_bracket[1])
        ):
            reason = reason or "public_level_and_native_category_label_disagree"
        objectives = json.loads(definition["objectives"])
        if (
            len(objectives) != 1
            or row is None
            or objectives[0]["d"] != row["objective_id"]
            or objectives[0].get("native_class") != "aJN"
            or any(objectives[0].get(k) for k in ("ckc", "ckd", "cke", "ckf"))
        ):
            reason = reason or "original_objective_identity_changed"
        rewards = json.loads(definition["rewards"])
        if len(rewards) != 2 or {r["type_id"] for r in rewards} != {5, 6}:
            reason = reason or "native_reward_family_changed"
        for reward in rewards:
            if (
                type(reward["raw_flag_ckk"]) is not bool
                or type(reward["parameters"]) is not list
                or len(reward["parameters"]) != (2 if reward["type_id"] == 5 else 1)
                or any(type(v) is not int or v <= 0 for v in reward["parameters"])
            ):
                reason = reason or "native_reward_parameters_changed"
        if reason:
            pending.append(dict(definition_id=identity, reason=reason))
            continue
        config, order = roles[0]
        route = config["route"]
        if (
            type(route.get("definition_id")) is not int
            or route["definition_id"] <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", config["evidence_hashes"]["plan"])
        ):
            pending.append(
                dict(
                    definition_id=identity, reason="route_or_plan_identity_unqualified"
                )
            )
            continue
        original_matches = [d for d in original_dungeons if boss in d["cno"]]
        if (
            len(original_matches) != 1
            or original_matches[0]["id"] != route["definition_id"]
            or route["start_map_id"] not in original_matches[0]["aHA"]
        ):
            pending.append(
                dict(
                    definition_id=identity,
                    reason="original_native_dungeon_identity_or_map_ambiguous",
                )
            )
            continue
        fact = sorted(facts, key=lambda f: f["receipt"])[0]
        accepted.append(
            dict(
                definition_id=identity,
                version=1,
                objective_id=objectives[0]["d"],
                category_id=int(definition["category_id"]),
                minimum_level=next(iter(levels)),
                minimum_level_authority="wakemu-reconstruction:explicit-public-row-level+original-category-label",
                boss_reference=boss,
                required_distinct=1,
                anchor_ms=int(definition["calendar_anchor_ms"]),
                period_ms=86400000,
                cooldown_ms=0,
                interpretation_policy=POLICY,
                derived_variable_name="wakemu.daily.boss." + str(boss),
                dungeon_definition_id=route["definition_id"],
                route_key=config["route_key"],
                route_policy_version=config["policy_version"],
                final_room_order=order,
                native_catalog_revision=revision,
                monsters_path="monsters.json",
                monsters_sha256=monsters_sha256,
                plan_sha256=config["evidence_hashes"]["plan"],
                public_url=PUBLIC_URL,
                original_dungeon_source_sha256=original_dungeon_sha256,
                original_dungeon_maps=original_matches[0]["aHA"],
                actual_start_map=route["start_map_id"],
                public_receipt=fact["receipt"],
                public_source_sha256=fact["source_sha256"],
                original_native_rewards=rewards,
                native_reward_order=[r["reward_id"] for r in rewards],
                reward_policy=REWARD_POLICY,
                source_claim="declared_Wakemu_reconstruction_not_original_numeric_selector",
                runtime_acceptance_active=False,
            )
        )
    return dict(
        qualified=accepted,
        pending=pending,
        counts=dict(
            qualified=len(accepted),
            pending=len(pending),
            by_category=dict(Counter(r["category_id"] for r in accepted)),
        ),
        interpretation_policy=POLICY,
        runtime_acceptance_active=False,
    )


def sql_literal(value):
    if value is None:
        return "NULL"
    if type(value) is bool:
        return str(value).lower()
    if type(value) is int:
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def sql_seed(result, schema):
    rows = result["qualified"]
    if not rows:
        raise ValueError("No attested daily contracts to seed")
    catalogs = {
        (r["native_catalog_revision"], r["monsters_path"], r["monsters_sha256"])
        for r in rows
    }
    output = [schema]
    for revision, path, sha in sorted(catalogs):
        output.append(
            "INSERT INTO recurring_hunter_catalog_sources VALUES("
            + ",".join(map(sql_literal, (revision, path, sha)))
            + ");"
        )
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
        "public_url",
        "public_source_sha256",
        "interpretation_policy",
        "reward_policy",
    )
    for row in sorted(rows, key=lambda r: r["definition_id"]):
        source = (
            "Wakemu-public-objective+native-bilingual+actual-final-role:"
            + row["public_source_sha256"]
        )
        output.append(
            "INSERT INTO recurring_hunter_contracts VALUES("
            + ",".join(sql_literal(row[k]) for k in fields)
            + ","
            + sql_literal(source)
            + ");"
        )
        output.append(
            "INSERT INTO recurring_hunter_targets VALUES("
            + ",".join(
                map(
                    sql_literal,
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
            output.append(
                "INSERT INTO recurring_hunter_rewards VALUES("
                + ",".join(map(sql_literal, values))
                + ");"
            )
        order = "ARRAY[" + ",".join(map(str, row["native_reward_order"])) + "]"
        output.append(
            "INSERT INTO recurring_hunter_target_authority VALUES("
            + ",".join(sql_literal(row[k]) for k in authority_fields)
            + ","
            + order
            + ");"
        )
    return "\n".join(output) + "\n"


def delta_sql_seed(result, prior, modulox, schema):
    """Append new contracts and a new sealed pool; never rewrite old sources."""
    old = {r["definition_id"]: r for r in prior["qualified"]}
    current = {r["definition_id"]: r for r in result["qualified"]}
    if set(old) - set(current):
        raise ValueError("Historical qualified daily identity lost")
    for identity, row in old.items():
        if current[identity] != row:
            raise ValueError("Historical qualified daily source changed")
    added = [r for r in result["qualified"] if r["definition_id"] not in old]
    if {r["definition_id"] for r in added} != {4194, 4212, 5117, 5397, 5398}:
        raise ValueError("Expected strict-public delta changed")
    # The catalog manifest is already immutable and present from293.
    seed = sql_seed(dict(qualified=added), "")
    seed = "\n".join(
        line
        for line in seed.splitlines()
        if not line.startswith("INSERT INTO recurring_hunter_catalog_sources ")
    )
    members = sorted(
        (r["category_id"], r["definition_id"], r["version"])
        for r in [*result["qualified"], *modulox["qualified"]]
    )
    if len(members) != 104 or len({r[0] for r in members}) != 20:
        raise ValueError("Expected combined daily50/Modulox54 pool changed")
    version = "wakemu.daily-hunter50-modulox54-v1"
    digest = hashlib.sha256(
        json.dumps(members, separators=(",", ":")).encode()
    ).hexdigest()
    output = [
        schema,
        seed,
        "INSERT INTO recurring_hunter_daily_pools VALUES("
        + ",".join(
            map(
                sql_literal,
                (version, "wakemu.daily-hunter-utc-sorted-rotation-v1", digest, False),
            )
        )
        + ");",
    ]
    for category, definition, version_id in members:
        output.append(
            "INSERT INTO recurring_hunter_daily_members VALUES("
            + ",".join(map(sql_literal, (version, category, definition, version_id)))
            + ");"
        )
    output.append(
        "UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version="
        + sql_literal(version)
        + ";"
    )
    output.append(
        "UPDATE recurring_hunter_daily_active SET pool_version="
        + sql_literal(version)
        + ",enabled=false WHERE singleton;"
    )
    return "\n".join(output) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--delta-from", type=Path)
    parser.add_argument("--combined-modulox", type=Path)
    args = parser.parse_args()
    evidence = ROOT / ".runtime/parallel-readiness-20261021/recurring-acceptance"
    definitions_path = (
        ROOT
        / "agents_docs/reports/parallel-readiness-20261021/recurring-native-definitions.csv"
    )
    source = json.loads(
        (evidence / "daily110-public-objective-corroboration.json").read_text()
    )
    configs = json.loads(
        (evidence / "web/current-final-room-boss-metadata.json").read_text()
    )
    monsters = json.loads(
        (evidence / "web/current-native-boss-scalar-records.json").read_text()
    )
    categories = json.loads(
        (evidence / "native-hunter-categories16-current.json").read_text()
    )
    extra = json.loads(
        (evidence / "web/daily65-new-positive-boss-records.json").read_text()
    )
    if (
        extra["revision"] != monsters["revision"]
        or extra["document"] != monsters["document"]
    ):
        raise ValueError("Additional daily boss source release changed")
    indexed = {r["reference"]: r for r in monsters["records"]}
    for record in extra["records"]:
        if record["reference"] in indexed and any(
            indexed[record["reference"]].get(k) != v for k, v in record.items()
        ):
            raise ValueError("Conflicting same-catalog scalar record")
        indexed.setdefault(record["reference"], record)
    monsters["records"] = list(indexed.values())
    dungeon_path = evidence / "native-dungeon-qa/original-aKU-definitions.json"
    original_dungeon_bytes = dungeon_path.read_bytes()
    original_dungeons = json.loads(original_dungeon_bytes)
    with gzip.open(ROOT / "server/protocol/npc-dialogues.json.gz", "rt") as stream:
        native = json.load(stream)
    if configs["revision"] != monsters["revision"]:
        raise ValueError("Native monster/config release changed")
    for language in ("en", "fr", "es"):
        archive = ROOT / f"client/contents/i18n/i18n_{language}.jar"
        if (
            hashlib.sha256(archive.read_bytes()).hexdigest()
            != native["provenance"]["languages_sha256"][language]
        ):
            raise ValueError("Original bilingual translation release changed")
        with ZipFile(archive) as zipped:
            native["translations"][language] = dict(
                line.split("=", 1)
                for line in zipped.read(f"texts_{language}.properties")
                .decode()
                .splitlines()
                if "=" in line
            )
    expected = {r["definition_id"] for r in source["rows"]}
    with definitions_path.open() as stream:
        definitions = [
            r for r in csv.DictReader(stream) if int(r["definition_id"]) in expected
        ]
    for observation in source["rows"]:
        for fact in observation["public_direct_objective_rows"]:
            receipt = evidence / "web" / fact["receipt"]
            raw = receipt.read_bytes()
            fact["source_sha256"] = hashlib.sha256(raw).hexdigest()
            text = json.loads(raw)
            # The exact public quest/objective pair must be observable in the
            # retained indexed page, not merely asserted by a candidate file.
            pattern = re.compile(
                r"^"
                + re.escape(fact["quest_title"])
                + r"\n+Lvl "
                + str(fact["minimum_level"])
                + r"\b(?P<body>.*?)(?=^Boss Hunt: |^Multi-Boss Hunt |\Z)",
                re.M | re.S,
            )
            matches = list(pattern.finditer(text))
            if not any(fact["objective"] in m["body"] for m in matches):
                raise ValueError("Public quest-objective source receipt changed")
    result = compile_targets(
        definitions,
        source["rows"],
        native["translations"],
        configs["configs"],
        monsters["records"],
        revision=configs["revision"],
        monsters_sha256=monsters["document"]["sha256"],
        categories=categories["categories"],
        original_dungeons=original_dungeons,
        original_dungeon_sha256=hashlib.sha256(original_dungeon_bytes).hexdigest(),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    columns = (
        "definition_id",
        "objective_id",
        "minimum_level",
        "minimum_level_authority",
        "boss_reference",
        "dungeon_definition_id",
        "route_key",
        "route_policy_version",
        "native_catalog_revision",
        "monsters_sha256",
        "plan_sha256",
        "public_url",
        "public_source_sha256",
        "interpretation_policy",
        "runtime_acceptance_active",
    )
    with args.csv.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in result["qualified"]:
            writer.writerow({key: row[key] for key in columns})
    if args.delta_from is not None:
        if args.combined_modulox is None:
            raise ValueError("Delta pool requires immutable Modulox source membership")
        prior = json.loads(args.delta_from.read_text())
        modulox = json.loads(args.combined_modulox.read_text())
        args.sql.write_text(
            delta_sql_seed(result, prior, modulox, args.schema.read_text())
        )
    else:
        args.sql.write_text(sql_seed(result, args.schema.read_text()))
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
