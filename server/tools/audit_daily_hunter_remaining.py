#!/usr/bin/env python3
"""Audit all daily hunter targets using original dungeon identities and stored plans.

This source-only tool never installs a target, activates a plan or grants credit.
Historical immutable plans remain explicitly separate from active configurations.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "agents_docs/reports/parallel-readiness-20261021"
EVIDENCE = ROOT / ".runtime/parallel-readiness-20261021/recurring-acceptance"


def norm(value):
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).replace("’", "'"))
        .strip()
        .casefold()
    )


def audit(definitions, observations, prior, originals, configurations, translations):
    """Return independent numeric joins, preserving unresolved and inactive scope."""
    indexed = {int(row["definition_id"]): row for row in definitions}
    if len(indexed) != len(definitions):
        raise ValueError("Duplicate original daily definition")
    observed = {row["definition_id"]: row for row in observations}
    if set(indexed) != set(observed) or len(observed) != len(observations):
        raise ValueError("Daily source/observation inventory differs")
    prior_qualified = {row["definition_id"] for row in prior["qualified"]}
    prior_reasons = {row["definition_id"]: row["reason"] for row in prior["pending"]}
    if prior_qualified & set(prior_reasons) or prior_qualified | set(
        prior_reasons
    ) != set(indexed):
        raise ValueError("Prior daily partition differs")
    names = {}
    for language in ("en", "fr"):
        names[language] = {}
        for key, value in translations[language].items():
            match = re.fullmatch(r"content\.7\.(\d+)", key)
            if match:
                names[language].setdefault(norm(value), set()).add(int(match[1]))
    rows = []
    for identity, source in sorted(indexed.items()):
        if (
            source["activation_criteria"]
            or source["eligibility_criteria"]
            or source["calendar_period_seconds"] != "86400"
            or source["repeatable"] != "True"
        ):
            raise ValueError("Unexpected daily lifecycle/gate")
        objectives = json.loads(source["objectives"])
        if (
            len(objectives) != 1
            or objectives[0]["native_class"] != "aJN"
            or any(objectives[0][key] for key in ("ckc", "ckd", "cke", "ckf"))
        ):
            raise ValueError("Original daily objective program changed")
        oid = objectives[0]["d"]
        observation = observed[identity]
        if oid != observation["objective_id"]:
            raise ValueError("Original daily objective identity changed")
        titles = {
            lang: translations[lang].get("content.62." + str(identity), "")
            for lang in ("en", "fr")
        }
        labels = {
            lang: translations[lang].get("content.64." + str(oid), "")
            for lang in ("en", "fr")
        }
        title_names = {
            lang: value.split(":", 1)[1] if ":" in value else ""
            for lang, value in titles.items()
        }
        refs = names["en"].get(norm(title_names["en"]), set()) & names["fr"].get(
            norm(title_names["fr"]), set()
        )
        original_pairs = []
        plans = []
        for original in originals:
            dungeon_names = {
                lang: translations[lang].get("content.137." + str(original["id"]), "")
                for lang in ("en", "fr")
            }
            literal = {
                lang: bool(name and norm(name) in norm(labels[lang]))
                for lang, name in dungeon_names.items()
            }
            if not any(literal.values()):
                continue
            for ref in sorted(refs & set(original["cno"])):
                pair = dict(
                    boss_reference=ref,
                    dungeon_definition_id=original["id"],
                    dungeon_names=dungeon_names,
                    literal_name_matches=literal,
                )
                original_pairs.append(pair)
                for config in configurations:
                    rooms = config.get("rooms") or []
                    route = config.get("route") or {}
                    if not rooms or route.get("definition_id") != original["id"]:
                        continue
                    last = max(rooms, key=lambda row: row["order"])
                    bosses = {
                        monster["ref_id"]
                        for monster in last["monsters"]
                        if monster["role"] == "boss"
                    }
                    if bosses == {ref} and route.get("start_map_id") in original["aHA"]:
                        plans.append(
                            dict(
                                pair,
                                route_key=config["route_key"],
                                policy_version=config["policy_version"],
                                final_room_order=last["order"],
                                is_active=config["is_active"],
                                plan_sha256=(config.get("evidence_hashes") or {}).get(
                                    "plan"
                                ),
                                policy_mode=config.get("policy_mode"),
                            )
                        )
        original_keys = {
            (row["dungeon_definition_id"], row["boss_reference"])
            for row in original_pairs
        }
        plan_keys = {
            (row["dungeon_definition_id"], row["boss_reference"]) for row in plans
        }
        active_keys = {
            (row["dungeon_definition_id"], row["boss_reference"])
            for row in plans
            if row["is_active"]
        }
        active_routes = {
            (row["route_key"], row["policy_version"])
            for row in plans
            if row["is_active"]
        }
        paired_dungeons = {key[0] for key in original_keys}
        stored_original = [
            config
            for config in configurations
            if (config.get("route") or {}).get("definition_id") in paired_dungeons
        ]
        positive = (
            len(original_keys) == len(plan_keys) == 1 and original_keys == plan_keys
        )
        active_positive = positive and len(active_keys) == len(active_routes) == 1
        if not refs:
            reason = "no_shared_original_EN_FR_boss_name_reference"
        elif not original_keys:
            reason = "no_original_dungeon_species_and_literal_objective_join"
        elif len(original_keys) > 1:
            reason = "multiple_original_dungeon_boss_pairs"
        elif not plan_keys:
            reason = (
                "stored_final_room_does_not_mark_original_candidate_as_single_boss"
                if stored_original
                else "original_pair_has_no_stored_dungeon_configuration"
            )
        elif not positive:
            reason = "stored_plan_pair_ambiguous"
        elif active_positive:
            reason = "unique_original_pair_and_active_final_boss_plan"
        else:
            reason = "unique_original_pair_prepared_plan_only_or_active_ambiguous"
        rows.append(
            dict(
                definition_id=identity,
                objective_id=oid,
                title_en=titles["en"],
                prior_qualified=identity in prior_qualified,
                prior_reason=prior_reasons.get(identity),
                public_objective_exact=observation["public_exact_native_objective"],
                bilingual_name_candidates=sorted(refs),
                original_objective_labels=labels,
                original_dungeon_pairs=original_pairs,
                matching_stored_plans=plans,
                native_positive_pair=positive,
                active_positive_pair=active_positive,
                reason=reason,
                runtime_target_authorized=False,
            )
        )
    remaining = [row for row in rows if not row["prior_qualified"]]
    return dict(
        scope="Source audit only; no new runtime binding or plan activation",
        rows=rows,
        counts=dict(
            all_daily_candidates=len(rows),
            prior_qualified=len(prior_qualified),
            remaining=len(remaining),
            prior_remaining_reasons=dict(
                Counter(row["prior_reason"] for row in remaining)
            ),
            remaining_native_join_reasons=dict(
                Counter(row["reason"] for row in remaining)
            ),
            remaining_positive_native_pair=sum(
                row["native_positive_pair"] for row in remaining
            ),
            remaining_positive_active_pair=sum(
                row["active_positive_pair"] for row in remaining
            ),
            remaining_public_exact_and_active_pair=sum(
                row["active_positive_pair"] and row["public_objective_exact"]
                for row in remaining
            ),
        ),
        runtime_authorized_new_targets=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configurations",
        type=Path,
        default=EVIDENCE / "web/all-immutable-dungeon-boss-configurations.json",
    )
    parser.add_argument(
        "--native-bosses",
        type=Path,
        default=EVIDENCE / "web/daily65-new-positive-boss-records.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BASE / "daily65-original-dungeon-disambiguation.json",
    )
    args = parser.parse_args()
    source = BASE / "recurring-native-definitions.csv"
    family_source = BASE / "recurring-source-family-classification.csv"
    with family_source.open() as stream:
        families = {
            row["definition_id"]: row["family"] for row in csv.DictReader(stream)
        }
    with source.open() as stream:
        definitions = [
            row
            for row in csv.DictReader(stream)
            if families[row["definition_id"]] == "trade_hunt_contract_candidate"
            and row["calendar_period_seconds"] == "86400"
            and row["activation_criteria"] == ""
        ]
    translations = {}
    archives = []
    for lang in ("en", "fr", "es"):
        archive = ROOT / f"client/contents/i18n/i18n_{lang}.jar"
        archives.append(archive)
        with ZipFile(archive) as zipped:
            translations[lang] = dict(
                line.split("=", 1)
                for line in zipped.read(f"texts_{lang}.properties")
                .decode()
                .splitlines()
                if "=" in line
            )
    observations_path = EVIDENCE / "daily110-public-objective-corroboration.json"
    prior_path = EVIDENCE / "daily45-source-derived-targets.json"
    original_path = EVIDENCE / "native-dungeon-qa/original-aKU-definitions.json"
    load = lambda path: json.loads(path.read_text())
    configuration_document = load(args.configurations)
    result = audit(
        definitions,
        load(observations_path)["rows"],
        load(prior_path),
        load(original_path),
        configuration_document["configs"],
        translations,
    )
    boss_document = load(args.native_bosses)
    if boss_document["revision"] != configuration_document["revision"]:
        raise ValueError("Native boss/configuration revisions differ")
    native_bosses = {row["reference"]: row for row in boss_document["records"]}
    for row in result["rows"]:
        if row["prior_qualified"] or not row["native_positive_pair"]:
            continue
        reference = row["original_dungeon_pairs"][0]["boss_reference"]
        record = native_bosses.get(reference)
        if (
            record is None
            or record["record_key"] != str(reference)
            or record["name_es"]
            != translations["es"].get("content.7." + str(reference))
        ):
            raise ValueError("New positive boss lacks same-catalog original identity")
        row["positive_native_record_verified"] = True
    result["native_monsters_document"] = boss_document["document"]
    result["catalog_revision"] = configuration_document["revision"]
    result["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            source,
            family_source,
            observations_path,
            prior_path,
            original_path,
            args.configurations,
            args.native_bosses,
            *archives,
        )
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
