"""Offline immutable-catalogue and ordinary cast timings; no session/DB writes."""
import cProfile,json,pstats,random,struct,time
import audit_active_spells as audit
from wakfu_server.combat_server_spell import prepare_server_spell,prepare_server_initialization
from wakfu_server.spells import encode_deck
from wakfu_server.combat_los import authoritative_visible

geometry=audit.map_geometry(1134)
origin=(-8,-7,-1);target=(-9,-7,-1)
terrain=audit.bounded_arena(geometry,origin,[target],radius=12)
character,monster,fight=audit.fixture(11,20,target,terrain,origin)
deck=encode_deck([5038],[],-1)
profile=cProfile.Profile();profile.enable()
start=time.perf_counter()
fight,_=prepare_server_initialization(character,{-7:monster},fight,3,deck,action_id=1,rng=random.Random(1))
print('initialization_seconds',time.perf_counter()-start,flush=True)
while fight.current.id!=7:fight.end_server_turn(fight.current.id,fight.turn_id)
for i in range(3):
 start=time.perf_counter()
 try:
  result=prepare_server_spell(struct.pack('>qqiih',7,(7<<32)|5038,*target),character,{-7:monster},fight,3,deck,action_id=2,critical=False,rng=random.Random(1),line_of_sight=lambda a,b,p:authoritative_visible(1134,a,b,p,blocking_footprints={x.id:{x.position[:2]} for x in p.actors.values() if x.hp>0}))
  print('cast',i,'seconds',time.perf_counter()-start,'packets',len(result.packets),flush=True)
 except ValueError as error:print('rejection',str(error),'seconds',time.perf_counter()-start,flush=True)
profile.disable();pstats.Stats(profile).sort_stats('cumtime').print_stats(25)
