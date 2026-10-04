#!/usr/bin/env python3
"""Reassemble captured plaintext Wakfu frames offline; never opens a network connection."""
import argparse, base64, collections, json, struct
from pathlib import Path


def extract(events):
    buffers = {}
    metadata = {}
    messages = []
    actions = []
    counts = collections.Counter()
    for line in events.open():
        r = json.loads(line)
        if r.get("event") == "action":
            actions.append(r)
            continue
        d = r.get("direction")
        stage = r.get("stage", "")
        if "payload_base64" not in r:
            continue
        isgame = r.get("remote", "").rsplit(":", 1)[-1] in (
            "5556",
            "5558",
            "15556",
            "15558",
        )
        if not isgame or not (
            (d == "in" and stage == "aCl#0") or (d == "out" and stage == "SslHandler#0")
        ):
            continue
        key = (r["channel"], d)
        buf = buffers.setdefault(key, bytearray())
        if not buf:
            metadata[key] = r
        buf.extend(base64.b64decode(r["payload_base64"]))
        while len(buf) >= 4:
            length = struct.unpack_from(">I", buf)[0]
            if not 6 <= length <= 327670:
                raise ValueError(f'Invalid frame size {length}, seq {r["seq"]}')
            if len(buf) < length:
                break
            frame = bytes(buf[:length])
            del buf[:length]
            origin = metadata[key]
            header = 6 if d == "in" else 7
            opcode = struct.unpack_from(">H", frame, 4 if d == "in" else 5)[0]
            row = {
                "frame_index": len(messages) + 1,
                "channel": r["channel"],
                "remote": r["remote"],
                "direction": d,
                "time": origin["time"],
                "capture_seq": origin["seq"],
                "final_chunk_seq": r["seq"],
                "length": length,
                "opcode": opcode,
                "body_base64": base64.b64encode(frame[header:]).decode(),
            }
            if d == "out":
                row["route"] = frame[4]
            messages.append(row)
            counts[d] += 1
            metadata[key] = r
    leftovers = [
        {"channel": k[0], "direction": k[1], "bytes": len(b)}
        for k, b in buffers.items()
        if b
    ]
    return messages, actions, dict(counts), leftovers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    events = args.capture / "events.jsonl" if args.capture.is_dir() else args.capture
    out = args.output or events.parent / "decoded"
    out.mkdir(exist_ok=True, parents=True, mode=0o700)
    messages, actions, counts, leftovers = extract(events)
    with (out / "frames.jsonl").open("w") as f:
        for r in messages:
            f.write(json.dumps(r) + "\n")
    (out / "actions.json").write_text(json.dumps(actions, indent=2) + "\n")
    summary = {
        "frames": counts,
        "unique_opcodes": {
            d: len({r["opcode"] for r in messages if r["direction"] == d})
            for d in ("in", "out")
        },
        "incomplete_streams": leftovers,
    }
    (out / "framing-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
