"""Export actual endpoint resources and encoded admitted decks without gameplay."""
import json, struct, sys, unittest
from pathlib import Path


def inspect():
    module = sys.modules["test_nox_prelude_five_modes_and_polary"]
    record = module.retained_components[0]
    before = module.verify_retained_component(record)
    case = record["case"]
    fight = case.fight
    decks = {}
    for identity, blob in case.decks.items():
        count = struct.unpack_from(">i", blob)[0]
        active = list(struct.unpack_from(">" + str(count) + "i", blob, 4))
        offset = 4 + 4 * count
        passive_count = struct.unpack_from(">i", blob, offset)[0]
        passive = list(
            struct.unpack_from(">" + str(passive_count) + "i", blob, offset + 4)
        )
        decks[str(identity)] = dict(active=active, passive=passive)
    row = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        decks=decks,
        actors={
            str(i): dict(
                hp=a.hp,
                position=a.position,
                ap=a.ap,
                mp=a.mp,
                max_ap=a.effect_maxima[2],
                wp=a.effect_stats[4],
                source=getattr(a, "native_summon_source", None),
                states=[(e.reference, e.level) for e in a.state_ledger.entries],
            )
            for i, a in fight.actors.items()
        },
        verification_before=before,
        verification_after=module.verify_retained_component(record),
        no_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-new-prelude-retained-actual-decks-resources-and-polarys.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()


def survivors():
    module = sys.modules["test_nox_prelude_five_modes_and_polary"]
    record = module.retained_components[0]
    before = module.verify_retained_component(record)
    fight = record["case"].fight
    selected = {
        i: a
        for i, a in fight.actors.items()
        if i in (2, 3, 5)
        or (getattr(a, "native_summon_source", None) or {}).get("ref") == 5775
    }
    row = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        actors={
            str(i): dict(
                hp=a.hp,
                max_hp=a.max_hp,
                position=a.position,
                ap=a.ap,
                mp=a.mp,
                maxima=dict(a.effect_maxima),
                stats=dict(a.effect_stats),
                states=[(e.reference, e.level) for e in a.state_ledger.entries],
            )
            for i, a in selected.items()
        },
        grants={
            str(i): getattr(fight, "native_spell_grants", {}).get(str(i), {})
            for i in (2, 3, 5)
        },
        verification_before=before,
        verification_after=module.verify_retained_component(record),
        no_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-new-prelude-survivors-and-polary-stats-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()


def reload_and_survivors():
    import importlib

    return importlib.reload(sys.modules[__name__]).survivors()
