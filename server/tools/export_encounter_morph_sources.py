"""Export an explicitly seeded native morphology dependency bundle offline."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from build_encounter_morph_supplement import build

ROOT = Path(__file__).resolve().parents[2]
JAVA_SOURCES = (
    "ExportOwnedCapturedProfiles.java",
    "ExportCapturedClassMechanicGraph.java",
    "ExportClassMechanicGraph.java",
    "ExportEffectRuntimeMetadata.java",
    "ExportNativeSpellLevelZero.java",
    "ExportNativeCastingRoots.java",
    "ProbeNativeCastingCategories.java",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def export(seeds, base, output):
    """Reuse the existing attested constructor, typed graph and bundle builder."""
    output = Path(output).resolve()
    if (ROOT / ".runtime").resolve() not in output.parents:
        raise ValueError("Native exports must remain in the private runtime tree")
    output.mkdir(parents=True, exist_ok=True)
    seed_doc = json.loads(Path(seeds).read_text())
    if seed_doc.get("schema") != "native-class-morph-profile-seeds-v1":
        raise ValueError("Explicit original native933 edges required")
    source_paths = [ROOT / "client/lib/wakfu-client.jar"]
    source_paths += sorted((ROOT / "client/contents/bdata").glob("*.jar"))
    source_paths += [ROOT / "sniffer/java" / name for name in JAVA_SOURCES]
    before = {str(path.relative_to(ROOT)): digest(path) for path in source_paths}
    write(output / "seeds.json", seed_doc)
    classes = output / "classes"
    classes.mkdir(exist_ok=True)
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-sourcepath",
            str(ROOT / "sniffer/java"),
            "-d",
            str(classes),
            *[str(ROOT / "sniffer/java" / name) for name in JAVA_SOURCES],
        ],
        cwd=ROOT,
        check=True,
    )

    def java(name, *arguments):
        subprocess.run(
            [
                "java",
                "-Xmx768m",
                "-cp",
                str(classes) + ":" + str(ROOT / "client/lib/*"),
                name,
                *map(str, arguments),
            ],
            cwd=ROOT,
            check=True,
        )

    java(
        "ExportOwnedCapturedProfiles",
        output / "seeds.json",
        output / "native-profiles.json",
    )
    java(
        "ExportCapturedClassMechanicGraph",
        output / "morph-typed-closure.jsonl.gz",
        "--morph-books-only",
        output / "native-profiles.json",
    )
    profiles = json.loads((output / "native-profiles.json").read_text())["profiles"]
    abilities = sorted(
        {
            row["reference"]
            for profile in profiles.values()
            for row in profile["abilities"]
        }
    )
    (output / "spells.txt").write_text("".join(str(ref) + "\n" for ref in abilities))
    java(
        "ExportNativeSpellLevelZero",
        output / "spells.txt",
        output / "morph-level-zero.json",
    )
    graph = [
        json.loads(line)
        for line in gzip.open(output / "morph-typed-closure.jsonl.gz", "rt")
    ]
    zero = json.loads((output / "morph-level-zero.json").read_text())
    roots = {
        int(ref)
        for row in zero["casting"].values()
        for level in row["levels"]
        for ref in level[2]
    }
    roots.update(
        int(ref)
        for row in graph
        if row["kind"] == "spell"
        for refs in row["root_samples"].values()
        for ref in refs
    )
    (output / "roots.txt").write_text("".join(str(ref) + "\n" for ref in sorted(roots)))
    java(
        "ExportNativeCastingRoots",
        output / "roots.txt",
        output / "morph-casting-roots.json",
    )
    after = {name: digest(ROOT / name) for name in before}
    if before != after:
        raise ValueError("Native inputs changed during morphology source export")
    common = dict(source_sha256_before=before, source_sha256_after=after, returncode=0)
    write(
        output / "export-receipt.json",
        dict(common, output_sha256=digest(output / "native-profiles.json")),
    )
    write(
        output / "dependency-export-receipt.json",
        dict(
            common,
            outputs={
                name: digest(output / name)
                for name in ("morph-typed-closure.jsonl.gz", "morph-level-zero.json")
            },
        ),
    )
    write(
        output / "casting-root-export-receipt.json",
        dict(
            returncode=0,
            output_sha256=digest(output / "morph-casting-roots.json"),
            native_inputs=before,
            sources_observed={},
        ),
    )
    return build(base, output, output / "bundle")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True, type=Path)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.seeds, args.base, args.output), indent=2))


if __name__ == "__main__":
    main()
