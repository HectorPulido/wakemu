using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(2,0,0), new CellXYZ(3,0,0) },
    new[] { (0,1), (1,0), (1,2), (2,1), (2,3), (3,2) }));
var owner = new Fighter { Id=1,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100 };
var summon = new Fighter { Id=2,TeamId=0,CellId=1,CurrentHP=100,MaxHP=100,
    Invocador=1,CurrentAP=6,MaxAP=6,CurrentMP=0,MaxMP=0 };
var enemy = new Fighter { Id=3,TeamId=1,CellId=2,CurrentHP=100,MaxHP=100 };
var spells = new List<MonsterTactics.Spell>();
bool available = true;
bool? castAllowed = true, damagePossible = true, sightVisible = true;
IReadOnlyList<int> reachableOrigins = Array.Empty<int>();
var board = new MonsterTactics.Board { Fighters=new[]{owner,summon,enemy},
    SpellsOf=f=>f.Id==summon.Id?spells:new(), SearchContinues=()=>available,
    SummonCastCriterion=(_,_,_,_)=>castAllowed,
    SummonDamageEvidence=(_,_,_,_)=>damagePossible,
    SummonSightEvidence=(_,_,_)=>sightVisible,
    SummonReachableOrigins=_=>reachableOrigins };
MonsterTactics.Spell Hit(int perTurn=0,int perTarget=0,int interval=0,int maxRange=1,bool lineOfSight=false) =>
    new(){Id=100,Grade=1,Cost=3,MinRange=1,Damage=20,
        PerTurn=perTurn,PerTarget=perTarget,Interval=interval,NeedsLineOfSight=lineOfSight,
        MaxRange=maxRange};
double Forecast(params MonsterTactics.Spell[] candidates)
{
    spells.Clear(); spells.AddRange(candidates);
    using var sim=MonsterTactics.Simulation.Replay(board,owner,Array.Empty<MonsterTactics.Action>());
    return MonsterTactics.SummonsNextTurn(sim,owner);
}
void Check(double expected,double actual,string name)
{
    if(Math.Abs(expected-actual)>0.00001)throw new Exception($"{name}: {actual} != {expected}");
    Console.WriteLine("PASS: "+name);
}
Check(20,Forecast(Hit()),"one witnessed cast is credited without assuming repeats");
var free7969 = new MonsterTactics.Spell { Id=7969, Grade=1, Cost=0, MinRange=2, MaxRange=16, Damage=25 };
enemy.CellId=3;
Check(25,Forecast(free7969),"certified free native spell 7969 is credited once");
summon.MaxAP=0;
Check(25,Forecast(free7969),"certified free spell7969 remains usable with zero summon AP");
summon.MaxAP=6;
var otherFree = new MonsterTactics.Spell { Id=7970, Grade=1, Cost=0, MinRange=2, MaxRange=16, Damage=20 };
Check(25,Forecast(free7969,otherFree),"one certified free summon action is credited across multiple free spells");
var negativeFree = new MonsterTactics.Spell { Id=7971, Grade=1, Cost=-1, MinRange=2, MaxRange=16, Damage=100 };
Check(25,Forecast(free7969,negativeFree),"certified summon forecast rejects a negative-cost spell");
summon.Recarga[7969]=2;
Check(20,Forecast(free7969,otherFree),"free spell cooldown beyond next turn excludes only that spell");
summon.Recarga[7969]=1;
Check(25,Forecast(free7969,otherFree),"free spell remains available when its cooldown expires next turn");
summon.Recarga.Clear();
enemy.CellId=2;
castAllowed=null;
Check(0,Forecast(Hit()),"unknown summon cast criterion is not credited");
castAllowed=false;
Check(0,Forecast(Hit()),"rejected summon cast criterion is not credited");
castAllowed=true;
damagePossible=null;
Check(0,Forecast(Hit()),"unknown summon damage evidence is not credited");
damagePossible=false;
Check(0,Forecast(Hit()),"rejected summon damage evidence is not credited");
damagePossible=true;
Check(20,Forecast(Hit()),"positive summon damage evidence credits one cast");
Check(20,Forecast(Hit(perTurn:1)),"per-turn cap does not reduce the witnessed cast");
Check(20,Forecast(Hit(perTarget:1)),"per-target cap does not reduce the witnessed cast");
Check(20,Forecast(Hit(interval:1)),"interval still allows the witnessed first cast");
summon.Recarga[100]=2;
Check(0,Forecast(Hit()),"cooldown extending beyond the next turn");
summon.Recarga[100]=1;
Check(20,Forecast(Hit()),"cooldown expiring before the next turn");
summon.Recarga.Clear();
available=false;
Check(0,Forecast(Hit()),"forecast stops when search budget is exhausted");
available=true;
// Native LOS must be positively observed even at distance one; missing
// evidence is not treated as visible.
enemy.CellId=0;
var adjacentLos=Hit(lineOfSight:true);
sightVisible=true;
Check(20,Forecast(adjacentLos),"visible LOS supports adjacent summon cast");
sightVisible=false;
Check(0,Forecast(adjacentLos),"blocked LOS rejects adjacent summon cast");
sightVisible=null;
Check(0,Forecast(adjacentLos),"unknown LOS rejects adjacent summon cast");
sightVisible=true;
enemy.CellId=3;
var losSpell=Hit(maxRange:2,lineOfSight:true);
sightVisible=true;
Check(20,Forecast(losSpell),"visible summon LOS is credited");
sightVisible=false;
Check(0,Forecast(losSpell),"blocked summon LOS is rejected");
sightVisible=null;
Check(0,Forecast(losSpell),"unknown summon LOS is not credited");
sightVisible=true;
// Without certified movement origins, an out-of-range cast stays out of range.
var shortSpell=Hit();
Check(0,Forecast(shortSpell),"future movement origin is not invented");
reachableOrigins=new[]{2};
Check(20,Forecast(shortSpell),"certified future origin enables the in-range cast");
Check(1,summon.CellId,"certified future origin does not mutate summon position");
reachableOrigins=Array.Empty<int>();
summon.JuegaTurno=false;
Check(0,Forecast(Hit()),"a summon without its own turn is not credited");
summon.JuegaTurno=true;
summon.Invocador=9;
Check(0,Forecast(Hit()),"another owner's summon is not credited");
summon.Invocador=1;
summon.NativeRegisteredSummon=false;
Check(0,Forecast(Hit()),"stale owner does not override native non-summon evidence");
summon.NativeRegisteredSummon=null;
spells.Clear();
using(var sim=MonsterTactics.Simulation.Replay(board,owner,Array.Empty<MonsterTactics.Action>()))
    Check(0,MonsterTactics.SummonsNextTurn(sim,owner),"no forecast from an absent spellbook");

// A past, still-owned spell is explicitly a discounted estimate, never a
// native cast receipt. It uses only the summon\u0027s present origin.
spells.Add(Hit(maxRange:2));
var estimatedBoard = new MonsterTactics.Board { Fighters=new[]{owner,summon,enemy},
    SummonEstimatedSpellsOf=f=>f.Id==summon.Id?spells:Array.Empty<MonsterTactics.Spell>() };
using(var sim=MonsterTactics.Simulation.Replay(estimatedBoard,owner,Array.Empty<MonsterTactics.Action>()))
    Check(5,MonsterTactics.EstimatedSummonsNextTurn(sim,owner),"previous owned spell gives a discounted estimate");
enemy.CellId=3;
spells.Clear(); spells.Add(Hit(maxRange:1));
using(var sim=MonsterTactics.Simulation.Replay(estimatedBoard,owner,Array.Empty<MonsterTactics.Action>()))
    Check(0,MonsterTactics.EstimatedSummonsNextTurn(sim,owner),"estimate does not invent summon movement");
enemy.CellId=3;
summon.MaxAP=0;
spells.Clear();
spells.Add(new MonsterTactics.Spell{Id=7969,Grade=1,Cost=0,MinRange=2,MaxRange=16,Damage=25});
using(var sim=MonsterTactics.Simulation.Replay(estimatedBoard,owner,Array.Empty<MonsterTactics.Action>()))
    Check(6.25,MonsterTactics.EstimatedSummonsNextTurn(sim,owner),"profile5522 free spell7969 contributes exactly one discounted forecast cast");
spells.Add(new MonsterTactics.Spell{Id=7970,Grade=1,Cost=-1,MinRange=2,MaxRange=16,Damage=100});
using(var sim=MonsterTactics.Simulation.Replay(estimatedBoard,owner,Array.Empty<MonsterTactics.Action>()))
    Check(6.25,MonsterTactics.EstimatedSummonsNextTurn(sim,owner),"negative-cost estimate is excluded while the free spell remains usable");
