#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
"""Summarize offline frame coverage without exposing authentication or chat data."""
import argparse
import base64
import collections
import importlib.util
import json
from pathlib import Path

from protocol_codec import decode_body


def audit(frames, known, catalog):
    classes = collections.defaultdict(list)
    for message in catalog["messages"]:
        classes[(message.get("direction"), message.get("opcode"))].append(
            message["class"]
        )
    counts = collections.defaultdict(collections.Counter)
    for frame in frames:
        key = (frame["direction"], frame["opcode"])
        counts[key]["frames"] += 1
        try:
            decoded = decode_body(
                *key, base64.b64decode(frame["body_base64"], validate=True)
            )
        except (ValueError, UnicodeError):
            counts[key]["decode_errors"] += 1
        else:
            counts[key]["decoded" if decoded is not None else "opaque"] += 1
    return [
        dict(
            direction=key[0],
            opcode=key[1],
            action=known.get(key, ("unresolved",))[0],
            classes=classes[key],
            **counts[key]
        )
        for key in sorted(counts)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "dictionary", root / "sniffer/summarize-protocol.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder = args.snapshot / "decoded"
    frames = [
        json.loads(line) for line in (folder / "frames.jsonl").read_text().splitlines()
    ]
    report = audit(
        frames,
        module.KNOWN,
        json.loads((root / "server/protocol/catalog.json").read_text()),
    )
    result = {
        "frame_count": len(frames),
        "opcodes": report,
        "notice": "Decoded fields do not prove that the local server implements an action.",
    }
    (folder / "coverage.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "frames": len(frames),
                "decoded": sum(r.get("decoded", 0) for r in report),
                "opaque": sum(r.get("opaque", 0) for r in report),
                "decode_errors": sum(r.get("decode_errors", 0) for r in report),
            }
        )
    )


if __name__ == "__main__":
    main()
