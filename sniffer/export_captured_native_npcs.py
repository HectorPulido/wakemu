"""Recover original NPC spawn identity/coordinates and observed initial roots.

Only native type1 exploration actors with format11 are decoded. This does not
infer a dialogue root from portrait, name, action ID or a compass marker.
"""
import argparse
import base64
import hashlib
import json
import struct
from pathlib import Path


def recover(path):
    actors, roots, interactions, active_actors = {}, [], [], {}
    pending = None
    for line in path.read_text().splitlines():
        frame = json.loads(line)
        opcode = frame.get("opcode")
        if frame.get("direction") == "out" and opcode == 13222:
            body = base64.b64decode(frame["body_base64"], validate=True)
            if len(body) != 16:
                raise ValueError("Malformed original NPC interaction")
            actor_id, action_id = struct.unpack(">qq", body)
            pending = {
                "actor_id": actor_id,
                "action_id": action_id,
                "request_frame_index": frame["frame_index"],
                "spawn": dict(active_actors[actor_id])
                if actor_id in active_actors
                else None,
            }
            continue
        if frame.get("direction") != "in":
            continue
        if opcode not in (12608, 12969):
            continue
        body = base64.b64decode(frame["body_base64"], validate=True)
        if opcode == 12969:
            if len(body) != 13:
                raise ValueError("Unexpected original dialogue-open layout")
            node, speaker_type, actor_id = struct.unpack(">ibq", body)
            response = {
                "actor_id": actor_id,
                "node_id": node,
                "speaker_type": speaker_type,
                "frame_index": frame["frame_index"],
            }
            roots.append(response)
            if pending is not None:
                interactions.append(
                    dict(
                        pending,
                        response=response,
                        actor_matches=speaker_type == 2
                        and actor_id == pending["actor_id"],
                    )
                )
                pending = None
            continue
        offset = 2
        for _ in range(body[1]):
            actor_type, actor_id, length = struct.unpack_from(">BqH", body, offset)
            offset += 11
            blob = body[offset : offset + length]
            offset += length
            if len(blob) != length:
                raise ValueError("Truncated original actor")
            if actor_type != 1 or not blob or blob[0] != 11:
                continue
            inner_id, kind, group_id, name_length = struct.unpack_from(">qBqH", blob, 1)
            if inner_id != actor_id:
                raise ValueError("Original actor envelope identity differs")
            start = 20 + name_length
            reference, x, y, z, map_id, direction = struct.unpack_from(
                ">hiihqB", blob, start
            )
            row = {
                "actor_id": actor_id,
                "reference_id": reference,
                "map_id": map_id,
                "x": x,
                "y": y,
                "z": z,
                "direction": direction,
                "frame_index": frame["frame_index"],
                "position_contract": "native_actor_spawn",
                "speaker_contract": "native_actor_breed_reference",
            }
            key = (actor_id, map_id, x, y, z)
            actors.setdefault(key, row)
            active_actors[actor_id] = row
        if offset != len(body):
            raise ValueError("Original actor frame has trailing data")
    rows = list(actors.values())
    for row in rows:
        # Observed first response proves the root for that interaction/context,
        # not a globally unconditional initial root for every quest state.
        row["observed_dialogue_opens"] = [
            entry["response"]
            for entry in interactions
            if entry["actor_matches"]
            and entry["spawn"] is not None
            and all(
                entry["spawn"][key] == row[key]
                for key in ("actor_id", "map_id", "x", "y", "z")
            )
        ]
    return {
        "schema": "captured-native-npc-spawns-v2",
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "actor_count": len(rows),
        "dialogue_open_count": len(roots),
        "actors": rows,
        "observed_interactions": interactions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = recover(args.capture)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "original_actor_positions=",
        result["actor_count"],
        "dialogue_opens=",
        result["dialogue_open_count"],
    )
