#!/usr/bin/env python3
"""Read-only classifier of typed native loot, world sources and quest markers.

This tool never publishes missions or treats a running guard as an activation.
Exact marker matches produce review candidates, not executable permissions.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


def guards(expression):
    """Accept only literal conjunctive quest/objective and absence predicates."""
    text = expression.strip().rstrip(";").strip()
    if not text:
        return dict(quests=[], complete=[], incomplete=[], absent=[])
    result = dict(quests=[], complete=[], incomplete=[], absent=[])
    for atom in re.split(r"\s+(?:and)\s+|\s*&&\s*", text):
        atom = atom.strip()
        if match := re.fullmatch(r"IsAchievementRunning\((\d+)\)", atom):
            result["quests"].append(int(match[1]))
        elif match := re.fullmatch(r"IsAchievementObjectiveComplete\((\d+)\)", atom):
            result["complete"].append(int(match[1]))
        elif match := re.fullmatch(
            r"(?:not\s+|!)IsAchievementObjectiveComplete\((\d+)\)", atom
        ):
            result["incomplete"].append(int(match[1]))
        elif match := re.fullmatch(
            r"GetItemQuantity\((\d+)\)\s*(?:<=\s*0|==\s*0|<\s*1)", atom
        ):
            result["absent"].append(int(match[1]))
        else:
            return None
    return result


def deterministic_item(effect, tables):
    parameters = effect.get("parameters", [])
    if effect["effect_type"] == 12:
        if len(parameters) == 2 and all(
            re.fullmatch(r"[1-9]\d*", p) for p in parameters
        ):
            return dict(
                reference=int(parameters[0]),
                quantity=int(parameters[1]),
                kind="native_item_effect",
            )
        return None
    if (
        effect["effect_type"] != 4
        or len(parameters) != 1
        or not re.fullmatch(r"[1-9]\d*", parameters[0])
    ):
        return None
    table = tables.get(int(parameters[0]))
    if not table or table.get("czg") != 1 or len(table.get("gBN", [])) != 1:
        return None
    entry = table["gBN"][0]
    if (
        entry.get("native_class") != "fFe"
        or entry.get("cqA") is not False
        or entry.get("cmY") != 1
        or entry.get("gBO") != []
        or entry.get("czk") != ""
        or entry.get("czl") != 0
        or entry.get("csE") != 1
        or type(entry.get("aAi")) is not int
        or entry["aAi"] <= 0
        or type(entry.get("cqy")) is not int
        or entry["cqy"] <= 0
        or entry["cqy"] != entry.get("cqz")
        or entry["cqy"] != entry.get("bfh")
    ):
        return None
    return dict(
        reference=entry["aAi"],
        quantity=entry["cqy"],
        kind="native_deterministic_loot",
        loot_list_id=table["d"],
        loot_entry_id=entry["d"],
    )


def classify(descriptors, tables, sources, context):
    table_index = {r["d"]: r for r in tables["tables"]}
    source_index = defaultdict(list)
    for source in sources:
        source_index[source.get("descriptor_id")].append(source)
    quests = {r["definition_id"]: r["data"]["native"] for r in context["definitions"]}
    objective_quests = defaultdict(set)
    for quest in quests.values():
        for objective in quest.get("cjJ", []):
            objective_quests[objective["d"]].add(quest["d"])
    publication = next(
        (
            r["value"]
            for r in context.get("settings", [])
            if r["name"] == "native_quest_conversation_contracts"
        ),
        {},
    )
    placements = defaultdict(list)
    for row in publication.get("placements", []):
        placements[row["quest_id"]].append(
            dict(
                activation_policy=row.get("activation_policy"),
                reference_id=row["row"]["reference_id"],
                map_id=row["row"]["map_id"],
                dialogue_root=row["row"]["dialogue_root"],
            )
        )
    candidates = []
    counters = Counter()
    for descriptor in descriptors["descriptors"]:
        for group in descriptor["groups"]:
            for action in group["actions"]:
                for effect in action["effects"]:
                    if effect["effect_type"] not in (4, 12):
                        continue
                    counters["item_or_loot_effects"] += 1
                    criteria = [action["criterion"], effect["criterion"]]
                    if not any(
                        "IsAchievementRunning(" in c
                        or "IsAchievementObjectiveComplete(" in c
                        for c in criteria
                    ):
                        continue
                    counters["lexical_quest_guard_effects"] += 1
                    parsed = [guards(c) for c in criteria]
                    payload = deterministic_item(effect, table_index)
                    row = dict(
                        descriptor_id=descriptor["descriptor_id"],
                        native_action_id=action["native_id"],
                        action=action["wire_action"],
                        effect_id=effect["action_reference"],
                        criteria=criteria,
                        item=payload,
                        status="review_required",
                        sources=source_index[descriptor["descriptor_id"]],
                    )
                    mentioned = set(
                        int(v)
                        for c in criteria
                        for v in re.findall(r"IsAchievementRunning\((\d+)\)", c)
                    )
                    for c in criteria:
                        for v in re.findall(
                            r"IsAchievementObjectiveComplete\((\d+)\)", c
                        ):
                            mentioned.update(objective_quests[int(v)])
                    row["quest_ids"] = sorted(mentioned)
                    row["levels"] = {
                        str(q): quests[q].get("cjP") for q in mentioned if q in quests
                    }
                    row["published_activation_paths"] = {
                        str(q): placements[q] for q in mentioned if placements[q]
                    }
                    reasons = []
                    if any(p is None for p in parsed):
                        reasons.append("nonliteral_or_unsupported_criterion")
                    if payload is None:
                        reasons.append("random_nested_or_unsupported_loot")
                    if any(group[k] != 0 for k in ("cod", "coe", "cnd", "cog")):
                        reasons.append("additional_group_cost_or_authority")
                    if any(
                        e["effect_type"] not in (1, 4, 12) for e in action["effects"]
                    ):
                        reasons.append("additional_native_effect_requires_producer")
                    if sum(e["effect_type"] in (4, 12) for e in action["effects"]) != 1:
                        reasons.append("multiple_item_effects_in_action")
                    positive_quests = set(q for p in parsed if p for q in p["quests"])
                    if len(positive_quests) != 1:
                        reasons.append("no_unique_literal_running_quest")
                    matches = []
                    for quest_id in positive_quests:
                        quest = quests.get(quest_id, {})
                        for source in row["sources"]:
                            for objective in quest.get("cjJ", []):
                                for mark in objective.get("ckd", []):
                                    if [
                                        source[k] for k in ("map_id", "x", "y", "z")
                                    ] == [
                                        mark[k] for k in ("ckj", "ckg", "ckh", "cki")
                                    ]:
                                        matches.append(
                                            dict(
                                                quest_id=quest_id,
                                                objective_id=objective["d"],
                                                object_id=source["id"],
                                                map_id=source["map_id"],
                                                objective_count=len(quest["cjJ"]),
                                            )
                                        )
                    row["exact_objective_matches"] = matches
                    if len(matches) != 1:
                        reasons.append("no_unique_exact_objective_marker")
                    row["reasons"] = reasons
                    row["status"] = (
                        "source_qualified_review_candidate"
                        if not reasons
                        else "blocked"
                    )
                    # Feedback scripts are not guessed safe and publication is
                    # deliberately absent even for source-qualified candidates.
                    row["native_scripts_needing_review"] = sorted(
                        {
                            e["action_reference"]
                            for e in action["effects"]
                            if e["effect_type"] == 1
                        }
                    )
                    candidates.append(row)
    candidates.sort(
        key=lambda r: (
            min(r["levels"].values(), default=9999),
            r["descriptor_id"],
            r["effect_id"],
        )
    )
    counters.update(
        dict(
            descriptors=len(descriptors["descriptors"]),
            loot_tables=len(tables["tables"]),
            generic_sources=len(sources),
            classified_candidates=len(candidates),
            source_qualified_review_candidates=sum(
                r["status"] != "blocked" for r in candidates
            ),
            level_at_most_35_candidates=sum(
                any(v <= 35 for v in r["levels"].values()) for r in candidates
            ),
        )
    )
    return dict(
        schema="native-quest-ground-pickup-readiness-v1",
        counts=dict(counters),
        blockers=dict(
            Counter(reason for row in candidates for reason in row["reasons"])
        ),
        candidates=candidates,
        publication_policy="Read-only: running guards never activate quests; marker matches require feedback-script review and actual activation-path validation before any manifest publication.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("descriptors", "tables", "sources", "context", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = classify(
        *(
            json.loads(getattr(args, name).read_text())
            for name in ("descriptors", "tables", "sources", "context")
        )
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
