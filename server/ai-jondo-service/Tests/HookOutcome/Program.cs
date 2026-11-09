using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0) },
    new[] { (0, 1), (1, 0) }));
var bot = new Fighter { Id = 1, TeamId = 0, CellId = 0, CurrentHP = 100, MaxHP = 100 };
var enemy = new Fighter { Id = 2, TeamId = 1, CellId = 1, CurrentHP = 100, MaxHP = 100 };
var board = new MonsterTactics.Board { Fighters = new[] { bot, enemy }, Walkable = _ => true, Sees = (_, _) => true };
bot.Buffs.ActiveSpells.Add(new Buffs.ActiveSpell { Hechizo = 911, Grado = 1, Lanzador = bot.Id });
var selfDamage = new SpellEffect { EffectId = 100, DiceNum = 30, DiceSide = 30, TargetMask = "C", Triggers = "TE" };
var enemyDamage = new SpellEffect { EffectId = 100, DiceNum = 20, DiceSide = 20, TargetMask = "A", Triggers = "TE", Forma = 'C', Tamano = 1 };
using var effects = SpellEffects.BeginScope(new() { [(911, 1)] = new[] { selfDamage, enemyDamage } });
using (var sim = MonsterTactics.Simulation.Replay(board, bot, Array.Empty<MonsterTactics.Action>()))
{
    sim.EndTurn();
    double expected = (100 - enemy.CurrentHP) - (100 - bot.CurrentHP);
    if (bot.CurrentHP >= 100 || enemy.CurrentHP >= 100 || sim.HookDamage != expected || expected >= 0)
        throw new Exception($"Triggered damage must use net team HP: own={bot.CurrentHP}, enemy={enemy.CurrentHP}, utility={sim.HookDamage}, expected={expected}");
}
if (bot.CurrentHP != 100 || enemy.CurrentHP != 100)
    throw new Exception("Hook simulation must restore the source fight");
Console.WriteLine("PASS triggered friendly damage lowers utility and simulation rewinds");
