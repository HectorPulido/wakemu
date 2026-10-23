"""Record actual expiry and release the existing scoped Tal resources."""
import importlib, json, unittest
from pathlib import Path


def release():
    module = importlib.import_module("test_talkasha_paid_native_rykaon")
    checkpoint = module.TAL_ACTUAL_CHECKPOINT
    actual = module._runtime_source_pins()
    expected = checkpoint["runtime_source_pins"]
    changed = sorted(
        k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k)
    )
    assert not changed, changed
    fight = checkpoint["current"].fight
    row = dict(
        changed_paths=changed,
        turn=fight.turn_id,
        table=getattr(fight, "native_table_turn", None),
        states={
            str(a.id): [(e.reference, e.level) for e in a.state_ledger.entries]
            for a in fight.actors.values()
        },
        boss_hp=fight.actors[-200].hp,
        reason="Root authorized release: actual ray window expired; no additional casts",
    )
    module.release_actual_talkasha_checkpoint()
    row["released"] = module.TAL_ACTUAL_CHECKPOINT is None
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal-actual-checkpoint-expiry-and-release.json"
    ).write_text(json.dumps(row, indent=2, default=repr))
    return unittest.TestSuite()
