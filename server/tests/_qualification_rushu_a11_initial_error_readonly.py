"""Preserve the authentic initial endpoint after an expiration fixture error."""
import json
from pathlib import Path
import sys
import unittest


def qualify():
    m = sys.modules["test_rushu_dd230_eleven_slot_opening"]
    cp = m.RUSHU_ACTUAL_CHECKPOINT
    assert cp is not None
    verification = m.verify_actual_checkpoint()
    runtime = cp["runtime"]
    fight = runtime.fight
    from wakfu_server.fight_checkpoint_store import snapshot

    result = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        phase=fight.phase,
        verification=verification,
        keys=list(cp),
        checkpoint=snapshot(fight, runtime=runtime),
        rng_state=cp["rng"].getstate(),
        cleanup_callbacks=len(cp["cleanups"]),
        receipt_path=cp.get("receipt_path"),
        no_actions=True,
    )
    Path(
        ".runtime/parallel-readiness-20261021/rushu-a11-initial-expiration-factory-branch-error-authentic-endpoint.json"
    ).write_text(json.dumps(result, indent=2, default=str) + "\n")
    return unittest.TestSuite()
