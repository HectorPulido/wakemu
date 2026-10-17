#!/usr/bin/env python3
"""Capture structural class/NPC closures from one read-only published snapshot.

Run in a fresh process: pinned verified documents replace catalog IO only in
this audit process. No Redis, catalog publication or combat admission occurs.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def write(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def capture(connection, output, *, offline_candidate=None):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    repository = Path(__file__).resolve().parents[2]
    source_paths = sorted((repository / "server/wakfu_server").rglob("*.py"))
    source_paths.extend(
        repository / "server/tools" / name
        for name in (
            "combat_operation_catalog.py",
            "combat_operation_catalog_capture.py",
        )
    )

    def source_hashes():
        return {
            path.relative_to(repository)
            .as_posix(): hashlib.sha256(path.read_bytes())
            .hexdigest()
            for path in source_paths
        }

    source_before = source_hashes()
    environment = {
        "WAKFU_NATIVE_GRANTED_CAST": os.environ.get("WAKFU_NATIVE_GRANTED_CAST", "0"),
        "WAKFU_TEST_GRANTEDCAST": os.environ.get("WAKFU_TEST_GRANTEDCAST", "0"),
    }
    actual_transaction = dict(
        isolation=connection.execute("SHOW transaction_isolation").fetchone()[0],
        read_only=connection.execute("SHOW transaction_read_only").fetchone()[0],
    )
    if actual_transaction != {"isolation": "repeatable read", "read_only": "on"}:
        raise ValueError(
            "Capture requires an actual repeatable-read read-only transaction"
        )
    revision = connection.execute(
        "SELECT a.revision FROM native_catalog_active a JOIN native_catalog_releases r "
        "USING(revision) WHERE a.id=1 AND r.complete"
    ).fetchone()[0]
    cache, hashes, probes = {}, {}, {}
    documents = output / "documents"
    documents.mkdir()

    def name(path):
        return Path(path).resolve().relative_to(DATA_ROOT.resolve()).as_posix()

    def load(path):
        key = name(path)
        if key not in cache:
            row = connection.execute(
                "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, key),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(key)
            raw, expected = bytes(row[0]), row[1]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Published document checksum mismatch: " + key)
            destination = documents / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            hashes[key] = expected
            cache[key] = json.loads(raw)
        return cache[key]

    def exists(path):
        key = name(path)
        result = (
            connection.execute(
                "SELECT 1 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, key),
            ).fetchone()
            is not None
        )
        probes[key] = result
        return result

    # Deliberately process-local; importing consumers only after installing IO
    # ensures every runtime merge reads this exact repeatable-read revision.
    native_catalog.load = load
    native_catalog.exists = exists
    native_catalog.release = lambda: revision
    import combat_operation_catalog as compiler
    from wakfu_server import combat_operation_registry as shared_registry

    if compiler.operation_registry is not shared_registry:
        raise ValueError(
            "Compiler must use the actual public shared operation registry module"
        )
    compile_catalog = compiler.compile_catalog
    from wakfu_server.combat_server_spell import compiled_runtime_catalog
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from wakfu_server.combat_class_initialization import level_zero_catalog
    from wakfu_server.combat_summon_spellbook import profile_abilities
    from wakfu_server.combat_summon_initial_states import native_initial_states
    from wakfu_server.combat_set_current_characteristic import set_current_registry
    from wakfu_server.combat_static_catalogs import characteristic_registry

    class_runtime = compiled_runtime_catalog()
    npc_runtime = npc_runtime_catalog()
    baseline_runtime = npc_runtime_catalog(imported=False)
    casting = load(DATA_ROOT / "native-spell-casting.json")["spells"]
    zero = level_zero_catalog()
    spells = dict(casting)
    for key, row in zero["spells"].items():
        spells[key] = dict(spells.get(key, {}), level_zero_roots=row[2])
    profiles = profile_abilities()
    initials = native_initial_states()
    summons = {
        key: dict(
            row,
            initial_state_triples=initials.get(key, {}).get(
                "initial_state_triples", []
            ),
        )
        for key, row in profiles.items()
    }
    inventory = load(DATA_ROOT / "spells.json")["spells"]
    innates = load(DATA_ROOT / "breed-innate-definitions.json")["breeds"]
    monsters = load(DATA_ROOT / "monsters.json")["monsters"]
    common = dict(
        spells=spells,
        states=class_runtime.source_states["states"],
        areas=load(DATA_ROOT / "native-effect-areas.json")["areas"],
        summons=summons,
    )
    class_seeds = sorted(
        {("spell", row["id"]) for row in inventory}
        | {
            ("state", state["reference"])
            for breed in innates
            for state in breed["innate_states"]
        }
    )
    monster_seeds = sorted(
        {
            ("spell", ability["spell_id"])
            for monster in monsters
            for ability in monster["native_abilities"]
        }
    )
    registry = characteristic_registry()
    current_registry = set_current_registry()
    current = tuple(int(key) for key in current_registry)
    retained = load(DATA_ROOT / "native-retained-effect-metadata.json")
    results = {}
    for label, runtime, seeds in (
        ("classes", class_runtime, class_seeds),
        ("monsters-imported-definitions", npc_runtime, monster_seeds),
        ("monsters-preserved-baseline", baseline_runtime, monster_seeds),
    ):
        tables = dict(common, effects=runtime.effects._source)
        plan = compile_catalog(
            tables,
            seeds,
            zero_effects=zero["effects"],
            characteristic_registry=registry,
            set_current_families=current,
            set_current_registry=current_registry,
            retained_metadata=retained,
        ).report()
        plan["revision"] = revision
        plan["definition_scope"] = label
        plan["activation_claim"] = False
        result_hash = write(output / (label + ".json"), plan)
        results[label] = dict(
            sha256=result_hash,
            seeds=len(seeds),
            nodes=len(plan["nodes"]),
            issues=len(plan["issues"]),
            reasons=dict(Counter(i["reason"] for i in plan["issues"])),
            families=len(plan["family_dependents"]),
        )
    examples = {}
    example_scopes = [
        ("class-granted-7009", class_runtime.effects._source, [("spell", 7009)]),
        ("native-capability-294001", npc_runtime.effects._source, [("effect", 294001)]),
        ("monster4536-baseline", baseline_runtime.effects._source, [("spell", 4536)]),
        (
            "monster4536-exported-definitions",
            npc_runtime.effects._source,
            [("spell", 4536)],
        ),
    ]
    candidate_evidence = None
    if offline_candidate is not None:
        candidate_manifest_path = offline_candidate / "manifest.json"
        candidate_manifest = json.loads(candidate_manifest_path.read_bytes())
        candidate_path = offline_candidate / "native-npc-spell-effect-trees.json"
        candidate_raw = candidate_path.read_bytes()
        candidate_hash = hashlib.sha256(candidate_raw).hexdigest()
        if (
            candidate_manifest["base_revision"] != revision
            or candidate_hash
            != candidate_manifest["changed_documents"][
                "native-npc-spell-effect-trees.json"
            ]
        ):
            raise ValueError("Offline candidate source seal or base revision differs")
        candidate_document = json.loads(candidate_raw)
        from wakfu_server.combat_effect_runtime import _merge_effects

        candidate_effects = _merge_effects(
            baseline_runtime.effects._source, {"effects": candidate_document["effects"]}
        )
        example_scopes.append(
            (
                "monster4536-offline-candidate-imported",
                candidate_effects,
                [("spell", 4536)],
            )
        )
        from wakfu_server.combat_npc_activation import imports_enabled

        before_policy = load(DATA_ROOT / "native-npc-spell-effect-trees.json").get(
            "activation_policy"
        )
        admission = json.loads((offline_candidate / "admission.json").read_bytes())
        reference, actor_level, spell = (
            admission[key] for key in ("reference", "actor_level", "spell")
        )
        candidate_evidence = dict(
            selected_action={
                "reference": reference,
                "actor_level": actor_level,
                "spell": spell,
            },
            policy_allowed_before=imports_enabled(
                before_policy, reference, actor_level, spell
            ),
            policy_allowed_candidate=imports_enabled(
                candidate_document.get("activation_policy"),
                reference,
                actor_level,
                spell,
            ),
            preserved_baseline_unchanged=(
                candidate_document["baseline_effects"]
                == load(DATA_ROOT / "native-npc-spell-effect-trees.json")[
                    "baseline_effects"
                ]
            ),
            admission_sha256=hashlib.sha256(
                (offline_candidate / "admission.json").read_bytes()
            ).hexdigest(),
            path=str(offline_candidate),
            sha256=candidate_hash,
            manifest_sha256=hashlib.sha256(
                candidate_manifest_path.read_bytes()
            ).hexdigest(),
            activated=False,
            base_revision=revision,
        )
    for label, effects, seeds in example_scopes:
        plan = compile_catalog(
            dict(common, effects=effects),
            seeds,
            zero_effects=zero["effects"],
            characteristic_registry=registry,
            set_current_families=current,
            set_current_registry=current_registry,
            retained_metadata=retained,
        ).report()
        plan.update(revision=revision, definition_scope=label, activation_claim=False)
        examples[label] = dict(
            sha256=write(output / (label + ".json"), plan),
            nodes=len(plan["nodes"]),
            issues=len(plan["issues"]),
        )
    npc_document = load(DATA_ROOT / "native-npc-spell-effect-trees.json")
    ownership = dict(
        classes={
            str(breed): sorted(row["id"] for row in inventory if row["breed"] == breed)
            for breed in sorted({row["breed"] for row in inventory})
        },
        innate_states={str(row["breed"]): row["innate_states"] for row in innates},
        monsters={
            str(row["ref"]): dict(
                min_level=row["min_level"],
                max_level=row["max_level"],
                abilities=row["native_abilities"],
            )
            for row in monsters
        },
        activation_policy=npc_document.get("activation_policy"),
    )
    ownership_hash = write(output / "ownership-and-activation.json", ownership)
    witnesses = {
        "effect294001": {
            "class_merged": class_runtime.effects._source.get("294001"),
            "npc_imported_definitions": npc_runtime.effects._source.get("294001"),
            "note": "A source definition witness; class-book reachability is determined separately by classes.json.",
        },
        "monster3217": next(row for row in monsters if row["ref"] == 3217),
        "spell4536": casting["4536"],
        "effect118972": {
            "exported": npc_document["effects"].get("118972"),
            "class_merged": class_runtime.effects._source.get("118972"),
            "npc_imported_definitions": npc_runtime.effects._source.get("118972"),
            "npc_preserved_baseline": baseline_runtime.effects._source.get("118972"),
        },
    }
    witness_hash = write(output / "incomplete-witnesses.json", witnesses)
    source_after = source_hashes()
    if source_before != source_after:
        raise ValueError(
            "Runtime/compiler source changed during capture; preserve attempt and rerun"
        )
    source_hash = write(output / "source-manifest.json", source_before)
    manifest = dict(
        schema="wakemu-operation-catalog-capture-v1",
        revision=revision,
        transaction=actual_transaction,
        environment=environment,
        shared_registry_module=shared_registry.__name__,
        source_manifest_sha256=source_hash,
        source_drift=0,
        consumed_documents=dict(sorted(hashes.items())),
        existence_probes=probes,
        results=results,
        examples=examples,
        offline_candidate=candidate_evidence,
        ownership_sha256=ownership_hash,
        witnesses_sha256=witness_hash,
        limitations=[
            "Structural closure only; no runtime combination or client qualification.",
            "Imported NPC definitions do not authorize attacks: activation_policy remains authoritative.",
            "All exported levels are unioned; unevaluated reference curves remain unknown.",
            "No database, Redis, client or service mutations performed.",
        ],
    )
    write(output / "manifest.json", manifest)
    return manifest


def main(argv=None):
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--offline-candidate",
        type=Path,
        help="Sealed prior candidate; compare offline without activation",
    )
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    kwargs = dict(options="-c default_transaction_read_only=on")
    password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    if password_file:
        kwargs["password"] = Path(password_file).read_text().strip()
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], **kwargs) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        manifest = capture(
            connection, args.output, offline_candidate=args.offline_candidate
        )
    print(
        json.dumps(
            dict(
                revision=manifest["revision"],
                results=manifest["results"],
                consumed_documents=len(manifest["consumed_documents"]),
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
