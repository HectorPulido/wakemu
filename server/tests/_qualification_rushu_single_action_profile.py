"""Profile exactly one authorized paid call on an existing private checkpoint."""
import cProfile
import json
import io
from pathlib import Path
import pstats
import time


class ContextProfile:
    """Keep profiling confined to the call, including its ordinary harness."""

    def __enter__(self):
        self.profile = cProfile.Profile()
        self.profile.enable()
        return self

    def __exit__(self, *exception):
        self.profile.disable()


def _endpoint(checkpoint, identity):
    runtime = checkpoint["runtime"]
    fight = runtime.fight
    actor = fight.actors[identity]
    return dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=fight.current.id,
        phase=fight.phase,
        ap=actor.ap,
        mp=actor.mp,
        wp=actor.effect_stats[4],
        position=list(actor.position),
        boss_hp=fight.actors[-200].hp,
        action_id=runtime.action_id,
    )


def _category(filename):
    normalized = filename.replace("\\", "/")
    if "/server/wakfu_server/" in normalized:
        return "production"
    if "/server/tests/" in normalized or "/.runtime/" in normalized:
        return "private_harness_or_proof"
    return "stdlib_dependency_or_builtin"


def profile_next_cast(checkpoint, *, identity, spell, cell, expected, output):
    """Execute once; never preview, restore RNG, re-admit, or retry the action.

    The caller supplies the exact observed endpoint as ``expected``. Verification,
    endpoint projection and report serialization run outside the profiler.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.with_suffix(".prof").exists():
        raise AssertionError(
            "Profile receipt already exists; refusing an accidental replay"
        )
    before = _endpoint(checkpoint, identity)
    for key, value in expected.items():
        if before[key] != value:
            raise AssertionError(f"Actual profile endpoint differs: {key}")
    verify = checkpoint["authorized_service_transition_verifier"]
    verification_before = verify()
    facts = dict(
        status="pending",
        action=dict(identity=identity, spell=spell, cell=list(cell)),
        before=before,
        verification_before=verification_before,
        scope="one real cp.cast_cell; no replay, preview or RNG reset",
    )
    timer = time.monotonic()
    context = ContextProfile()
    try:
        with context:
            checkpoint["cast_cell"](identity, spell, tuple(cell))
        facts["status"] = "paid_call_returned"
    except BaseException as error:
        facts.update(
            status="actual_call_raised_no_retry",
            error_type=type(error).__name__,
            error=str(error),
        )
        raise
    finally:
        facts["call_wall_seconds"] = time.monotonic() - timer
        context.profile.dump_stats(str(output.with_suffix(".prof")))
        facts["after"] = _endpoint(checkpoint, identity)
        facts["verification_after"] = verify()
        report = io.StringIO()
        stats = pstats.Stats(context.profile, stream=report)
        report.write("TOP CUMULATIVE (overlapping inclusive times)\n")
        stats.sort_stats("cumulative").print_stats(80)
        report.write("\nTOP SELF (exclusive times)\n")
        stats.sort_stats("tottime").print_stats(80)
        output.with_suffix(".txt").write_text(report.getvalue())
        rows = []
        totals = {}
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
        facts.update(
            profile_total_seconds=stats.total_tt,
            category_exclusive_self_seconds=totals,
            top_cumulative=sorted(
                rows, key=lambda row: row["cumulative_seconds"], reverse=True
            )[:80],
            top_self=sorted(rows, key=lambda row: row["self_seconds"], reverse=True)[
                :80
            ],
            interpretation="Cumulative rows overlap; category totals sum exclusive self time only. "
            "Normal cp.cast_cell includes private source/proof callbacks; these are labeled separately. "
            "Outer verification and report IO are excluded.",
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
    return facts
