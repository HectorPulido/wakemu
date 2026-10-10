"""Extract server-authored scenario dispatch evidence from decoded capture frames."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


def decode_scenario_dispatch(body):
    if len(body) < 10:
        raise ValueError("Truncated native scenario dispatch")
    reward, event_id, scenario_id, count = struct.unpack_from(">Biib", body)
    if count < 0 or len(body) != 10 + count * 8:
        raise ValueError("Invalid native scenario argument count or trailing bytes")
    arguments = list(struct.unpack_from(">" + "q" * count, body, 10))
    prefix = "reward" if reward == 1 else "event"
    function = f"{prefix}_{scenario_id}_{event_id}".replace("-", "_")
    return {
        "scenario_id": scenario_id,
        "event_id": event_id,
        "reward": reward == 1,
        "function": function,
        "argument_count": count,
        "arguments": arguments,
    }


def audit(frames, scripts):
    output = []
    with zipfile.ZipFile(scripts) as archive:
        names = set(archive.namelist())
        for line in frames.open():
            row = json.loads(line)
            if row.get("opcode") != 13411 or row.get("direction") != "in":
                continue
            dispatch = decode_scenario_dispatch(base64.b64decode(row["body_base64"]))
            script = f"scenario/{dispatch['scenario_id']}.lua"
            body = archive.read(script) if script in names else None
            dispatch.update(
                frame_index=row.get("frame_index"),
                script=script,
                script_exists=body is not None,
                script_sha256=hashlib.sha256(body).hexdigest()
                if body is not None
                else None,
                function_exists=bool(
                    body is not None
                    and re.search(
                        rb"function\s+"
                        + re.escape(dispatch["function"].encode())
                        + rb"\s*\(",
                        body,
                    )
                ),
            )
            # Arguments can identify players; retain them only in private output.
            output.append(dispatch)
    return {
        "schema_version": 1,
        "frames_sha256": hashlib.sha256(frames.read_bytes()).hexdigest(),
        "dispatches": output,
        "semantics": "Server selects scenario ID and event/reward function; client executes Lua presentation. No map association is inferred from filenames.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path)
    parser.add_argument(
        "--scripts", type=Path, default=Path("client/contents/scripts/scripts.jar")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.frames, args.scripts)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Decoded {len(result['dispatches'])} native scenario dispatches")
