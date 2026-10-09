#!/usr/bin/env python3
"""Stream the pretty normal-cast report one bounded action at a time."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re


def summarize(path):
    pairs, breed, level = [], None, None
    in_actions, action = False, None
    peak = 0
    with Path(path).open() as source:
        for line in source:
            if line.startswith('      "breed": '):
                breed = json.loads(line.split(":", 1)[1].rstrip().rstrip(","))
            elif line.startswith('      "level": '):
                level = json.loads(line.split(":", 1)[1].rstrip().rstrip(","))
            elif line == '        "actions": [\n':
                in_actions = True
            elif in_actions and line == "        ],\n":
                in_actions = False
            elif in_actions and line == "          {\n":
                action = [line]
            elif action is not None:
                action.append(line)
                if line not in ("          },\n", "          }\n"):
                    continue
                raw = "".join(action).strip().rstrip(",")
                peak = max(peak, len(raw))
                entry = json.loads(raw)
                action = None
                if (
                    entry.get("origin") != "normal_owned_deck"
                    or entry.get("status") != "bounded_search_exhausted"
                ):
                    continue
                selection = entry.get("target_selection") or {}
                decisions = selection.get("rejected", [])
                contexts = []
                for rejected in decisions:
                    diagnostic = rejected.get("native_casting_diagnostic") or {}
                    contexts.append(
                        dict(
                            target=rejected.get("target"),
                            result=rejected.get("native_casting_result"),
                            reason=rejected.get("reason"),
                            authority_unresolved=rejected.get("authority_unresolved"),
                            criterion=diagnostic.get("criterion"),
                            flags=diagnostic.get("selected_casting_flags"),
                            target_id=diagnostic.get("target_id"),
                            failed_stages=[
                                event.get("stage")
                                for event in diagnostic.get("trace", [])
                                if event.get("value") is False
                            ],
                        )
                    )
                criteria = sorted({c["criterion"] for c in contexts if c["criterion"]})
                names = sorted(
                    set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", "\n".join(criteria)))
                )
                tags = []
                if any(
                    name in names
                    for name in ("HasSummonWithBreed", "IsOwnSummon", "IsBreedId")
                ):
                    tags.append("owned_summon_population")
                if any("State" in name for name in names):
                    tags.append("native_state_transition")
                if any("Area" in name for name in names):
                    tags.append("owned_effect_area_population")
                if any(
                    name in names
                    for name in (
                        "GetTeamId",
                        "IsEnnemy",
                        "IsEnemy",
                        "GetAlliesCountInRange",
                    )
                ):
                    tags.append("team_or_neighborhood_population")
                if "GetCharac" in names:
                    tags.append("current_resource_or_armor_threshold")
                if any(name in names for name in ("IsCarrying", "IsCarried")):
                    tags.append("carry_relation")
                pairs.append(
                    dict(
                        breed=breed,
                        level=level,
                        spell_reference=entry["reference"],
                        source_function_names=names,
                        source_search_tags=tags,
                        candidate_count=selection.get("candidate_count"),
                        checked_count=selection.get("checked_count"),
                        candidate_limit=selection.get("candidate_limit"),
                        candidate_truncated=selection.get("candidate_truncated"),
                        search_complete=selection.get("search_complete"),
                        contexts=contexts,
                    )
                )
    if action is not None:
        raise ValueError("Truncated action in completed report")
    keys = {(p["breed"], p["level"], p["spell_reference"]) for p in pairs}
    if len(keys) != len(pairs):
        raise ValueError("Duplicate bounded spell-level pairs")
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return dict(
        report=str(path),
        report_sha256=digest.hexdigest(),
        bounded_pairs=len(pairs),
        peak_action_characters=peak,
        class_counts=dict(collections.Counter(p["breed"] for p in pairs)),
        failed_stage_counts=dict(
            collections.Counter(
                stage
                for p in pairs
                for c in p["contexts"]
                for stage in c["failed_stages"]
            )
        ),
        pairs=pairs,
        full_functional_completion=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = summarize(args.report)
    if result["bounded_pairs"] != 43:
        raise ValueError("Expected43 bounded pairs in the qualified source report")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "bounded_pairs",
                    "peak_action_characters",
                    "class_counts",
                    "failed_stage_counts",
                )
            }
        )
    )
