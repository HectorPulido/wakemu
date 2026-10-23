"""Archive endpoint identity facts and release the CSV-qualified Tal component."""
import importlib, json, unittest
from pathlib import Path


def release():
    recipe = importlib.import_module("test_talkasha_paid_native_rykaon")
    checkpoint = recipe.TAL_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    current = checkpoint["current"]
    row = dict(
        scope="CSV task11 prerequisite8148 qualified; no full-fight gate",
        status=checkpoint["receipt"]["status"],
        turn=current.fight.turn_id,
        table=getattr(current.fight, "native_table_turn", None),
        actor_ids=sorted(current.fight.actors),
        identities=dict(
            current=id(current),
            runtime=id(current.runtime),
            store=id(checkpoint["store"]),
            rng=id(current.rng),
        ),
        cleanups=len(checkpoint["cleanups"]),
    )
    try:
        row["loaded_implementation_verification"] = checkpoint[
            "loaded_implementation_verifier"
        ]()
    finally:
        recipe.release_actual_talkasha_checkpoint()
        recipe.TAL_RETAIN_ENCOUNTER_CHECKPOINT = False
        recipe.TAL_HOLD_ACTUAL_CHECKPOINT = False
        row["slot_none"] = recipe.TAL_ACTUAL_CHECKPOINT is None
        row["released"] = True
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal262-qualified-endpoint-identity-and-release.json"
        ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
