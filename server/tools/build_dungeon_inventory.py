"""Build an evidence inventory without changing runtime configuration or services."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile


def build(source, output):
    inputs = {}

    def read(name):
        path = source / name
        raw = path.read_bytes()
        inputs[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    index = read("native-dungeon-index-refined.json")
    catalog = read("composition-catalog.json")
    configurations = read("local-policy-configs-all87/configurations.json")[
        "configurations"
    ]
    routes = read("native-bulk-entry-routes.json")
    actors = {x["map_id"]: x for x in read("native-dungeon-environment-actors.json")}
    live_manifest = read("inventory-native-snapshot/manifest.json")
    native_objects = read("inventory-native-snapshot/native-map-objects.json")
    native_transports = read(
        "inventory-native-snapshot/native-generic-teleporters.json"
    )
    monsters = {
        m["ref"]: m for m in read("inventory-native-snapshot/monsters.json")["monsters"]
    }
    locale_file = Path("client/contents/i18n/i18n_es.jar")
    names_es = {}
    if locale_file.exists():
        inputs[str(locale_file)] = hashlib.sha256(locale_file.read_bytes()).hexdigest()
        with zipfile.ZipFile(locale_file) as archive:
            for line in (
                archive.read("texts_es.properties").decode("utf-8").splitlines()
            ):
                match = re.match(r"^content\.137\.(\d+)=(.*)$", line)
                if match:
                    names_es[int(match[1])] = re.sub(
                        r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), match[2]
                    )
    guide_by_slug = {x["dungeon"]["slug"]: x for x in catalog["dungeons"]}
    config_by_slug = {x["slug"]: x for x in configurations}
    native = {x["id"]: x for x in index["native_dungeons"]}
    rows = {
        f"native:{key}": {
            "key": f"native:{key}",
            "native": value,
            "guides": [],
            "configurations": [],
        }
        for key, value in native.items()
    }
    for link in index["guide_links"]:
        slug = link["guide_slug"]
        config = config_by_slug.get(slug)
        identifier = link.get("client_definition_id")
        if identifier not in native and config:
            identifier = config["route"].get(
                "native_definition_id", config["route"].get("definition_id")
            )
        key = f"native:{identifier}" if identifier in native else f"legacy-guide:{slug}"
        row = rows.setdefault(
            key, {"key": key, "native": None, "guides": [], "configurations": []}
        )
        guide = guide_by_slug[slug]
        source_data = guide["source"]
        article_path = Path(source_data["archive_directory"]) / "article.txt"
        text = article_path.read_text() if article_path.exists() else ""
        lines = text.splitlines()
        evidence = []
        pattern = re.compile(
            r"qu[eê]te|acc[eè]s|porte|t[eé]l[eé]port|coffre|secret|levier|interrupteur|puzzle|r[eé]colt|ressource|achievement|condition",
            re.I,
        )
        for number, line in enumerate(lines, 1):
            if pattern.search(line):
                evidence.append(
                    {
                        "line": number,
                        "text": line[:900],
                        "review_status": "candidate_excerpt_requires_context",
                    }
                )
        row["guides"].append(
            {
                "slug": slug,
                "name": guide["dungeon"]["name"],
                "identity_status": link["status"],
                "source": source_data,
                "extraction": guide["extraction"],
                "rooms": guide["rooms"],
                "entry_and_extras_candidate_evidence": evidence,
            }
        )
        if config:
            topology = config["topology"]
            row["configurations"].append(
                {
                    "slug": slug,
                    "version": config["version"],
                    "route": config["route"],
                    "plan_policy": config["compiled_plan"].get("policy_mode"),
                    "official": config["compiled_plan"].get("official"),
                    "roster_ready": config["compiled_plan"].get("roster_ready"),
                    "rooms": config["compiled_plan"]["rooms"],
                    "topology": {
                        key: value for key, value in topology.items() if key != "rooms"
                    },
                    "anchors": [
                        {"order": x["order"], "anchor": x.get("anchor")}
                        for x in topology["rooms"]
                    ],
                }
            )
    for row in rows.values():
        definition = row["native"]
        row["name_es"] = names_es.get(definition["id"]) if definition else None
        row["native_species_pool"] = (
            [
                {
                    "ref_id": ref,
                    "name_es": monsters.get(ref, {}).get("name"),
                    "min_level": monsters.get(ref, {}).get("min_level"),
                    "max_level": monsters.get(ref, {}).get("max_level"),
                }
                for ref in definition.get("raw_cno", [])
            ]
            if definition
            else []
        )
        maps = (
            definition.get("raw_aHA", [])
            if definition
            else [c["route"]["start_map_id"] for c in row["configurations"]]
        )
        row["native_entry_routes"] = [
            x for x in routes if definition and x["definition_id"] == definition["id"]
        ]
        row["environment_actor_evidence"] = [
            {
                "map_id": m,
                "coverage": "exported" if m in actors else "unknown",
                "actor_count": len(actors.get(m, {}).get("actors", [])),
                "scripts": dict(
                    Counter(a["script"] for a in actors.get(m, {}).get("actors", []))
                ),
            }
            for m in maps
        ]
        map_set = set(maps)
        row["native_objects"] = [
            {k: o[k] for k in ("map_id", "id", "type", "x", "y", "z")}
            for o in native_objects
            if o["map_id"] in map_set
        ]
        row["native_object_type_counts"] = dict(
            Counter(o["type"] for o in row["native_objects"])
        )
        row["native_internal_teleports"] = [
            {
                "source_map": t["map_id"],
                "source_object": t["id"],
                "destinations": [
                    d for d in t["destinations"] if d["map_id"] in map_set
                ],
            }
            for t in native_transports
            if t["map_id"] in map_set
            and any(d["map_id"] in map_set for d in t["destinations"])
        ]
        row["native_exits"] = [
            {
                "source_map": t["map_id"],
                "source_object": t["id"],
                "destinations": [
                    d for d in t["destinations"] if d["map_id"] not in map_set
                ],
            }
            for t in native_transports
            if t["map_id"] in map_set
            and any(d["map_id"] not in map_set for d in t["destinations"])
        ]
        row["unknowns"] = [
            "Official internal gate/teleport sequence and runtime collision validation",
            "Exhaustive noncombat interactions, secrets, resources and quest NPCs",
            "Live full-run acceptance except separately recorded Jalato acceptance",
        ]
        if not row["guides"]:
            row["unknowns"].append(
                "Reviewed per-room monster composition and guide evidence"
            )
        if not row["native_entry_routes"] and definition:
            row["unknowns"].append(
                "Native entrance route not resolved in exported bulk routes"
            )
    ordered = sorted(
        rows.values(),
        key=lambda r: (r["native"] or {})
        .get("name_fr", r["guides"][0]["slug"] if r["guides"] else "")
        .casefold(),
    )
    summary = {
        "native_definitions": len(native),
        "guide_records": len(index["guide_links"]),
        "union_records": len(rows),
        "native_with_guide": sum(bool(r["native"] and r["guides"]) for r in ordered),
        "native_without_guide": sum(
            bool(r["native"] and not r["guides"]) for r in ordered
        ),
        "legacy_guide_records": sum(r["native"] is None for r in ordered),
        "native_entry_routes": len(routes),
        "configuration_records": len(configurations),
        "actual_identity_status_counts": dict(
            Counter(x["status"] for x in index["guide_links"])
        ),
        "guide_composition_status_counts": dict(
            Counter(x["extraction"]["status"] for x in catalog["dungeons"])
        ),
        "guide_rooms": sum(len(x["rooms"]) for x in catalog["dungeons"]),
        "configured_rooms": sum(
            len(x["compiled_plan"]["rooms"]) for x in configurations
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "Local native client catalog union archived guides; not a current-live-game completeness assertion",
                "summary": summary,
                "source_sha256": inputs,
                "live_catalog_release": live_manifest["release"],
                "records": ordered,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    def clean(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", "")

    lines = [
        "# Dungeon evidence inventory",
        "",
        "Generated from private local catalog exports and archived guides. Runtime services and databases are not changed. This is a client-version inventory, not proof that every current live-game dungeon is supported.",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "## Reading the evidence",
        "",
        "Native monster references describe a species pool, not room composition. Guide composition may belong to another game version. Generated configurations are local approximations; their room order and automatic travel do not establish official gates or teleporters. Native criterion text is evidence, not proof that the server implements its authority. An empty criterion means no criterion on that exported entry, not absence of all quest requirements.",
        "",
        "Environment actor counts include decorative scripts; they do not prove gameplay extras are implemented. Keyword excerpts in inventory.json are research leads, not confirmed quests or secrets. Unknown is deliberate.",
        "",
        "Native objects and teleport destinations were read from the active PostgreSQL catalog in a READ ONLY transaction. The release and document hashes are recorded in JSON; exported native dungeon definitions and archived guides retain their separate hashes. Doors/teleport objects are confirmed native asset evidence, not proof of correct server handling or progression order. JSON is the complete per-room/per-monster matrix; this Markdown provides one row per union entry.",
        "",
        "## Confirmed structural evidence",
        "",
        "Tofullero (native 27): three Door objects, two Teleporter objects and no same-dungeon teleport destination. Jalato / Pâturages des Bouftous (native 90): no Door objects, six Teleporter objects and four internal teleport sources. These support the reported difference between physical doors and room travel. Door opening authority and traversal remain unaccepted.",
        "",
        "Native assets also contain LootChest, Stele, Collector, CraftTable and trigger objects; presence does not establish rewards, secrets or quests are implemented. The per-entry object IDs and exact interior teleport destination criteria are in JSON.",
        "",
        "Ultimate bosses require separate correction: [Ultimate boss audit](ULTIMATE-BOSS-AUDIT-20261009.md) confirms 10 of 11 live configured bosses have duplicate-boss rosters; four native ultimate-boss definitions have no installed configuration. Ombrage has the correct single-boss count only, which does not certify fight mechanics.",
        "",
        "## All entries",
        "",
        "| Native ID / name | Type / native level | Maps / species pool | Guide rooms / composition | Local config / transition | Entry requirements | Interior extras / gaps |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in ordered:
        n = row["native"] or {}
        guides = row["guides"]
        configs = row["configurations"]
        label = f"{n.get('id', 'legacy')} / {row.get('name_es') or n.get('name_fr', guides[0]['slug'] if guides else '')}"
        guide_desc = (
            "; ".join(
                f"[{g['slug']}]({g['source']['url']}): {len(g['rooms'])} rooms / {g['extraction']['status']} / version {g['source'].get('game_version', 'unknown')}"
                for g in guides
            )
            or "No reviewed guide"
        )
        config_desc = (
            "; ".join(
                f"{c['slug']}: {len(c['rooms'])} rooms; {c['plan_policy']}; order verified={c['topology'].get('official_room_order_verified')}; auto edges={len(c['topology'].get('auto_edges', []))}; doors={len(c['topology'].get('doors', []))}"
                for c in configs
            )
            or "No generated configuration"
        )
        entry_routes = row["native_entry_routes"] or [c["route"] for c in configs]
        criterion = (
            "; ".join(
                x.get("criterion") or "(empty exported criterion)" for x in entry_routes
            )
            or "Unknown entrance"
        )
        extras = (
            "Native objects: "
            + str(row["native_object_type_counts"])
            + "; internal teleport sources="
            + str(len(row["native_internal_teleports"]))
            + "; "
            + "; ".join(
                f"map {a['map_id']}: {a['coverage']}, {a['actor_count']} environment actors {a['scripts']}"
                for a in row["environment_actor_evidence"]
            )
            + "; gameplay extras and official gate/teleport sequence unknown"
        )
        values = [
            label,
            f"{n.get('type', 'legacy / unclassified')} / {n.get('raw_aWb', 'unknown')}",
            f"{n.get('raw_aHA', 'see JSON')} / refs {n.get('raw_cno', 'unknown')}",
            guide_desc,
            config_desc,
            criterion,
            extras,
        ]
        lines.append("| " + " | ".join(clean(v) for v in values) + " |")
    detail = [
        "# Per-dungeon evidence",
        "",
        "Native Spanish names retain French aliases. Read [inventory scope and limitations](INVENTORY.md). Reference pools are not encounter rosters. Official order, collision and quest authority need verification; native object presence is independently proven.",
        "",
    ]
    for row in ordered:
        n = row["native"] or {}
        title = row.get("name_es") or n.get("name_fr") or row["guides"][0]["slug"]
        detail.extend(
            [
                f"## {title} ({row['key']})",
                "",
                f"French alias: {n.get('name_fr', 'unmapped legacy guide')}. Type: {n.get('type', 'legacy')}. Native level: {n.get('raw_aWb', 'unknown')}. Maps: {n.get('raw_aHA', 'see configured entry')}.",
                "",
                "Species pool: "
                + (
                    ", ".join(
                        f"{m['name_es'] or 'unknown'} [{m['ref_id']}] level {m['min_level']}-{m['max_level']}"
                        for m in row["native_species_pool"]
                    )
                    or "Unknown native pool"
                ),
                "",
                "### Guide composition",
                "",
            ]
        )
        for g in row["guides"]:
            detail.extend(
                [
                    f"[{g['slug']}]({g['source']['url']}); extraction={g['extraction']['status']}; version={g['source'].get('game_version', 'unknown')}; client version match={g['source'].get('client_version_match', 'unknown')}.",
                    "",
                ]
            )
            for room in g["rooms"]:
                detail.append(
                    f"- Room {room['order']} ({room.get('composition_status', 'unknown')}): "
                    + (
                        ", ".join(
                            f"{m.get('count', '?')} × {m.get('name', '?')} [ref {m.get('ref_id', '?')}, {m.get('role', '?')}]"
                            for m in room["monsters"]
                        )
                        or "Unknown composition"
                    )
                )
            detail.append("")
        if not row["guides"]:
            detail.extend(["No reviewed guide; room composition unknown.", ""])
        detail.extend(["### Native entrance and interiors", ""])
        for route in row["native_entry_routes"] or [
            c["route"] for c in row["configurations"]
        ]:
            criterion = route.get("criterion") or "(empty on this entry)"
            detail.extend(
                [
                    f"Entry map {route['entry_map_id']}, object {route['entry_object_id']}, destination {route['destination_id']}, template {route['template_id']}. Criterion:",
                    "",
                    "```text",
                    criterion,
                    "```",
                    "",
                ]
            )
        detail.extend(
            ["Object counts: " + str(row["native_object_type_counts"]) + ".", ""]
        )
        for t in row["native_internal_teleports"]:
            detail.append(
                f"- Internal transport object {t['source_object']} on map {t['source_map']}: "
                + "; ".join(
                    f"map {d['map_id']} ({d['x']},{d['y']},{d['z']}), criterion={d.get('criterion') or 'empty'}, item={d.get('item_reference', 0)}"
                    for d in t["destinations"]
                )
            )
        for kind in (
            "Door",
            "LootChest",
            "Stele",
            "Collector",
            "CraftTable",
            "ZoneTrigger",
            "PositionTrigger",
            "Board",
        ):
            objects = [o for o in row["native_objects"] if o["type"] == kind]
            if objects:
                detail.append(
                    f"- {kind}: "
                    + "; ".join(
                        f"{o['id']} at map {o['map_id']} ({o['x']},{o['y']},{o['z']})"
                        for o in objects
                    )
                )
        detail.extend(["", "### Local implementation", ""])
        for c in row["configurations"]:
            detail.extend(
                [
                    f"{c['slug']} v{c['version']}: policy={c['plan_policy']}; official={c['official']}; official order verified={c['topology'].get('official_room_order_verified')}; automatic transition edges={len(c['topology'].get('auto_edges', []))}.",
                    "",
                ]
            )
            for room in c["rooms"]:
                detail.append(
                    f"- Configured room {room['order']}: "
                    + ", ".join(
                        f"{m.get('count', '?')} × {m.get('name', '?')} [{m.get('ref_id', '?')}]"
                        for m in room["monsters"]
                    )
                )
            detail.append("")
        if not row["configurations"]:
            detail.extend(
                ["No configuration in the reviewed installed-generation bundle.", ""]
            )
        detail.extend(["Unresolved: " + "; ".join(row["unknowns"]) + ".", ""])
    (output / "DETAILS.md").write_text("\n".join(detail) + "\n")
    lines.insert(
        2,
        "Natural gate progression research: [AUTOMATIC-FLOW-REVIEW.md](AUTOMATIC-FLOW-REVIEW.md).",
    )
    lines.insert(
        2,
        "Current public game-version comparison: [PUBLIC-VERSION-CROSSCHECK.md](PUBLIC-VERSION-CROSSCHECK.md).",
    )
    lines.insert(
        2,
        "Detailed per-dungeon room rosters, names, criteria, doors and extras: [DETAILS.md](DETAILS.md).",
    )
    (output / "INVENTORY.md").write_text("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path(".runtime/local/methodwakfu-dungeons")
    )
    parser.add_argument("--output", type=Path, default=Path("docs/reports/dungeons"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
