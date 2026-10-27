using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

if (args.SequenceEqual(new[]{"--general-effects-only"}))
{
    Console.WriteLine($"{GeneralEffectCases.Run()} general effect checks passed");
    return;
}

if (args.SequenceEqual(new[]{"--directional-geometry-only"}))
{
    Console.WriteLine($"{DirectionalAreaCases.Run(geometryOnly:true)} pure directional geometry checks passed");
    return;
}

if (args.SequenceEqual(new[]{"--directional-only"}))
{
    Console.WriteLine($"{DirectionalAreaCases.Run()} directional geometry checks passed");
    return;
}

if (args.SequenceEqual(new[]{"--hazard-only"}))
{
    Console.WriteLine($"{HazardRouteCases.Run()} hazard checks passed");
    return;
}

if (args.SequenceEqual(new[]{"--search-quality-only"}))
{
    Console.WriteLine($"{SearchQualityCases.Run()} search-quality checks passed");
    return;
}
if (args.SequenceEqual(new[]{"--queue-only"}))
{
    Console.WriteLine($"{PlanningGateCases.Run()+PlannerDeadlineCases.Run()} queue/deadline checks passed");
    return;
}
if (args.SequenceEqual(new[]{"--aoe-only"}))
{
    Console.WriteLine($"{AoeQualityCases.Run()} area-quality checks passed");
    return;
}

int checks = 0;
void Check(bool value,string name)
{
    if (!value) throw new Exception("FAIL: "+name);
    checks++; Console.WriteLine("PASS: "+name);
}
Fighter Fighter(long id,int team,int cell,int hp=100,int ap=6,int mp=3) => new()
{
    Id=id,TeamId=team,CellId=cell,CurrentHP=hp,MaxHP=100,
    CurrentAP=ap,MaxAP=ap,CurrentMP=mp,MaxMP=mp,Level=10,IsMonster=true,
};
using var geometry=MapGeometry.BeginScope(new GeometryContext(
    Enumerable.Range(0,5).Select(x=>new CellXYZ(x,0,0)).ToArray(),
    Enumerable.Range(0,4).SelectMany(x=>new[]{(x,x+1),(x+1,x)})));
var bot=Fighter(1,0,0);
var enemy=Fighter(2,1,3,40);
var board=new MonsterTactics.Board{Fighters=new[]{bot,enemy},Walkable=_=>true,Sees=(_,_)=>true};
var hit=new MonsterTactics.Spell
{
    Id=1,Grade=1,Cost=3,MinRange=1,MaxRange=1,Damage=20,
    Rows=new[]{SemanticRows.Create("damage",20,"enemy")},
};
var plan=MonsterTactics.PlanTurn(board,bot,new[]{hit},budgetMs:1000);
Check(plan.Count>0,"literal PlanTurn produces an attack plan");
Check(plan[0].Path.SequenceEqual(new[]{0,1,2}),"native directed topology gives complete move-attack prefix");
Check(bot.CellId==0 && bot.CurrentHP==100 && bot.CurrentAP==6 && bot.CurrentMP==3 && enemy.CurrentHP==40,
      "planning rewinds private fighter state");
using(var sim=MonsterTactics.Simulation.Replay(board,bot,plan))
{
    Check(enemy.CurrentHP==0,"literal multi-action replay applies the full damage sequence");
}
Check(enemy.CurrentHP==40 && bot.CellId==0,"damage replay disposal restores the complete source");

bot=Fighter(1,0,0,100,6,0);enemy=Fighter(2,1,1,100);
board=new MonsterTactics.Board{Fighters=new[]{bot,enemy},Walkable=_=>true,Sees=(_,_)=>true};
var setup=new MonsterTactics.Spell
{
    Id=2,Grade=1,Cost=2,MinRange=0,MaxRange=0,Buff=4,
    Rows=new[]{SemanticRows.Create("gain_ap",4,"self")},
};
var heavy=new MonsterTactics.Spell
{
    Id=3,Grade=1,Cost=4,MinRange=1,MaxRange=1,Damage=30,
    Rows=new[]{SemanticRows.Create("damage",30,"enemy")},
};
plan=MonsterTactics.PlanTurn(board,bot,new[]{heavy,setup},budgetMs:1000);
Console.WriteLine("Preparation plan: "+string.Join(',',plan.Select(a=>a.Spell.Id)));
Check(plan.Count>=3 && plan[0].Spell.Id==2 && plan.Count(a=>a.Spell.Id==3)==2,
      "literal beam retains AP preparation for two subsequent attacks");

var ally=Fighter(3,0,1,20);bot=Fighter(1,0,0,100,6,0);enemy=Fighter(2,1,4,100);
board=new MonsterTactics.Board{Fighters=new[]{bot,ally,enemy},Walkable=_=>true,Sees=(_,_)=>true};
var heal=new MonsterTactics.Spell
{
    Id=4,Grade=1,Cost=2,MinRange=1,MaxRange=3,Heal=25,
    Rows=new[]{SemanticRows.Create("heal",25,"ally")},
};
var healing=new MonsterTactics.Action(new[]{0},heal,ally,1,25,25,6,0);
using(var sim=MonsterTactics.Simulation.Replay(board,bot,new[]{healing}))
    Check(ally.CurrentHP==45,"normalized healing row is applied by the unchanged simulation");
Check(ally.CurrentHP==20 && bot.CurrentAP==6,"healing and resource mutations rewind");
try {SemanticRows.Create("unknown_wakfu_effect",1,"enemy");throw new Exception("Unknown semantic accepted");}
catch(NotSupportedException){Check(true,"unprojected effects cannot masquerade as numeric Dofus IDs");}
var zone=SemanticRows.WithOffsets(SemanticRows.Create("damage",10,"enemy"),new[]{(0,0),(1,0)});
Check(EffectEngine.CasillasDelEfecto(zone,0,1).SequenceEqual(new[]{1,2}),
      "native area offsets resolve at each aimed cell");
Check(EffectEngine.CasillasDelEfecto(zone,0,3).SequenceEqual(new[]{3,4}),
      "area projection is not frozen to the first target");
using(SpellEffects.BeginScope(new(){[(9,1)]=new[]{zone}}))
{
    Check(SpellEffects.De(9,1).Count==1,"request-scoped semantic rows are visible inside the request");
    using(SpellEffects.BeginScope(new()))
        Check(SpellEffects.De(9,1).Count==0,"nested request cannot see another request's spell rows");
    Check(SpellEffects.De(9,1).Count==1,"nested semantic scope restores its caller");
}
Check(SpellEffects.De(9,1).Count==0,"semantic rows are removed when request ends");
checks += HostProjectionCases.Run();
checks += HazardRouteCases.Run();
checks += SpecificAiCases.Run();
checks += NativeElementCases.Run();
checks += FootprintCases.Run();
checks += PlanningGateCases.Run();
checks += PlannerDeadlineCases.Run();
checks += NativeSupportCases.Run();
checks += SearchQualityCases.Run();
checks += AoeQualityCases.Run();
checks += DirectionalAreaCases.Run();
checks += GeneralEffectCases.Run();
Console.WriteLine($"{checks} checks passed");
