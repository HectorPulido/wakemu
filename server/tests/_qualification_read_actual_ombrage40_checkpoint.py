"""Read actual retained Ombrage state and disk-pin differences without actions."""
import importlib, hashlib, json, unittest
from pathlib import Path


def observe():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    fight = checkpoint["runtime"].fight
    root = Path("server/wakfu_server")
    actual = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*.py")
    }
    expected = checkpoint["runtime_source_pins"]
    output = dict(
        held=True,
        turn=fight.turn_id,
        table=getattr(fight, "native_table_turn", None),
        current=getattr(fight.current, "id", None),
        boss_hp=fight.actors[-200].hp,
        boss_states=[
            (e.reference, e.level) for e in fight.actors[-200].state_ledger.entries
        ],
        changed_paths=sorted(
            k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k)
        ),
        original_pins=expected,
        actor_hp={str(a.id): a.hp for a in fight.actors.values()},
        areas=getattr(fight, "native_effect_areas", {}),
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-actual-checkpoint-and-pin-differences.json"
    ).write_text(json.dumps(output, indent=2, default=repr))
    return unittest.TestSuite()
