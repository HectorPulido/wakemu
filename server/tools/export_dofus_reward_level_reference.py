#!/usr/bin/env python3
"""Export a transparent, per-level Dofus reference fallback for Wakemu.

This reads the Starloco SQL seed and its ordered monster updates. It does not
execute SQL or touch the Dofus checkout. The resulting medians are a local
fallback policy, not a claim that Dofus has one universal reward per level.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path


MAX_LEVEL = 200
SEED_PATH = Path("db-init/04-game.sql")
UPDATE_GLOB = "db-init/*update_game*.sql"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _insert_values(line: str) -> list[str] | None:
    prefix = "INSERT INTO `monsters` VALUES ("
    if not line.startswith(prefix):
        return None
    payload = line[len(prefix) :].rsplit(");", 1)[0]
    return next(
        csv.reader(
            [payload],
            delimiter=",",
            quotechar="'",
            escapechar="\\",
            skipinitialspace=True,
        )
    )


def _field_assignment(statement: str, name: str) -> str | None:
    # Reward fields and id are scalar numbers or numeric pipe-delimited strings.
    match = re.search(
        r"(?<![\w])`?"
        + re.escape(name)
        + r"`?(?![\w])\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(-?\d+))",
        statement,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return next(value for value in match.groups() if value is not None)


def _where_id(statement: str) -> int | None:
    match = re.search(
        r"\bWHERE\s*\(?\s*`?id`?\s*=\s*['\"]?(\d+)",
        statement,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def load_monsters(
    dofus_root: Path,
) -> tuple[dict[int, dict], list[Path], dict[str, int]]:
    """Load base rows, then apply only reward-relevant monster SQL updates."""
    seed = dofus_root / SEED_PATH
    if not seed.is_file():
        raise FileNotFoundError(seed)
    rows: dict[int, dict] = {}
    for line in seed.read_text(encoding="utf-8", errors="replace").splitlines():
        values = _insert_values(line)
        if values is None or len(values) < 21:
            continue
        try:
            identity = int(values[0])
            rows[identity] = {
                "id": identity,
                "name": values[1].strip(),
                "grades": values[4],
                "min_kamas": int(values[12]),
                "max_kamas": int(values[13]),
                "exps": values[14],
                "monster_type": int(values[17]),
                "is_boss": int(values[19]),
                "is_archmonster": int(values[20]),
            }
        except (ValueError, IndexError):
            continue

    update_paths = sorted((dofus_root).glob(UPDATE_GLOB))
    update_counts = {path.name: 0 for path in update_paths}
    for path in update_paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not re.match(r"\s*UPDATE\s+`?monsters`?\s+SET\b", line, re.IGNORECASE):
                continue
            old_id = _where_id(line)
            if old_id is None or old_id not in rows:
                continue
            set_clause = re.split(r"\bWHERE\b", line, maxsplit=1, flags=re.IGNORECASE)[
                0
            ]
            row = rows[old_id]
            for field, key, converter in (
                ("minKamas", "min_kamas", int),
                ("maxKamas", "max_kamas", int),
                ("exps", "exps", str),
                ("grades", "grades", str),
                ("type", "monster_type", int),
                ("isBoss", "is_boss", int),
                ("isArchmonster", "is_archmonster", int),
            ):
                value = _field_assignment(set_clause, field)
                if value is not None:
                    row[key] = converter(value)
            new_id = _field_assignment(set_clause, "id")
            if new_id is not None:
                new_id = int(new_id)
                row["id"] = new_id
                if new_id != old_id:
                    rows[new_id] = row
                    del rows[old_id]
            update_counts[path.name] += 1
    return rows, update_paths, update_counts


def build_reference(rows: dict[int, dict]) -> dict:
    by_level: dict[int, list[tuple[int, int, int]]] = {
        level: [] for level in range(1, MAX_LEVEL + 1)
    }
    excluded = {
        "wrong_type": 0,
        "boss_or_archmonster": 0,
        "invocation": 0,
        "invalid_grade_data": 0,
        "zero_xp_or_out_of_range": 0,
    }
    for row in rows.values():
        if row["monster_type"] != 1:
            excluded["wrong_type"] += 1
            continue
        if row["is_boss"] or row["is_archmonster"]:
            excluded["boss_or_archmonster"] += 1
            continue
        if "invoc" in row["name"].casefold():
            excluded["invocation"] += 1
            continue
        try:
            grade_levels = [
                int(entry.split("@", 1)[0]) for entry in row["grades"].split("|")
            ]
            grade_xp = [int(value) for value in row["exps"].split("|")]
        except (ValueError, IndexError):
            excluded["invalid_grade_data"] += 1
            continue
        for level, base_xp in zip(grade_levels, grade_xp):
            if not 1 <= level <= MAX_LEVEL or base_xp <= 0:
                excluded["zero_xp_or_out_of_range"] += 1
                continue
            by_level[level].append((base_xp, row["min_kamas"], row["max_kamas"]))

    def floor_median(values: list[int]) -> int:
        # Dofus records are integers; floor the median if an even sample gives .5.
        return int(statistics.median(values))

    observed: list[dict] = []
    for level, samples in by_level.items():
        if not samples:
            continue
        observed.append(
            {
                "level": level,
                "monster_grade_count": len(samples),
                "base_xp_median": floor_median([sample[0] for sample in samples]),
                "min_kamas_median": floor_median([sample[1] for sample in samples]),
                "max_kamas_median": floor_median([sample[2] for sample in samples]),
            }
        )

    if not observed or observed[0]["level"] != 1:
        raise ValueError("Dofus source has no level-1 fallback baseline")
    observed_by_level = {row["level"]: row for row in observed}
    defaults: list[dict] = []
    source_level = 1
    for level in range(1, MAX_LEVEL + 1):
        source = observed_by_level.get(level)
        if source is not None:
            source_level = level
        else:
            source = observed_by_level[source_level]
        defaults.append(
            {
                "level": level,
                "source_level": source_level,
                "monster_grade_count": source["monster_grade_count"],
                "base_xp": source["base_xp_median"],
                "min_kamas": source["min_kamas_median"],
                "max_kamas": source["max_kamas_median"],
                "fallback": "observed_level_median"
                if level == source_level
                else "nearest_lower_observed_level",
            }
        )
    return {
        "observed_levels": observed,
        "defaults_by_level": defaults,
        "coverage": {
            "target_levels": MAX_LEVEL,
            "observed_source_levels": len(observed),
            "filled_levels": len(defaults),
            "levels_using_nearest_lower_fallback": sum(
                row["fallback"] != "observed_level_median" for row in defaults
            ),
            "excluded_source_rows": excluded,
        },
    }


def export(dofus_root: Path, output: Path) -> dict:
    rows, updates, update_counts = load_monsters(dofus_root)
    result = build_reference(rows)
    source_paths = [dofus_root / SEED_PATH, *updates]
    result.update(
        {
            "schema_version": 1,
            "source": "Starloco Dofus SQL monster table; local fallback aggregation for Wakemu",
            "policy": {
                "meaning": "Derived emulator fallback, not an official or universal per-level reward formula.",
                "input_rows": "Final monsters table after seed and ordered db-init update_game files.",
                "include": "monster_type=1; not boss or archmonster; name does not contain 'invoc'; grade XP > 0; grade level 1..200.",
                "aggregation": "floor(integer median) independently for base XP, min kamas and max kamas among eligible monster-grade rows at each source level.",
                "holes": "For an unobserved level, carry the nearest lower observed level; expose source_level so this is auditable.",
                "wakemu_mapping": "No Dofus monster IDs are mapped to Wakfu references. Apply these values only as a level fallback, overridden by explicit Wakemu reference+level policy rows.",
            },
            "source_files": [
                {
                    "path": str(path.relative_to(dofus_root)),
                    "sha256": sha256(path),
                    "applied_monster_updates": update_counts.get(path.name, 0),
                }
                for path in source_paths
            ],
            "exporter": {
                "path": "server/tools/export_dofus_reward_level_reference.py",
                "sha256": sha256(Path(__file__).resolve()),
            },
            "source_monster_rows": len(rows),
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dofus-root",
        type=Path,
        required=True,
        help="Read-only Starloco checkout containing db-init/04-game.sql",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("server/protocol/dofus-reward-level-reference.json"),
    )
    args = parser.parse_args()
    result = export(args.dofus_root, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source_monster_rows": result["source_monster_rows"],
                **result["coverage"],
                "source_hashes": {
                    source["path"]: source["sha256"]
                    for source in result["source_files"]
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
