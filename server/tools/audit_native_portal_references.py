#!/usr/bin/env python3
"""Read native class-file references without running a client or guessing owners."""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path


def references(raw):
    if raw[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("Invalid Java class header")
    count = struct.unpack_from(">H", raw, 8)[0]
    pool = [None] * count
    offset, index = 10, 1
    while index < count:
        tag = raw[offset]
        offset += 1
        if tag == 1:
            size = struct.unpack_from(">H", raw, offset)[0]
            offset += 2
            pool[index] = (
                tag,
                raw[offset : offset + size].decode("utf8", errors="replace"),
            )
            offset += size
        elif tag in (7, 8, 16, 19, 20):
            pool[index] = (tag, struct.unpack_from(">H", raw, offset)[0])
            offset += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            pool[index] = (tag, *struct.unpack_from(">HH", raw, offset))
            offset += 4
        elif tag in (3, 4):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag == 15:
            offset += 3
        else:
            raise ValueError("Unsupported Java constant pool tag")
        index += 1
    result = []
    for item in pool:
        if item and item[0] in (10, 11):
            owner = pool[pool[item[1]][1]][1]
            name_type = pool[item[2]]
            name, descriptor = pool[name_type[1]][1], pool[name_type[2]][1]
            if owner in ("fee", "fed") or name in ("cXm", "cXn"):
                result.append(dict(owner=owner, name=name, descriptor=descriptor))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=Path("client/lib/wakfu-client.jar"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = []
    with zipfile.ZipFile(args.jar) as archive:
        for name in archive.namelist():
            if name.endswith(".class"):
                found = references(archive.read(name))
                if found:
                    result.append(dict(class_file=name, references=found))
    payload = dict(
        schema="native-portal-method-references-v1",
        jar_sha256=hashlib.sha256(args.jar.read_bytes()).hexdigest(),
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        classes=result,
    )
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(dict(classes=len(result), jar_sha256=payload["jar_sha256"])))


if __name__ == "__main__":
    main()
