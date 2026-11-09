using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0) },
    new[] { (0, 1), (1, 0) }));
var bot = new Fighter { Id = 1, TeamId = 0, CellId = 0, CurrentHP = 30, MaxHP = 100 };
var enemy = new Fighter { Id = 2, TeamId = 1, CellId = 1, CurrentHP = 100, MaxHP = 100 };
var board = new MonsterTactics.Board { Fighters = new[] { bot, enemy }, Walkable = _ => true, Sees = (_, _) => true };
bot.Buffs.ActiveSpells.Add(new Buffs.ActiveSpell { Hechizo = 912, Grado = 1, Lanzador = bot.Id });
var selfHeal = new SpellEffect { EffectId = 108, DiceNum = 30, DiceSide = 30, TargetMask = "C", Triggers = "TE" };
using var effects = SpellEffects.BeginScope(new() { [(912, 1)] = new[] { selfHeal } });
using (var sim = MonsterTactics.Simulation.Replay(board, bot, Array.Empty<MonsterTactics.Action>()))
{
    sim.EndTurn();
    double healed = bot.CurrentHP - 30;
    if (healed <= 0 || sim.HookDamage != healed)
        throw new Exception($"Triggered healing must contribute its effective value: healed={healed}, utility={sim.HookDamage}");
}
if (bot.CurrentHP != 30) throw new Exception("Replay must restore HP");
Console.WriteLine("PASS triggered healing contributes effective utility");

bot.CurrentHP = 100;
enemy.CurrentHP = 30;
bot.Buffs.ActiveSpells.Clear();
bot.Buffs.ActiveSpells.Add(new Buffs.ActiveSpell { Hechizo = 913, Grado = 1, Lanzador = bot.Id });
var enemyHeal = new SpellEffect { EffectId = 108, DiceNum = 20, DiceSide = 20, TargetMask = "A", Triggers = "TE", Forma = 'C', Tamano = 1 };
using (SpellEffects.BeginScope(new() { [(913, 1)] = new[] { enemyHeal } }))
using (var sim = MonsterTactics.Simulation.Replay(board, bot, Array.Empty<MonsterTactics.Action>()))
{
    sim.EndTurn();
    double healed = enemy.CurrentHP - 30;
    if (healed <= 0 || sim.HookDamage != -healed)
        throw new Exception($"Triggered enemy healing must lower utility: healed={healed}, utility={sim.HookDamage}");
}
if (enemy.CurrentHP != 30) throw new Exception("Replay must restore enemy HP");
Console.WriteLine("PASS enemy healing decreases effective utility");

bot.CurrentHP = 30;
enemy.CurrentHP = 10;
bot.Buffs.ActiveSpells.Clear();
bot.Buffs.ActiveSpells.Add(new Buffs.ActiveSpell { Hechizo = 914, Grado = 1, Lanzador = bot.Id });
var lethal = new SpellEffect { EffectId = 100, DiceNum = 20, DiceSide = 20, TargetMask = "A", Triggers = "TE", Forma = 'C', Tamano = 1 };
using (SpellEffects.BeginScope(new() { [(914, 1)] = new[] { selfHeal, lethal } }))
using (var sim = MonsterTactics.Simulation.Replay(board, bot, Array.Empty<MonsterTactics.Action>()))
{
    sim.EndTurn();
    if (bot.CurrentHP != 60 || enemy.CurrentHP != 0 || sim.HookDamage != 40)
        throw new Exception($"Healing and lethal damage should both contribute once: bot={bot.CurrentHP}, enemy={enemy.CurrentHP}, utility={sim.HookDamage}");
}
if (bot.CurrentHP != 30 || enemy.CurrentHP != 10) throw new Exception("Replay must restore both teams");
Console.WriteLine("PASS healing and lethal damage contribute once");
