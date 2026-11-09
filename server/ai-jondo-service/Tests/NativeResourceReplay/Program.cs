using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

void Check(bool condition, string name)
{
    if (!condition) throw new Exception("FAIL: " + name);
    Console.WriteLine("PASS: " + name);
}

var cells = new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0) };
using var geometry = MapGeometry.BeginScope(new GeometryContext(cells, new[] { (0, 1), (1, 0) }));
var bot = new Fighter { Id = 1, TeamId = 1, CellId = 0, CurrentHP = 100, MaxHP = 100,
    CurrentAP = 6, MaxAP = 6, CurrentMP = 2, MaxMP = 2, NativeCurrentWp = 2 };
var enemy = new Fighter { Id = 2, TeamId = 2, CellId = 1, CurrentHP = 100, MaxHP = 100 };
var spell = new MonsterTactics.Spell { Id = 7, Grade = 1, Cost = 2, MinRange = 1, MaxRange = 1 };
var board = new MonsterTactics.Board { Fighters = new[] { bot, enemy },
    SpellMovementCost = _ => 1, SpellWakfuCost = _ => 1 };
var first = new MonsterTactics.Action(new[] { 0 }, spell, enemy, 1, 1, ActionPoints: 6, MovementPoints: 2);
using (var outer = MonsterTactics.Simulation.Replay(board, bot, new[] { first }))
{
    Check(bot.CurrentAP == 4 && bot.CurrentMP == 1 && bot.NativeCurrentWp == 1,
        "first simulated cast pays its AP, MP and WP");
    var second = new MonsterTactics.Action(new[] { 0 }, spell, enemy, 1, 1, ActionPoints: 4, MovementPoints: 1);
    using (var inner = MonsterTactics.Simulation.Replay(outer.Board, bot, new[] { second }))
        Check(bot.CurrentAP == 2 && bot.CurrentMP == 0 && bot.NativeCurrentWp == 0,
            "second simulated cast pays remaining resources");
    Check(bot.CurrentAP == 4 && bot.CurrentMP == 1 && bot.NativeCurrentWp == 1,
        "nested replay restores its parent's resources");
}
Check(bot.CurrentAP == 6 && bot.CurrentMP == 2 && bot.NativeCurrentWp == 2,
    "disposing replay restores authoritative resources");
bot.NativeCurrentWp = null;
using (var replay = MonsterTactics.Simulation.Replay(board, bot, new[] { first }))
    Check(bot.NativeCurrentWp is null, "missing WP evidence remains unknown");
Check(bot.NativeCurrentWp is null && bot.CurrentMP == 2, "unknown WP survives replay cleanup");
