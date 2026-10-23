"""Private one-call profile of the naturally reached owned boss END20 route."""
import cProfile
import io
import json
from pathlib import Path
import pstats
import time


def _endpoint(checkpoint):
    runtime = checkpoint["runtime"]
    fight = runtime.fight
    return dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        phase=fight.phase,
        current=None if fight.current is None else fight.current.id,
        action_id=runtime.action_id,
        area_count=len(getattr(fight, "native_effect_areas", {})),
        players={
            identity: dict(
                hp=fight.actors[identity].hp,
                ap=fight.actors[identity].ap,
                mp=fight.actors[identity].mp,
                wp=fight.actors[identity].effect_stats[4],
                position=list(fight.actors[identity].position),
            )
            for identity in checkpoint["identities"]
            if identity in fight.actors
        },
    )


def _category(filename):
    filename = filename.replace("\\", "/")
    if "/server/wakfu_server/" in filename:
        return "production"
    if "/server/tests/" in filename or "/.runtime/" in filename:
        return "private_harness_or_proof"
    return "stdlib_dependency_or_builtin"


def profiled_advance(checkpoint, advance, output_stem):
    """Return the exact ordinary advance result; never replay or rewind it.

    The surrounding ordinary action wrapper owns source attestations/snapshots,
    outside this profiler. Instrument only the naturally selected boss20 call;
    its normal ACK/next-START work remains part of that public call.
    """
    runtime = checkpoint["runtime"]
    fight = runtime.fight
    if not (
        fight.native_table_turn == 20
        and fight.current is not None
        and fight.current.id == -200
    ):
        raise AssertionError("END20 profiler requires the actual current boss20")
    marker = "actual_native_end20_profile_attempted"
    if checkpoint.get(marker):
        # A private diagnostic must not block a legitimate later runtime call.
        # It also must not profile a second END or replay a completed action.
        return advance(runtime)
    checkpoint[marker] = True
    stem = Path(output_stem)
    before = _endpoint(checkpoint)
    profile = cProfile.Profile()
    call_error = None
    started = time.monotonic()
    try:
        profile.enable()
        return advance(runtime)
    except BaseException as error:
        call_error = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        profile.disable()
        elapsed = time.monotonic() - started
        # Profiling/report failure must not turn a successful terminal/reward
        # transition into a gameplay failure. Keep that error on private cp.
        try:
            stem.parent.mkdir(parents=True, exist_ok=True)
            profile.dump_stats(str(stem.with_suffix(".prof")))
            report = io.StringIO()
            stats = pstats.Stats(profile, stream=report)
            report.write("TOP CUMULATIVE (overlapping inclusive times)\n")
            stats.sort_stats("cumulative").print_stats(100)
            report.write("\nTOP SELF (exclusive times)\n")
            stats.sort_stats("tottime").print_stats(100)
            stem.with_suffix(".txt").write_text(report.getvalue())
            rows, totals = [], {}
            for (filename, line, name), (
                primitive,
                calls,
                self_time,
                cumulative,
                _,
            ) in stats.stats.items():
                category = _category(filename)
                totals[category] = totals.get(category, 0.0) + self_time
                rows.append(
                    dict(
                        file=filename,
                        line=line,
                        function=name,
                        primitive_calls=primitive,
                        calls=calls,
                        self_seconds=self_time,
                        cumulative_seconds=cumulative,
                        category=category,
                    )
                )
            facts = dict(
                scope="ONE_REAL_PUBLIC_ADVANCE_AT_BOSS20_NOT_SYNTHETIC_END",
                status="returned" if call_error is None else "native_call_raised",
                call_error=call_error,
                before=before,
                after=_endpoint(checkpoint),
                call_wall_seconds=elapsed,
                profile_total_seconds=stats.total_tt,
                exclusive_self_seconds_by_category=totals,
                top_cumulative=sorted(
                    rows, key=lambda row: row["cumulative_seconds"], reverse=True
                )[:100],
                top_self=sorted(
                    rows, key=lambda row: row["self_seconds"], reverse=True
                )[:100],
                verification_scope="Caller performs current source attestations and snapshots outside this profile.",
                limits="cProfile adds overhead; no speedup or uninstrumented latency inferred. "
                "Cumulative rows overlap. The ordinary call includes its real ACK/next-START work. "
                "No engine monkeypatch, new fight, RNG reset, preview or turn rewind.",
            )
            path = stem.with_suffix(".json")
            path.write_text(json.dumps(facts, indent=2, default=str) + "\n")
            checkpoint["actual_native_end20_profile_receipt"] = str(path)
        except Exception as error:
            checkpoint["actual_native_end20_profile_export_error"] = dict(
                type=type(error).__name__, message=str(error)
            )
