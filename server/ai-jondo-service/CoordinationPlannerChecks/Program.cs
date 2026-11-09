using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

void Check(bool value, string name)
{
    if (!value) throw new Exception("FAIL: " + name);
    Console.WriteLine("PASS: " + name);
}
var narrowCells = new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(2,0,0) };
using (MapGeometry.BeginScope(new GeometryContext(narrowCells, new[] { (0,1), (1,0), (1,2), (2,1) })))
{
    var bot = F(1, 1, 0, ap:0, mp:1); var enemy = F(2, 2, 2);
    var board = new MonsterTactics.Board { Fighters = new[] { bot, enemy },
        TeamReservedXY = new HashSet<(int, int)> { (1, 0) }, ActorBlocksNativeLos = true };
    var attack = new MonsterTactics.Spell { Id = 8, Grade = 1, Cost = 3, MinRange = 1, MaxRange = 1, Damage = 20 };
    Check(MonsterTactics.Reposition(board, bot, new[] { attack }).Last() == 1,
        "the only route to the enemy is used despite a reserved corridor");
}
Fighter F(long id, int team, int cell, int hp = 100, int ap = 3, int mp = 0) => new()
{
    Id = id, TeamId = team, CellId = cell, CurrentHP = hp, MaxHP = 100,
    CurrentAP = ap, MaxAP = ap, CurrentMP = mp, MaxMP = mp, IsMonster = true, Level = 10,
};
var cells = new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0), new CellXYZ(0, 1, 0) };
var edges = new[] { (0, 1), (1, 0), (0, 2), (2, 0) };
using (MapGeometry.BeginScope(new GeometryContext(cells, edges)))
{
    var bot = F(1, 1, 0); var first = F(2, 2, 1); var focus = F(3, 2, 2);
    var board = new MonsterTactics.Board { Fighters = new[] { bot, first, focus }, TeamFocusId = focus.Id };
    var attack = new MonsterTactics.Spell { Id = 7, Grade = 1, Cost = 3, MinRange = 1, MaxRange = 1,
        Damage = 20, Rows = new[] { SemanticRows.Create("damage", 20, "enemy") } };
    var plan = MonsterTactics.PlanTurn(board, bot, new[] { attack }, budgetMs: 1000);
    Check(plan.Count == 1 && plan[0].Target.Id == focus.Id,
        "equal attacks prefer actual simulated damage to visible team focus");
    Check(bot.CurrentAP == 3 && first.CurrentHP == 100 && focus.CurrentHP == 100,
        "focus simulation restores source combat state");

    var armoredFirst = F(4, 2, 1); var armoredFocus = F(5, 2, 2);
    foreach (var target in new[] { armoredFirst, armoredFocus })
    {
        target.NativeHpMinimum = 0; target.NativeHpFrozen = false; target.NativeHpRawMode = "bounded";
        target.NativeStats = new Dictionary<int, int> { [87] = 0 };
    }
    armoredFocus.NativeForecastArmor = 20;
    armoredFocus.NativeArmorAuthority = new NativePoolAuthority(0, 20, false);
    var armorRow = SemanticRows.Create("damage", 20, "enemy", nativeCoefficientMask: 0);
    NativeEffectAmounts.Bind(armorRow, 0, 20, probability: 1);
    bot.NativeStats = new Dictionary<int, int> { [87] = 0 };
    var armorAttack = new MonsterTactics.Spell { Id = 9, Grade = 1, Cost = 3, MinRange = 1, MaxRange = 1,
        Damage = 20, Rows = new[] { armorRow } };
    var armorBoard = new MonsterTactics.Board { Fighters = new[] { bot, armoredFirst, armoredFocus } };
    var withoutFocus = MonsterTactics.PlanTurn(armorBoard, bot, new[] { armorAttack }, budgetMs: 1000);
    Check(withoutFocus.Count == 1 && withoutFocus[0].Target.Id == armoredFirst.Id,
        "without focus, equal attacks keep the first target despite the other's armor");
    var withArmorFocus = MonsterTactics.PlanTurn(armorBoard with { TeamFocusId = armoredFocus.Id }, bot,
        new[] { armorAttack }, budgetMs: 1000);
    Check(withArmorFocus.Count == 1 && withArmorFocus[0].Target.Id == armoredFocus.Id,
        "focus changes the choice when simulated damage reduces the marked enemy's armor");
    Check(armoredFocus.CurrentHP == 100 && armoredFocus.NativeForecastArmor == 20 && bot.CurrentAP == 3,
        "armor focus simulation restores HP, armor, and AP after planning");

    var inactive = board with { TeamFocusId = 99 };
    var ordinary = MonsterTactics.PlanTurn(inactive, bot, new[] { attack }, budgetMs: 1000);
    Check(ordinary.Count == 1, "a stale absent focus preserves ordinary attacking");
    first.CurrentHP = 10;
    var decisive = MonsterTactics.PlanTurn(board, bot, new[] { attack }, budgetMs: 1000);
    Check(decisive.Count == 1 && decisive[0].Target.Id == first.Id,
        "focus preference does not override a more valuable decisive action");
}
var positionCells = new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(0,1,0), new CellXYZ(2,2,0) };
var positionEdges = new[] { (0,1), (1,0), (0,2), (2,0) };
using (MapGeometry.BeginScope(new GeometryContext(positionCells, positionEdges)))
{
    var bot = F(1, 1, 0, ap:0, mp:1); var enemy = F(2, 2, 3);
    var board = new MonsterTactics.Board { Fighters = new[] { bot, enemy },
        TeamReservedXY = new HashSet<(int, int)> { (1, 0) }, ActorBlocksNativeLos = true };
    var attack = new MonsterTactics.Spell { Id = 7, Grade = 1, Cost = 3, MinRange = 1, MaxRange = 1, Damage = 20 };
    var path = MonsterTactics.Reposition(board, bot, new[] { attack });
    Check(path.Last() == 2, "idle movement avoids blocking a confirmed allied firing corridor");
    Check(bot.CellId == 0 && bot.CurrentMP == 1, "reposition scoring does not mutate the source");
    var transparent = board with { ActorBlocksNativeLos = false };
    var noAuthority = board with { ActorBlocksNativeLos = null };
    Check(MonsterTactics.Reposition(transparent, bot, new[] { attack }).SequenceEqual(
            MonsterTactics.Reposition(noAuthority, bot, new[] { attack })),
        "unknown LOS blocking authority never invents a corridor cost");
    var owner = F(3, 1, 1); var corridor = new TeamCorridor(3, 1, 2, 3, new HashSet<(int,int)> { (1,0) });
    var simulationBoard = board with { Fighters = new[] { bot, enemy, owner }, TeamCorridors = new[] { corridor } };
    Check(MonsterTactics.LiveCorridor(simulationBoard, bot, corridor), "confirmed corridor is live in its original simulated state");
    enemy.CurrentHP = 0;
    Check(!MonsterTactics.LiveCorridor(simulationBoard, bot, corridor), "a defeated simulated target invalidates its corridor");
    enemy.CurrentHP = 100; enemy.CellId = 2;
    Check(!MonsterTactics.LiveCorridor(simulationBoard, bot, corridor), "a displaced simulated target invalidates its corridor");
    enemy.CellId = 3; owner.CellId = 2;
    Check(!MonsterTactics.LiveCorridor(simulationBoard, bot, corridor), "a displaced simulated owner invalidates its corridor");
}
var retreatCells = new[] {
    new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(2,0,0), new CellXYZ(3,0,0)
};
var retreatEdges = new[] { (0,1), (1,0), (1,2), (2,1), (2,3), (3,2) };
using (MapGeometry.BeginScope(new GeometryContext(retreatCells, retreatEdges)))
{
    var lowHp = F(10, 1, 0, hp:20, ap:3, mp:2);
    var enemy = F(11, 2, 3);
    var board = new MonsterTactics.Board {
        Fighters = new[] { lowHp, enemy },
        SightEvidence = (_, _) => false,
    };
    var allyOnlyHeal = new MonsterTactics.Spell {
        Id = 3140, Grade = 1, Cost = 2, MinRange = 1, MaxRange = 3,
        Damage = 20, Heal = 10, NativeNoSelfHeal = true,
    };
    var retreat = MonsterTactics.Reposition(board, lowHp, new[] { allyOnlyHeal });
    Check(retreat.SequenceEqual(new[] { 0 }),
        "certified allied-only healing does not prevent low-HP withdrawal");

    var possibleSelfHeal = new MonsterTactics.Spell {
        Id = 3140, Grade = 1, Cost = 2, MinRange = 1, MaxRange = 3,
        Damage = 20, Heal = 10,
    };
    var legacySnapshotSpell = new MonsterTactics.Spell {
        Id = 3140, Grade = 1, Cost = 2, MinRange = 1, MaxRange = 3, Damage = 20, Heal = 10,
    };
    Check(!legacySnapshotSpell.NativeNoSelfHeal,
        "an older spell snapshot without nativeNoSelfHeal keeps the conservative default");
    var selfHealPath = MonsterTactics.Reposition(board, lowHp, new[] { possibleSelfHeal });
    var legacyPath = MonsterTactics.Reposition(board, lowHp, new[] { legacySnapshotSpell });
    Check(selfHealPath.SequenceEqual(new[] { 0, 1, 2 }) && legacyPath.SequenceEqual(new[] { 0, 1, 2 }),
        "actual or unknown self-healing evidence preserves the normal approach");

    var mixedEvidence = MonsterTactics.Reposition(board, lowHp, new[] {
        allyOnlyHeal,
        new MonsterTactics.Spell { Id = 3141, Grade = 1, Heal = 5 },
    });
    Check(mixedEvidence.SequenceEqual(new[] { 0, 1, 2 }),
        "a second heal with possible self-targeting preserves the conservative approach");
}
