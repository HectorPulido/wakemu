"""Deterministic structural set cover over existing native whole-item graphs.

Feature presence is never execution or an expected outcome. Qualified features
are removed only by an explicit input ledger naming a receipt and its scope.
No gameplay imports, SQL, RNG, actual actors or full catalog loads are used.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def shape(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Non-numeric native parameter")
    if value in (-2, -1, 0, 1):
        return str(int(value))
    return ("positive" if value > 0 else "negative") + (
        "-integer" if int(value) == value else "-fractional"
    )


def effect_features(effect, retained):
    family = effect["effect_class"]
    result = {
        "family:" + str(family),
        "definition:"
        + canonical(
            [family, effect["native_definition_class"], effect["native_execution_mode"]]
        ),
        "level-window:"
        + canonical([family, effect["minimum_level"], effect["maximum_level"]]),
        "selector:"
        + canonical([family, effect["native_target_selector"], effect["area_native"]]),
        "timing:" + canonical([family, effect["native_timing_definition"]]),
        "probability:"
        + canonical(
            [family, effect["probability_base"], effect["probability_per_level"]]
        ),
    }
    raw = effect["parameters"]
    if len(raw) != effect["parameter_count"] * 2:
        raise ValueError("Malformed original parameter descriptor")
    pairs = [(raw[index], raw[index + 1]) for index in range(0, len(raw), 2)]
    result.add(
        "parameter-shape:"
        + canonical([family, [[shape(a), shape(b)] for a, b in pairs]])
    )
    # Preserve actual constant control operands separately from base amounts
    # and state/spell identities. These positions are the existing parsers'
    # coefficient/far modes, common group prefix, state chance and percent flag.
    controls = set()
    if family in (1, 24, 25, 26, 27, 1083, 1085):
        controls.update((1, 2))
    if family in (330, 844, 913, 999, 1020, 1047):
        controls.update(range(min(6, len(pairs))))
    if family == 304:
        controls.add(2)
    for index in controls:
        if index < len(pairs):
            result.add("parameter-control:" + canonical([family, index, *pairs[index]]))
    for flag in effect["native_effect_flags"]:
        result.add("flag:" + canonical([family, flag]))
    for mask_index, mask in enumerate(effect["target_masks"]):
        for event in mask or ():
            result.add("event-mask:" + canonical([mask_index, event]))
            result.add("event-family-mask:" + canonical([family, mask_index, event]))
    if any(effect["target_masks"]):
        fields = (
            "event_global_subscription",
            "event_reverse_subscription",
            "event_caster_code",
            "event_target_code",
            "owner_on_caster",
            "event_suppresses_level_one",
            "event_execution_count",
            "event_execution_count_per_level",
        )
        if any(key not in retained for key in fields):
            raise ValueError("Missing original retained subscription metadata")
        result.add(
            "subscription-mode:"
            + canonical([family, {key: retained[key] for key in fields}])
        )
    return result


def greedy_cover(candidates, target, *, anchors=()):
    selected, uncovered = [], set(target)
    by_reference = {row["reference"]: row for row in candidates}
    for reference in anchors:
        row = by_reference[reference]
        selected.append(row)
        uncovered.difference_update(row["_features"])
    while uncovered:
        possible = [
            row
            for row in candidates
            if row not in selected and row["_features"] & uncovered
        ]
        if not possible:
            break
        row = min(
            possible,
            key=lambda r: (
                -len(r["_features"] & uncovered),
                len(r["effect_ids"]),
                r["reference"],
            ),
        )
        selected.append(row)
        uncovered.difference_update(row["_features"])
    # Deterministic redundancy pruning improves the greedy upper bound; this
    # is not a proof of a globally minimum or executable scenario count.
    for row in tuple(reversed(selected)):
        if row["reference"] in anchors:
            continue
        others = set().union(*(r["_features"] for r in selected if r is not row))
        if target <= others:
            selected.remove(row)
    covered, result = set(), []
    for row in selected:
        new = (row["_features"] & target) - covered
        covered.update(row["_features"] & target)
        result.append(
            dict(
                reference=row["reference"],
                name=row["name"],
                kind=row["kind"],
                new_feature_count=len(new),
                new_feature_ids=sorted(new),
                all_feature_ids=sorted(row["_features"]),
                effect_ids=row["effect_ids"],
                state_ids=row["state_ids"],
                executed=False,
                expected_outcomes_invented=False,
            )
        )
    return dict(
        candidate_count=len(candidates),
        selected_count=len(result),
        target_feature_count=len(target),
        covered_feature_count=len(covered),
        structural_coverage_percent=100 * len(covered) / len(target) if target else 100,
        uncovered_feature_ids=sorted(target - covered),
        selected=result,
        minimum_guaranteed=False,
        execution_qualification_claimed=False,
    )


def plan(partition, closure, native_inventory, qualified, event_frontier=None):
    effect_index = native_inventory["effects"]
    features, candidates = defaultdict(set), []
    family_effects = defaultdict(set)
    for row in partition["rows"]:
        if row["classification"] != "relevant":
            continue
        selected = {"source-kind:" + row["kind"]}
        selected.update("criterion:" + name for name in row["criterion_functions"])
        for identity in row["effect_ids"]:
            effect = closure["effects"][str(identity)]
            retained = effect_index[str(identity)]["retained_metadata"]
            selected.update(effect_features(effect, retained))
            family_effects[effect["effect_class"]].add(identity)
        for identity in row["state_ids"]:
            state = closure["states"][str(identity)]
            keys = (
                "clock_actor",
                "duration_base",
                "duration_per_level",
                "realtime_duration_base",
                "realtime_duration_per_level",
                "maximum_level",
                "tick_at_turn_end",
                "additive",
                "replace",
                "refresh",
                "protected",
                "skip_turn_timer",
            )
            selected.add("state-policy:" + canonical({key: state[key] for key in keys}))
        candidate = dict(row, _features=selected)
        candidates.append(candidate)
        for feature in selected:
            features[feature].add(row["reference"])
    proof, qualified_ids = [], set()
    for entry in qualified.get("entries", ()):
        if (
            entry.get("status") != "qualified"
            or entry.get("feature_id") not in features
            or not isinstance(entry.get("evidence"), str)
            or not entry["evidence"]
            or not isinstance(entry.get("scope"), str)
            or not entry["scope"]
        ):
            raise ValueError(
                "Feature qualification needs an exact known feature, evidence and scope"
            )
        proof.append(entry)
        qualified_ids.add(entry["feature_id"])
    all_ids = set(features)
    categories = defaultdict(set)
    for feature in features:
        categories[feature.split(":", 1)[0]].add(feature)
    category_rows = []
    for category, values in sorted(categories.items()):
        amount = len(values & qualified_ids)
        category_rows.append(
            dict(
                category=category,
                total_features=len(values),
                evidence_mapped_qualified_features=amount,
                not_yet_mapped_to_input_evidence=len(values) - amount,
                qualification_percent=100 * amount / len(values) if proof else None,
            )
        )
    existing = [27152] if 27152 in {r["reference"] for r in candidates} else []

    def category_cover(names):
        return greedy_cover(
            candidates,
            set().union(*(value for key, value in categories.items() if key in names)),
        )

    result = dict(
        schema=1,
        purpose="structural candidate witness planning only",
        relevant_references=len(candidates),
        source_features=len(features),
        semantic_execution_percent=None,
        qualified_feature_evidence=proof,
        qualified_input_absent=not bool(proof),
        categories=category_rows,
        feature_index=[
            dict(
                feature_id=key,
                category=key.split(":", 1)[0],
                reference_count=len(value),
                references=sorted(value),
            )
            for key, value in sorted(features.items())
        ],
        per_reference=[
            dict(
                reference=row["reference"],
                name=row["name"],
                kind=row["kind"],
                feature_ids=sorted(row["_features"]),
            )
            for row in candidates
        ],
        full_structural_cover=greedy_cover(candidates, all_ids),
        continuation_after_explicit_qualified_features=greedy_cover(
            candidates, all_ids - qualified_ids
        ),
        existing_ready_anchor_cover=greedy_cover(candidates, all_ids, anchors=existing),
        family_only_cover=category_cover(("family",)),
        core_dimensions_cover=category_cover(
            ("family", "event-mask", "criterion", "source-kind")
        ),
        parameter_domain_cover=category_cover(("parameter-shape", "parameter-control")),
        event_mask_frontier_cover=category_cover(
            ("event-mask", "event-family-mask", "subscription-mode")
        ),
        limits=[
            "A selected source contains features; its Ready does not prove every branch executed.",
            "Use actual native triggers, payments, eligibility, RNG and retention, not inserted state/stat setup.",
            "No damage/heal amount or other expected outcome is calculated or invented.",
            "Unmapped evidence is not proof of a missing handler; join existing family contracts before adding tests.",
            "Feature coverage does not prove parameter equivalence outside recorded shapes/control operands.",
            "Selected whole-item candidates are not a legal simultaneous equipment layout or separate required fights.",
        ],
    )
    if event_frontier is not None:
        target, missing = set(), []
        for group in event_frontier["current_static_event_frontier"]["groups"]:
            for mask in group["mask_indices"]:
                key = "event-mask:" + canonical([mask, group["event"]])
                if key in all_ids:
                    target.add(key)
                else:
                    missing.append(key)
        result["known_event_dependency_cover"] = greedy_cover(candidates, target)
        result["known_event_dependency_cover"]["missing_source_feature_ids"] = sorted(
            set(missing)
        )
        result["known_event_dependency_cover"][
            "source_frontier_ref_count"
        ] = event_frontier["current_static_event_frontier"]["total_unique_scrolls"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", type=Path, required=True)
    parser.add_argument("--closure", type=Path, required=True)
    parser.add_argument("--native-inventory", type=Path, required=True)
    parser.add_argument("--qualified-features", type=Path)
    parser.add_argument("--event-frontier", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {
        key: getattr(args, key) for key in ("partition", "closure", "native_inventory")
    }
    documents = {key: json.loads(path.read_text()) for key, path in paths.items()}
    qualified = (
        json.loads(args.qualified_features.read_text())
        if args.qualified_features
        else {}
    )
    frontier = (
        json.loads(args.event_frontier.read_text()) if args.event_frontier else None
    )
    result = plan(
        documents["partition"],
        documents["closure"],
        documents["native_inventory"],
        qualified,
        frontier,
    )
    result["source_sha256"] = {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in paths.items()
    }
    result["source_sha256"]["planner"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    if args.event_frontier:
        result["source_sha256"]["event_frontier"] = hashlib.sha256(
            args.event_frontier.read_bytes()
        ).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                relevant_references=result["relevant_references"],
                feature_count=result["source_features"],
                candidates=result["full_structural_cover"]["selected_count"],
                existing_anchor_candidates=result["existing_ready_anchor_cover"][
                    "selected_count"
                ],
                event_candidates=result["event_mask_frontier_cover"]["selected_count"],
                categories=result["categories"],
            )
        )
    )


if __name__ == "__main__":
    main()
