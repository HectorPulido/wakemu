"""Seal and execute one native attack admission offline; never publish catalogs."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    raw = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(raw)
    return digest(raw)


def build(directory, reference, actor_level, spell):
    from wakfu_server import native_catalog, monsters
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.combat_npc_activation import imports_enabled
    from prepare_monster_spell_activation import merge_npc

    started = time.monotonic()
    directory.mkdir(parents=True, exist_ok=False)
    hashes = native_catalog.document_hashes()
    names = (
        "native-npc-spell-effect-trees.json",
        "native-class-casting-roots.json",
        "native-spell-casting.json",
        "monsters.json",
    )
    raw = {name: native_catalog.read_bytes(DATA_ROOT / name) for name in names}
    for name, value in raw.items():
        if digest(value) != hashes[name]:
            raise ValueError("Native source bytes differ from published seal")
    npc = json.loads(raw[names[0]])
    roots = json.loads(raw[names[1]])
    owned = monsters.native_abilities(reference, actor_level)
    ability = next((row for row in owned if row["spell_id"] == spell), None)
    if ability is None:
        raise ValueError("Selected native actor does not own attack")
    if imports_enabled(npc.get("activation_policy"), reference, actor_level, spell):
        raise ValueError("Selected native attack is already admitted")
    casting = catalog()[str(spell)]
    level = ability["spell_level"]
    selected_roots = casting["levels"][level - 1][2]
    missing = [
        root for root in selected_roots if str(root) not in npc["baseline_effects"]
    ]
    if not missing or any(str(root) not in npc["effects"] for root in selected_roots):
        raise ValueError(
            "Expected genuinely missing admitted definition with exact native export"
        )
    if any(str(root) not in roots["roots"] for root in selected_roots):
        raise ValueError("Exact native casting root metadata is unavailable")
    source = monsters.reference(reference)
    # Only this selected level/attack is admitted in the offline candidate.
    # The actual native ownership book remains untouched and independently checked.
    admitted = merge_npc(
        npc,
        {"spells": {}, "effects": {}},
        [
            {
                "ref": reference,
                "min_level": actor_level,
                "max_level": actor_level,
                "spell_ids": [spell],
            }
        ],
    )
    changed = {}
    for name, data in ((names[0], admitted), (names[1], roots)):
        changed[name] = write(directory / name, data)
    manifest = {
        "schema": "native-npc-activation-candidate-v1",
        "activated": False,
        "base_revision": native_catalog.release(),
        "changed_documents": changed,
        "base_document_hashes": {name: hashes[name] for name in changed},
        "unchanged_documents": {
            name: value for name, value in hashes.items() if name not in changed
        },
        "qualification": "one offline isolated attack; not a complete book, spawn or live activation",
    }
    write(directory / "manifest.json", manifest)
    receipt = {
        "schema": "wakemu-spatial-content-admission-v1",
        "reference": reference,
        "actor_level": actor_level,
        "spell": spell,
        "spell_level": level,
        "native_name": source["name"],
        "owned": owned,
        "native_roots": selected_roots,
        "missing_admitted_roots_before": missing,
        "native_costs": casting["costs"][level - 1],
        "native_criterion": casting["cast_criterion_raw"],
        "verified_native_documents": {name: hashes[name] for name in names},
        "base_revision": manifest["base_revision"],
        "candidate_documents": changed,
        "ownership_changed": False,
        "native_definitions_changed": False,
        "resource_top_up": False,
        "live_activation": False,
        "runtime_spell_id_branches_added": 0,
        "generic_importer": "prepare_monster_spell_activation.merge_npc",
        "build_seconds": time.monotonic() - started,
    }
    write(directory / "admission.json", receipt)
    return receipt


def execute(directory, output, admitted):
    started = time.monotonic()
    admission = json.loads((directory / "admission.json").read_text())
    # Install before importing native readers with process-lifetime caches.
    from validate_monster_spell_activation import install_overlay, fixture

    overlay = install_overlay(directory, overlay=admitted)
    from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from wakfu_server.combat_geometry_snapshot import source_snapshot
    from wakfu_server.fight_checkpoint_store import snapshot

    fight, character, monsters, deck = fixture(
        admission["reference"],
        admission["actor_level"],
        (-9, -7, -1),
    )
    npc = fight.current
    target = fight.actors[7]
    if (
        npc.id not in monsters
        or owned_spells(fight, monsters)[admission["spell"]] != admission["spell_level"]
    ):
        raise AssertionError("Native action book differs from sealed admission")
    source = source_snapshot(fight)
    initial = snapshot(fight)
    before_resources = [npc.ap, npc.mp, npc.effect_stats[4]]
    action = {
        "type": "cast",
        "spellId": admission["spell"],
        "level": admission["spell_level"],
        "target": list(target.position),
        "targetId": target.id,
    }
    receipt = {
        "schema": "wakemu-spatial-content-execution-v2",
        "engine": "current-shared",
        "admitted": admitted,
        "admission_sha256": digest((directory / "admission.json").read_bytes()),
        "overlay_audited_base_document_hashes": overlay["audited_base_document_hashes"],
        "initial": initial,
        "native_resources_before": before_resources,
        "action": action,
        "live_delivery": False,
        "resource_top_up": False,
    }
    error = None
    try:
        tx = prepare_npc_spell(
            fight, action, character, monsters, deck, action_id=11, rng=random.Random(0)
        )
    except Exception as raised:
        error = raised
    if source_snapshot(fight) != source:
        raise AssertionError("Native preparation changed source fight")
    if not admitted:
        expected = "Unsupported native NPC effect roots: " + ",".join(
            map(str, admission["missing_admitted_roots_before"])
        )
        compiled = npc_runtime_catalog(imported=False)
        if (
            type(error) is not ValueError
            or str(error) != expected
            or any(
                str(root) in compiled.effects
                for root in admission["missing_admitted_roots_before"]
            )
        ):
            raise AssertionError(
                "Before admission did not reject exact missing native definition"
            ) from error
        receipt.update(
            status="expected_unintegrated_definition_rejection",
            error={"type": "ValueError", "message": str(error)},
            source_unchanged=True,
        )
    else:
        if error is not None:
            raise error
        after = tx.fight.actors[npc.id]
        if [after.ap, after.mp, after.effect_stats[4]] != [
            a - b for a, b in zip(before_resources, admission["native_costs"])
        ]:
            raise AssertionError("Native costs differ from actual resource consumption")
        if (
            tx.fight.actors[target.id].position == target.position
            or after.position != npc.position
        ):
            raise AssertionError(
                "Native displacement did not move target and preserve caster"
            )
        receipt.update(
            status="native_attack_prepared",
            source_unchanged=True,
            final=snapshot(tx.fight),
            outcomes=tx.outcomes,
            plan=tx.plan,
            native_resources_after=[after.ap, after.mp, after.effect_stats[4]],
            events=tx.events,
            packets=[
                {"recipient": target.id, "opcode": opcode, "payload_hex": payload.hex()}
                for opcode, payload in tx.packets
            ],
        )
    receipt["execution_seconds"] = time.monotonic() - started
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, receipt)
    return {
        "status": receipt["status"],
        "engine": "current-shared",
        "admitted": admitted,
        "receipt_sha256": digest(output.read_bytes()),
        "execution_seconds": receipt["execution_seconds"],
    }


def _cli_asset_owner_factories():
    """Retain cached resource factories before an overlay replaces Redis reads."""
    from wakfu_server import native_catalog

    # Both original factories cache at most one owner. The overlay's NoRedis
    # adapter creates no external resource; retain the original factory so an
    # already opened real Redis client can never disappear from cleanup.
    return (("database", native_catalog._database), ("redis", native_catalog._redis))


def _close_cli_asset_owners(factories):
    """Close existing owners without constructing new clients or connections."""
    errors = []
    for kind, factory in factories:
        try:
            if kind not in ("database", "redis"):
                raise ValueError("Unknown native CLI resource owner")
            size = factory.cache_info().currsize
            if type(size) is not int or size not in (0, 1):
                raise ValueError("Unexpected native CLI resource cache population")
            if size == 0:
                continue
            owner = factory()
        except Exception as error:
            errors.append(error)
            continue
        closed = False
        try:
            owner.close()
            closed = True
        except Exception as error:
            errors.append(error)
        try:
            if kind == "database" and closed:
                if owner.pool.closed is not True:
                    raise RuntimeError("Native CLI database pool remained open")
            elif kind == "redis":
                # Attempt owned-pool closure even if Redis.close itself failed.
                # Redis.close may also leave a caller-supplied pool open.
                owner.connection_pool.disconnect()
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("Native CLI resource cleanup failed", errors)


def _finish_cli_assets(factories):
    """Finish this short-lived CLI after complete assertions and serialization.

    Process-lifetime immutable asset cycles may be retained until the OS
    reclaims this normally exiting process. This is not a server/worker GC
    policy. Imported build/execute callers retain their own resource lifecycle.
    """
    _close_cli_asset_owners(factories)
    import gc

    gc.freeze()


class _ReceiptBuffer:
    """Tool-only output sink; archived gameplay executes without file writes."""

    def __init__(self):
        self.raw = None
        self.parent = self

    def mkdir(self, **unused):
        pass

    def write_bytes(self, raw):
        self.raw = bytes(raw)
        return len(raw)

    def read_bytes(self):
        if self.raw is None:
            raise ValueError("Native recipe produced no receipt")
        return self.raw


_AUDIT_HELPER = None


def _audit_helper():
    """Load the fixed stdlib-only helper without occupying archive tool names."""
    global _AUDIT_HELPER
    if _AUDIT_HELPER is None:
        import importlib.util

        path = Path(__file__).with_name("combat_migration_replay.py")
        spec = importlib.util.spec_from_file_location(
            "trusted_spatial_replay_audit", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _AUDIT_HELPER = module
    return _AUDIT_HELPER


def _source_pin(root):
    return _audit_helper().historical_source_sha256(root)


def _archive_root(root, expected, manifest_sha256):
    root = root.resolve()
    current = Path(__file__).resolve().parents[1]
    if (
        root == current
        or (root / "wakfu_server").resolve() == (current / "wakfu_server").resolve()
    ):
        raise ValueError("Historical spatial engine must be an external archive")
    manifest = root.parent / "validation-snapshot.json"
    if (
        not manifest.is_file()
        or digest(manifest.read_bytes()) != manifest_sha256
        or not (root / "tools" / "combat_spatial_pilot_content_import.py").is_file()
    ):
        raise ValueError("Pinned historical spatial archive unavailable")
    data = json.loads(manifest.read_bytes())
    # Close the entire archive importable Python source tree, including root
    # helpers excluded by canonical engine identity. Only bytecode caches are
    # outside this frozen public-source scope; no venv paths are installed.
    expected_python = {
        name.removeprefix("server/"): value
        for name, value in data["files"].items()
        if name.startswith("server/")
        and name.endswith(".py")
        and "__pycache__" not in Path(name).parts
    }
    actual_python = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError(
                "Historical Python source tree contains a symlink: " + str(relative)
            )
        if path.is_file() and path.suffix == ".py":
            actual_python[relative.as_posix()] = digest(path.read_bytes())
    if actual_python.keys() != expected_python.keys():
        raise ValueError(
            "Historical Python module membership differs from pinned snapshot"
        )
    if actual_python != expected_python:
        raise ValueError("Historical Python source differs from pinned snapshot")
    if _source_pin(root) != expected:
        raise ValueError("Historical spatial engine differs from exact source pin")
    return root


def _spatial_worker(args):
    import importlib.util
    import sys

    audit = _audit_helper()

    current = Path(__file__).resolve().parents[1]
    root = (
        current
        if args.lane == "current"
        else _archive_root(
            args.historical_server_root,
            args.expected_source_sha256,
            args.historical_manifest_sha256,
        )
    )
    if _source_pin(root) != args.expected_source_sha256:
        raise ValueError("Spatial engine differs from exact source pin")
    runner_hash = digest(Path(__file__).read_bytes())
    audit_hash = digest(Path(audit.__file__).read_bytes())
    source_hash = _source_pin(root)
    catalog_hash = digest((args.catalog_bundle / "catalog.json").read_bytes())
    # Candidate file membership and every byte are sealed across execution.
    candidate_hashes = {
        p.relative_to(args.candidate).as_posix(): digest(p.read_bytes())
        for p in args.candidate.rglob("*")
        if p.is_file()
    }
    if args.lane == "historical":
        sys.path[:] = [
            entry for entry in sys.path if Path(entry).resolve() != current.resolve()
        ]
    sys.path.insert(0, str(root / "tools"))
    sys.path.insert(0, str(root))
    sys.dont_write_bytecode = True
    sys.addaudithook(audit._read_only)
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog
    from wakfu_server.combat_reproduction import (
        source_identity,
        catalog_identity,
        controlled_environment,
    )

    with ReplayCatalog(args.catalog_bundle).install():
        if source_identity()["sha256"] != source_hash:
            raise ValueError("Spatial import domain differs from selected engine")
        catalog = catalog_identity()
        output = _ReceiptBuffer()
        clocks = dict(wall_time_ns=1700000000000000000, monotonic_ns=123000000000)
        policies = dict(WAKFU_NATIVE_AREA_CALLBACKS="1", WAKFU_NATIVE_GRANTED_CAST="1")
        expected_validator = (
            root / "tools" / "validate_monster_spell_activation.py"
        ).resolve()
        existing_validator = sys.modules.get("validate_monster_spell_activation")
        if (
            existing_validator is not None
            and Path(getattr(existing_validator, "__file__", "")).resolve()
            != expected_validator
        ):
            raise ValueError("Spatial validator already imported from another engine")
        validator = importlib.import_module("validate_monster_spell_activation")
        if Path(getattr(validator, "__file__", "")).resolve() != expected_validator:
            raise ValueError("Spatial validator origin differs from selected engine")
        with controlled_environment(clocks, policies):
            if args.lane == "current":
                execute(args.candidate, output, args.admit)
            else:
                path = root / "tools" / "combat_spatial_pilot_content_import.py"
                spec = importlib.util.spec_from_file_location(
                    "pinned_historical_spatial_recipe", path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.execute(args.candidate, output, args.backend, args.admit)
        if sys.modules.get("validate_monster_spell_activation") is not validator:
            raise ValueError(
                "Spatial validator import identity changed during execution"
            )
        receipt = json.loads(output.read_bytes())
        if source_identity()["sha256"] != source_hash or catalog_identity() != catalog:
            raise ValueError("Spatial source/catalog changed during execution")
    if audit._ISOLATION_VIOLATIONS:
        raise ValueError("Spatial recipe attempted forbidden external effects")
    if args.lane == "historical":
        _archive_root(
            root, args.expected_source_sha256, args.historical_manifest_sha256
        )
    if (
        _source_pin(root) != source_hash
        or digest(Path(__file__).read_bytes()) != runner_hash
        or digest(Path(audit.__file__).read_bytes()) != audit_hash
        or digest((args.catalog_bundle / "catalog.json").read_bytes()) != catalog_hash
        or candidate_hashes
        != {
            p.relative_to(args.candidate).as_posix(): digest(p.read_bytes())
            for p in args.candidate.rglob("*")
            if p.is_file()
        }
    ):
        raise ValueError("Spatial diagnostic inputs changed during execution")
    return dict(
        schema="wakemu-spatial-source-worker-v1",
        lane=args.lane,
        source_sha256=source_hash,
        expected_source_sha256=args.expected_source_sha256,
        selected_backend=args.backend if args.lane == "historical" else None,
        validator_origin=str(expected_validator),
        runner_sha256=runner_hash,
        audit_helper_sha256=audit_hash,
        candidate_files=candidate_hashes,
        catalog_manifest_sha256=catalog_hash,
        catalog=catalog,
        clocks=clocks,
        policies=policies,
        historical_manifest_sha256=args.historical_manifest_sha256
        if args.lane == "historical"
        else None,
        receipt=receipt,
        receipt_sha256=digest(output.read_bytes()),
        isolation="fresh-interpreter-read-only-offline-catalog",
        live_delivery=False,
    )


def _run_spatial_worker(args, lane, expected):
    import subprocess
    import sys
    import sysconfig

    tool = Path(__file__).resolve()
    command = [
        str(tool),
        "_worker",
        "--candidate",
        str(args.candidate.resolve()),
        "--catalog-bundle",
        str(args.catalog_bundle.resolve()),
        "--lane",
        lane,
        "--expected-source-sha256",
        expected,
    ]
    if lane == "historical":
        command += [
            "--historical-server-root",
            str(args.historical_server_root.resolve()),
            "--historical-manifest-sha256",
            args.historical_manifest_sha256,
            "--backend",
            args.backend,
        ]
    if args.admit:
        command.append("--admit")
    server = tool.parents[1]
    bootstrap = (
        "import runpy,sys;sys.path.append("
        + repr(sysconfig.get_path("purelib"))
        + ");sys.path.insert(0,"
        + repr(str(server))
        + ");sys.argv="
        + repr(command)
        + ";runpy.run_path("
        + repr(str(tool))
        + ",run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", bootstrap],
        capture_output=True,
        text=True,
        timeout=args.timeout,
    )
    if completed.returncode:
        raise RuntimeError(
            "Isolated " + lane + " spatial recipe failed: " + completed.stderr[-4000:]
        )
    return json.loads(completed.stdout)


def _receipt_differences(old, new, path, output):
    """Exact recursive JSON comparison, with no domain imports or normalization."""
    if type(old) is not type(new):
        output.append(dict(path=path, old=old, new=new))
    elif type(old) is dict:
        for key in dict.fromkeys([*old, *new]):
            child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in old or key not in new:
                output.append(
                    dict(
                        path=child,
                        old_present=key in old,
                        new_present=key in new,
                        old=old.get(key),
                        new=new.get(key),
                    )
                )
            else:
                _receipt_differences(old[key], new[key], child, output)
    elif type(old) is list:
        for index in range(max(len(old), len(new))):
            child = path + "/" + str(index)
            if index >= len(old) or index >= len(new):
                output.append(
                    dict(
                        path=child,
                        old_present=index < len(old),
                        new_present=index < len(new),
                        old=old[index] if index < len(old) else None,
                        new=new[index] if index < len(new) else None,
                    )
                )
            else:
                _receipt_differences(old[index], new[index], child, output)
    elif old != new:
        output.append(dict(path=path, old=old, new=new))


def _sha256_pin(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def compare_spatial_receipts(historical, current):
    """Keep raw observations and classify every difference without hiding state."""
    old, new = historical["receipt"], current["receipt"]
    differences = []
    _receipt_differences(old, new, "", differences)
    metadata = {"schema", "backend", "engine", "execution_seconds"}
    for row in differences:
        path = row["path"]
        # Only receipt metadata and the retired diagnostic selector itself are
        # expected differences. Actor IDs, ownership, topology and order remain
        # exact inputs to qualification, without renumbering or sorting.
        expected = path.lstrip("/").split("/")[0] in metadata or (
            path in ("/initial/native_spatial_backend", "/final/native_spatial_backend")
            and row.get("old_present") is True
            and row.get("new_present") is False
            and row["old"] == old.get("backend")
            and row["old"] in ("legacy", "pilot")
        )
        row["classification"] = (
            "expected-diagnostic-metadata" if expected else "unresolved"
        )
    binding_errors = []
    if historical.get("lane") != "historical" or current.get("lane") != "current":
        binding_errors.append("distinct-historical-current-lanes-required")
    for lane, worker in (("historical", historical), ("current", current)):
        if not _sha256_pin(worker.get("source_sha256")) or worker.get(
            "source_sha256"
        ) != worker.get("expected_source_sha256"):
            binding_errors.append(lane + "-exact-source-pin-required")
    if historical.get("source_sha256") == current.get("source_sha256"):
        binding_errors.append("distinct-engine-identities-required")
    if (
        not _sha256_pin(historical.get("historical_manifest_sha256"))
        or current.get("historical_manifest_sha256") is not None
    ):
        binding_errors.append("historical-manifest-pin-required")
    if (
        historical.get("selected_backend") not in ("legacy", "pilot")
        or old.get("backend") != historical.get("selected_backend")
        or old.get("schema") != "wakemu-spatial-content-execution-v1"
        or new.get("engine") != "current-shared"
        or "backend" in new
        or new.get("schema") != "wakemu-spatial-content-execution-v2"
        or current.get("selected_backend") is not None
    ):
        binding_errors.append("historical-current-producer-contract-required")
    binding = not binding_errors and all(
        historical.get(key) == current.get(key)
        for key in (
            "candidate_files",
            "catalog_manifest_sha256",
            "catalog",
            "runner_sha256",
            "audit_helper_sha256",
            "isolation",
            "clocks",
            "policies",
        )
    )
    succeeded = old.get("status") == new.get("status") == "native_attack_prepared"
    rejected = (
        old.get("status")
        == new.get("status")
        == "expected_unintegrated_definition_rejection"
    )
    return dict(
        schema="wakemu-spatial-archived-current-comparison-v1",
        historical=historical,
        current=current,
        differences=differences,
        bindings_match=binding,
        binding_errors=binding_errors,
        actions_succeeded=succeeded,
        expected_rejection_reproduced=rejected,
        qualified=binding
        and (succeeded or rejected)
        and all(
            row["classification"] == "expected-diagnostic-metadata"
            for row in differences
        ),
        qualification=(
            "one-owned-native-attack-preparation-not-complete-class-or-live-client"
            if succeeded
            else "exact-unadmitted-definition-rejection-not-successful-native-action"
        ),
        live_delivery=False,
        live_activation=False,
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("build")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--reference", type=int, required=True)
    create.add_argument("--level", type=int, required=True)
    create.add_argument("--spell", type=int, required=True)
    run = sub.add_parser(
        "execute", help="Execute only the actual current shared engine"
    )
    run.add_argument("--candidate", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--admit", action="store_true")
    for name in ("execute-historical", "compare-historical", "_worker"):
        command = sub.add_parser(name)
        command.add_argument("--candidate", type=Path, required=True)
        command.add_argument("--catalog-bundle", type=Path, required=True)
        command.add_argument("--expected-source-sha256", required=True)
        command.add_argument(
            "--historical-server-root", type=Path, required=name != "_worker"
        )
        command.add_argument("--historical-manifest-sha256", required=name != "_worker")
        command.add_argument("--backend", choices=("legacy", "pilot"), default="legacy")
        command.add_argument("--admit", action="store_true")
        if name == "_worker":
            command.add_argument(
                "--lane", choices=("historical", "current"), required=True
            )
        else:
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--timeout", type=int, default=300)
        if name == "compare-historical":
            command.add_argument("--expected-current-source-sha256", required=True)
    args = parser.parse_args()
    if args.command == "_worker":
        from contextlib import redirect_stdout
        import io

        with redirect_stdout(io.StringIO()):
            result = _spatial_worker(args)
        # Assertions, read-only isolation and source seals are complete. Keep
        # immutable native asset cycles until this short-lived worker exits,
        # matching the existing CLI cleanup without changing server GC policy.
        import gc

        gc.freeze()
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.command in ("execute-historical", "compare-historical"):
        if args.output.exists() or args.timeout <= 0:
            parser.error("Use a new private output and a positive timeout")
        old = _run_spatial_worker(args, "historical", args.expected_source_sha256)
        result = (
            old
            if args.command == "execute-historical"
            else compare_spatial_receipts(
                old,
                _run_spatial_worker(
                    args, "current", args.expected_current_source_sha256
                ),
            )
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        import os

        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "receipt_sha256": digest(args.output.read_bytes()),
                    "qualified": result.get("qualified"),
                    "live_delivery": False,
                },
                sort_keys=True,
            )
        )
        return 0 if result.get("qualified", True) else 1
    factories = _cli_asset_owner_factories()
    result = (
        build(args.output, args.reference, args.level, args.spell)
        if args.command == "build"
        else execute(args.candidate, args.output, args.admit)
    )
    _finish_cli_assets(factories)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
