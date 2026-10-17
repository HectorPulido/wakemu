"""Measure offline native-content qualification costs, not human authoring time.

Each fixed native case runs in a fresh bounded subprocess against a captured
published catalog. No new catalog definitions, attacks or gameplay writes are
introduced. Existing cases are integration proxies, not new content releases.
"""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import time

SERVER = Path(__file__).resolve().parents[1]
ROOT = SERVER.parent
CASES = {
    "known-operation": {
        "category": "known-operation-integration-proxy",
        "spell_reference": 6266,
        "breed": 15,
        "level": 20,
        "evidence": "test_combat_spell_transaction.py:test_server_entry_executes_full_native_roots_without_spell_whitelist",
        "expected": "damage-and-native-resource-cost",
    },
    "existing-operation-combination": {
        "category": "new-combination-integration-proxy",
        "spell_reference": 7320,
        "breed": 2,
        "level": 19,
        "evidence": "test_combat_spell_transaction.py:test_server_entry_conditional_spell_damage_and_displacement_share_transaction",
        "expected": "damage-and-push-in-one-transaction",
    },
    "missing-operation": {
        "category": "new-operation-required-dependency-qualification",
        "effect_reference": 294001,
        "effect_class": 803,
        "evidence": "published combat-state-definitions.json native effect294001; current factory handler inventory",
        "expected": "actual-native-handler-rejection",
    },
}


class CatalogTiming:
    """Observe exclusive catalog-call time without double-counting recursion."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.elapsed = 0.0
        self.calls = 0
        self.depth = 0

    def install(self):
        for name in ("load", "record", "read_bytes", "read_text", "exists", "open"):
            original = getattr(self.catalog, name)

            def measured(*args, _original=original, **kwargs):
                outer = self.depth == 0
                started = time.perf_counter() if outer else None
                self.depth += 1
                try:
                    return _original(*args, **kwargs)
                finally:
                    self.depth -= 1
                    if outer:
                        self.elapsed += time.perf_counter() - started
                        self.calls += 1

            setattr(self.catalog, name, measured)

    @contextmanager
    def phase(self, stages, name):
        started = time.perf_counter()
        catalog_before = self.elapsed
        calls_before = self.calls
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started
            catalog = self.elapsed - catalog_before
            stages[name] = {
                "wall_ms": round(elapsed * 1000, 3),
                "catalog_ms": round(catalog * 1000, 3),
                "non_catalog_ms": round(max(0, elapsed - catalog) * 1000, 3),
                "catalog_calls": self.calls - calls_before,
            }


def _assert(condition, reason):
    if not condition:
        raise AssertionError(reason)


def initial_player_observation(fight):
    """Read only fields needed by these assertions from the actual Actor API."""
    actor, target = fight.actors[7], fight.actors[-7]
    return {"ap": actor.ap, "target_hp": target.hp, "target_position": target.position}


def _player_case(name, timing, stages):
    with timing.phase(stages, "fixture_setup"):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_reproduction_state import encode_state

        definition = CASES[name]
        character, monster, fight = SpellTransactionTests().native_server_fixture(
            definition["breed"],
            definition["level"],
            native_qi=True,
            target_distance=2 if name == "existing-operation-combination" else 1,
        )
        source = encode_state(fight)
        target = fight.actors[-7]
        original = initial_player_observation(fight)
        spell = definition["spell_reference"]
        body = struct.pack(">qqiih", 7, (7 << 32) | spell, *target.position)
        deck = encode_deck([spell])
    with timing.phase(stages, "execution"):
        result = prepare_server_spell(
            body,
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
    with timing.phase(stages, "validation"):
        _assert(encode_state(fight) == source, "Preparation changed the original Fight")
        updated = result.fight.actors[-7]
        _assert(updated.hp < original["target_hp"], "Native damage did not apply")
        _assert(
            result.fight.actors[7].ap < original["ap"], "Native AP cost did not apply"
        )
        opcodes = [opcode for opcode, _ in result.packets]
        _assert(bool(opcodes), "No prepared presentation packets")
        if name == "existing-operation-combination":
            _assert(
                updated.position[0] > original["target_position"][0],
                "Native push did not apply",
            )
            _assert(
                opcodes.count(12613) >= 2, "Combination effect delivery is incomplete"
            )
        observation = {
            "status": "prepared-and-validated",
            "source_preserved": True,
            "ap_before": original["ap"],
            "ap_after": result.fight.actors[7].ap,
            "target_hp_before": original["target_hp"],
            "target_hp_after": updated.hp,
            "position_before": original["target_position"],
            "position_after": updated.position,
            "packet_count": len(result.packets),
            "packet_opcodes": opcodes,
        }
    return observation


def _missing_case(timing, stages):
    with timing.phase(stages, "fixture_setup"):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            UnsupportedEffectExecution,
            run_effect_transaction,
        )
        from wakfu_server.combat_reproduction_state import encode_state

        NativeRuntimeFactoryTests.setUpClass()
        fixture = NativeRuntimeFactoryTests()
        fixture.setUp()
        effect = fixture.states["effects"].get("294001")
        _assert(
            effect is not None, "Native effect294001 is absent from the pinned catalog"
        )
        _assert(effect["effect_class"] == 803, "Native effect294001 changed family")
        _assert(
            effect["criteria"] == "" and effect["parameters"] == [],
            "Native effect294001 prerequisites changed",
        )
        factory = fixture.factory()
        source = encode_state(fixture.fight)
        dispatcher, _ = factory(copy.deepcopy(fixture.fight), {})
        _assert(
            803 not in dispatcher.handlers,
            "Family803 is implemented; reclassify this benchmark",
        )
    rejection = None
    with timing.phase(stages, "execution"):
        try:
            run_effect_transaction(
                fixture.fight,
                [EffectInvocation(294001, 1, 7, -7, (1, 0, 0))],
                lambda preview: factory(preview, {})[0],
            )
        except UnsupportedEffectExecution as error:
            rejection = str(error)
    with timing.phase(stages, "validation"):
        _assert(
            rejection == "No handler for native effect class 803",
            "Expected actual missing803 dependency rejection",
        )
        _assert(
            encode_state(fixture.fight) == source,
            "Rejected native effect changed source state",
        )
        observation = {
            "status": "dependency-rejected-and-validated",
            "source_preserved": True,
            "error_type": "UnsupportedEffectExecution",
            "dependency": "effect-family803",
            "native_effect_reference": 294001,
            "handler_present": False,
            "attack_success_claimed": False,
        }
    return observation


def source_comparison(bundle, current, evidence_path=None):
    path = Path(evidence_path) if evidence_path else Path(bundle) / "player-spell.json"
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Source evidence exceeds size bound")
    raw = path.read_bytes()
    evidence = json.loads(raw)
    source = evidence.get("source", evidence)
    files = source.get("files") if isinstance(source, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("Missing bundle source evidence")
    mismatches = 0
    for name, digest in files.items():
        # Older reproduction manifests use paths relative to server; baseline
        # inventories use checkout-relative names. Compare actual content.
        canonical = name if name in current["files"] else "server/" + name
        mismatches += current["files"].get(canonical) != digest
    current_python = {
        "implementation": sys.implementation.name,
        "version": list(sys.version_info[:3]),
    }
    captured_python = source.get("python")
    python_matches = (
        captured_python == current_python if captured_python is not None else None
    )
    return {
        "status": "matching" if not mismatches else "different",
        "compared_files": len(files),
        "mismatched_files": mismatches,
        "python_status": "unknown-legacy"
        if python_matches is None
        else "matching"
        if python_matches
        else "different",
        "python_matches": python_matches,
        "current_python": current_python,
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
    }


def execute_worker(
    name,
    bundle,
    root,
    expected_catalog_revision,
    allow_source_drift=False,
    source_evidence=None,
):
    """Only fixed trusted cases may execute; no arbitrary fixture/module input."""
    if name not in CASES:
        raise ValueError("Unknown fixed content baseline case")
    if Path(root).resolve() != ROOT:
        raise ValueError("Source root must match the executing tool checkout")
    sys.path.insert(0, str(SERVER))
    sys.path.insert(0, str(SERVER / "tests"))
    from combat_baseline_inventory import source_manifest, catalog_manifest
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog

    before = source_manifest(root)
    comparison = source_comparison(bundle, before, source_evidence)
    if (
        comparison["status"] != "matching" or comparison["python_matches"] is not True
    ) and not allow_source_drift:
        raise ValueError(
            "Catalog bundle source differs; explicit comparison authorization required"
        )
    started = time.perf_counter()
    catalog = ReplayCatalog(bundle)
    _assert(
        catalog.manifest["revision"] == expected_catalog_revision,
        "Pinned catalog revision differs from explicit target",
    )
    catalog_install_ms = (time.perf_counter() - started) * 1000
    timing = CatalogTiming(catalog)
    timing.install()
    stages = {}
    # These cases operate solely on private in-memory previews. Removing live
    # backend configuration also makes unintended direct accesses fail closed.
    for key in ("WAKFU_DATABASE_URL", "WAKFU_REDIS_URL"):
        os.environ.pop(key, None)
    with catalog.install():
        catalog_identity = catalog_manifest()
        observation = (
            _missing_case(timing, stages)
            if name == "missing-operation"
            else _player_case(name, timing, stages)
        )
    after = source_manifest(root)
    _assert(
        before["sha256"] == after["sha256"], "Source inputs changed during measurement"
    )
    _assert(
        before["validation_snapshot"]["status"] in ("absent", "verified"),
        "Invalid source snapshot",
    )
    _assert(
        catalog_identity["status"] == "published", "Pinned catalog identity unavailable"
    )
    return {
        "schema": "wakemu-content-integration-baseline-v1",
        "case": name,
        "python": {
            "implementation": sys.implementation.name,
            "version": list(sys.version_info[:3]),
            "executable": str(Path(sys.executable).resolve()),
        },
        "definition": CASES[name],
        "observation": observation,
        "source_sha256": before["sha256"],
        "source_file_count": before["file_count"],
        "catalog_revision": catalog_identity["revision"],
        "catalog_sha256": catalog_identity["sha256"],
        "catalog_bundle_sha256": hashlib.sha256(
            (Path(bundle) / "catalog.json").read_bytes()
        ).hexdigest(),
        "source_stable": True,
        "catalog_verification_install_ms": round(catalog_install_ms, 3),
        "bundle_source_comparison": comparison,
        "allow_source_drift": allow_source_drift,
        "stages": stages,
        "human_authoring_time": {
            "status": "unmeasured",
            "reason": "No new implementation or catalog publication performed",
        },
        "limitations": [
            "Existing native content is used as a qualification proxy; this is not full content-authoring cost.",
            "Player cases measure preparation and packets, not socket delivery, rendering or full integration suites.",
            "LOS is explicit permissive fixture authority, as in the established native transaction regressions.",
            "Catalog verification/install and per-stage catalog calls are measured separately; cold process filesystem cache is uncontrolled.",
            "Source provenance collection and process startup are outside stage times and included in supervisor wall time.",
        ],
    }


def supervise(
    bundle,
    output,
    root=ROOT,
    timeout=180,
    *,
    expected_catalog_revision,
    allow_source_drift=False,
    source_evidence=None
):
    if not 1 <= timeout <= 600:
        raise ValueError("Timeout must be between 1 and 600 seconds")
    root, bundle, output = (
        Path(root).resolve(),
        Path(bundle).resolve(),
        Path(output).resolve(),
    )
    if not output.is_relative_to(root / ".runtime"):
        raise ValueError("Output must remain in checkout .runtime")
    if output.exists():
        raise ValueError("Use a new output directory")
    output.mkdir(parents=True, mode=0o700)
    reports = []
    for name in CASES:
        started = time.perf_counter()
        try:
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                name,
                "--bundle",
                str(bundle),
                "--root",
                str(root),
                "--catalog-revision",
                expected_catalog_revision,
            ]
            if allow_source_drift:
                command.append("--allow-source-drift")
            if source_evidence:
                command.extend(["--source-evidence", str(source_evidence)])
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=dict(os.environ, PYTHONPATH=str(SERVER)),
            )
            if process.returncode != 0:
                report = {
                    "case": name,
                    "status": "worker-failed",
                    "exit_code": process.returncode,
                }
                try:
                    diagnostic = json.loads(process.stdout.strip().splitlines()[-1])
                    report["error_type"] = diagnostic.get(
                        "error_type", "UnknownWorkerError"
                    )
                except (ValueError, IndexError):
                    pass
            else:
                report = json.loads(process.stdout.strip().splitlines()[-1])
        except subprocess.TimeoutExpired:
            report = {"case": name, "status": "timeout", "timeout_seconds": timeout}
        except (ValueError, IndexError):
            report = {"case": name, "status": "invalid-worker-output"}
        report["supervisor_wall_ms"] = round((time.perf_counter() - started) * 1000, 3)
        (output / (name + ".json")).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        reports.append(report)
    summary = {
        "schema": "wakemu-content-integration-baseline-index-v1",
        "cases": reports,
        "complete": all("observation" in report for report in reports),
        "human_authoring_time_measured": False,
    }
    (output / "index.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--catalog-revision",
        required=True,
        help="Explicit expected published revision for this measurement",
    )
    parser.add_argument(
        "--allow-source-drift",
        action="store_true",
        help="Explicitly measure current code with older bundle definitions; record source differences",
    )
    parser.add_argument(
        "--source-evidence",
        type=Path,
        help="Source manifest or case with source mapping; default bundle/player-spell.json",
    )
    parser.add_argument("--worker", choices=tuple(CASES), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        try:
            report = execute_worker(
                args.worker,
                args.bundle,
                args.root,
                args.catalog_revision,
                args.allow_source_drift,
                args.source_evidence,
            )
        except Exception as error:
            print(
                json.dumps(
                    {
                        "case": args.worker,
                        "status": "infrastructure-or-validation-error",
                        "error_type": type(error).__name__,
                    }
                )
            )
            return 2
    else:
        if args.output is None:
            parser.error("--output is required")
        report = supervise(
            args.bundle,
            args.output,
            args.root,
            args.timeout,
            expected_catalog_revision=args.catalog_revision,
            allow_source_drift=args.allow_source_drift,
            source_evidence=args.source_evidence,
        )
    print(json.dumps(report, sort_keys=True))
    return 0 if args.worker or report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
