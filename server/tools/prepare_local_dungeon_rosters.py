"""Write optional local roster drafts; never change evidence, DB, or services."""
import argparse
from collections import Counter
import json
from pathlib import Path

from wakfu_server.dungeon_local_roster_policy import draft
from wakfu_server.dungeon_legacy_catalog import policy_definition


def prepare(
    plans,
    index,
    native,
    *,
    capacity=121,
    generation_target=8,
    allow_local_defaults=False,
    legacy_entries=()
):
    links = {row["guide_slug"]: row for row in index["guide_links"]}
    legacy = {entry["slug"]: entry for entry in legacy_entries}
    results, excluded = [], []
    for plan in plans:
        link = links.get(plan["slug"])
        if (
            link is None
            or link["status"] != "exact_unique"
            or len(link["candidates"]) != 1
        ):
            if plan["slug"] not in legacy:
                excluded.append(
                    {
                        "slug": plan["slug"],
                        "reason": "unresolved_native_dungeon_identity",
                    }
                )
                continue
            definition = policy_definition(legacy[plan["slug"]])
        else:
            definition = link["candidates"][0]
        local_count = None
        if not plan.get("rooms") and allow_local_defaults:
            kind = definition.get("type", "")
            if kind == "ULTIMATE_BOSS":
                local_count = 1
            elif kind == "DUNGEON_3_PLAYERS":
                local_count = 3
        try:
            result = draft(
                plan,
                definition,
                native,
                capacity=capacity,
                generation_target=generation_target,
                room_count=local_count,
            )
        except ValueError as error:
            excluded.append({"slug": plan["slug"], "reason": str(error)})
            continue
        results.append(result)
    return {
        "schema_version": 1,
        "artifact_kind": "optional_local_roster_batch",
        "official": False,
        "runtime_imported": False,
        "runtime_ready": False,
        "policy_mode": "generated_native_species_policy",
        "summary": {
            "input_dungeons": len(plans),
            "drafts": len(results),
            "excluded": len(excluded),
            "generated_rooms": sum(
                room["policy_applied"] for row in results for room in row["rooms"]
            ),
            "room_count_sources": dict(
                Counter(row["room_count_source"] for row in results)
            ),
        },
        "drafts": results,
        "excluded": excluded,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--native-index", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capacity", type=int, default=121)
    parser.add_argument("--generation-target", type=int, default=8)
    parser.add_argument(
        "--legacy-registry",
        type=Path,
        help="Explicit validated local registry for maps without native aKU definitions.",
    )
    parser.add_argument(
        "--allow-local-default-room-count",
        action="store_true",
        help="Explicitly draft one room for ultimate bosses and three for three-player dungeons when guide rooms are absent.",
    )
    args = parser.parse_args()
    plans = json.loads(args.plans.read_text())["dungeons"]
    native = json.loads(args.native_monsters.read_text())["monsters"]
    index = json.loads(args.native_index.read_text())
    result = prepare(
        plans,
        index,
        native,
        capacity=args.capacity,
        generation_target=args.generation_target,
        allow_local_defaults=args.allow_local_default_room_count,
        legacy_entries=()
        if args.legacy_registry is None
        else json.loads(args.legacy_registry.read_text())["entries"],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
