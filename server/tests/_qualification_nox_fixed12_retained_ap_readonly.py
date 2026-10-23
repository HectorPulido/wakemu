"""Inspect the paid actor without casting, replaying or changing its token."""
import json
from pathlib import Path
import sys
import unittest


def inspect():
    module = sys.modules["test_nox_cube24_fixed12_joint"]
    assert len(module.retained_components) == 1
    record = module.retained_components[0]
    verification = module.verify_retained_component(record)
    case = record["case"]
    actor = case.fight.actors[4]
    row = dict(
        verification_before=verification,
        turn=case.fight.turn_id,
        table=case.fight.native_table_turn,
        actor_id=actor.id,
        ap=actor.ap,
        effect_maxima=getattr(actor, "effect_maxima", None),
        effect_stats=getattr(actor, "effect_stats", None),
        states=[
            dict(
                uid=e.uid,
                reference=e.reference,
                level=e.level,
                caster_id=getattr(e, "caster_id", None),
                effect_ids=getattr(e, "effect_ids", None),
            )
            for e in actor.state_ledger.entries
        ],
        relevant_events=[
            e
            for e in case.fight.events
            if isinstance(e, dict)
            and (
                e.get("state_id") in (8917, 8918)
                or (
                    e.get("stat_id") == 2 and e.get("target_id", e.get("actor_id")) == 4
                )
            )
        ],
        original_failure="AP0 versus expected1 after six paid casts; no actions in this inspection",
    )
    row["verification_after"] = module.verify_retained_component(record)
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-fixed12-retained-actor4-ap-and-mode-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
