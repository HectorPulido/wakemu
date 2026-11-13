#!/usr/bin/env python3
"""Extract native fake-fighter area lifecycles from decoded fight frames.

Input may contain private capture fields. Output deliberately contains only
frame indices, effect/area references, cell coordinates and retirements.
It preserves observed raw area UIDs only internally for pairing.
"""
import argparse
import base64
import json
from pathlib import Path


def _varint(raw, offset):
    value = shift = 0
    while offset < len(raw) and shift < 70:
        byte = raw[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7
    raise ValueError("Invalid protobuf varint")


def _fields(raw):
    result = {}
    offset = 0
    while offset < len(raw):
        tag, offset = _varint(raw, offset)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid protobuf field")
        if wire == 0:
            value, offset = _varint(raw, offset)
        elif wire == 2:
            length, offset = _varint(raw, offset)
            end = offset + length
            if end > len(raw):
                raise ValueError("Truncated protobuf field")
            value, offset = raw[offset:end], end
        elif wire in (1, 5):
            end = offset + (8 if wire == 1 else 4)
            if end > len(raw):
                raise ValueError("Truncated fixed protobuf field")
            value, offset = raw[offset:end], end
        else:
            raise ValueError("Unsupported protobuf wire type")
        result[number] = value
    return result


def _signed(value):
    return value - (1 << 64) if value >= 1 << 63 else value


def extract(frames, area_reference=1808, spell=7968):
    active = {}
    events = []
    for frame in frames:
        fields = frame.get("fields") or {}
        opcode = frame.get("opcode")
        if opcode == 12613 and fields.get("mzM") == 315:
            payload = fields.get("hwM") or {}
            data = _fields(base64.b64decode(payload["base64"], validate=True))
            if data.get(4) != area_reference:
                continue
            position = _fields(data[5])
            additional = _fields(data[8])
            uid = _signed(additional[21])
            cell = [_signed(position.get(i, 0)) for i in (1, 2, 3)]
            active[uid] = cell
            events.append(
                {
                    "frame": frame["frame_index"],
                    "kind": "area_created",
                    "reference": area_reference,
                    "effect": data[3],
                    "cell": cell,
                }
            )
        elif opcode == 13726 and fields.get("mzt") in active:
            cell = active.pop(fields["mzt"])
            events.append(
                {"frame": frame["frame_index"], "kind": "area_retired", "cell": cell}
            )
        elif opcode == 12678 and fields.get("hwf") == spell:
            events.append(
                {
                    "frame": frame["frame_index"],
                    "kind": "spell_cast",
                    "spell": spell,
                    "active_cells": sorted(active.values()),
                }
            )
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decoded_fights", type=Path)
    parser.add_argument("fight_id", help="Fight key in decoded_fights JSON")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.decoded_fights.read_text())
    result = extract(data[args.fight_id])
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Extracted {len(result)} sanitized area lifecycle events")


if __name__ == "__main__":
    main()
