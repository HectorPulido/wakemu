"""Read the already retained actual Tal fight without advancing it."""
import importlib
import json
from pathlib import Path
import unittest


def observe():
    module = importlib.import_module("test_talkasha_paid_native_rykaon")
    checkpoint = module.TAL_ACTUAL_CHECKPOINT
    current = checkpoint["current"]
    fight = current.fight

    def code(function):
        return dict(
            file=function.__code__.co_filename,
            line=function.__code__.co_firstlineno,
            names=function.__code__.co_names,
        )

    phase = importlib.import_module("wakfu_server.combat_npc_phase_controller")
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    row = dict(
        runtime_source_pins_match=module._runtime_source_pins()
        == checkpoint["runtime_source_pins"],
        table=getattr(fight, "native_table_turn", None),
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        actors=[
            dict(id=a.id, hp=a.hp, ap=a.ap, mp=a.mp, wp=a.wp, position=a.position)
            for a in fight.actors.values()
        ],
        deliver_npc_table_phase=code(phase.deliver_npc_table_phase),
        bind_roles=code(roles.bind_roles),
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal-actual-melee-checkpoint-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=repr))
    return unittest.TestSuite()
