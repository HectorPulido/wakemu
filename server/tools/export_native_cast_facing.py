"""Extract only literal common1040 casting-facing contracts from installed Lua.

First run ExportNativeCastScripts.java to produce the original spell/script TSV.
Unknown scripts and nonliteral parameters remain explicit pending entries.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def extract(source):
    source = re.sub(r"--[^\n]*", "", source)
    calls = re.findall(r"executeScript\s*\(\s*1040\s*,\s*params\s*\)", source)
    blocks = re.findall(r"\bparams\s*=\s*\{(.*?)\}", source, re.S)
    if len(calls) != 1 or len(blocks) != 1:
        return {"status": "pending", "reason": "No unique literal1040 params"}
    result = {"status": "verified", "template": 1040}
    for key, default in (
        ("turnCasterTowardTargetCell", True),
        ("useDiags", False),
        ("casterAnimOnTarget", False),
    ):
        values = re.findall(r'"' + key + r'"\s*,\s*([^,\n}]+)', blocks[0])
        if len(values) > 1 or (values and values[0].strip() not in ("true", "false")):
            return {
                "status": "pending",
                "reason": "Nonliteral or repeated facing parameter",
            }
        result[key] = values[0].strip() == "true" if values else default
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("identities")
    parser.add_argument("output")
    args = parser.parse_args()
    archive = Path("client/contents/scripts/scripts.jar")
    records = {}
    with zipfile.ZipFile(archive) as scripts:
        for line in Path(args.identities).read_text().splitlines():
            reference, identity = map(int, line.split("\t"))
            try:
                record = extract(scripts.read(f"{identity}.lua").decode("utf-8"))
            except KeyError:
                record = {"status": "pending", "reason": "Casting script missing"}
            records[str(reference)] = {"script_id": identity, **record}
    Path(args.output).write_text(
        json.dumps(
            {
                "source": "bPK.cbH + installed1040.lua/aiL.setMobileLookAt",
                "scripts_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "spells": records,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
