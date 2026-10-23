"""Export native zero-damage source facts from the existing live checkpoint."""
import importlib, json, unittest
from pathlib import Path


def observe():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    fight = checkpoint["runtime"].fight
    boss = fight.actors[-200]
    groups = {}
    for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
        invocation = row.get("invocation", {})
        if row.get("target_id") == boss.id or (
            isinstance(invocation, dict)
            and (
                invocation.get("target_id") == boss.id
                or invocation.get("reference") in (266503, 266506)
            )
        ):
            groups[str(uid)] = row
    records = {
        str(uid): row
        for uid, row in getattr(fight, "native_retained_records", {}).items()
        if row.get("target_id") == boss.id
        or row.get("generic_effect") in (266503, 266506)
    }
    output = dict(
        turn=fight.turn_id,
        table=getattr(fight, "native_table_turn", None),
        current=getattr(fight.current, "id", None),
        boss=dict(
            hp=boss.hp,
            max_hp=boss.max_hp,
            ap=boss.ap,
            mp=boss.mp,
            position=boss.position,
            direction=boss.direction,
            stats=boss.effect_stats,
            maxima=boss.effect_maxima,
            minima=boss.effect_minima,
            frozen=boss.effect_frozen,
            properties={k: v for k, v in vars(boss).items() if "propert" in k},
            states=[vars(entry) for entry in boss.state_ledger.entries],
        ),
        owners={
            str(identity): dict(
                hp=actor.hp,
                ap=actor.ap,
                mp=actor.mp,
                wp=actor.effect_stats.get(4),
                position=actor.position,
                direction=actor.direction,
                stats=actor.effect_stats,
                properties={k: v for k, v in vars(actor).items() if "propert" in k},
            )
            for identity, actor in fight.actors.items()
            if identity in checkpoint["characters"]
        },
        owned_groups=groups,
        retained_records=records,
        fight_property_facts={k: v for k, v in vars(fight).items() if "propert" in k},
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-actual-zero-damage-source-facts.json"
    ).write_text(json.dumps(output, indent=2, default=str))
    return unittest.TestSuite()
