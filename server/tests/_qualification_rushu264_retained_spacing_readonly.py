"""Identify the exact initial spacing failure without advancing the live case."""
import itertools, json, sys, unittest
from pathlib import Path


def inspect():
    recipe = sys.modules["test_rushu_native_party_phase_one"]
    checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    before = recipe.verify_actual_checkpoint()
    fight = checkpoint["runtime"].fight
    owners = checkpoint["identities"]
    positions = {
        str(i): dict(
            position=fight.actors[i].position,
            hp=fight.actors[i].hp,
            ap=fight.actors[i].ap,
            mp=fight.actors[i].mp,
        )
        for i in owners
    }
    pairs = [
        dict(
            left=a,
            right=b,
            distance=sum(
                abs(x - y)
                for x, y in zip(
                    fight.actors[a].position[:2], fight.actors[b].position[:2]
                )
            ),
        )
        for a, b in itertools.combinations(owners, 2)
    ]
    receipt = checkpoint["receipt"]
    row = dict(
        phase=fight.phase,
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        players=positions,
        pairs=pairs,
        pairs_below_three=[p for p in pairs if p["distance"] < 3],
        last_boundaries=receipt.get("boundaries", [])[-2:],
        last_casts=receipt.get("casts", [])[-3:],
        last_movements=receipt.get("movements", [])[-3:],
        last_native_events=receipt.get("native_events", [])[-3:],
        pending_cast=receipt.get("pending_cast"),
        verification_before=before,
        verification_after=recipe.verify_actual_checkpoint(),
        cleanup_callbacks=len(checkpoint["cleanups"]),
        no_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/rushu264-retained-spacing-failure-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
