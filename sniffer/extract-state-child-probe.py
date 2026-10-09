"""Extract only the two state-child payloads for offline delivery controls."""
import argparse
import os
from pathlib import Path
import struct
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "client-tools/diagnostics")
)
from gui_capture_tail import CaptureTail, integer_fields

parser = argparse.ArgumentParser()
parser.add_argument("capture", type=Path, help="private capture events.jsonl")
parser.add_argument("output", type=Path)
args = parser.parse_args()
os.umask(0o077)
args.output.mkdir(parents=True, exist_ok=True)
found = set()
for row in CaptureTail(args.capture).read():
    if row["direction"] != "in" or row["opcode"] not in (12613, 13497):
        continue
    body = row["body"]
    offset = 17 if row["opcode"] == 12613 else 16
    if len(body) < offset + 2:
        continue
    family = struct.unpack_from(">i", body, 12)[0]
    if family not in (330, 400):
        continue
    size = struct.unpack_from(">h", body, offset)[0]
    if size < 0 or len(body) != offset + 2 + size:
        raise ValueError("Malformed effect wrapper")
    payload = body[offset + 2 :]
    generic = integer_fields(payload).get(3)
    if (family, generic) not in ((330, 408737), (400, 150327)) or family in found:
        continue
    found.add(family)
    (args.output / f"state-ui-delivery-{family}.bin").write_bytes(payload)
    print(
        f'family={family} generic={generic} opcode={row["opcode"]} time={row["time"]}'
    )
if found != {330, 400}:
    raise ValueError("Capture lacks the two audited state children")
