"""Extract native door and Lua references without inventing unlock conditions."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile


FUNCTION = re.compile(r"^\s*(?:local\s+)?function\s+([\w.:]+)\s*\(", re.M)
IE_CALL = re.compile(r"InteractiveElement\.([A-Za-z_]\w*)\s*\(\s*(\d+)\s*[,)]")


def script_references(text, object_ids):
    """Only typed calls have strong object identity; numeric matches remain leads."""
    functions = list(FUNCTION.finditer(text))
    references = []
    for call in IE_CALL.finditer(text):
        identifier = int(call.group(2))
        if identifier not in object_ids:
            continue
        enclosing = [f for f in functions if f.start() < call.start()]
        name = enclosing[-1].group(1) if enclosing else "<top-level>"
        line = text.count("\n", 0, call.start()) + 1
        line_text = text.splitlines()[line - 1].strip()
        references.append(
            {
                "object_id": identifier,
                "method": call.group(1),
                "function": name,
                "line": line,
                "statement": line_text,
                "authority": "client_presentation_call_not_server_unlock_condition",
            }
        )
    return references


def run():
    source = Path(".runtime/local/methodwakfu-dungeons/inventory-native-snapshot")
    output = Path("docs/reports/dungeons")
    door_file = source / "door-parameters.json"
    doors = json.loads(door_file.read_text())
    native_doors = {d["id"]: d for d in doors}
    inventory_file = output / "inventory.json"
    inventory = json.loads(inventory_file.read_text())
    native_records = [r for r in inventory["records"] if r["native"]]
    objects = {o["id"]: o for r in native_records for o in r["native_objects"]}
    lua_file = Path("client/contents/scripts/scripts.jar")
    references = defaultdict(list)
    files_scanned = 0
    event_leads = []
    with zipfile.ZipFile(lua_file) as archive:
        for name in archive.namelist():
            if not name.endswith(".lua"):
                continue
            files_scanned += 1
            text = archive.read(name).decode("utf-8", errors="replace")
            for ref in script_references(text, objects):
                references[ref["object_id"]].append(dict(ref, script=name))
            if name.startswith("scenario/") and re.search(
                r"FIGHT_ENDED|MONSTER_DEATH|ouverture.{0,30}porte", text, re.I
            ):
                event_leads.append(
                    {
                        "script": name,
                        "sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                        "candidate_events": [
                            {"line": i, "comment": line.strip()[:300]}
                            for i, line in enumerate(text.splitlines(), 1)
                            if re.search(
                                r"FIGHT_ENDED|MONSTER_DEATH|ouverture.{0,30}porte",
                                line,
                                re.I,
                            )
                        ],
                        "map_binding": "unknown_until_native_event_definition_linked",
                    }
                )
    records = []
    for row in native_records:
        maps = set(row["native"]["raw_aHA"])
        selected = [
            dict(d, script_references=references.get(d["id"], []))
            for d in doors
            if d["map_id"] in maps
        ]
        records.append(
            {
                "definition_id": row["native"]["id"],
                "name_es": row["name_es"],
                "name_fr": row["native"]["name_fr"],
                "maps": sorted(maps),
                "doors": selected,
                "typed_object_script_references": [
                    {"object": objects[identifier], "references": refs}
                    for identifier, refs in references.items()
                    if objects[identifier]["map_id"] in maps
                ],
                "native_teleport_edges": row["native_internal_teleports"],
                "graph_confidence": "exact_native_transport_edges; physical_door_edges_require_geometry_export",
                "official_unlock_conditions": "not_recovered_from_client_door_metadata_or_visual_calls",
            }
        )
    summary = {
        "native_definitions": len(records),
        "lua_files_scanned": files_scanned,
        "global_native_doors_decoded": len(doors),
        "global_doors_empty_parameters": sum(not d["native_parameters"] for d in doors),
        "dungeon_doors": sum(len(r["doors"]) for r in records),
        "dungeon_doors_with_typed_script_references": sum(
            bool(d["script_references"]) for r in records for d in r["doors"]
        ),
        "dungeon_object_ids_with_typed_script_references": len(references),
        "scenario_event_leads": len(event_leads),
        "official_unlock_dependencies_recovered": 0,
    }
    document = {
        "schema_version": 1,
        "summary": summary,
        "catalog_release": inventory["live_catalog_release"],
        "sources": {
            "scripts_jar_sha256": hashlib.sha256(lua_file.read_bytes()).hexdigest(),
            "door_parameters_sha256": hashlib.sha256(
                door_file.read_bytes()
            ).hexdigest(),
            "inventory_sha256": hashlib.sha256(inventory_file.read_bytes()).hexdigest(),
        },
        "native_door_decoder": "bEE.Door -> bBk; Re.bbz parameters, Re.bkP state; bBk.dSG parses interaction rights and two booleans, not encounter dependencies",
        "records": records,
        "unbound_scenario_event_leads": event_leads,
    }
    (output / "native-script-flow.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
