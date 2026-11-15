#!/usr/bin/env python3
"""Extract the native Celestial Dojo contract from the official 2026-11-12 capture.

Read-only over the private official capture and the installed native quest
export. Produces one authority document: entry portal, scenario choreography,
client callbacks, the seven lesson fights (bootstrap roster, terrain template,
positions, teams, terminal winners), the observed casts and the exact mission
packet order. This never claims that one observed run is the only valid way.
"""

import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server"))

from wakfu_server.combat.combat_protocol_reconstruction import (  # noqa: E402
    MalformedPacket,
    decode_packet,
)

SCHEMA = "wakemu.rii-dojo-official-contract-v1"
QUEST_EXPORT = REPO / ".runtime/quest-extraction/native-quest-definitions.json"


def _rows(path):
    with path.open() as handle:
        for line in handle:
            yield json.loads(line)


def _localized(translations, table, identity):
    for language in ("es", "en", "fr"):
        value = translations.get(language, {}).get(f"content.{table}.{identity}")
        if value:
            return value
    return None


def _npc_descriptor(body):
    """Read the trailing NPC descriptor fields used by the local encoder."""
    if len(body) < 28:
        return {}
    return dict(
        reference=struct.unpack_from(">h", body, len(body) - 27)[0],
        ai_control=body[len(body) - 25],
        level=struct.unpack_from(">h", body, len(body) - 24)[0],
        cell=list(struct.unpack_from(">iih", body, 1)),
        world_identity=struct.unpack_from(">q", body, 10)[0],
    )


def extract(capture, out):
    analysis = Path(capture) / "analysis"
    catalog = json.loads((analysis / "catalog.json").read_text())
    opcode_class = {
        row["opcode"]: row["class"] for row in catalog["messages"] if "opcode" in row
    }
    frames = list(_rows(analysis / "decoded" / "frames.jsonl"))
    inbound = {row["frame_index"]: row for row in _rows(analysis / "inbound.jsonl")}
    timeline = json.loads((analysis / "quest-timeline.json").read_text())
    by_frame = {row["frame_index"]: row for row in timeline}
    fights = json.loads((analysis / "airyna-seven-fights.json").read_text())
    export = json.loads(QUEST_EXPORT.read_text())
    translations = export["translations"]

    def body(frame):
        return base64.b64decode(frame["body_base64"])

    contract = {
        "schema": SCHEMA,
        "source_capture": str(Path(capture).name),
        "authority": (
            "one official playthrough decoded with its matching client; observed "
            "behavior, not a claim about every valid completion path"
        ),
        "dojo_entry": {},
        "arrival_choreography": [],
        "client_callbacks": [],
        "dialogue_edges": [],
        "carrier_quests": [],
        "lessons": [],
        "quest_packet_order": {},
        "native_definitions": {},
    }

    # Entry portal and every map transition inside the dojo window.
    for frame in frames:
        if frame["direction"] != "in" or frame["opcode"] != 13974:
            continue
        raw = body(frame)
        size = struct.unpack_from(">H", raw, 0)[0]
        block = raw[2 : 2 + size]
        x, y, z, map_id = struct.unpack_from(">iihq", block, 18)
        if map_id in (1387, 1388) or frame["frame_index"] < 14200 and map_id == 1385:
            preceding = [
                other
                for other in frames
                if other["direction"] == "out"
                and other["frame_index"] < frame["frame_index"]
                and other["frame_index"] >= frame["frame_index"] - 12
                and other["opcode"] in (12296, 12870, 13686)
            ]
            record = dict(
                frame=frame["frame_index"],
                time=frame["time"],
                map_id=map_id,
                cell=[x, y, z],
                request=[
                    dict(
                        frame=other["frame_index"],
                        opcode=other["opcode"],
                        class_name=opcode_class.get(other["opcode"]),
                        hex=body(other).hex(),
                    )
                    for other in preceding
                ],
            )
            if map_id == 1388 and not contract["dojo_entry"]:
                contract["dojo_entry"] = record
            elif map_id == 1387 and not contract["arrival_choreography"]:
                contract["arrival_choreography"].append(record)

    # Scenario events, client callbacks, quest packets and dialogue edges in order.
    events = []
    for frame in frames:
        index, opcode = frame["frame_index"], frame["opcode"]
        raw = body(frame)
        direction = frame["direction"]
        if direction == "in" and opcode == 13411:
            mode = raw[0]
            event_id = struct.unpack_from(">i", raw, 1)[0]
            scenario = struct.unpack_from(">i", raw, 5)[0]
            count = raw[9]
            args = [struct.unpack_from(">q", raw, 10 + 8 * n)[0] for n in range(count)]
            events.append(
                dict(
                    frame=index,
                    time=frame["time"],
                    kind="scenario_event",
                    mode=mode,
                    scenario=scenario,
                    event=event_id,
                    arguments=args if count <= 20 else f"{count} actor uids",
                    argument_count=count,
                )
            )
        elif direction == "out" and opcode == 12921:
            events.append(
                dict(
                    frame=index,
                    time=frame["time"],
                    kind="client_scenario_callback",
                    event=struct.unpack_from(">i", raw, 0)[0],
                )
            )
        elif direction == "out" and opcode == 13222:
            uid = struct.unpack_from(">q", raw, 0)[0]
            tail = struct.unpack_from(">i", raw, len(raw) - 4)[0]
            events.append(
                dict(
                    frame=index,
                    time=frame["time"],
                    kind="dialogue_open_request",
                    actor_uid=uid,
                    npc_action=tail,
                )
            )
        elif direction == "out" and opcode == 12058:
            node, choice = struct.unpack_from(">ii", raw, 0)
            events.append(
                dict(
                    frame=index,
                    time=frame["time"],
                    kind="dialogue_choice",
                    node=node,
                    choice=choice,
                    choice_text=_localized(translations, 66, choice),
                )
            )
            contract["dialogue_edges"].append(events[-1])
        elif direction == "out" and opcode == 12925:
            events.append(
                dict(
                    frame=index,
                    time=frame["time"],
                    kind="client_fight_left",
                    hex=raw.hex(),
                )
            )
        elif direction == "in" and opcode in (13832, 13422, 13205, 13312, 13371, 13295):
            row = inbound.get(index, {})
            fields = {
                key: value
                for key, value in (row.get("fields") or {}).items()
                if key != "class"
            }
            entry = dict(
                frame=index,
                time=frame["time"],
                opcode=opcode,
                class_name=opcode_class.get(opcode),
                fields=fields,
            )
            if index in by_frame:
                entry["timeline"] = by_frame[index]["kind"]
            events.append(entry)

    events.sort(key=lambda row: row["frame"])
    contract["events"] = events

    # Per-lesson decoded fight data.
    order = sorted(fights)
    for position, fight_id in enumerate(order, start=1):
        rows = fights[fight_id]
        bootstrap = terminal = None
        casts = Counter()
        for frame in rows:
            raw = body(frame)
            if (
                frame["direction"] == "in"
                and frame["opcode"] == 12847
                and bootstrap is None
            ):
                try:
                    bootstrap = decode_packet(12847, raw)
                except (MalformedPacket, ValueError):
                    bootstrap = None
            if (
                frame["direction"] == "in"
                and frame["opcode"] == 12238
                and terminal is None
            ):
                try:
                    terminal = decode_packet(12238, raw)
                except (MalformedPacket, ValueError):
                    terminal = None
            if frame["direction"] == "out":
                casts[frame["opcode"]] += 1
        monsters = []
        if bootstrap and bootstrap.get("actors"):
            for actor in bootstrap["actors"]:
                descriptor = actor.get("descriptor") or b""
                extra = _npc_descriptor(descriptor) if actor.get("kind") == 1 else {}
                monsters.append(
                    dict(
                        actor_id=actor["id"],
                        kind=actor["kind"],
                        team=actor["team"],
                        **extra,
                    )
                )
        objective = [
            row
            for row in timeline
            if row["kind"] == "objective_completed"
            and rows[0]["frame_index"]
            <= row["frame_index"]
            <= rows[-1]["frame_index"] + 40
        ]
        lesson = dict(
            position=position,
            fight_id=int(fight_id),
            first_frame=rows[0]["frame_index"],
            last_frame=rows[-1]["frame_index"],
            start_time=rows[0]["time"],
            end_time=rows[-1]["time"],
            frame_count=len(rows),
            bootstrap=dict(
                fight=bootstrap["fight"] if bootstrap else None,
                phase=bootstrap.get("phase") if bootstrap else None,
                metadata=list(bootstrap["metadata"]) if bootstrap else None,
                monsters=monsters,
            ),
            terminal=dict(
                winners=terminal.get("winners") if terminal else None,
                losers=terminal.get("losers") if terminal else None,
            ),
            client_request_counts=dict(casts),
            objectives_completed=[row["id"] for row in objective],
            quests_completed=[
                row["id"]
                for row in timeline
                if row["kind"] == "quest_completed"
                and rows[0]["frame_index"]
                <= row["frame_index"]
                <= rows[-1]["frame_index"] + 40
            ],
        )
        # The observed scenario pair around this fight.
        window = [
            row
            for row in events
            if row.get("kind") in ("scenario_event", "dialogue_choice")
            and rows[0]["frame_index"] - 260
            <= row["frame"]
            <= rows[-1]["frame_index"] + 40
        ]
        lesson["scenario_and_dialogue"] = window[-6:]
        contract["lessons"].append(lesson)

    # Carrier and hidden definitions touched by the dojo.
    by_id = {row["d"]: row for row in export["definitions"]}
    for identity in (5143, 5154, 5160, 5592):
        definition = by_id.get(identity)
        if definition is None:
            continue
        contract["native_definitions"][str(identity)] = dict(
            title=_localized(translations, 62, identity),
            hidden=definition.get("aqb"),
            presentation=definition.get("aeV"),
            minimum_level=definition.get("cjP"),
            parent=definition.get("bwX"),
            availability=definition.get("cjI"),
            activation_guard=definition.get("aHe"),
            objectives=[
                dict(
                    id=obj["d"],
                    text=_localized(translations, 64, obj["d"]),
                    prerequisite=obj.get("ckc"),
                    counter=obj.get("ckf"),
                    markers=[
                        dict(x=m["ckg"], y=m["ckh"], z=m["cki"], map_id=m["ckj"])
                        for m in (obj.get("ckd") or [])
                    ],
                )
                for obj in definition.get("cjJ", [])
            ],
            rewards=[
                dict(
                    id=row["d"],
                    type=row.get("aeV"),
                    parameters=row.get("ckl"),
                )
                for row in definition.get("cjK", [])
            ],
        )

    hidden_carriers = [
        row
        for row in timeline
        if row["kind"] in ("objective_completed", "quest_completed")
        and row["id"] in (11542, 5592, 10606, 10595, 10596, 10607, 10594, 5154)
    ]
    contract["carrier_quests"] = hidden_carriers

    Path(out).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n")
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        default=str(
            Path.home() / "Documents/Wakfu-captures-private/official-incarnam-20261112"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            REPO
            / "agents_docs/reports/quest-reconstruction/dojo-official-contract-20261112.json"
        ),
    )
    args = parser.parse_args()
    contract = extract(args.capture, args.output)
    print("dojo entry:", json.dumps(contract["dojo_entry"], ensure_ascii=False)[:220])
    print("events:", len(contract["events"]), "lessons:", len(contract["lessons"]))
    for lesson in contract["lessons"]:
        monsters = [m for m in lesson["bootstrap"]["monsters"] if m.get("kind") == 1]
        print(
            "  lesson",
            lesson["position"],
            "fight",
            lesson["fight_id"],
            "terrain",
            lesson["bootstrap"]["metadata"],
            "monsters",
            [
                (m.get("reference"), m.get("level"), tuple(m.get("cell", ())))
                for m in monsters
            ],
            "quests",
            lesson["quests_completed"],
            "winners",
            lesson["terminal"]["winners"],
            "losers",
            lesson["terminal"]["losers"],
            "objectives",
            lesson["objectives_completed"],
        )
    print("wrote", args.output)


if __name__ == "__main__":
    main()
