"""Focused installed-family877 reachability and real common-entry audit."""
import sys,json,random,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_active_spells as audit
from wakfu_server.combat_server_spell import prepare_server_initialization,prepare_server_spell,prewarm_runtime_catalogs
from wakfu_server.spells import SPELLS,encode_deck
from wakfu_server.combat_parameters import parameter_value
from wakfu_server.fight_checkpoint_store import snapshot

before=audit.init.source_hashes();spells=audit.catalog();states=audit.states_catalog()
effects={**spells['effects'],**states['effects']}
family={int(k) for k,v in effects.items() if v['effect_class']==877}
reverse={}
for k,v in effects.items():
 for child in v.get('children',[]):reverse.setdefault(int(child),set()).add(int(k))
 if v['effect_class'] in (304,350) and len(v['parameters'])>=2:
  # Evaluate all legal parent levels; do not infer a fixed reference from raw floats.
  refs={((parameter_value(v['parameters'],0,l)+32768)%65536)-32768 for l in range(1,201)}
  for ref in refs:
   state=states['states'].get(str(ref))
   if state:
    for child in state['effect_ids']:reverse.setdefault(int(child),set()).add(int(k))
reachable=set(family);pending=list(family)
while pending:
 for parent in reverse.get(pending.pop(),()):
  if parent not in reachable:reachable.add(parent);pending.append(parent)
names={r['id']:r['name'] for r in json.load(open('server/protocol/spell-names.json'))['spells']}
users=[]
for key,v in spells['spells'].items():
 if any(int(c) in reachable for row in v['levels'] for c in row[2]):
  owned=SPELLS.get(int(key),{})
  users.append(dict(id=int(key),name=names.get(int(key)),breed=owned.get('breed'),kind=owned.get('kind'),unlock_level=owned.get('unlock_level')))
innates=[]
for breed,definition in audit.BREEDS.items():
 for innate in definition['innate_states']:
  state=states['states'].get(str(innate['reference']))
  if state and any(int(c) in reachable for c in state['effect_ids']):
   innates.append(dict(breed=breed,state_id=innate['reference'],state_name=state.get('name')))
# Sangre also reaches877 through the class innate/event tree, not its cast tree.
if any(r['breed']==11 for r in innates) and not any(r['id']==5028 for r in users):
 owned=SPELLS[5028]
 users.append(dict(id=5028,name=names.get(5028),breed=11,kind=owned['kind'],unlock_level=owned['unlock_level'],reachability='through_installed_innate'))
print('USERS',json.dumps(users),flush=True)
prewarm_runtime_catalogs()
origin=(-8,-7,-1);terrain=audit.bounded_arena(audit.map_geometry(1134),origin,[(-7,-7,-1)],radius=12)
rows=[]
for user in users:
 if user['breed'] not in audit.BREEDS:continue
 for level in sorted({max(1,user['unlock_level']),200}):
  definition=spells['spells'][str(user['id'])]
  variants=audit.target_candidates(definition,level,terrain,origin) if user['kind']=='active' else [('initialization',(-7,-7,-1))]
  for variant,cell in variants:
   enemy_cell=cell if variant=='enemy' else next(c for c in sorted(terrain['cells']) if c not in (origin,cell))
   char,mob,base=audit.fixture(user['breed'],level,enemy_cell,terrain,origin)
   deck=encode_deck([user['id']] if user['kind']=='active' else [],[user['id']] if user['kind']=='passive' else [])
   row=dict(spell_id=user['id'],name=user['name'],breed=user['breed'],level=level,variant=variant,gameplay_verified=False)
   initial=snapshot(base);original=None;fight=None
   try:
    fight,packets=prepare_server_initialization(char,{-7:mob},base,3,deck,action_id=1,rng=random.Random(1))
    assert snapshot(base)==initial
    if user['kind']=='active':
     while fight.current.id!=7:fight.end_server_turn(fight.current.id,fight.turn_id)
     original=snapshot(fight)
     result=prepare_server_spell(struct.pack('>qqiih',7,(7<<32)|user['id'],*cell),char,{-7:mob},fight,3,deck,action_id=2,critical=False,rng=random.Random(1),line_of_sight=lambda a,b,p:audit.authoritative_visible(1134,a,b,p,blocking_footprints={x.id:{x.position[:2]} for x in p.actors.values() if x.hp>0}))
     assert snapshot(fight)==original
     row['status']='returned';row['packet_count']=len(result.packets)
    else:row.update(status='initialized',packet_count=len(packets))
   except ValueError as error:row.update(status='rejected',reason=str(error))
   row['rollback_preserved']=snapshot(base)==initial and (original is None or snapshot(fight)==original)
   rows.append(row);print(json.dumps(row),flush=True)
report=dict(effect_class=877,definitions=sorted(family),reachable_spell_users=users,innate_users=innates,cases=rows,sources_stable=before==audit.init.source_hashes(),gameplay_verified=False,note='Reachability includes nested state definitions; criteria/events may prevent a877 execution in a successful cast.')
Path('docs/reports/combat-inventory/minimum-resource-877-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print('FINAL',len(rows),report['sources_stable'],flush=True)
