"""Preserve bounded authentic terminal facts before releasing scoped resources."""
import importlib, json, unittest
from pathlib import Path


def bounded(value):
    if isinstance(value, bytes):
        return {"length": len(value), "hex_prefix": value[:2048].hex()}
    if isinstance(value, (list, tuple)):
        return [bounded(v) for v in value[-160:]]
    if isinstance(value, dict):
        return {str(k): bounded(v) for k, v in list(value.items())[-160:]}
    return value


def observe():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    runtime = checkpoint["runtime"]
    fight = runtime.fight
    selected = lambda owner: {
        key: bounded(value)
        for key, value in vars(owner).items()
        if any(
            word in key.lower()
            for word in (
                "event",
                "death",
                "journal",
                "history",
                "last",
                "pending",
                "bootstrap",
            )
        )
        and "catalog" not in key.lower()
    }
    boss = fight.actors[-200]
    result = dict(
        phase=fight.phase,
        turn=fight.turn_id,
        table=getattr(fight, "native_table_turn", None),
        current=getattr(fight.current, "id", None),
        order=fight.order,
        actors={
            str(a.id): dict(
                hp=a.hp,
                max_hp=a.max_hp,
                position=a.position,
                native_death_status=getattr(a, "native_death_status", None),
                terminal_fields=selected(a),
            )
            for a in fight.actors.values()
        },
        boss=dict(
            wp=boss.effect_stats.get(4),
            hp=boss.hp,
            max_hp=boss.max_hp,
            minima=boss.effect_minima,
        ),
        fight_fields=selected(fight),
        runtime_fields=selected(runtime),
        runtime_available_keys=sorted(vars(runtime)),
        fight_available_keys=sorted(vars(fight)),
        phase_deliveries=getattr(fight, "native_npc_phase_deliveries", None),
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-original-terminal-authentic-tail.json"
    ).write_text(json.dumps(result, indent=2, default=str))
    return unittest.TestSuite()
