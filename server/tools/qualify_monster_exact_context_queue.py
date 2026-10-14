"""Execute only missing authentic owner contexts in one budgeted offline catalog."""
import argparse
from contextlib import contextmanager
import gc
import gzip
import hashlib
import json
from pathlib import Path
import signal
import sys
import time


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def deadline(seconds):
    def expired(signum, frame):
        raise TimeoutError("Native context wall-time budget exhausted")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def verified_fixture_cache_scope(cache):
    """Retain attested fixtures on completion; invalidate interrupted contexts."""
    try:
        yield
    except BaseException:
        cache.clear()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "queue", "candidate", "native-inventory", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fallback", type=Path, action="append", default=[])
    parser.add_argument("--seconds-per-context", type=float, default=30)
    args = parser.parse_args()
    if args.output.exists() or args.seconds_per_context <= 0:
        raise ValueError("Require new output and positive time bound")
    root = args.root.resolve()
    sys.path[:0] = [
        str(root / p) for p in ("server", "server/tools", "server/ai-service")
    ]
    from qualify_monster_effect_work import source_map
    from offline_monster_catalog import OfflineMonsterCatalog

    queue = json.loads(args.queue.read_text())
    contexts = queue["contexts"]
    identities = [
        tuple(c[k] for k in ("reference", "actor_level", "spell_id", "spell_level"))
        for c in contexts
    ]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate native context in missing-case queue")
    before = source_map(root, False)
    candidate_sha = sha(args.candidate / "manifest.json")
    report = dict(
        schema="exact-owner-missing-context-execution-v1",
        source_root=str(root),
        queue_path=str(args.queue.resolve()),
        queue_sha256=sha(args.queue),
        source_sha256_before=before,
        candidate_manifest_sha256=candidate_sha,
        status="running",
        cases=[],
        planned_contexts=len(contexts),
        actual_ai_enabled=False,
        previous_positive_cases_repeated=0,
        admission=False,
    )
    started = time.monotonic()

    def save():
        report["elapsed_seconds"] = time.monotonic() - started
        report["visited_contexts"] = len(report["cases"])
        report["validated_contexts"] = sum(
            r["raw_case"]["status"] == "validated" for r in report["cases"]
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.output)

    catalog = OfflineMonsterCatalog(args.candidate, args.fallback)
    try:
        with catalog.install():
            import validate_monster_spell_activation as validator

            validator.install_overlay(args.candidate)
            manifest = json.loads((args.candidate / "manifest.json").read_text())
            expected = manifest["native_source_provenance"]["bundle_documents"][
                "monsters.json.gz"
            ]
            if sha(args.native_inventory) != expected:
                raise ValueError("Native inventory source differs")
            with gzip.open(args.native_inventory, "rt") as stream:
                validator.NATIVE_SOURCE_MONSTERS = {
                    r["ref"]: r for r in json.load(stream)["monsters"]
                }
            from wakfu_server.monsters import native_abilities
            from wakfu_server.combat_geometry import published_geometry

            scope = set(manifest["selected_references"])
            cells = published_geometry(1134).cells
            cache = validator.ReferenceFixtureCache()
            from consume_monster_fullbook_completions import freeze_warm_catalogs

            freeze_warm_catalogs()
            for position, context in enumerate(contexts):
                tick = time.monotonic()
                identity = identities[position]
                row = dict(context=context, reused=False)
                try:
                    if identity[0] not in scope:
                        row["raw_case"] = dict(
                            level=identity[1],
                            spell_id=identity[2],
                            spell_level=identity[3],
                            status="pending_candidate_scope",
                            errors={"Native owner outside candidate scope": 1},
                        )
                    else:
                        owned = native_abilities(identity[0], identity[1])
                        matches = [a for a in owned if a["spell_id"] == identity[2]]
                        if (
                            len(matches) != 1
                            or matches[0]["spell_level"] != identity[3]
                        ):
                            raise ValueError(
                                "Queue differs from actual native owner ability level"
                            )
                        with verified_fixture_cache_scope(cache), deadline(
                            args.seconds_per_context
                        ):
                            row["raw_case"] = validator.run_case(
                                *identity,
                                cells,
                                12,
                                propagate_infrastructure=True,
                                fixture_cache=cache,
                                recovery_search=True,
                                recovery_attempt_cap=6,
                                recovery_scene_cap=4
                            )
                except TimeoutError as error:
                    row["raw_case"] = dict(
                        level=identity[1],
                        spell_id=identity[2],
                        spell_level=identity[3],
                        status="pending_context_timeout",
                        errors={str(error): 1},
                    )
                row["elapsed_seconds"] = time.monotonic() - tick
                report["cases"].append(row)
                save()
                print(
                    json.dumps(
                        dict(
                            completed=position + 1,
                            total=len(contexts),
                            reference=identity[0],
                            spell_id=identity[2],
                            status=row["raw_case"]["status"],
                            validated=report["validated_contexts"],
                        )
                    ),
                    flush=True,
                )
            report["status"] = "completed_missing_native_contexts"
    except Exception as error:
        report.update(
            status="infrastructure_or_source_error",
            error=type(error).__name__ + ": " + str(error),
        )
        raise
    finally:
        report.update(
            source_sha256_after=source_map(root, False),
            catalog=catalog.receipt(),
            candidate_unchanged=sha(args.candidate / "manifest.json") == candidate_sha,
        )
        report["sources_stable"] = before == report["source_sha256_after"]
        save()


if __name__ == "__main__":
    main()
