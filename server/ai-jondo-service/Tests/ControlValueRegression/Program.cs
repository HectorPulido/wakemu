using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0), new CellXYZ(2, 0, 0) },
    new[] { (0, 1), (1, 0), (1, 2), (2, 1) }));
var caster = new Fighter { Id = 1, TeamId = 0, CellId = 0, CurrentHP = 100, MaxHP = 100,
    CurrentAP = 6, MaxAP = 6 };
var target = new Fighter { Id = 2, TeamId = 1, CellId = 1, CurrentHP = 100, MaxHP = 100,
    CurrentAP = 6, MaxAP = 6, CurrentMP = 3, MaxMP = 3 };
var board = new MonsterTactics.Board { Fighters = new[] { caster, target } };

foreach (var (kind, held, weight) in new[] { ("remove_ap", 6, 55), ("remove_mp", 3, 30) })
{
    double Value(int amount, bool summoned)
    {
        target.Invocador = summoned ? 99 : 0;
        var spell = new MonsterTactics.Spell { Id = 1, Grade = 1, Cost = 2, MinRange = 1,
            MaxRange = 1, Rows = new[] { SemanticRows.Create(kind, amount, "enemy") } };
        return MonsterTactics.ValueOfRows(board, spell, caster, 0, 1, new List<Fighter> { target });
    }
    var normal = Value(100, false);
    var summon = Value(100, true);
    if (normal != held * weight || summon != normal / 2)
        throw new Exception($"{kind}: expected regular {held * weight} and summon {held * weight / 2.0}; got {normal} and {summon}");
    if (Value(1, true) != weight / 2.0)
        throw new Exception($"{kind}: low withdrawal must keep summon discount");
    if (Value(held, true) != held * weight / 2.0)
        throw new Exception($"{kind}: exact withdrawal must keep summon discount");
    if (kind == "remove_ap") target.CurrentAP = target.MaxAP = 0;
    else target.CurrentMP = target.MaxMP = 0;
    if (Value(100, false) != 0 || Value(100, true) != 0)
        throw new Exception($"{kind}: zero-resource actors must not earn withdrawal utility");
    Console.WriteLine("PASS: " + kind);
}

target.CurrentAP = target.MaxAP = 6;
target.CurrentMP = target.MaxMP = 3;
target.Invocador = 0;
foreach (var (kind, held, weight) in new[] { ("remove_ap", 6, 55), ("remove_mp", 3, 30) })
{
    var spell = new MonsterTactics.Spell { Id = 2, Grade = 1, Cost = 2, MinRange = 1,
        MaxRange = 1, Rows = new[] { SemanticRows.Create(kind, held, "enemy"),
                                    SemanticRows.Create(kind, held, "enemy") } };
    double actual = MonsterTactics.ValueOfRows(board, spell, caster, 0, 1, new List<Fighter> { target });
    if (actual != held * weight)
        throw new Exception($"{kind}: two guaranteed immediate withdrawals must not exceed the target's resource pool; got {actual}");
}
Console.WriteLine("PASS: multiple control rows remain bounded by target resources");

var half = SemanticRows.Create("remove_ap", 6, "enemy");
SemanticRows.WithControlEvidence(half, 0.5, false);
var conditional = SemanticRows.Create("remove_ap", 6, "enemy");
SemanticRows.WithControlEvidence(conditional, 1, true);
var never = SemanticRows.Create("remove_ap", 6, "enemy");
SemanticRows.WithControlEvidence(never, 0, false);
var guaranteed = SemanticRows.Create("remove_ap", 6, "enemy");
SemanticRows.WithControlEvidence(guaranteed, 1, false);
MonsterTactics.Spell Single(SpellEffect row) => new() { Id=3, Grade=1, Cost=2, MinRange=1, MaxRange=1, Rows=new[] { row } };
double Score(SpellEffect row) => MonsterTactics.ValueOfRows(board, Single(row), caster, 0, 1, new List<Fighter> { target });
if (Score(half) != 165 || Score(conditional) != 0 || Score(never) != 0 || Score(guaranteed) != 330)
    throw new Exception("Control scoring must retain native probability and treat unknown conditions as unknown");
foreach (var row in new[] { half, conditional, never })
{
    var spell = Single(row);
    var action = new MonsterTactics.Action(new[] { 0 }, spell, target, 1, 1, 1, 6, 0);
    using (MonsterTactics.Simulation.Replay(board, caster, new[] { action }))
        if (target.CurrentAP != 6) throw new Exception("Uncertain control cannot become a guaranteed replay mutation");
    if (target.CurrentAP != 6) throw new Exception("Replay must restore source control state");
}
Console.WriteLine("PASS: uncertain control is weighted without inventing guaranteed replay outcomes");

var other = new Fighter { Id=3, TeamId=1, CellId=2, CurrentHP=100, MaxHP=100, CurrentAP=2, MaxAP=2 };
var areaBoard = new MonsterTactics.Board { Fighters = new[] { caster, target, other } };
var areaSpell = new MonsterTactics.Spell { Id=4, Grade=1, Cost=2, MinRange=1, MaxRange=1,
    Rows = new[] { SemanticRows.Create("remove_ap", 6, "enemy", fixedCells: new[] { 1, 2 }),
                   SemanticRows.Create("remove_ap", 6, "enemy", fixedCells: new[] { 1, 2 }) } };
double areaValue = MonsterTactics.ValueOfRows(areaBoard, areaSpell, caster, 0, 1, new List<Fighter> { target, other });
if (areaValue != (6 + 2) * 55)
    throw new Exception($"Resource budgets must be tracked separately for each actor: {areaValue}");
var interrupted = new MonsterTactics.Spell { Id=5, Grade=1, Cost=2, MinRange=1, MaxRange=1,
    Rows = new[] { SemanticRows.Create("remove_ap", 6, "enemy"), SemanticRows.Create("gain_ap", 6, "enemy"),
                   SemanticRows.Create("remove_ap", 6, "enemy") } };
double interruptedValue = MonsterTactics.ValueOfRows(board, interrupted, caster, 0, 1, new List<Fighter> { target });
if (interruptedValue != 330)
    throw new Exception($"An intervening gain must stop shared removal budgeting: {interruptedValue}");
Console.WriteLine("PASS: per-target budgets and intervening resource gains");
