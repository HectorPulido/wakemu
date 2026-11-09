using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0) },
    new[] { (0,1), (1,0) }));
var actor = new Fighter { Id=1, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
    CurrentAP=3, MaxAP=3, CurrentMP=0, MaxMP=0 };
var enemy = new Fighter { Id=2, TeamId=1, CellId=1, CurrentHP=1000, MaxHP=1000,
    CurrentMP=3, MaxMP=3 };
var board = new MonsterTactics.Board { Fighters=new[] { actor, enemy },
    Walkable=_=>true, Sees=(_,_)=>true };
var enemies = new List<Fighter> { enemy };
var allies = new List<Fighter> { actor };
SpellEffect Row(double probability, bool conditional)
{
    var row = SemanticRows.Create("damage", 80, "enemy");
    SemanticRows.WithApplicationEvidence(row, probability, conditional);
    return row;
}
MonsterTactics.Spell Spell(SpellEffect row) => new() { Id=1, Grade=1, Cost=3,
    MinRange=1, MaxRange=1, Damage=80, Rows=new[] { row } };
double Score(SpellEffect row) => MonsterTactics.ValueOfCast(board, Spell(row),
    actor, 0, 1, enemies, allies, enemy);
var certain = Row(1, false);
var quarter = Row(.25, false);
var conditional = Row(1, true);
var never = Row(0, false);
double baseline = Score(certain);
if (!(baseline > 0) || Math.Abs(Score(quarter) - baseline * .25) > 1e-8
    || Score(conditional) != 0 || Score(never) != 0)
    throw new Exception("Classic health rows must respect native probability and unknown conditions");
double Future(SpellEffect row)
{
    using var sim = MonsterTactics.Simulation.Replay(board, actor, Array.Empty<MonsterTactics.Action>());
    return MonsterTactics.NextBlow(sim, actor, new[] { Spell(row) }, uncapped:true);
}
if (Math.Abs(Future(quarter) - Future(certain) * .25) > 1e-8 || Future(conditional) != 0)
    throw new Exception("Future damage must not assume uncertain legacy health rows are guaranteed");
var legacy = SemanticRows.Create("damage", 80, "enemy");
if (Math.Abs(Score(legacy)-baseline) > 1e-8)
    throw new Exception("Rows without native probability evidence must retain legacy behavior");
Console.WriteLine("PASS classic health chance, conditions, next-turn forecast, and legacy fallback");
