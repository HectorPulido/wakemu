#!/usr/bin/env python3
"""Extract an existing WakIA request to a private local file for HostLab."""
import argparse
import json
import os
from pathlib import Path
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def pointer(data, value):
    """Select a JSON Pointer without searching or exposing captured content."""
    if value == "":
        return data
    if not value.startswith("/"):
        raise ValueError("Invalid JSON pointer")
    for raw in value[1:].split("/"):
        part = ""
        i = 0
        while i < len(raw):
            if raw[i] == "~":
                if i + 1 >= len(raw) or raw[i + 1] not in "01":
                    raise ValueError("Invalid JSON pointer escape")
                part += "/" if raw[i + 1] == "1" else "~"
                i += 2
            else:
                part += raw[i]
                i += 1
        if isinstance(data, dict):
            if part not in data:
                raise ValueError("JSON pointer not found")
            data = data[part]
        elif isinstance(data, list):
            if (
                not part.isascii()
                or not part.isdigit()
                or (len(part) > 1 and part[0] == "0")
            ):
                raise ValueError("Invalid JSON pointer index")
            index = int(part)
            if index >= len(data):
                raise ValueError("JSON pointer index not found")
            data = data[index]
        else:
            raise ValueError("JSON pointer traverses a scalar")
    return data


def extract(data, index):
    if isinstance(data, list):
        if not 0 <= index < len(data):
            raise ValueError("Input index out of range")
        data = data[index]
    elif index:
        raise ValueError("--index requires an input array")
    if isinstance(data, dict) and "protocol" not in data and "request" in data:
        data = data["request"]
    if (
        not isinstance(data, dict)
        or type(data.get("protocol")) is not int
        or data["protocol"] != 1
        or not isinstance(data.get("source"), dict)
        or not isinstance(data.get("board"), dict)
        or not isinstance(data.get("requestId"), str)
    ):
        raise ValueError("Input is not a WakIA protocol-1 request")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="Private JSON request or array of {request: ...}"
    )
    parser.add_argument(
        "--output", required=True, help="New private output file; never overwritten"
    )
    parser.add_argument(
        "--index", type=int, default=0, help="Zero-based entry in an input array"
    )
    parser.add_argument(
        "--path", default="", help="Optional JSON Pointer to the request or its wrapper"
    )
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as stream:
            request = extract(
                pointer(json.load(stream, object_pairs_hook=unique_object), args.path),
                args.index,
            )
        encoded = (
            json.dumps(
                request, ensure_ascii=True, separators=(",", ":"), allow_nan=False
            ).encode()
            + b"\n"
        )
        fd = os.open(Path(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
        except BaseException:
            os.unlink(args.output)
            raise
    except (ValueError, TypeError, OSError) as error:
        # Do not print the input or its field values to a terminal or log.
        print(f"Cannot extract request ({type(error).__name__}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
