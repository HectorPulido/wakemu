"""Inventory native quest shapes without claiming that metadata enables gameplay.

The input is ExportNativeQuestDefinitions JSON (or gzip). An optional publication
snapshot contains ``settings`` name/value pairs and active toolkit ``profiles``.
This read-only tool deliberately never derives gameplay bindings from text or
waypoints. Semantic hints help prioritize review; they are not activation rules.
"""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

SINGLE_COUNTER = re.compile(r'GetAchievementVariable\("([^"\\]+)"\)\s*>=\s*([0-9]+)\Z')
VARIABLE = re.compile(r'GetAchievementVariable\("([^"\\]+)"\)')
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
# These are the shared dungeon_criteria evaluator's supported predicate names.
# Dedicated mission providers may support additional names; this is not an
# assertion that such predicates are globally unsupported by the server.
SHARED_PREDICATES = frozenset(
    (
        "IsNeoServer",
        "GetBooleanSystemConfiguration",
        "GetRealLevel",
        "GetItemQuantity",
        "HasState",
        "IsAfter",
        "IsBefore",
        "GetDate",
        "IsAchievementRunning",
        "IsAchievementObjectiveComplete",
        "IsAchievementComplete",
    )
)
SUPPORTED_REWARD_TYPES = frozenset((2, 3, 5, 6, 11, 12, 15, 17))
OBJECTIVE_HINTS = (
    ("dialogue", r"(?:Talk to|Speak to|Speak with|Ask |Report to|Report back)"),
    ("combat", r"(?:Defeat |Kill |Hunt )"),
    ("delivery", r"(?:Take [0-9]+ |Bring |Give |Deliver )"),
    ("travel", r"(?:Go to|Head to|Enter |Explore |Cross )"),
    (
        "interaction",
        r"(?:Inspect |Examine |Search |Activate |Use |Interact |Pray |Deactivate |Open |Knock )",
    ),
    ("completion", r"(?:Complete |Finish )"),
    ("harvest", r"(?:Harvest |Collect )"),
    ("planting", r"Plant "),
    ("crafting", r"(?:Craft |Make )"),
)


def objective_hint(text):
    """A localized review hint only; e.g. 'complete' may mean quest or dungeon."""
    return next(
        (label for label, pattern in OBJECTIVE_HINTS if re.match(pattern, text)),
        "other",
    )


def load_export(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    document = json.loads(raw)
    if document.get("schema_version") != 1 or not isinstance(
        document.get("definitions"), list
    ):
        raise ValueError("Expected native quest export schema 1")
    ids = [row["d"] for row in document["definitions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate native definition identity")
    return document, hashlib.sha256(raw).hexdigest()


def counter_shape(objective):
    """Describe native counter syntax; do not infer its gameplay event source."""
    conditions = objective.get("ckf") or []
    if not conditions:
        return "direct_event"
    if len(conditions) == 1:
        condition = conditions[0]
        expression = condition.get("ckm", "").strip()
        match = SINGLE_COUNTER.fullmatch(expression)
        sources = condition.get("ckn")
        if (
            match is not None
            and 0 < int(match[2]) < 2**63
            and isinstance(sources, list)
            and len(sources) == 1
            and type(sources[0]) is int
            and sources[0] > 0
        ):
            return "single_counter"
        names = VARIABLE.findall(expression)
        reduced = VARIABLE.sub("V", expression)
        if len(names) > 1 and re.fullmatch(
            r"\s*\(\s*V(?:\s*\+\s*V)+\s*\)\s*(?:>=|==)\s*[0-9]+\s*",
            reduced,
        ):
            if all(
                re.fullmatch(r"(?:hunterLevel[0-9]+Boss|neoHunterBoss)[0-9]+", n)
                for n in names
            ):
                return "distinct_boss_counter"
            return "sum_counter"
    return "special_counter"


def publication_index(snapshot):
    """Index explicit publication coverage, which is not end-to-end acceptance."""
    covered = defaultdict(set)
    for row in snapshot.get("recurring_contracts", ()):
        if row.get("has_acceptance_source") is True:
            covered[(row["definition_id"], row["objective_id"])].add(
                "recurring:" + row["interpretation_policy"]
            )
    for row in snapshot.get("profiles", ()):
        document = row.get("document", row)
        provider = "toolkit:" + row.get("profile_id", document.get("id", "unknown"))
        for entry in document.get("bindings", ()):
            covered[(entry["quest_id"], entry["objective_id"])].add(provider)
        for entry in document.get("links", ()):
            covered[(entry["parent_quest_id"], entry["objective_id"])].add(provider)
    settings = snapshot.get("settings", ())
    settings = settings.items() if isinstance(settings, dict) else settings
    for name, value in settings:
        if not isinstance(value, dict) or name == "mission_journal_preview":
            continue
        for entry in value.get("bindings", ()):
            if "quest_id" in entry and "objective_id" in entry:
                covered[(entry["quest_id"], entry["objective_id"])].add(name)
    return covered


def inspect(document, *, revision=None, publications=None, include_achievements=False):
    """Return finite, disjoint structural counts and separately labelled hints."""
    definitions = document["definitions"]
    quests = [row for row in definitions if row.get("aqb") is False]
    selected = definitions if include_achievements else quests
    translations = document.get("translations", {})

    def text(kind, identity, language="en"):
        return translations.get(language, {}).get(f"content.{kind}.{identity}", "")

    coverage = publication_index(publications or {})
    rows, predicates = [], Counter()
    objective_shapes, quest_shapes, hints = Counter(), Counter(), Counter()
    objective_hints = Counter()
    categories = Counter()
    for definition in sorted(selected, key=lambda item: item["d"]):
        identity = definition["d"]
        objectives = definition["cjJ"]
        shape_counts = Counter(counter_shape(obj) for obj in objectives)
        localized_objectives = Counter(
            objective_hint(text(64, obj["d"])) for obj in objectives
        )
        objective_hints.update(localized_objectives)
        objective_shapes.update(shape_counts)
        shape = (
            "counter_only"
            if "direct_event" not in shape_counts
            else (
                "mixed_direct_and_counter"
                if len(shape_counts) > 1
                else (
                    "single_direct_event"
                    if len(objectives) == 1
                    else "direct_event_chain"
                )
            )
        )
        quest_shapes[shape] += 1
        criteria = [definition.get("cjI", "")]
        criteria += [obj.get(key, "") for obj in objectives for key in ("ckc", "cke")]
        calls = {
            name
            for expr in criteria
            for name in CALL.findall(expr)
            if name not in ("and", "or", "not")
        }
        predicates.update(calls)
        outside_shared = sorted(calls - SHARED_PREDICATES)
        title = text(62, identity)
        category = definition["cjG"]
        categories[category] += 1
        inferred = []
        for prefix, label in (
            ("Boss Hunt:", "boss_hunt"),
            ("Hunting Trophies:", "adjusted_boss_hunt"),
            ("Monster Hunt:", "monster_hunt"),
            ("Neo Boss Hunt:", "neo_boss_hunt"),
        ):
            if title.startswith(prefix):
                inferred.append(label)
        # These are native category identities with localized category labels,
        # not a string-derived mapping to a monster, NPC, item or event.
        category_title = text(61, category)
        if category_title == "Monster Hunt":
            inferred.append("monster_hunt")
        if category_title.startswith("Adjustable Level - Bosses"):
            inferred.append("adjusted_boss_hunt")
        if category_title.startswith("Level Group ["):
            inferred.append("hunter_level_group")
        hints.update(set(inferred))
        published = [obj["d"] for obj in objectives if (identity, obj["d"]) in coverage]
        rows.append(
            {
                "quest_id": identity,
                "title_en": title,
                "title_es": text(62, identity, "es"),
                "definition_kind": (
                    "quest" if definition.get("aqb") is False else "achievement"
                ),
                "hidden": definition.get("isVisible") is False,
                "category_id": category,
                "category_en": category_title,
                "shape": shape,
                "objective_count": len(objectives),
                "counter_shapes": dict(sorted(shape_counts.items())),
                "timed_or_recurring": any(
                    definition.get(key, 0) != 0 for key in ("cjL", "cjU", "getDuration")
                ),
                "waypoint_objective_count": sum(
                    bool(obj.get("ckd")) for obj in objectives
                ),
                "shared_transition_predicates_requiring_adapter": outside_shared,
                "reward_types_requiring_adapter": sorted(
                    {reward["aeV"] for reward in definition.get("cjK", ())}
                    - SUPPORTED_REWARD_TYPES
                ),
                "localized_candidate_hints": sorted(set(inferred)),
                "localized_objective_hints": dict(sorted(localized_objectives.items())),
                "published_objectives": published,
                "all_objectives_have_explicit_publication": bool(objectives)
                and len(published) == len(objectives),
                "publication_providers": sorted(
                    {
                        provider
                        for obj in objectives
                        for provider in coverage.get((identity, obj["d"]), ())
                    }
                ),
            }
        )
    summary = {
        "definition_count": len(definitions),
        "quest_definition_count": len(quests),
        "visible_quest_count": sum(row.get("isVisible") is True for row in quests),
        "hidden_quest_count": sum(row.get("isVisible") is False for row in quests),
        "achievement_definition_count": len(definitions) - len(quests),
        "selected_definition_count": len(rows),
        "selected_objective_count": sum(row["objective_count"] for row in rows),
        "quest_shapes": dict(sorted(quest_shapes.items())),
        "objective_shapes": dict(sorted(objective_shapes.items())),
        "timed_or_recurring_quests": sum(row["timed_or_recurring"] for row in rows),
        "quests_with_waypoints": sum(
            row["waypoint_objective_count"] > 0 for row in rows
        ),
        "waypoint_objectives": sum(row["waypoint_objective_count"] for row in rows),
        "quests_with_some_explicit_publication": sum(
            bool(row["published_objectives"]) for row in rows
        ),
        "quests_with_all_objectives_explicitly_published": sum(
            row["all_objectives_have_explicit_publication"] for row in rows
        ),
        "quests_requiring_shared_transition_predicate_adapter": sum(
            bool(row["shared_transition_predicates_requiring_adapter"]) for row in rows
        ),
        "quests_requiring_reward_type_adapter": sum(
            bool(row["reward_types_requiring_adapter"]) for row in rows
        ),
        "localized_candidate_hints": dict(sorted(hints.items())),
        "localized_objective_hints": dict(sorted(objective_hints.items())),
        "shared_transition_predicates": dict(predicates.most_common()),
        "categories": [
            {"id": key, "title_en": text(61, key), "quests": count}
            for key, count in categories.most_common()
        ],
    }
    return {
        "schema": "wakemu.mission-archetype-inventory-v1",
        "native_revision": revision,
        "limitations": [
            "Published objectives do not establish activation, NPC reachability, reward delivery or end-to-end acceptance.",
            "Waypoint markers describe navigation, not proof that entering the cell completes an objective.",
            "Localized candidate hints are prioritization aids, never gameplay bindings.",
            "Recurring coverage requires explicit recurring_contracts with has_acceptance_source=true; scenario providers are not inferred.",
            "Unsupported-by-shared predicates may be supported by dedicated mission adapters.",
        ],
        "summary": summary,
        "quests": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_export", type=Path)
    parser.add_argument(
        "--publications", type=Path, help="Optional read-only publication snapshot JSON"
    )
    parser.add_argument("--include-achievements", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document, revision = load_export(args.native_export)
    snapshot = json.loads(args.publications.read_text()) if args.publications else None
    result = inspect(
        document,
        revision=revision,
        publications=snapshot,
        include_achievements=args.include_achievements,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
        compact = {
            key: value
            for key, value in result["summary"].items()
            if key != "categories"
        }
        print(json.dumps(compact, ensure_ascii=False, indent=2))
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
