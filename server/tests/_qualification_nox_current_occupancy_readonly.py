"""Read the physical occupied cells, including dead actors, without moving."""
import json, sys, unittest
from pathlib import Path


def inspect():
    recipe = sys.modules["test_nox_prelude_five_modes_and_polary"]
    record = recipe.retained_components[0]
    before = recipe.verify_retained_component(record)
    fight = record["case"].fight
    row = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        actors={
            str(i): dict(
                hp=a.hp,
                ap=a.ap,
                mp=a.mp,
                position=a.position,
                physical_radius=a.physical_radius,
                native_obstacle_id=getattr(a, "native_obstacle_id", None),
            )
            for i, a in fight.actors.items()
        },
        native_qi_slots=getattr(fight, "native_qi_slots", None),
        qi_attributes={
            k: v
            for k, v in vars(fight).items()
            if "qi" in k.lower() and "slots" in k.lower()
        },
        before=before,
        after=recipe.verify_retained_component(record),
        no_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-killer-current-all-occupancy-including-dead-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
