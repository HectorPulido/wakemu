"""Compile reviewed room evidence into immutable, non-executable import plans.

Native reference resolution belongs to the catalog mapper. This module never
fuzzily matches names, selects monster grades, or invents spawn coordinates.
"""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class MonsterRoster:
    name: str
    ref_id: int | None
    count: int | None
    role: str
    native_min_level: int | None
    native_max_level: int | None
    guide_min_level: int | None
    guide_max_level: int | None


@dataclass(frozen=True)
class RoomPlan:
    order: int
    monsters: tuple[MonsterRoster, ...]
    diagnostics: tuple[str, ...]

    @property
    def roster_ready(self):
        return not self.diagnostics


@dataclass(frozen=True)
class DungeonPlan:
    slug: str
    source_url: str
    source_sha256: str
    document_sha256: str
    definition_id: int | None
    template_id: int | None
    asset_map_id: int | None
    rooms: tuple[RoomPlan, ...]
    diagnostics: tuple[str, ...]

    @property
    def roster_ready(self):
        return (
            bool(self.rooms)
            and not self.diagnostics
            and all(r.roster_ready for r in self.rooms)
        )

    def import_record(self):
        result = asdict(self)
        result["roster_ready"] = self.roster_ready
        result["runtime_ready"] = False
        result["runtime_prerequisites"] = [
            "native_asset_instance_transport",
            "encounter_spawn_policy",
            "room_gate_policy",
            "victory_progression_handoff",
        ]
        return result


def _optional_positive(value, field):
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"Invalid {field}")
    return value


def compile_document(document, native_monsters):
    """Compile a schema-validated document against authoritative native refs.

    Unknown data is retained in drafts, while malformed or conflicting explicit
    identities fail closed. Native level ranges suffice for roster readiness;
    actual encounter grade selection remains a separate runtime policy.
    """
    if document.get("schema_version") != 1:
        raise ValueError("Unsupported composition schema")
    catalog = {}
    for native in native_monsters:
        ref = _optional_positive(native.get("ref"), "native ref")
        if ref is None or ref in catalog:
            raise ValueError("Missing or duplicate native reference")
        low = _optional_positive(
            None
            if type(native.get("min_level")) is int and native["min_level"] == 0
            else native.get("min_level"),
            "native minimum level",
        )
        high = _optional_positive(
            None
            if type(native.get("max_level")) is int and native["max_level"] == 0
            else native.get("max_level"),
            "native maximum level",
        )
        if low is not None and high is not None and high < low:
            raise ValueError("Invalid native level range")
        catalog[ref] = (low, high)
    diagnostics = []
    if document["extraction"]["reviewed"] is not True:
        diagnostics.append("unreviewed_extraction")
    if document["source"]["client_version_match"] == "mismatch":
        diagnostics.append("client_version_mismatch")
    rooms = []
    orders = set()
    for room in document["rooms"]:
        order = _optional_positive(room["order"], "room order")
        if order is None or order in orders:
            raise ValueError("Missing or duplicate room order")
        orders.add(order)
        missing = []
        if room["composition_status"] != "complete":
            missing.append("incomplete_composition")
        roster = []
        for index, monster in enumerate(room["monsters"]):
            ref = _optional_positive(monster["ref_id"], "monster ref")
            count = _optional_positive(monster["count"], "monster count")
            low = _optional_positive(monster["min_level"], "guide minimum level")
            high = _optional_positive(monster["max_level"], "guide maximum level")
            if low is not None and high is not None and high < low:
                raise ValueError("Invalid guide level range")
            native_low, native_high = catalog.get(ref, (None, None))
            if ref is None:
                missing.append(f"monster[{index}].unresolved_reference")
            elif ref not in catalog:
                missing.append(f"monster[{index}].absent_native_reference")
            if count is None:
                missing.append(f"monster[{index}].unknown_count")
            if native_low is None or native_high is None:
                missing.append(f"monster[{index}].missing_native_level_range")
            if monster["role"] not in ("monster", "boss", "unknown"):
                raise ValueError("Invalid monster role")
            roster.append(
                MonsterRoster(
                    monster["name"],
                    ref,
                    count,
                    monster["role"],
                    native_low,
                    native_high,
                    low,
                    high,
                )
            )
        if not roster:
            missing.append("empty_roster")
        rooms.append(RoomPlan(order, tuple(roster), tuple(missing)))
    if orders and orders != set(range(1, max(orders) + 1)):
        diagnostics.append("non_contiguous_room_order")
    dungeon = document["dungeon"]
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return DungeonPlan(
        dungeon["slug"],
        document["source"]["url"],
        document["source"]["article_sha256"],
        digest,
        _optional_positive(dungeon["client_definition_id"], "definition"),
        _optional_positive(dungeon["client_template_id"], "template"),
        _optional_positive(dungeon["client_asset_map_id"], "asset map"),
        tuple(sorted(rooms, key=lambda r: r.order)),
        tuple(diagnostics),
    )


def compile_catalog(documents, native_monsters):
    native_monsters = tuple(native_monsters)
    plans = tuple(compile_document(document, native_monsters) for document in documents)
    if len({plan.slug for plan in plans}) != len(plans):
        raise ValueError("Duplicate dungeon slug")
    return tuple(sorted(plans, key=lambda plan: plan.slug))


def write_import_plan(path, plans):
    """Persist a draft catalog atomically; this does not activate encounters."""
    from pathlib import Path

    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"schema_version": 1, "dungeons": [plan.import_record() for plan in plans]},
            indent=2,
        )
        + "\n",
        encoding="utf8",
    )
    temporary.replace(path)


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compositions", required=True, type=Path)
    parser.add_argument("--native-monsters", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    compositions = json.loads(args.compositions.read_text(encoding="utf8"))
    native = json.loads(args.native_monsters.read_text(encoding="utf8"))
    plans = compile_catalog(compositions["dungeons"], native["monsters"])
    write_import_plan(args.output, plans)
    print(
        json.dumps(
            {
                "dungeons": len(plans),
                "rooms": sum(len(p.rooms) for p in plans),
                "roster_ready": sum(p.roster_ready for p in plans),
                "runtime_imported": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
