"""Join offline native infinite-wave records with dungeon and transport evidence."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import zipfile


def build(waves, inventory, transports, locale, native_objects=()):
    with zipfile.ZipFile(locale) as archive:
        texts = dict(
            line.split("=", 1)
            for line in archive.read("texts_es.properties").decode().splitlines()
            if "=" in line
        )
    rows = []
    linked = set()
    for dungeon in inventory["records"]:
        native = dungeon.get("native") or {}
        if native.get("type") not in ("INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE"):
            continue
        matches = [r for r in waves["records"] if r["id"] == native["raw_cnl"]]
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous native wave definition")
        wave = matches[0]
        if wave["raw_cpb"] not in native["raw_aHA"]:
            raise ValueError("Native wave/dungeon map mismatch")
        linked.add(wave["id"])
        interior = set(native["raw_aHA"])
        entries = []
        for transport in transports:
            destinations = [
                d
                for d in transport["destinations"]
                if d["map_id"] in interior and transport["map_id"] not in interior
            ]
            if destinations:
                entries.append(
                    {
                        "map_id": transport["map_id"],
                        "object_id": transport["id"],
                        "destinations": destinations,
                    }
                )
        for obj in native_objects:
            if obj.get("type") != "InfiniteWaves":
                continue
            payload = bytes.fromhex(obj["payload_hex"])
            match = re.search(
                rb"\x00\x00\x00([\x01-\x03])([0-9]{1,3})\x00\x00\x00\x00\x00\x01\x01$",
                payload,
            )
            if match and len(match[2]) == match[1][0] and int(match[2]) == wave["id"]:
                entries.append(
                    {
                        "map_id": obj["map_id"],
                        "object_id": obj["id"],
                        "x": obj["x"],
                        "y": obj["y"],
                        "z": obj["z"],
                        "kind": "native_InfiniteWaves",
                        "wave_id": wave["id"],
                        "parameter_evidence": "length-prefixed decimal suffix; native consumer still needs end-to-end proof",
                    }
                )
        rows.append(
            {
                "dungeon_id": native["id"],
                "name_es": dungeon["name_es"],
                "type": native["type"],
                "level": wave["raw_rI"],
                "wave_definition": wave,
                "species": [
                    {"reference": ref, "name_es": texts.get("content.7." + str(ref))}
                    for ref in wave["species_refs"]
                ],
                "entrances": entries,
                "native_objects": dungeon["native_objects"],
                "exits": dungeon["native_exits"],
                "configured": bool(dungeon["configurations"]),
            }
        )
    return {
        "schema_version": 1,
        "scope": "Installed client only; species pools are not exact wave rosters",
        "binary_table_id": waves["binary_table_id"],
        "summary": {
            "native_wave_records": len(waves["records"]),
            "public_rifts": len(rows),
            "classic": sum(r["type"] == "INFINITE_WAVE" for r in rows),
            "ultimate": sum(r["type"] == "ULTIMATE_INFINITE_WAVE" for r in rows),
            "configured": sum(r["configured"] for r in rows),
        },
        "rifts": rows,
        "unlinked_wave_definitions": [
            dict(r, name_es=texts.get("content.89." + str(r["raw_cpc"])))
            for r in waves["records"]
            if r["id"] not in linked
        ],
        "client_ui_evidence": {
            k: v for k, v in texts.items() if k.startswith("infinite.waves.")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--waves",
        type=Path,
        default=Path(".runtime/local/rift-review/native-infinite-waves.json"),
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument(
        "--transports",
        type=Path,
        default=Path(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ),
    )
    parser.add_argument(
        "--objects",
        type=Path,
        default=Path(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-map-objects.json"
        ),
    )
    parser.add_argument(
        "--locale", type=Path, default=Path("client/contents/i18n/i18n_es.jar")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/reports/rifts/inventory.json")
    )
    args = parser.parse_args()
    result = build(
        json.loads(args.waves.read_text()),
        json.loads(args.inventory.read_text()),
        json.loads(args.transports.read_text()),
        args.locale,
        json.loads(args.objects.read_text()),
    )
    result["source_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            args.waves,
            args.inventory,
            args.transports,
            args.objects,
            args.locale,
            Path("client/lib/wakfu-client.jar"),
            Path("client/contents/bdata/147.jar"),
        )
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"]))
