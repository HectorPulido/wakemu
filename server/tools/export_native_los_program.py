#!/usr/bin/env python3
"""Reproduce original Sf.bfZ integer raster program from the installed class."""
import argparse, hashlib, json, re, subprocess, zipfile
from pathlib import Path


def convert(text):
    body = text.split("public final boolean bfZ();", 1)[1].split(
        "public void a(Sh);", 1
    )[0]
    rows = []
    for line in body.splitlines():
        match = re.match(r"\s*(\d+):\s+(\w+)\s*(.*)", line)
        if not match or int(match[1]) < 23:
            continue
        offset, op, operand = int(match[1]), match[2], match[3]
        args = []
        if op.startswith(("aload_", "iload_", "istore_")):
            op, index = op.rsplit("_", 1)
            args = [int(index)]
        elif op.startswith("iconst_"):
            args = [-1 if op.endswith("m1") else int(op.rsplit("_", 1)[1])]
            op = "constant"
        elif op in ("ldc", "sipush", "bipush"):
            args = [
                int(operand.split("// int ")[1] if "// int " in operand else operand)
            ]
            op = "constant"
        elif op in ("iload", "istore", "aload"):
            args = [int(operand)]
        elif op == "iinc":
            args = [int(part.strip()) for part in operand.split(",")]
        elif op in ("getfield", "putfield"):
            args = [operand.split("Field ")[1].split(":")[0]]
        elif op == "invokevirtual":
            args = [operand.split("Method ")[1].split(":")[0]]
        elif op == "goto" or op.startswith("if"):
            args = [int(operand)]
        elif op not in (
            "iadd",
            "isub",
            "imul",
            "ineg",
            "ishl",
            "iushr",
            "i2s",
            "ireturn",
        ):
            raise ValueError("Unaudited Sf opcode " + op)
        rows.append((offset, [op, *args]))
    indices = {offset: i for i, (offset, _) in enumerate(rows)}
    for _, row in rows:
        if row[0] == "goto" or row[0].startswith("if"):
            row[1] = indices[row[1]]
        if row[0] in ("getfield", "putfield") and row[1] not in (
            "bnO",
            "bnP",
            "bnQ",
            "bnR",
            "bnS",
            "bnT",
            "bnU",
            "bnV",
            "bnW",
            "bnX",
        ):
            raise ValueError("Unaudited Sf field")
        if row[0] == "invokevirtual" and row[1] not in ("m", "bfX"):
            raise ValueError("Unaudited Sf call")
    return [row for _, row in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--javap", required=True)
    parser.add_argument(
        "--output", default="server/protocol/native-los-ray-program.json"
    )
    args = parser.parse_args()
    text = subprocess.check_output(
        [args.javap, "-classpath", "client/lib/*", "-p", "-c", "Sf"], text=True
    )
    with zipfile.ZipFile("client/lib/wakfu-client.jar") as jar:
        sha = hashlib.sha256(jar.read("Sf.class")).hexdigest()
    output = dict(
        schema="native-Sf-bfZ-int-v1",
        class_sha256=sha,
        source="Original Sf.bfZ integer raster; topology check bfX/m implemented separately; assertion-only prologue omitted with required explicit geometry",
        instructions=convert(text),
    )
    Path(args.output).write_text(json.dumps(output, separators=(",", ":")) + "\n")
