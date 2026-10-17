"""Repeatable, read-only extraction and versioned local objective content seed.

Native identities and admission facts come from the published catalog. Reward
amounts, curated equipment choices and objective targets are explicit local
content policy, not claimed upstream quest definitions.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import hashlib
import json
import re
import zipfile
from pathlib import Path


VERSION = 1
EQUIPMENT_REFERENCES = (
    2021,
    2023,
    2024,
    2299,
    2307,
    2294,
    2865,
    4230,
    3608,
    4327,
    8257,
    8258,
    8259,
    6576,
    6579,
    12385,
    7573,
    7574,
    7576,
    17097,
    17121,
    17133,
    19038,
    19046,
    19047,
    19694,
    19701,
    19702,
    20722,
    20723,
    20724,
    10046,
    22595,
    22598,
    17096,
    17107,
)
BANDS = (
    (1, 5),
    (6, 20),
    (21, 40),
    (41, 60),
    (61, 80),
    (81, 100),
    (101, 120),
    (121, 140),
    (141, 160),
    (161, 180),
    (181, 185),
    (186, 199),
    (200, MAX_CHARACTER_LEVEL),
)
PREFIX = "content-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_snapshot(db):
    """Caller supplies a transaction; explicitly prohibit database mutations."""
    db.execute("SET TRANSACTION READ ONLY")
    revision = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()["revision"]
    hashes = {}

    def document(path):
        row = db.execute(
            "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()
        if row is None:
            raise ValueError("Missing native content source: " + path)
        raw = bytes(row["raw"])
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Native content source checksum mismatch")
        hashes[path] = row["sha256"]
        return json.loads(raw)

    source = {"revision": revision, "document_hashes": hashes}
    transports = document("native-transports.json")
    objects = document("native-transport-objects.json")
    cells = document("territory-map-cells.json")
    equipment = document("item-equipment-rules.json")["items"]
    stacks = document("item-stack-rules.json")["items"]
    sublimations = document("item-sublimations.json")["items"]
    # The indexed policy avoids decoding the 150 MB executable effect document.
    path = "native-npc-spell-effect-trees.json"
    row = db.execute(
        "SELECT payload FROM native_catalog_records WHERE revision=%s AND path=%s "
        "AND collection='activation_policy' AND record_key='enabled_monsters'",
        (revision, path),
    ).fetchone()
    if row is None or not isinstance(row["payload"], dict):
        raise ValueError("Missing indexed native NPC activation authority")
    hashes[path] = db.execute(
        "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
        (revision, path),
    ).fetchone()["sha256"]
    activation = row["payload"]
    names = db.execute(
        "SELECT value FROM settings WHERE name='admin_map_names'"
    ).fetchone()["value"]
    source["map_names_sha256"] = hashlib.sha256(canonical(names).encode()).hexdigest()
    dungeons = []
    for row in db.execute(
        "SELECT c.route_key,c.policy_version,c.configuration->'route' AS route,"
        "c.configuration->>'slug' AS slug,c.configuration->'compiled_plan' AS plan "
        "FROM dungeon_runtime_configurations c JOIN dungeon_runtime_active_configurations a "
        "USING(route_key,policy_version) ORDER BY c.route_key"
    ):
        plan = row["plan"]
        members = [
            member for room in plan["rooms"] for member in room.get("monsters", [])
        ]
        dungeons.append(
            {
                "route_key": row["route_key"],
                "policy_version": row["policy_version"],
                "route": row["route"],
                "slug": row["slug"],
                "room_count": len(plan["rooms"]),
                "roster_ready": plan.get("roster_ready"),
                "policy_mode": plan.get("policy_mode"),
                "members": members,
            }
        )
    source["dungeons_sha256"] = hashlib.sha256(canonical(dungeons).encode()).hexdigest()
    return dict(
        provenance=source,
        transports=transports,
        objects=objects,
        territories=cells,
        equipment=equipment,
        stacks=stacks,
        sublimations=sublimations,
        map_names=names,
        dungeons=dungeons,
        activation=activation,
    )


def _definition(
    key,
    title,
    description,
    kind,
    event,
    filters,
    target,
    policy,
    *,
    recurrence="once",
    minimum=1,
    maximum=MAX_CHARACTER_LEVEL,
):
    return dict(
        key=f"{PREFIX}.{key}",
        title=title,
        description=description,
        kind=kind,
        enabled=True,
        objectives=[dict(key="complete", event=event, filters=filters, target=target)],
        schedule=dict(type=recurrence, timezone="America/Bogota"),
        rewards=[dict(kind="scaled", policy_key=policy)],
        level_range=dict(minimum=minimum, maximum=maximum),
        prerequisite_keys=[],
    )


def _policies(equipment, sublimations):
    result = []
    for suffix, factor, gear, scroll in (
        ("exploration", 1, False, False),
        ("territory", 2, False, False),
        ("daily", 5, False, False),
        ("dungeon", 10, True, False),
        ("weekly", 25, True, True),
        ("ranking", 15, True, False),
    ):
        bands = []
        for minimum, maximum in BANDS:
            tier = (minimum - 1) // 20 + 1
            rewards = [
                dict(kind="kamas", amount=100 * tier * factor),
                {"aeV": 5, "ckl": [27083, 10 * max(1, tier * factor // 2)]},
                {"aeV": 5, "ckl": [27093, 10 * tier * factor]},
            ]
            if gear and minimum >= 6:
                eligible = [r for r in equipment if r["minimum_level"] <= minimum]
                nearest = max(r["minimum_level"] for r in eligible)
                pool = [
                    r["reference"]
                    for r in eligible
                    if r["minimum_level"] >= nearest - 10
                ]
                rewards.append(
                    dict(kind="random_item", references=sorted(pool), quantity=10)
                )
            if scroll and minimum >= 61:
                rewards.append(
                    dict(
                        kind="random_item", references=sorted(sublimations), quantity=10
                    )
                )
            bands.append(dict(minimum=minimum, maximum=maximum, rewards=rewards))
        key = "weekly-ranking-v1" if suffix == "ranking" else f"{PREFIX}.{suffix}"
        result.append(dict(key=key, policy=dict(bands=bands)))
    return result


# Names and references verified against the active native monsters document.
ASSIGNED_MONSTERS = (
    (1, "Jalató", 1, 20),
    (4, "Tofu", 1, 20),
    (5, "Tofona", 1, 20),
    (41, "Jalalínea", 1, 20),
    (87, "Pío rojo", 21, 40),
    (88, "Pío azul", 21, 40),
    (90, "Pío verde", 21, 40),
    (271, "Pío violeta", 21, 40),
    (94, "Diente de león diabólico", 41, 60),
    (1274, "Girasol explosivo", 41, 60),
    (5104, "Arakna peluda", 61, 80),
    (5111, "Milubo", 61, 80),
    (5113, "Minilubo", 61, 80),
    (1779, "Gran Bayotoro", 81, 100),
    (1828, "Ghulotony", 81, 100),
    (1825, "Murciego rechoncho", 81, 100),
    (2367, "Mimut rabioso", 101, 120),
    (3007, "Jyman", 101, 120),
    (3009, "Kiryuk", 101, 120),
    (4887, "Tronkónido oscuro", 121, 140),
    (4888, "Abráknido oscuro", 121, 140),
    (5468, "Puerroculto", 121, 140),
    (4779, "Blop tamborrudo", 141, 160),
    (5037, "Bulbambú", 141, 160),
    (4778, "Blop Dylan", 141, 160),
    (5035, "Bulbiflor", 141, 160),
    (3394, "Siclick", 161, 180),
    (3396, "Lapso", 161, 180),
    (4922, "Patapatas", 161, 180),
    (4203, "Rastrejón", 181, MAX_CHARACTER_LEVEL),
    (4204, "Tejardor", 181, MAX_CHARACTER_LEVEL),
    (4205, "Tejoso", 181, MAX_CHARACTER_LEVEL),
    (4208, "Dragoloso", 181, MAX_CHARACTER_LEVEL),
)


def assignment_templates(definitions, dungeon_metadata):
    result = []
    for reference, name, minimum, maximum in ASSIGNED_MONSTERS:
        for recurrence, quantity in (("daily", 10), ("weekly", 30)):
            rule = _definition(
                f"unused",
                f"{recurrence.title()} hunt: {name}",
                f"Defeat {quantity} {name}.",
                "daily" if recurrence == "daily" else "recurring",
                "original_monster_killed",
                {"references": [reference]},
                quantity,
                f"{PREFIX}.{recurrence}",
                recurrence=recurrence,
                minimum=minimum,
                maximum=maximum,
            )
            rule.update(
                key=f"assign-v1.{recurrence}.monster.{reference}", scope="account"
            )
            result.append(rule)
    metadata = {row["definition_id"]: row for row in dungeon_metadata}
    for source in definitions:
        if not source["key"].startswith("content-v1.dungeon."):
            continue
        native = metadata[source["objectives"][0]["filters"]["dungeon_id"]]
        if (
            native.get("native_criterion")
            or native["qualification_notes"]
            or native["minimum"] is None
            or native["minimum"] > MAX_CHARACTER_LEVEL
        ):
            continue
        rule = json.loads(canonical(source))
        rule["level_range"] = {
            "minimum": max(1, min(MAX_CHARACTER_LEVEL, native["minimum"])),
            "maximum": min(MAX_CHARACTER_LEVEL, native["maximum"] + 20),
        }
        name = source["title"].removeprefix("Dungeon: ")
        rule.update(
            key=source["key"].replace(
                "content-v1.dungeon.", "assign-v1.weekly.dungeon."
            ),
            title="Weekly: " + name,
            description="Complete " + name + ".",
            kind="recurring",
            scope="account",
            schedule={"type": "weekly", "timezone": "America/Bogota"},
            rewards=[{"kind": "scaled", "policy_key": "content-v1.weekly"}],
        )
        result.append(rule)
    return result


def build_catalog(snapshot, profiles):
    stacks = {r["reference"]: r for r in snapshot["stacks"]}
    equipment = {r["reference"]: r for r in snapshot["equipment"]}
    reviewed = []
    for reference in EQUIPMENT_REFERENCES:
        row = equipment.get(reference)
        if (
            row is None
            or row.get("has_conditions") is not False
            or not row.get("name")
            or not 1 <= row["minimum_level"] <= MAX_CHARACTER_LEVEL
            or reference not in stacks
            or stacks[reference]["maximum"] < 1
        ):
            raise ValueError(
                "Curated equipment lacks native reward authority: " + str(reference)
            )
        reviewed.append(row)
    sublimations = [
        r["reference"] for r in snapshot["sublimations"] if r["type"] == "BASIC"
    ]
    if len(sublimations) != 388 or any(ref not in stacks for ref in sublimations):
        raise ValueError("Incomplete basic sublimation reward pool")
    if any(ref not in stacks or stacks[ref]["maximum"] < 1 for ref in (27083, 27093)):
        raise ValueError("Missing native enchanting material authority")
    objects = {r["id"]: r for r in snapshot["objects"]}
    names = snapshot["map_names"]
    map_rows = {}
    arrivals = []
    for row in snapshot["transports"]:
        obj = objects.get(row["id"])
        if (
            obj is None
            or row["kind"] not in (1, 2)
            or row.get("condition")
            or len(obj.get("arrival_heights", [])) != 1
            or ("map_id" in row and obj["map_id"] != row["map_id"])
        ):
            continue
        map_id = obj["map_id"]
        name = names.get(str(map_id))
        if not isinstance(name, str) or not name.strip():
            continue
        entry = map_rows.setdefault(
            map_id, dict(map_id=map_id, name=name, transport_ids=[])
        )
        entry["transport_ids"].append(row["id"])
        arrivals.append((map_id, row["x"], row["y"], row["id"]))
    definitions = []
    for map_id, row in sorted(map_rows.items()):
        definitions.append(
            _definition(
                f"map.{map_id}",
                f"Explore: {row['name']}",
                f"Enter {row['name']} (map {map_id}) through a successful world transition. One-time discovery.",
                "achievement",
                "map_entered",
                {"map_id": map_id},
                1,
                f"{PREFIX}.exploration",
            )
        )
    # Regions are reviewed exact native bindings at admitted transport arrivals,
    # not every unknown geometry cell or a fuzzy match on a region's name.
    grid = {
        (m["map_id"], x, y): r["region_id"]
        for m in snapshot["territories"]["maps"]
        for r in m["regions"]
        for x, y in r["cells"]
    }
    zones = {}
    for map_id, x, y, transport_id in arrivals:
        region_id = grid.get((map_id, x // 18, y // 18))
        if region_id is None:
            continue
        zones.setdefault(
            (map_id, region_id),
            dict(
                map_id=map_id,
                region_id=region_id,
                map_name=map_rows[map_id]["name"],
                name=snapshot.get("territory_names", {}).get(str(region_id)),
                transport_id=transport_id,
                arrival=[x, y],
            ),
        )
    for (map_id, region_id), row in sorted(zones.items()):
        definitions.append(
            _definition(
                f"region.{map_id}.{region_id}",
                f"Territory: {row['name'] or row['map_name']} [{region_id}]",
                f"Enter native territory {region_id} on {row['map_name']} (map {map_id}). "
                "Credit requires the server's exact territory grid, not entering any other part of the map.",
                "achievement",
                "region_entered",
                {"map_id": map_id, "region_id": region_id},
                1,
                f"{PREFIX}.territory",
            )
        )
    admitted, warnings = [], []
    for row in snapshot["dungeons"]:
        members = row["members"]
        reasons = []
        if not members or row["roster_ready"] is not True:
            reasons.append("native_roster_not_ready")
        if members and any(
            not 1 <= m["native_min_level"] <= m["native_max_level"] <= 200
            for m in members
        ):
            reasons.append("native_roster_outside_positive_level_1_200")
        missing = sorted(
            {
                m["ref_id"]
                for m in members
                if str(m["ref_id"]) not in snapshot["activation"]
            }
        )
        if missing:
            reasons.append("roster_references_absent_from_normal_activation_policy")
        item = dict(
            route_key=row["route_key"],
            slug=row["slug"],
            definition_id=row["route"]["definition_id"],
            start_map_id=row["route"]["start_map_id"],
            native_criterion=row["route"].get("criterion", ""),
            room_count=row["room_count"],
            minimum=min((m["native_min_level"] for m in members), default=None),
            maximum=max((m["native_max_level"] for m in members), default=None),
            missing_monster_references=missing,
            qualification_notes=reasons,
        )
        if reasons:
            warnings.append(item)
        admitted.append(item)
        name = names.get(str(item["start_map_id"]), row["slug"])
        definitions.append(
            _definition(
                f"dungeon.{item['definition_id']}",
                f"Dungeon: {name}",
                f"Complete {name}. Native access, encounter and seasonal requirements remain in force; "
                "entering the map is not completion.",
                "achievement",
                "dungeon_completed",
                {"dungeon_id": item["definition_id"]},
                1,
                f"{PREFIX}.dungeon",
            )
        )
    for profile in profiles:
        minimum, maximum = profile["min_level"], profile["max_level"]
        if not 1 <= minimum <= maximum <= MAX_CHARACTER_LEVEL:
            raise ValueError("Challenge content profile exceeds supported player range")
        profile_key = profile["key"]
        references = sorted({member["ref_id"] for member in profile["roster"]})
        if not references or any(
            str(ref) not in snapshot["activation"] for ref in references
        ):
            raise ValueError("Challenge content lacks activated native monsters")
        bracket = f"{minimum:03d}-{maximum:03d}"
        definitions.append(
            _definition(
                f"daily.hunt.{bracket}",
                f"Daily hunt: levels {minimum}-{maximum}",
                "Defeat 10 original monsters from this bracket's reviewed native challenge roster. "
                "Summoned copies do not count.",
                "daily",
                "original_monster_killed",
                {"references": references},
                10,
                f"{PREFIX}.daily",
                recurrence="daily",
                minimum=minimum,
                maximum=maximum,
            )
        )
    definitions.append(
        _definition(
            "weekly.challenge",
            "Weekly private challenge",
            "Win this week's finite private challenge. Use !challenge weekly to enter. "
            "The strongest active hero selects the challenge bracket; rewards use the owner's source level. "
            "Reconnect resumes the same run. One reward per weekly period across all brackets.",
            "mission",
            "challenge_completed",
            {"won": True, "ranked": True},
            1,
            f"{PREFIX}.weekly",
            recurrence="weekly",
        )
    )
    definitions.append(
        _definition(
            "daily.pvp",
            "Daily PvP victory",
            "Win a completed duel against a different account. "
            "Same-account opponents and aborted fights do not qualify.",
            "pvp",
            "pvp_completed",
            {
                "won": True,
                "same_account": False,
                "reason": "defeat",
                "fight_kind": "duel",
            },
            1,
            f"{PREFIX}.daily",
            recurrence="daily",
        )
    )
    definitions.append(
        _definition(
            "pvp.first_victory",
            "First PvP victory",
            "Win a normal completed duel against a different account. Aborted fights do not qualify.",
            "pvp",
            "pvp_completed",
            {
                "won": True,
                "same_account": False,
                "reason": "defeat",
                "fight_kind": "duel",
            },
            1,
            f"{PREFIX}.daily",
        )
    )
    definitions.append(
        _definition(
            "pvp.weekly_victories",
            "Weekly PvP victories",
            "Win ten normal completed duels against different-account opponents this week. "
            "Aborted fights do not qualify.",
            "pvp",
            "pvp_completed",
            {
                "won": True,
                "same_account": False,
                "reason": "defeat",
                "fight_kind": "duel",
            },
            10,
            f"{PREFIX}.weekly",
            recurrence="weekly",
        )
    )
    definitions.append(
        _definition(
            "daily.pve_victories",
            "Daily PvE victories",
            "Win three completed PvE fights today. PvP and aborted fights do not count.",
            "daily",
            "combat_completed",
            {"won": True, "fight_kind": "pve"},
            3,
            f"{PREFIX}.daily",
            recurrence="daily",
        )
    )
    if admitted:
        definitions.append(
            _definition(
                "weekly.dungeons",
                "Weekly dungeon circuit",
                "Complete three qualifying dungeon boss encounters this week. Native access restrictions remain in force.",
                "recurring",
                "dungeon_completed",
                {"dungeon_id": sorted({r["definition_id"] for r in admitted})},
                3,
                f"{PREFIX}.weekly",
                recurrence="weekly",
            )
        )
    specific = assignment_templates(definitions, admitted)
    definitions = [
        d
        for d in definitions
        if not d["key"].startswith(("content-v1.daily.", "content-v1.pvp."))
        and d["key"]
        not in {
            "content-v1.weekly.challenge",
            "content-v1.weekly.dungeons",
            "content-v1.pvp.first_victory",
            "content-v1.pvp.weekly_victories",
        }
    ]
    definitions.extend(specific)
    keys = [d["key"] for d in definitions]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate native content objective identity")
    return dict(
        version=VERSION,
        provenance=snapshot["provenance"],
        policy_note="Local modest reward amounts and curated item pools. No legacy objectives or earned rewards replaced.",
        policies=_policies(reviewed, sublimations),
        definitions=definitions,
        inventory=dict(
            maps=list(map_rows.values()),
            special_zones=list(zones.values()),
            dungeons=admitted,
            dungeon_qualification_warnings=warnings,
            equipment=reviewed,
            basic_sublimation_references=sublimations,
            material_references=[27083, 27093],
            challenge_profiles=profiles,
            counts=dict(
                maps=len(map_rows),
                special_zones=len(zones),
                dungeons_admitted=len(admitted),
                dungeons_with_qualification_notes=len(warnings),
                definitions=len(definitions),
            ),
        ),
    )


def migration_sql(document):
    """Seed only new namespaced content; never rewrite legacy progress/rewards."""
    payload = canonical(document)
    if "$objective_content$" in payload:
        raise ValueError("Unsafe content SQL delimiter")
    return (
        "-- Generated by wakfu_server.objectives.content; no legacy objective replacements.\n"
        "CREATE TEMP TABLE objective_content_seed(document jsonb) ON COMMIT DROP;\n"
        "INSERT INTO objective_content_seed VALUES ($objective_content$"
        + payload
        + "$objective_content$::jsonb);\n"
        "INSERT INTO objectives_reward_policies(key,policy,revision)\n"
        "SELECT r->>'key',r->'policy',1 FROM objective_content_seed, "
        "LATERAL jsonb_array_elements(document->'policies') r ON CONFLICT(key) DO NOTHING;\n"
        "INSERT INTO objectives_definitions(key,definition,revision)\n"
        "SELECT r->>'key',r,1 FROM objective_content_seed, "
        "LATERAL jsonb_array_elements(document->'definitions') r ON CONFLICT(key) DO NOTHING;\n"
    )


def add_territory_names(snapshot, i18n_jar):
    """Read original region localization; never change the client archive."""
    with zipfile.ZipFile(i18n_jar) as archive:
        raw = archive.read("texts_en.properties")
    names = {}
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"content\.66\.(-?\d+)=(.*)", line)
        if match and match[2].strip():
            names[match[1]] = match[2].replace(r"\'", "'")
    snapshot["territory_names"] = names
    snapshot["provenance"]["territory_names"] = {
        "source": "original texts_en.properties, content.66.<region_id>",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return snapshot


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--i18n-jar", required=True, type=Path)
    parser.add_argument("--catalog-output", required=True, type=Path)
    parser.add_argument("--migration-output", required=True, type=Path)
    args = parser.parse_args()
    snapshot = add_territory_names(json.loads(args.snapshot.read_text()), args.i18n_jar)
    profiles = json.loads(args.profiles.read_text())
    document = build_catalog(snapshot, profiles)
    args.catalog_output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    )
    args.migration_output.write_text(migration_sql(document))
    print(canonical(document["inventory"]["counts"]))


if __name__ == "__main__":
    main()
