"""Actual paid DROP/recollection and damage from the retained first-cycle endpoint."""
import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import time
import traceback
import unittest

RECIPE_SHA = "48d682f2aade719b72a0bd4720b27ad98632528e84d75f4f432795f09c184233"


def _build(checkpoint, recipe):
    path = Path(recipe.__file__)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RECIPE_SHA
    parsed = ast.parse(path.read_text())
    case = next(row for row in parsed.body if isinstance(row, ast.ClassDef))
    method = next(
        row
        for row in case.body
        if isinstance(row, ast.FunctionDef) and row.name == "_run"
    )
    original_with = next(row for row in method.body if isinstance(row, ast.Try)).body[0]
    imports = [
        copy.deepcopy(row)
        for row in method.body
        if isinstance(row, (ast.Import, ast.ImportFrom))
    ]
    originals = [
        copy.deepcopy(row)
        for row in method.body
        if isinstance(row, ast.Assign)
        and any(
            isinstance(name, ast.Name)
            and name.id
            in (
                "original_damage",
                "original_heal",
                "original_execute",
                "original_event",
            )
            for target in row.targets
            for name in ast.walk(target)
        )
    ]
    observers = [
        copy.deepcopy(row)
        for row in method.body
        if isinstance(row, ast.FunctionDef)
        and row.name
        in ("observe_event", "observe_vitality", "observe_damage", "observe_heal")
    ]
    helpers = [
        copy.deepcopy(row)
        for row in original_with.body
        if isinstance(row, ast.FunctionDef)
        and row.name in ("visible", "cast", "movement_path", "move")
    ]
    actions = ast.parse(
        """
from wakfu_server.boss_score_runtime import staged_score
from wakfu_server.combat_global_pv_collections import global_area_order

def holder(actor, reference):
    return [entry for entry in actor.state_ledger.entries if entry.reference == reference and entry.level <= 10]

def snapshot():
    current = runtime.fight
    return dict(table=current.native_table_turn, turn=current.turn_id, current=current.current.id,
        score=staged_score(current), boss_hp=current.actors[-200].hp,
        boss_stats=dict(current.actors[-200].effect_stats),
        players={owner: dict(hp=current.actors[owner].hp, ap=current.actors[owner].ap,
            mp=current.actors[owner].mp, maximum_ap=current.actors[owner].effect_maxima[2],
            position=current.actors[owner].position,
            states=[(entry.reference,entry.level,entry.caster_id) for entry in current.actors[owner].state_ledger.entries])
            for owner in identities})

def cast_cell(owner, spell, cell):
    current, actor = runtime.fight, runtime.fight.actors[owner]
    uid = spell if spell in granted_spells(current, owner) else (owner << 32) | spell
    before = dict(ap=actor.ap,mp=actor.mp,wp=actor.effect_stats[4])
    facts['pending_cast'] = dict(actor=owner,spell=spell,target_cell=cell,before_resources=before)
    transaction = prepare_server_spell(struct.pack('>qqiih',owner,uid,*cell),
        characters[owner],monsters,current,actor.owner_id,decks[owner],
        action_id=runtime.action_id+1,line_of_sight=visible,critical=False,**common)
    commit_spell_transaction(runtime,transaction,stats_serializer=serialize)
    facts['casts'].append(dict(actor=owner,spell=spell,target_cell=cell,
        table=runtime.fight.native_table_turn,costs=transaction.plan['costs'],
        before_resources=before,after_resources=dict(ap=runtime.fight.actors[owner].ap,
            mp=runtime.fight.actors[owner].mp,wp=runtime.fight.actors[owner].effect_stats[4]),
        consumed_healing={}))
    facts['pending_cast'] = None

def attack(owner):
    before = snapshot()
    cast(owner, 6971, -200)
    after = snapshot()
    self.assertLess(after['boss_hp'], before['boss_hp'])
    self.assertGreater(after['score'], before['score'])
    facts.setdefault('paid_damage_calibration', []).append(dict(actor=owner, spell=6971,
        before=before, after=after, staged_events=list(runtime.fight.boss_score_events.values())))

pc2,pc4 = identities[1],identities[3]
self.assertEqual((runtime.fight.native_table_turn,runtime.fight.turn_id,runtime.fight.current.id),(5,30,pc2))
self.assertEqual(runtime.fight.actors[pc2].position,(-45,11,-4))
source_grade = holder(runtime.fight.actors[pc2],6998)[0].level
self.assertEqual(source_grade,1)
base_max = facts['drop_component_before']['players'][pc2]['maximum_ap']
self.assertEqual(runtime.fight.actors[pc2].effect_maxima[2],base_max+source_grade)
self.assertNotIn(190,runtime.fight.native_effect_areas)
self.assertNotIn(190,global_area_order(runtime.fight))
facts['resumed_before_actual_drop'] = snapshot()
cast_cell(pc2,7271,(-44,11,-4))
dropped = [row for row in runtime.fight.native_effect_areas.values()
           if row['reference']==1650 and tuple(row['cell'])==(-44,11,-4)]
self.assertEqual(len(dropped),1)
dropped = dropped[0]
self.assertEqual(dropped['owner_id'],pc2)
self.assertEqual(dropped['effect_reference'],318822)
self.assertEqual(next(entry.level for entry in dropped['state_ledger'].entries if entry.reference==7001),source_grade)
self.assertFalse(holder(runtime.fight.actors[pc2],6998))
self.assertEqual(runtime.fight.actors[pc2].effect_maxima[2],base_max)
facts['actual_drop'] = dict(uid=dropped['uid'],reference=1650,creator=318822,
    owner=pc2,cell=dropped['cell'],grade=source_grade)
move(pc2,(-45,12,-4))
advance_actual_turn(runtime)
while runtime.awaiting_ack is not None:
    runtime.acknowledge_turn(struct.pack('>i',runtime.awaiting_ack))
self.assertEqual(runtime.fight.current.id,pc4)
other_max = runtime.fight.actors[pc4].effect_maxima[2]
move(pc4,(-44,11,-4))
held = holder(runtime.fight.actors[pc4],6998)
self.assertEqual(len(held),1)
self.assertEqual((held[0].level,held[0].caster_id),(source_grade,pc2))
self.assertEqual(runtime.fight.actors[pc4].effect_maxima[2],other_max+source_grade)
self.assertNotIn(dropped['uid'],runtime.fight.native_effect_areas)
self.assertNotIn(dropped['uid'],global_area_order(runtime.fight))

facts.update(status='actual_paid_drop_recollection_without_replayed_prefix_or_attack',
    actual_recollection=dict(actor=pc4,caster=pc2,grade=held[0].level,consumed_uid=dropped['uid']),
    drop_component_after=snapshot())
"""
    ).body
    body = (
        imports
        + originals
        + observers
        + helpers
        + [ast.With(items=copy.deepcopy(original_with.items[2:]), body=actions)]
    )
    function = ast.FunctionDef(
        name="continue_drop",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=body,
        decorator_list=[],
    )
    namespace = dict(vars(recipe))
    namespace.update(checkpoint)
    facts = copy.deepcopy(checkpoint["receipt"])
    namespace.update(
        self=checkpoint["fixture"],
        facts=facts,
        seed_probe=False,
        tanks=checkpoint["identities"][:4],
        healers=checkpoint["identities"][4:],
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            __file__,
            "exec",
        ),
        namespace,
    )
    return namespace["continue_drop"], facts


class RetainedPaidDropDamage(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_native_party_phase_one")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        recipe.verify_actual_checkpoint()
        action, facts = _build(checkpoint, recipe)
        output = Path(checkpoint["receipt_path"]).with_name(
            Path(checkpoint["receipt_path"]).stem
            + "-actual-paid-drop-recollection.json"
        )
        facts.update(
            prefix_receipt=checkpoint["continuation_receipt_path"],
            status="pending_actual_drop",
        )
        for key in ("error", "error_type", "traceback"):
            facts.pop(key, None)
        try:
            action()
        except Exception as error:
            facts.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            facts[
                "loaded_implementation_attestation"
            ] = recipe.verify_actual_checkpoint()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
            checkpoint["receipt"] = facts
            checkpoint["continuation_receipt_path"] = str(output)


def qualify():
    return unittest.TestSuite([RetainedPaidDropDamage()])
