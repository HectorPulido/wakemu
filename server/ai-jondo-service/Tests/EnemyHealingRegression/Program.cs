using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(2,0,0), new CellXYZ(3,0,0) },
    new[] { (0,1), (1,0), (1,2), (2,1), (2,3), (3,2) }));
var bot = new Fighter { Id=1, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100, CurrentAP=6, MaxAP=6 };
var enemy = new Fighter { Id=2, TeamId=1, CellId=1, CurrentHP=90, MaxHP=100 };
var other = new Fighter { Id=3, TeamId=1, CellId=2, CurrentHP=70, MaxHP=100 };
var ally = new Fighter { Id=4, TeamId=0, CellId=3, CurrentHP=50, MaxHP=100 };
var actors = new[] {bot,enemy,other,ally};
foreach (var actor in actors)
{
    actor.NativeHpMinimum=0; actor.NativeHpFrozen=false; actor.NativeHpRawMode="bounded";
    actor.NativeUndead=false; actor.NativeIsCarried=false; actor.NativeHealingResistanceEnabled=false;
    actor.NativeHealingResistanceMinimum=0; actor.NativeHealingResistanceMaximum=1000;
    actor.NativeHealingResistanceFrozen=false; actor.NativeVirtualHpFrozen=false;
    actor.NativeStats=new Dictionary<int,int>{{87,0},{32,0}};
    actor.NativeArmorAuthority=new NativePoolAuthority(0,int.MaxValue,false);
    actor.NativeBarrierAuthority=new NativePoolAuthority(0,int.MaxValue,false);
    actor.NativeVirtualHpAuthority=new NativePoolAuthority(0,0,false);
}
var board = new MonsterTactics.Board { Fighters=actors, Walkable=_=>true, Sees=(_,_)=>true,
    Reach=(row,caster,from,aim)=>row.TargetMask == "a" ? new[] {ally} : new[] {enemy,other} };
var healEnemy = SemanticRows.Create("heal", 50, "enemy");
var healAlly = SemanticRows.Create("heal", 20, "ally");
var enemies = new List<Fighter>{enemy,other};
var allies = new List<Fighter>{bot,ally};
double Score(params SpellEffect[] rows) => MonsterTactics.ValueOfCast(board,
    new MonsterTactics.Spell { Id=41, Grade=1, Cost=3, MinRange=1, MaxRange=1, Rows=rows },
    bot,0,1,enemies,allies,enemy);
void Check(double actual,double expected,string name)
{
    if (Math.Abs(actual-expected)>1e-8) throw new Exception($"{name}: expected {expected}, got {actual}");
}
Check(Score(healEnemy,healEnemy), -40, "enemy healing is capped independently per target");
Check(Score(healEnemy,healEnemy,healAlly,healAlly), 0, "ally and enemy healing share correct caps");
var nativeHealEnemy = SemanticRows.Create("heal", 50, "enemy", nativeCoefficientMask:0);
NativeEffectAmounts.Bind(nativeHealEnemy, 0, 50, 1);
Check(Score(nativeHealEnemy,nativeHealEnemy), -40, "native healing rows respect each target's missing HP");
enemy.CurrentHP=50; other.CurrentHP=100; ally.CurrentHP=90;
Check(Score(healEnemy,healEnemy,healAlly,healAlly), -40, "caps adapt to current HP");
enemy.CurrentHP=100;
enemy.NativeVirtualHpMax=50;
enemy.NativeVirtualHpAuthority=new NativePoolAuthority(0,50,false);
enemy.NativeStats=new Dictionary<int,int>{{87,0},{32,0},{92,0}};
Check(Score(nativeHealEnemy), -50, "native healing of enemy virtual HP is not ignored");
Check(Score(nativeHealEnemy,nativeHealEnemy), -50, "native enemy virtual healing is capped across rows");
Check(Score(healEnemy), 0, "legacy enemy healing does not invent virtual restoration");
enemy.NativeStats=new Dictionary<int,int>{{87,0},{32,0},{92,30}};
Check(Score(nativeHealEnemy), -20, "native enemy virtual healing is capped by the remaining pool");
enemy.NativeVirtualHpAuthority=new NativePoolAuthority(0,50,true);
enemy.NativeVirtualHpFrozen=true;
Check(Score(nativeHealEnemy), 0, "frozen enemy virtual HP cannot be healed");
if (enemy.CurrentHP!=100 || other.CurrentHP!=100 || ally.CurrentHP!=90)
    throw new Exception("Scoring changed the source fight");
Console.WriteLine("PASS enemy healing capped across rows and targets without source mutation");
