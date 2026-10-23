"""Read loaded fixture code and an existing Ivory UID; no collection or gameplay."""
import hashlib
import importlib
import json
from pathlib import Path
from types import CodeType
import unittest


def shape(code):
    constants = [
        shape(v) if isinstance(v, CodeType) else repr(v) for v in code.co_consts
    ]
    return {
        "code": code.co_code.hex(),
        "names": code.co_names,
        "vars": code.co_varnames,
        "constants": constants,
    }


def find(code, name):
    if code.co_name == name:
        return code
    for value in code.co_consts:
        if isinstance(value, CodeType):
            result = find(value, name)
            if result is not None:
                return result
    return None


def observe():
    module = importlib.import_module("test_rushu_native_party_phase_one")
    loaded = module.RushuNativePartyPhaseOneTests._run.__code__
    path = Path(module.__file__)
    fresh = find(compile(path.read_text(), str(path), "exec"), "_run")
    fingerprint = lambda c: hashlib.sha256(repr(shape(c)).encode()).hexdigest()
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    server = importlib.import_module("wakfu_server.combat_server_spell")
    end = server.prepare_server_turn_end
    depth = 0
    while hasattr(end, "__wrapped__"):
        end = end.__wrapped__
        depth += 1
    result = {
        "rushu_loaded_sha": fingerprint(loaded),
        "rushu_fresh_sha": fingerprint(fresh),
        "same_logic": shape(loaded) == shape(fresh),
        "loaded_first_line": loaded.co_firstlineno,
        "fresh_first_line": fresh.co_firstlineno,
        "bind_roles_loaded_names": roles.bind_roles.__code__.co_names,
        "turn_end_wrapper_depth": depth,
        "turn_end_loaded_names": end.__code__.co_names,
        "ivory": [],
    }
    import _qualification_failed_fight_readonly_gc_snapshot as saved

    for runtime in saved.retained_runtimes:
        fight = runtime.fight
        if (
            getattr(fight, "native_npc_initialization_receipts", {})
            .get(-200, {})
            .get("ref")
            != 4378
        ):
            continue
        boss = fight.actors[-200]
        entries = []
        for entry in getattr(getattr(boss, "state_ledger", None), "entries", ()):
            if entry.uid == 687:
                entries.append(
                    {
                        name: getattr(entry, name, None)
                        for name in (
                            "uid",
                            "reference",
                            "effect_ids",
                            "level",
                            "caster_id",
                            "target_id",
                        )
                    }
                )
        result["ivory"].append(
            {
                "turn": fight.turn_id,
                "boss_uid687": entries,
                "retained785": getattr(fight, "native_retained_records", {}).get(785),
            }
        )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/rushu-loaded-logic-and-retained-ivory687-proof.json"
    ).write_text(json.dumps(result, indent=2, default=repr))
    return unittest.TestSuite()
