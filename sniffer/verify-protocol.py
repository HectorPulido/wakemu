#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
"""Offline checks for fragmentation, multiple frames, signed heights and byte lengths."""
import base64, importlib.util, json, struct, tempfile
from pathlib import Path
from protocol_codec import decode_body

spec = importlib.util.spec_from_file_location(
    "capture_decoder", Path(__file__).with_name("decode-capture.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def frame(op, body):
    return struct.pack(">IH", 6 + len(body), op) + body


one = frame(23, b"\1version")
two = frame(309, b"\1\2\3\4")
stream = one + two
for chunks in (
    [stream],
    [stream[:3], stream[3:8], stream[8:]],
    [bytes([b]) for b in stream],
):
    with tempfile.TemporaryDirectory(dir=".runtime") as directory:
        events = Path(directory) / "events.jsonl"
        rows = [
            {
                "event": "message",
                "direction": "in",
                "stage": "aCl#0",
                "channel": "test",
                "remote": "127.0.0.1:5556",
                "seq": i + 1,
                "time": "test",
                "payload_base64": base64.b64encode(chunk).decode(),
            }
            for i, chunk in enumerate(chunks)
        ]
        events.write_text("".join(json.dumps(r) + "\n" for r in rows))
        messages, _, counts, leftovers = module.extract(events)
        assert [r["opcode"] for r in messages] == [23, 309]
        assert [base64.b64decode(r["body_base64"]) for r in messages] == [
            one[6:],
            two[6:],
        ]
        assert counts == {"in": 2} and not leftovers
body = struct.pack(">iiihB", 1, 0, 0, 0, 2) + bytes([0xA0, 0xBF])
r = decode_body("out", 13331, body)
assert r["end_position"] == {"x": -2, "y": 0, "z": -1}
text = "acción ñ"
encoded = text.encode()
r = decode_body("out", 12366, struct.pack(">H", len(encoded)) + encoded)
assert r["text"] == text
for malformed in (struct.pack(">H", 999) + b"x", b"\0"):
    try:
        decode_body("out", 12366, malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("Truncated string accepted")
print(
    "Offline checks passed: fragmentation/coalescing, signed movement heights, UTF-8 byte lengths and truncated payload rejection."
)
