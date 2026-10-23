"""Read native AP runner identities from the same paid Polary kills."""
import json, sys, unittest
from pathlib import Path


def inspect():
    recipe = sys.modules["test_nox_prelude_five_modes_and_polary"]
    record = recipe.retained_components[0]
    before = recipe.verify_retained_component(record)
    fight = record["case"].fight
    rows = []
    for uid, row in getattr(fight, "owned_stat_effects", {}).items():
        if row.get("stat_id") == 2 and row.get("caster_id") in (566, 1333):
            selected = {
                k: row.get(k)
                for k in (
                    "uid",
                    "target_id",
                    "caster_id",
                    "effect_class",
                    "family",
                    "stat_id",
                    "actual",
                    "timer",
                    "state_uid",
                )
            }
            retained = getattr(fight, "native_retained_records", {}).get(uid)
            if retained is None:
                retained = getattr(fight, "native_retained_records", {}).get(str(uid))
            invocation = (
                retained.get("invocation")
                if isinstance(retained, dict)
                else getattr(retained, "invocation", None)
            )
            selected["retained_invocation"] = (
                None
                if invocation is None
                else {
                    k: getattr(invocation, k, None)
                    for k in (
                        "reference",
                        "caster_id",
                        "target_id",
                        "state_uid",
                        "native_explicit_target",
                        "wakemu_fresh_child_selection",
                        "native_preselected_target",
                    )
                }
            )
            rows.append(selected)
    result = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        rows=rows,
        actors={
            str(i): dict(
                hp=fight.actors[i].hp,
                ap=fight.actors[i].ap,
                maximum_ap=fight.actors[i].effect_maxima[2],
                team=fight.actors[i].team,
                native_initial_team=getattr(
                    fight.actors[i], "native_initial_team", None
                ),
                team_attributes={
                    k: v for k, v in vars(fight.actors[i]).items() if "team" in k
                },
            )
            for i in range(1, 7)
        },
        frozen_roles=getattr(fight, "native_encounter_roles", None),
        before=before,
        after=recipe.verify_retained_component(record),
        no_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-paid-polary-ap-distinct-uid-authority-readonly.json"
    ).write_text(json.dumps(result, indent=2, default=str))
    return unittest.TestSuite()
