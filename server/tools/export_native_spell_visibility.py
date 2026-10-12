"""Export sealed additive aNr.cvc metadata without catalog/ownership mutations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native_spell_visibility import SCHEMA, validate_visibility

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def export(references, output):
    references = list(references)
    if (
        not references
        or len(set(references)) != len(references)
        or any(type(ref) is not int or ref <= 0 for ref in references)
    ):
        raise ValueError("Invalid exact visibility reference set")
    output = Path(output).resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        raise ValueError(
            "Native visibility exports must remain private beneath .runtime"
        )
    output.mkdir(parents=True, exist_ok=False)
    classes = output / "classes"
    classes.mkdir()
    source = ROOT / "sniffer/java/ExportNativeSpellVisibility.java"
    classpath = str(ROOT / "client/lib/*")
    subprocess.run(
        ["javac", "-proc:none", "-cp", classpath, "-d", str(classes), str(source)],
        check=True,
    )
    command = [
        "java",
        "-Xmx128m",
        "-cp",
        str(classes) + ":" + classpath,
        "ExportNativeSpellVisibility",
    ]
    source_id = int(
        subprocess.check_output(command + ["--source-id"], text=True).strip()
    )
    inputs = [
        ROOT / "client/lib/wakfu-client.jar",
        ROOT / f"client/contents/bdata/{source_id}.jar",
        source,
        Path(__file__),
        ROOT / "server/tools/native_spell_visibility.py",
    ]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    refs = output / "refs.txt"
    refs.write_text("\n".join(map(str, sorted(references))) + "\n")
    raw = subprocess.check_output(
        command + [str(refs), str(ROOT / "client/contents/bdata")], text=True
    )
    (output / "native.jsonl").write_text(raw)
    rows = [json.loads(line) for line in raw.splitlines() if line]
    spells = {str(row["reference"]): row for row in rows}
    if len(spells) != len(rows) or set(map(int, spells)) != set(references):
        raise ValueError("Native visibility source set differs")
    after = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    if before != after:
        raise ValueError("Native visibility inputs changed during export")
    document = dict(
        schema=SCHEMA,
        source="aNr.cvc.bPS.eQe.tz.fyT.l.fyF.gtS.bPv.f",
        spells=spells,
        ownership_changed=False,
        resource_authority_changed=False,
        source_sha256=before,
        binary_type_id=source_id,
    )
    validate_visibility(document)
    target = output / "native-spell-visibility.json"
    target.write_text(json.dumps(document, indent=2) + "\n")
    receipt = dict(
        schema="sealed-native-spell-visibility-export-v1",
        refs=sorted(references),
        document_sha256=sha(target),
        source_sha256=before,
        original_inputs_stable=True,
        activated=False,
        deployed=False,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            export(
                [
                    int(line)
                    for line in args.refs.read_text().splitlines()
                    if line.strip()
                ],
                args.output,
            )
        )
    )
