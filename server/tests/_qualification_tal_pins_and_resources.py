"""Read actual checkpoint pins and resources only."""
import importlib, json, unittest
from pathlib import Path


def observe():
    module = importlib.import_module("test_talkasha_paid_native_rykaon")
    checkpoint = module.TAL_ACTUAL_CHECKPOINT
    actual = module._runtime_source_pins()
    expected = checkpoint["runtime_source_pins"]
    fight = checkpoint["current"].fight
    result = dict(
        changed_paths=sorted(
            key
            for key in set(actual) | set(expected)
            if actual.get(key) != expected.get(key)
        ),
        table=getattr(fight, "native_table_turn", None),
        turn=fight.turn_id,
        current=fight.current.id,
        actors=[
            dict(
                id=a.id,
                hp=a.hp,
                ap=a.ap,
                mp=a.mp,
                wp=a.effect_stats.get(4),
                position=a.position,
            )
            for a in fight.actors.values()
        ],
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal-checkpoint-pins-and-resources.json"
    ).write_text(json.dumps(result, indent=2, default=repr))
    return unittest.TestSuite()
