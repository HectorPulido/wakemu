"""Compile exact original Boat columns and native departure evidence into SQL data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from wakfu_server.native_boat_arrivals import POLICY, SETTING, _hash
from wakfu_server.native_boats import load as boats
from wakfu_server.store import Store


def compile_authority(db, columns, departures, *, client_sha256):
    contracts = boats(db)
    if contracts["provenance"]["client_sha256"] != client_sha256:
        raise ValueError("Column reader used another original client")
    revision = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()["revision"]
    linked = {r[k] for r in contracts["routes"] for k in ("source", "destination")}
    endpoints = {r["id"]: r for r in contracts["endpoints"]}
    result = []
    if columns["native_surface_filter"] != "NONE; retain bLD negative":
        raise ValueError("Native column source was filtered")
    for row in columns["columns"]:
        endpoint = endpoints.get(row["endpoint_id"])
        if endpoint is None or row["endpoint_id"] not in linked:
            continue
        if (endpoint["map_id"], endpoint["x"], endpoint["y"]) != (
            row["map_id"],
            row["arrival_x"],
            row["arrival_y"],
        ):
            raise ValueError("Exact native endpoint/column differs")
        surfaces = row["all_surfaces"]
        if row["native_surface_count"] != len(surfaces) or len(surfaces) != 1:
            continue
        surface = surfaces[0]
        source = [row["arrival_x"], row["arrival_y"], surface["z"]]
        if surface["bLD_signed"] != -1:
            continue
        if departures["native_movement"] != "Sm(3,0,2,true)":
            raise ValueError("Departure reader used another native movement policy")
        native = []
        for path in departures["departures"]:
            if path["from"] != source:
                continue
            for target in path["accepted_native_transitions"]:
                candidates = [
                    a
                    for a in path["target_surfaces"]
                    if a["z"] == target[2] and a["bLD"] >= 0
                ]
                if len(candidates) != 1 or target[:2] != path["toXY"]:
                    raise ValueError(
                        "Native departure target has no exact accepted surface"
                    )
                native.append(dict(target=target, target_bLD=candidates[0]["bLD"]))
        if not native:
            continue
        document = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, f"combat-maps/{row['map_id']}.json"),
        ).fetchone()
        topology = Path(f"client/contents/maps/tplg/{row['map_id']}.jar")
        entry = dict(
            endpoint_id=endpoint["id"],
            endpoint_sha256=_hash(endpoint),
            map_id=endpoint["map_id"],
            source=source,
            surface_count=1,
            surface_bLD=-1,
            surface_bLE=surface["bLE_signed"],
            surface_bLF=surface["bLF_signed"],
            surface_aYX=surface["aYX_signed"],
            geometry_sha256=document["sha256"],
            topology_sha256=hashlib.sha256(topology.read_bytes()).hexdigest(),
            native_departures=native,
        )
        entry["proof_sha256"] = _hash(entry)
        result.append(entry)
    if not result:
        raise ValueError("No exact linked unique-column native departure qualified")
    return dict(
        schema_version=1,
        policy=POLICY,
        catalog_revision=revision,
        client_sha256=client_sha256,
        source_authority="Original aKq/fzH endpoint; rE/eGt.zm/eGj.a POSITION; exact VB/Vy column; native Sm(3,0,2,true) directed departures. Arrival/source only, never walkable destination.",
        arrivals=result,
    )


def sql(value):
    literal = (
        "'"
        + json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).replace("'", "''")
        + "'::jsonb"
    )
    return (
        "-- Original Boat arrival-only columns and native directed departures; no terrain/player mutation.\n"
        "INSERT INTO settings(name,value) VALUES('"
        + SETTING
        + "',"
        + literal
        + ") ON CONFLICT(name) DO NOTHING;\n"
        "DO $boat_arrival$ BEGIN IF NOT EXISTS(SELECT 1 FROM settings WHERE name='"
        + SETTING
        + "' AND value="
        + literal
        + ") THEN RAISE EXCEPTION 'Conflicting native Boat arrival authority'; END IF; END $boat_arrival$;\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--columns", type=Path, required=True)
    parser.add_argument("--departures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            value = compile_authority(
                db,
                json.loads(args.columns.read_text()),
                json.loads(args.departures.read_text()),
                client_sha256=hashlib.sha256(
                    Path("client/lib/wakfu-client.jar").read_bytes()
                ).hexdigest(),
            )
    finally:
        store.close()
    args.output.write_text(sql(value))
    print(
        json.dumps(
            dict(
                arrivals=len(value["arrivals"]),
                output=str(args.output),
                sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
            )
        )
    )


if __name__ == "__main__":
    main()
