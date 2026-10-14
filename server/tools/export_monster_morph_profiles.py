"""Validate an atomic, source-attested morphology supplement without admission."""
import gzip
import hashlib
import json
from pathlib import Path

NAMES = (
    "native-class-morph-profiles.json",
    "native-class-morph933-effect-closure.json",
    "native-class-morph933-level-zero.json",
    "native-class-morph933-casting-roots.json",
)
PROOF = "native_source_package"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def package_document(path, manifest, *, root):
    """Return four verified documents; copied profiles retain their proof locator."""
    path, root = Path(path).resolve(), Path(root).resolve()
    directory = path if path.is_dir() else path.parent
    profiles_path = directory / NAMES[0]
    profiles = read(profiles_path)
    locator = profiles.get(PROOF)
    receipt_path = Path(locator["receipt"]) if locator else directory / "receipt.json"
    if (
        not receipt_path.is_absolute()
        or (root / ".runtime").resolve() not in receipt_path.resolve().parents
    ):
        raise ValueError("Morphology proof must be an explicit private source artifact")
    if locator and sha(receipt_path) != locator["receipt_sha256"]:
        raise ValueError("Morphology package receipt changed")
    receipt = read(receipt_path)
    if receipt.get("schema") != "native-npc-morph-preserved-supplement-v1":
        raise ValueError("Missing native morphology supplement proof")
    original_directory = receipt_path.parent
    owner = original_directory.parent
    for filename in ("export-receipt.json", "dependency-export-receipt.json"):
        proof = read(owner / filename)
        before, after = proof.get("source_sha256_before"), proof.get(
            "source_sha256_after"
        )
        if (
            not before
            or before != after
            or proof.get("returncode", proof.get("exit_code")) != 0
        ):
            raise ValueError("Unstable native morphology source export")
        for name, digest in before.items():
            source = Path(name) if Path(name).is_absolute() else root / name
            if sha(source) != digest:
                raise ValueError("Native morphology source changed: " + name)
    export = read(owner / "export-receipt.json")
    if sha(owner / "native-profiles.json") != export["output_sha256"]:
        raise ValueError("Native morphology profile bytes changed")
    dependency = read(owner / "dependency-export-receipt.json")
    for name, digest in dependency["outputs"].items():
        if sha(owner / name) != digest:
            raise ValueError("Native morphology dependency bytes changed")
    roots_proof = read(owner / "casting-root-export-receipt.json")
    if (
        roots_proof.get("returncode") != 0
        or sha(owner / "morph-casting-roots.json") != roots_proof["output_sha256"]
    ):
        raise ValueError("Native morphology root export changed")
    for name, digest in {
        **roots_proof["native_inputs"],
        **roots_proof["sources_observed"],
    }.items():
        if sha(root / name) != digest:
            raise ValueError("Native morphology root source changed")
    from import_captured_class_dependencies import native_effect

    graph = [
        json.loads(line)
        for line in gzip.open(owner / "morph-typed-closure.jsonl.gz", "rt")
    ]
    closure = read(original_directory / NAMES[1])
    for row in graph:
        if row["kind"] == "effect" and closure["effects"].get(
            str(row["reference"])
        ) != native_effect(row):
            raise ValueError("Morphology closure differs from native graph")
    for filename, source, sections in (
        (NAMES[2], "morph-level-zero.json", ("spells", "casting", "effects")),
        (NAMES[3], "morph-casting-roots.json", ("roots",)),
    ):
        merged, raw = read(original_directory / filename), read(owner / source)
        for section in sections:
            if any(
                merged[section].get(key) != value for key, value in raw[section].items()
            ):
                raise ValueError("Morphology zero/root data differs from native export")
    native_profiles = read(owner / "native-profiles.json")["profiles"]
    if any(
        profiles["profiles"].get(key) != value for key, value in native_profiles.items()
    ):
        raise ValueError("Morphology profiles differ from native constructor export")
    outputs = {}
    for name in NAMES:
        original = original_directory / name
        supplied = directory / name
        if sha(original) != receipt["outputs"][name]:
            raise ValueError("Native morphology merged output changed")
        expected = read(original)
        actual = read(supplied)
        if name == NAMES[0]:
            actual.pop(PROOF, None)
        if actual != expected:
            raise ValueError("Copied morphology output differs from attested source")
        base_path = Path(receipt["base"]) / name
        if (
            sha(base_path) != receipt["base_sha256"][name]
            or manifest.get(name) != receipt["base_sha256"][name]
        ):
            raise ValueError("Morphology original base does not match candidate base")
        base = read(base_path)
        sections = {
            NAMES[0]: ("profiles",),
            NAMES[1]: ("effects",),
            NAMES[2]: ("spells", "casting", "effects"),
            NAMES[3]: ("roots",),
        }[name]
        for section in sections:
            if any(
                expected[section].get(key) != value
                for key, value in base[section].items()
            ):
                raise ValueError("Existing class morphology record changed")
        outputs[name] = original.read_bytes()
    expected_spells = {
        a["reference"] for p in profiles["profiles"].values() for a in p["abilities"]
    }
    if (
        set(read(original_directory / NAMES[1])["spell_reference_closure"])
        != expected_spells
    ):
        raise ValueError("Morphology ability closure is incomplete")
    profiles = read(original_directory / NAMES[0])
    profiles[PROOF] = {
        "receipt": str(receipt_path),
        "receipt_sha256": sha(receipt_path),
    }
    outputs[NAMES[0]] = (json.dumps(profiles, separators=(",", ":")) + "\n").encode()
    return outputs
