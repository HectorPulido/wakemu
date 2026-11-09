using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using System.Text.Json;
using Wakfu.Jondo;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0) },
    new[] { (0, 1), (1, 0) }));
var actor = new Fighter { Id=1, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
    CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0 };
var enemy = new Fighter { Id=2, TeamId=1, CellId=1, CurrentHP=1000, MaxHP=1000,
    CurrentMP=3, MaxMP=3 };
var board = new MonsterTactics.Board { Fighters = new[] { actor, enemy } };
MonsterTactics.Spell Hit(int id, int damage, int perTurn=0, int perTarget=0, int interval=0) =>
    new() { Id=id, Grade=1, Cost=3, MinRange=1, MaxRange=1, Damage=damage,
        PerTurn=perTurn, PerTarget=perTarget, Interval=interval };
double Forecast(params MonsterTactics.Spell[] spells)
{
    using var sim = MonsterTactics.Simulation.Replay(board, actor, Array.Empty<MonsterTactics.Action>());
    return MonsterTactics.NextBlow(sim, actor, spells, uncapped: true);
}

var occupancyCells=Enumerable.Range(-2,6).SelectMany(y=>Enumerable.Range(-1,8).Select(x=>new CellXYZ(x,y,0))).ToArray();
var occupancyEdges=Enumerable.Range(0,occupancyCells.Length).SelectMany(i=>Enumerable.Range(0,occupancyCells.Length).Where(j=>
    Math.Abs(occupancyCells[i].X-occupancyCells[j].X)+Math.Abs(occupancyCells[i].Y-occupancyCells[j].Y)==1).Select(j=>(i,j))).ToArray();
using (MapGeometry.BeginScope(new GeometryContext(occupancyCells,occupancyEdges)))
{
    int Cell(int x,int y)=>MapGeometry.PointToCell(x,y,0);
    int oldAnchor=Cell(0,0), destination=Cell(3,0);
    var mover=new Fighter { Id=81,TeamId=0,CellId=oldAnchor,CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=3,MaxMP=3,NativeDirection=2 };
    var enemyAtOldArea=new Fighter { Id=82,TeamId=1,CellId=Cell(0,1),CurrentHP=1000,MaxHP=1000,
        CurrentMP=3,MaxMP=3 };
    var enemyAtNewBody=new Fighter { Id=83,TeamId=1,CellId=Cell(5,0),CurrentHP=1000,MaxHP=1000,
        CurrentMP=3,MaxMP=3 };
    var occupancyBoard=new MonsterTactics.Board { Fighters=new[]{mover,enemyAtOldArea,enemyAtNewBody} };
    var freeArea5559=new MonsterTactics.Spell { Id=5559,Grade=20,Cost=3,MinRange=3,MaxRange=8,
        Damage=25,Zone=1,NeedsFreeCell=true,RangeBoostable=false };
    var originalExtra=mover.ExtraCells.ToArray();
    var originalDirection=mover.NativeDirection;
    var attackOptions=MonsterTactics.Options(occupancyBoard, mover, new[]{freeArea5559});
    Check(attackOptions.Any(o=>o.Target==enemyAtOldArea && o.TargetCell==oldAnchor && o.From!=oldAnchor && o.Path.Count>1)?1:0,1,
        "spell5559 can aim at the caster's vacated cell after moving and hit its neighboring enemy");
    mover.CurrentMP=0;
    Check(MonsterTactics.Options(occupancyBoard,mover,new[]{freeArea5559})
        .Any(o=>o.Target==enemyAtOldArea && o.TargetCell==oldAnchor)?1:0,0,
        "free-cell cast cannot target the caster's still-occupied current cell without movement");
    mover.CurrentMP=3;
    Check(mover.CellId==oldAnchor && mover.ExtraCells.SequenceEqual(originalExtra)
          && mover.NativeDirection==originalDirection?1:0,1,
        "hypothetical free-cell options restore actor anchor, footprint and direction");

    var largeMover=new Fighter { Id=84,TeamId=0,CellId=oldAnchor,CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=3,MaxMP=3,NativePhysicalRadius=1 };
    var largeBoard=new MonsterTactics.Board { Fighters=new[]{largeMover,enemyAtOldArea,enemyAtNewBody} };
    var shortRangeFreeCell=new MonsterTactics.Spell { Id=5559,Grade=20,Cost=3,MinRange=1,MaxRange=8,
        Damage=25,Zone=1,NeedsFreeCell=true,RangeBoostable=false };
    var largeOptions=MonsterTactics.Options(largeBoard,largeMover,new[]{shortRangeFreeCell});
    Check(largeOptions.Any(o=>o.Target==enemyAtOldArea && o.TargetCell==oldAnchor && o.From!=oldAnchor)?1:0,1,
        "large caster may use its vacated old anchor after its body moves clear");
    Check(largeBoard.OccupiedAt(largeMover,destination,Cell(4,0))
          && !largeOptions.Any(o=>o.Target==enemyAtNewBody && o.TargetCell==Cell(4,0) && o.From==destination)?1:0,1,
        "free-cell cast cannot target a cell inside the caster's new large footprint");

    var blocker=new Fighter { Id=85,TeamId=0,CellId=oldAnchor,CurrentHP=100,MaxHP=100 };
    var movedFrom=new Fighter { Id=86,TeamId=0,CellId=Cell(-1,0),CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=6,MaxMP=6 };
    var blockedOldCell=new MonsterTactics.Board { Fighters=new[]{movedFrom,blocker,enemyAtOldArea} };
    Check(MonsterTactics.Options(blockedOldCell,movedFrom,new[]{freeArea5559})
        .Any(o=>o.Target==enemyAtOldArea && o.TargetCell==oldAnchor)?1:0,0,
        "another actor occupying the released candidate cell still blocks the cast");

    var summonMover=new Fighter { Id=87,TeamId=0,CellId=oldAnchor,CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=1,MaxMP=1 };
    var summonBoard=new MonsterTactics.Board { Fighters=new[]{summonMover,enemyAtOldArea} };
    var summonSpell=new MonsterTactics.Spell { Id=5559,Grade=20,Cost=3,MinRange=0,MaxRange=1,Summons=true };
    var summonOptions=MonsterTactics.Options(summonBoard,summonMover,new[]{summonSpell});
    Check(summonOptions.Any(o=>o.From!=oldAnchor && o.TargetCell==oldAnchor && o.Path.Count>1)?1:0,1,
        "invocation landing can reuse the caster's released cell after a one-cell move");
    var summonMoverAway=new Fighter { Id=89,TeamId=0,CellId=Cell(-1,0),CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=2,MaxMP=2 };
    var blockedSummonBoard=new MonsterTactics.Board { Fighters=new[]{summonMoverAway,enemyAtOldArea,
        new Fighter { Id=88,TeamId=1,CellId=oldAnchor,CurrentHP=100,MaxHP=100 }} };
    Check(MonsterTactics.Options(blockedSummonBoard,summonMoverAway,new[]{summonSpell})
        .Any(o=>o.From!=summonMoverAway.CellId && o.TargetCell==oldAnchor && o.Path.Count>1)?1:0,0,
        "another actor occupying the released cell blocks the invocation landing");

    var summonRow=new SpellEffect { EffectId=EffectEngine.InvocaUnDoble,DiceNum=20,DiceSide=1,
        TargetMask="A",Triggers="I" };
    var portalSummon=new MonsterTactics.Spell { Id=5559,Grade=20,Cost=3,MinRange=0,MaxRange=8,
        Rows=new[]{summonRow} };
    var portalBoard=new MonsterTactics.Board { Fighters=new[]{mover,enemyAtOldArea},
        Walkable=_=>true,CanSummon=(_,_,_)=>true };
    double physicalCellValue=MonsterTactics.ValueOfRows(portalBoard,portalSummon,mover,
        Cell(2,0),oldAnchor,new(){enemyAtOldArea},allowHealthSequence:false,actorPhysicalOrigin:oldAnchor);
    Check(physicalCellValue,0,
        "portal-projected summon rejects the caster's physical origin as occupied");
    double projectedCellValue=MonsterTactics.ValueOfRows(portalBoard,portalSummon,mover,
        Cell(2,0),oldAnchor,new(){enemyAtOldArea},allowHealthSequence:false);
    Check(projectedCellValue>0?1:0,1,
        "portal-projected double can land on the caster's physical origin only when origin evidence is omitted");
}
void Check(double expected, double actual, string description)
{
    if (Math.Abs(expected - actual) > 0.000001)
        throw new Exception($"{description}: expected {expected}, got {actual}");
    Console.WriteLine("PASS: " + description);
}
Check(15, Forecast(Hit(1, 30)), "unlimited next-turn casts fit the AP budget");
Check(7.5, Forecast(Hit(1, 30, perTurn:1)), "per-turn limit applies to next-turn forecast");
Check(7.5, Forecast(Hit(1, 30, perTarget:1)), "per-target limit applies to next-turn forecast");
Check(7.5, Forecast(Hit(1, 30, interval:1)), "cast-triggered cooldown limits subsequent casts");
Check(10, Forecast(Hit(1, 30, perTurn:1), Hit(2, 10)), "remaining AP may pay for another legal spell");
actor.LanzadosEsteTurno[1] = 1;
actor.LanzadosPorObjetivo[(1, enemy.Id)] = 1;
Check(7.5, Forecast(Hit(1, 30, perTurn:1, perTarget:1)), "current-turn counters reset for next-turn forecast");
actor.Recarga[1] = 2;
Check(0, Forecast(Hit(1, 30)), "cooldown beyond next turn excludes spell");
actor.Recarga[1] = 1;
Check(15, Forecast(Hit(1, 30)), "cooldown expiring next turn permits spell");
actor.Recarga.Clear();
var profile5522Free = new MonsterTactics.Spell {
    Id=7969, Grade=1, Cost=0, MinRange=1, MaxRange=1, Damage=25,
};
Check(6.25, Forecast(profile5522Free),
    "profile5522 spell7969 at zero AP is conservatively forecast as one cast");
actor.Recarga[7969] = 2;
Check(0, Forecast(profile5522Free), "free spell7969 remains excluded by a cooldown beyond next turn");
actor.Recarga[7969] = 1;
Check(6.25, Forecast(profile5522Free), "free spell7969 returns when its cooldown expires next turn");
actor.Recarga.Clear();
var paidAlternative = new MonsterTactics.Spell {
    Id=7970, Grade=1, Cost=3, MinRange=1, MaxRange=1, Damage=10,
};
Check(11.25, Forecast(profile5522Free, paidAlternative),
    "single free spell7969 combines with one affordable normal cast");
actor.MaxAP = 0; actor.CurrentAP = 0;
Check(6.25, Forecast(profile5522Free), "free spell7969 remains usable with zero AP budget");
actor.MaxAP = 6; actor.CurrentAP = 6;
var secondFree = new MonsterTactics.Spell { Id=7971, Grade=1, Cost=0,
    MinRange=1, MaxRange=1, Damage=15 };
Check(10, Forecast(profile5522Free, secondFree),
    "two distinct free native spells each contribute at most one forecast cast");
var savedBoard = board;
int freeSpellChecks = 0;
board = savedBoard with { SearchContinues = () => ++freeSpellChecks <= 100 };
double freeBounded = Forecast(profile5522Free, secondFree, paidAlternative);
if (!double.IsFinite(freeBounded) || freeSpellChecks >= 100)
    throw new Exception("zero-cost cast forecast must terminate within the shared search budget");
Console.WriteLine("PASS: zero-cost cast forecasts terminate within the shared search budget");
board = savedBoard with { SpellMovementCost = spell => spell.Id is 7969 or 7971 ? 1 : 0 };
actor.MaxMP = 1; actor.CurrentMP = 0;
Check(6.25, Forecast(profile5522Free, secondFree),
    "distinct free spells share the one available PM when their native cost is nonzero");
actor.MaxMP = 0;
board = savedBoard;
actor.MaxMP = 0; actor.CurrentMP = 0;
var close = Hit(3, 40, perTurn: 1);
var distant = new MonsterTactics.Spell { Id=4, Grade=1, Cost=3, MinRange=1, MaxRange=5,
    Damage=10, PerTurn=1 };
Check(16, Forecast(close, distant), "mixed-range future casts retain their own reach likelihood");
enemy.CurrentMP = 0; enemy.MaxMP = 0;
Check(45, Forecast(close, distant), "pinned enemies use the same reach likelihood for both spells");
enemy.CurrentMP = 3; enemy.MaxMP = 3;
actor.CurrentAP = 10; actor.MaxAP = 10;
var efficient = new MonsterTactics.Spell { Id=5, Grade=1, Cost=4, MinRange=1, MaxRange=1, Damage=5 };
var expensive = new MonsterTactics.Spell { Id=6, Grade=1, Cost=5, MinRange=1, MaxRange=1, Damage=6 };
Check(3, Forecast(efficient, expensive), "future forecast uses both 5 AP casts when greedy 4 AP casts leave unused AP");
MonsterTactics.Spell Expensive(int perTurn=0, int perTarget=0, int interval=0, int range=1) =>
    new() { Id=6, Grade=1, Cost=5, MinRange=1, MaxRange=range, Damage=6,
        PerTurn=perTurn, PerTarget=perTarget, Interval=interval };
Check(2.75, Forecast(efficient, Expensive(perTurn:1)), "bounded refinement respects the per-turn spell limit");
Check(2.75, Forecast(efficient, Expensive(perTarget:1)), "bounded refinement respects the per-target spell limit");
Check(2.75, Forecast(efficient, Expensive(interval:1)), "bounded refinement respects cooldown intervals");
expensive = Expensive(range:5);
Check(7.2, Forecast(efficient, expensive), "bounded refinement keeps each spell's own range likelihood");
actor.MaxAP = 64; actor.CurrentAP = 64;
if (!double.IsFinite(Forecast(efficient, expensive))) throw new Exception("unusual AP fallback must stay bounded");
Console.WriteLine("PASS: unusual AP falls back to the existing forecast");
actor.MaxAP = 10; actor.CurrentAP = 10;
int budgetChecks = 0;
board = new MonsterTactics.Board { Fighters = new[] { actor, enemy },
    SearchContinues = () => ++budgetChecks <= 18 };
double partial = Forecast(efficient, expensive);
if (!double.IsFinite(partial) || budgetChecks > 24)
    throw new Exception("forecast must return a finite partial result after the deadline");
Console.WriteLine("PASS: bounded refinement honors the shared deadline");

using (MapGeometry.BeginScope(new GeometryContext(
    Enumerable.Range(0, 7).Select(x => new CellXYZ(x, 0, 0)).ToArray(),
    Enumerable.Range(0, 6).SelectMany(x => new[] { (x, x + 1), (x + 1, x) }).ToArray())))
{
    var mover = new Fighter { Id=21, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=3 };
    var distantEnemy = new Fighter { Id=22, TeamId=1, CellId=6, CurrentHP=1000, MaxHP=1000,
        CurrentMP=3, MaxMP=3 };
    var paidBoard = new MonsterTactics.Board {
        Fighters = new[] { mover, distantEnemy },
        SpellMovementCost = spell => spell.Id == 3119 ? 1 : 0,
    };
    var paid3119 = new MonsterTactics.Spell {
        Id=3119, Grade=1, Cost=3, MinRange=1, MaxRange=4, Damage=20,
    };
    var payableAlternative = new MonsterTactics.Spell {
        Id=3120, Grade=1, Cost=3, MinRange=1, MaxRange=6, Damage=15,
    };
    double ForecastMovement(MonsterTactics.Board forecastBoard, params MonsterTactics.Spell[] spells)
    {
        using var sim = MonsterTactics.Simulation.Replay(
            forecastBoard, mover, Array.Empty<MonsterTactics.Action>());
        return MonsterTactics.NextBlow(sim, mover, spells, uncapped:true);
    }
    Check(12, ForecastMovement(paidBoard, paid3119),
        "spell 3119 forecasts one cast after approach and its 1 MP cast cost");
    mover.MaxMP = 2;
    Check(0, ForecastMovement(paidBoard, paid3119),
        "3119 is excluded when the required approach leaves no PM for its cast");
    var alternativeOnly = ForecastMovement(paidBoard, payableAlternative);
    Check(alternativeOnly > 10 &&
          Math.Abs(ForecastMovement(paidBoard, paid3119, payableAlternative) - alternativeOnly) < 0.000001
              ? 1 : 0, 1,
        "a zero-PM alternative remains selectable when movement plus 3119 exceeds the shared MP budget");
    mover.MaxMP = 3;
    var legacyUnknown = new MonsterTactics.Board { Fighters = new[] { mover, distantEnemy } };
    var explicitFree = legacyUnknown with { SpellMovementCost = _ => 0 };
    Check(24, ForecastMovement(legacyUnknown, paid3119),
        "unknown movement-cost evidence retains the legacy two-cast estimate");
    Check(Math.Abs(ForecastMovement(legacyUnknown, paid3119)
                   - ForecastMovement(explicitFree, paid3119)) < 0.000001
          && ForecastMovement(legacyUnknown, paid3119) > ForecastMovement(paidBoard, paid3119)
              ? 1 : 0, 1,
        "missing movement-cost evidence preserves the zero-cost legacy forecast");

    var adjacentActor = new Fighter { Id=31, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=1 };
    var adjacentEnemy = new Fighter { Id=32, TeamId=1, CellId=1, CurrentHP=1000, MaxHP=1000,
        CurrentMP=3, MaxMP=3 };
    var sharedMpBoard = new MonsterTactics.Board {
        Fighters = new[] { adjacentActor, adjacentEnemy },
        SpellMovementCost = spell => spell.Id is 3119 or 3121 ? 1 : 0,
    };
    var firstPaidSpell = new MonsterTactics.Spell {
        Id=3119, Grade=1, Cost=3, MinRange=1, MaxRange=1, Damage=20,
    };
    var secondPaidSpell = new MonsterTactics.Spell {
        Id=3121, Grade=1, Cost=3, MinRange=1, MaxRange=1, Damage=15,
    };
    double ForecastSharedMp(params MonsterTactics.Spell[] spells)
    {
        using var sim = MonsterTactics.Simulation.Replay(
            sharedMpBoard, adjacentActor, Array.Empty<MonsterTactics.Action>());
        return MonsterTactics.NextBlow(sim, adjacentActor, spells, uncapped:true);
    }
    var firstOnly = ForecastSharedMp(firstPaidSpell);
    var secondOnly = ForecastSharedMp(secondPaidSpell);
    Check(Math.Max(firstOnly, secondOnly),
        ForecastSharedMp(firstPaidSpell, secondPaidSpell),
        "distinct 1-PM spells share a single available PM instead of being summed");
}

using (MapGeometry.BeginScope(new GeometryContext(
    new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0)},new[]{(0,1),(1,0)})))
{
    List<MonsterTactics.Action> ResourcePlan(int mp,int? wp,int pmCost,int wpCost,
        MonsterTactics.Spell spell,int hp=100)
    {
        var caster=new Fighter { Id=61,TeamId=0,CellId=0,CurrentHP=hp,MaxHP=100,
            CurrentAP=0,MaxAP=0,CurrentMP=mp,MaxMP=mp,NativeCurrentWp=wp };
        var target=new Fighter { Id=62,TeamId=1,CellId=1,CurrentHP=1000,MaxHP=1000 };
        var resourceBoard=new MonsterTactics.Board { Fighters=new[]{caster,target},
            SpellMovementCost=_=>pmCost,SpellWakfuCost=_=>wpCost };
        return MonsterTactics.PlanTurn(resourceBoard,caster,new[]{spell},width:6,depth:4,branch:4,budgetMs:500);
    }
    var repeat2858=new MonsterTactics.Spell { Id=2858,Grade=1,Cost=0,MinRange=1,MaxRange=1,Damage=20 };
    Check(ResourcePlan(10,null,5,0,repeat2858).Count(a=>a.Spell.Id==2858),2,
        "native 2858 costs 0 AP and 5 PM, allowing two casts from 10 PM");
    Check(ResourcePlan(5,null,5,0,repeat2858).Count(a=>a.Spell.Id==2858),1,
        "native 2858 is limited to one cast by 5 PM");
    var repeat2527=new MonsterTactics.Spell { Id=2527,Grade=1,Cost=0,MinRange=0,MaxRange=1,Heal=20 };
    Check(ResourcePlan(0,2,0,1,repeat2527,hp:30).Count(a=>a.Spell.Id==2527),2,
        "0 AP/1 WP healing spell repeats within known two-WP balance");
    Check(ResourcePlan(0,1,0,1,repeat2527,hp:30).Count(a=>a.Spell.Id==2527),1,
        "0 AP/1 WP healing spell is limited by one available WP");
    Check(ResourcePlan(0,null,0,1,repeat2527,hp:30).Count(a=>a.Spell.Id==2527),1,
        "unknown WP balance preserves one-cast fallback for 0 AP/1 WP healing");
    Check(ResourcePlan(10,null,5,1,repeat2858).Count(a=>a.Spell.Id==2858),1,
        "combined PM and unknown WP cost prevents a second free-AP cast");
    Check(ResourcePlan(10,2,5,1,repeat2858).Count(a=>a.Spell.Id==2858),2,
        "combined PM and known WP balance permits resource-funded repeats");
    Check(ResourcePlan(10,2,0,0,repeat2858).Count(a=>a.Spell.Id==2858),1,
        "a spell free in AP, PM and WP retains the one-cast guard");

    var plannedActor=new Fighter { Id=71,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100,
        CurrentAP=0,MaxAP=0,CurrentMP=10,MaxMP=10,NativeCurrentWp=2 };
    var plannedTarget=new Fighter { Id=72,TeamId=1,CellId=1,CurrentHP=1000,MaxHP=1000 };
    var plannedBoard=new MonsterTactics.Board { Fighters=new[]{plannedActor,plannedTarget},
        SpellMovementCost=_=>5,SpellWakfuCost=_=>1 };
    var planned=new MonsterTactics.Action(new[]{0},repeat2858,plannedTarget,1,1,Value:20,
        ActionPoints:0,MovementPoints:10);
    plannedActor.CurrentMP=4;
    Check(MonsterTactics.Revalidate(plannedBoard,plannedActor,planned)==null?1:0,1,
        "revalidation rejects a 0-AP action when its PM cost is unaffordable");
    plannedActor.CurrentMP=10; plannedActor.NativeCurrentWp=0;
    Check(MonsterTactics.Revalidate(plannedBoard,plannedActor,planned)==null?1:0,1,
        "revalidation rejects a 0-AP action when its WP cost is unaffordable");
}

var bodySource = new Fighter { Id=41, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
    CurrentAP=3, MaxAP=3, CurrentMP=0, MaxMP=0 };
var bodyTarget = new Fighter { Id=42, TeamId=1, CellId=1, CurrentHP=1000, MaxHP=1000,
    NativePhysicalRadius=1, MonsterId=1345, CurrentMP=0, MaxMP=0 };
var bodySpell = new MonsterTactics.Spell { Id=801, Grade=1, Cost=3,
    MinRange=1, MaxRange=2, Damage=25 };
double BodyForecast()
{
    using var sim=MonsterTactics.Simulation.Replay(
        new MonsterTactics.Board { Fighters=new[]{bodySource,bodyTarget} },
        bodySource,Array.Empty<MonsterTactics.Action>());
    return MonsterTactics.NextBlow(sim,bodySource,new[]{bodySpell},uncapped:true);
}
using (MapGeometry.BeginScope(new GeometryContext(
    new[]{new CellXYZ(0,0,0),new CellXYZ(3,0,8),new CellXYZ(2,0,-99)},Array.Empty<(int,int)>())))
{
    Check(BodyForecast()>0?1:0,1,
        "large body edge is in range when center is out, even at another Z height");
    bodyTarget.NativePhysicalRadius=0;
    Check(BodyForecast(),0,"radius-zero target falls back to center range");
}
bodyTarget.NativePhysicalRadius=1;
using (MapGeometry.BeginScope(new GeometryContext(
    new[]{new CellXYZ(0,0,0),new CellXYZ(3,0,8)},Array.Empty<(int,int)>())))
{
    Check(BodyForecast(),0,"missing body edge column falls back to the target center");
}

using (MapGeometry.BeginScope(new GeometryContext(
    new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},Array.Empty<(int,int)>())))
{
    var caster=new Fighter { Id=51,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100,CurrentAP=3,MaxAP=3 };
    var diagonalEnemy=new Fighter { Id=52,TeamId=1,CellId=1,CurrentHP=100,MaxHP=100 };
    var linearEnemy=new Fighter { Id=53,TeamId=1,CellId=2,CurrentHP=100,MaxHP=100 };
    var alignmentBoard=new MonsterTactics.Board { Fighters=new[]{caster,diagonalEnemy,linearEnemy},
        Sees=(from,to)=>true };
    var both3931=new MonsterTactics.Spell { Id=3931,Grade=1,Cost=3,MinRange=1,MaxRange=4,
        Damage=20,InLine=true,NativeDiagonal=true,NeedsLineOfSight=true };
    var bothOptions=MonsterTactics.Options(alignmentBoard,caster,new[]{both3931});
    Check(bothOptions.Any(a=>a.Target.Id==diagonalEnemy.Id)?1:0,1,
        "certified3931 accepts diagonal enemy aim");
    Check(bothOptions.Any(a=>a.Target.Id==linearEnemy.Id)?1:0,1,
        "certified3931 retains linear enemy aim");

    var diagonalOnly8286=new MonsterTactics.Spell { Id=8286,Grade=1,Cost=3,MinRange=1,MaxRange=4,
        Damage=20,InLine=false,NativeDiagonal=true };
    var diagonalOnlyOptions=MonsterTactics.Options(alignmentBoard,caster,new[]{diagonalOnly8286});
    Check(diagonalOnlyOptions.Any(a=>a.Target.Id==diagonalEnemy.Id)?1:0,1,
        "certified8286 accepts diagonal-only enemy aim");
    Check(diagonalOnlyOptions.Any(a=>a.Target.Id==linearEnemy.Id)?1:0,0,
        "certified8286 rejects linear-only enemy aim");

    var legacyLinear=new MonsterTactics.Spell { Id=9001,Grade=1,Cost=3,MinRange=1,MaxRange=4,
        Damage=20,InLine=true };
    var legacyOptions=MonsterTactics.Options(alignmentBoard,caster,new[]{legacyLinear});
    Check(legacyOptions.Any(a=>a.Target.Id==diagonalEnemy.Id)?1:0,0,
        "legacy snapshot without diagonal certificate retains linear restriction");
    Check(legacyOptions.Any(a=>a.Target.Id==linearEnemy.Id)?1:0,1,
        "legacy snapshot without diagonal certificate keeps its linear cast");

    var blockedDiagonalBoard=alignmentBoard with { Sees=(from,to)=>to!=diagonalEnemy.CellId };
    var blockedDiagonal=MonsterTactics.Options(blockedDiagonalBoard,caster,new[]{both3931});
    Check(blockedDiagonal.Any(a=>a.Target.Id==diagonalEnemy.Id)?1:0,0,
        "diagonal certificate does not bypass blocked native line of sight");
    Check(blockedDiagonal.Any(a=>a.Target.Id==linearEnemy.Id)?1:0,1,
        "blocked diagonal leaves the valid linear candidate available");

    var specificRequest=JsonDocument.Parse("""{"board":{"actors":[{"id":51,"monsterRef":1,"team":0,"cell":0,"hp":100,"maxHp":100,"wp":0},{"id":52,"monsterRef":2,"team":1,"cell":1,"hp":100,"maxHp":100,"wp":0}]}}""").RootElement;
    var specific=new SpecificContext(specificRequest,alignmentBoard,caster,new[]{both3931},
        new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(specific.Casts(3931,new[]{diagonalEnemy.CellId},1,"alignment regression").Any()?1:0,1,
        "specific strategy Casts accepts certified diagonal aim");
    var specificLegacy=new SpecificContext(specificRequest,alignmentBoard,caster,new[]{legacyLinear},
        new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(specificLegacy.Casts(9001,new[]{diagonalEnemy.CellId},1,"legacy alignment regression").Any()?1:0,0,
        "specific strategy Casts preserves legacy linear restriction without certificate");

    var supportRequest=JsonDocument.Parse("""{"board":{"actors":[{"id":51,"team":0,"wp":0,"states":[]},{"id":52,"team":1,"wp":0,"states":[]}]},"spells":[{"id":3931,"nativeSupport":{"version":1,"aimKinds":["enemy"],"effects":[{"nativeReference":77,"targets":["enemy"],"benefit":"harmful","kind":"add_state","stateId":77,"confidence":"known","probability":100}]}}]}""").RootElement;
    var supportCandidates=NativeSupportCandidates.Propose(supportRequest,alignmentBoard,caster,
        new[]{both3931},new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(supportCandidates.Any(c=>c.SpellId==3931)?1:0,1,
        "native support proposal consumes the certified diagonal alignment");
    var legacySupport=NativeSupportCandidates.Propose(supportRequest,alignmentBoard,caster,
        new[]{legacyLinear},new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(legacySupport.Any(c=>c.SpellId==9001)?1:0,0,
        "native support proposal keeps legacy linear restriction without certificate");

    caster.CurrentHP=50;
    var certifiedSelfHeal=new MonsterTactics.Spell { Id=986,Grade=20,Cost=3,MinRange=1,MaxRange=3,
        Heal=9,NativeAllowSelf=true };
    var selfHealOptions=MonsterTactics.Options(alignmentBoard,caster,new[]{certifiedSelfHeal});
    Check(selfHealOptions.Any(a=>a.Target.Id==caster.Id)?1:0,1,
        "planner permits real spell986 self-heal with certified allow_self and positive minimum range");
    var uncertifiedSelfHeal=new MonsterTactics.Spell { Id=986,Grade=20,Cost=3,MinRange=1,MaxRange=3,Heal=9 };
    Check(MonsterTactics.Options(alignmentBoard,caster,new[]{uncertifiedSelfHeal})
        .Any(a=>a.Target.Id==caster.Id)?1:0,0,
        "planner retains positive minimum-range behavior without allow_self evidence");
    var legacyMinZero=new MonsterTactics.Spell { Id=986,Grade=20,Cost=3,MinRange=0,MaxRange=3,Heal=9 };
    Check(MonsterTactics.Options(alignmentBoard,caster,new[]{legacyMinZero})
        .Any(a=>a.Target.Id==caster.Id)?1:0,1,
        "planner keeps the existing minRange-zero self-cast fallback");
    var legacyZeroRange=new MonsterTactics.Spell { Id=986,Grade=20,Cost=3,MinRange=1,MaxRange=0,Heal=9 };
    Check(MonsterTactics.Options(alignmentBoard,caster,new[]{legacyZeroRange})
        .Any(a=>a.Target.Id==caster.Id)?1:0,1,
        "planner keeps the existing zero-range self-cast fallback");

    var selfContextRequest=JsonDocument.Parse("""{"board":{"actors":[{"id":51,"monsterRef":1,"team":0,"cell":0,"hp":50,"maxHp":100,"wp":0},{"id":52,"monsterRef":2,"team":1,"cell":1,"hp":100,"maxHp":100,"wp":0}]}}""").RootElement;
    var selfContext=new SpecificContext(selfContextRequest,alignmentBoard,caster,new[]{certifiedSelfHeal},
        new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(selfContext.Casts(986,new[]{caster.CellId},1,"self range regression").Any()?1:0,1,
        "specific strategy Casts permits certified self aim below positive minimum range");
    var selfContextLegacy=new SpecificContext(selfContextRequest,alignmentBoard,caster,new[]{uncertifiedSelfHeal},
        new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(selfContextLegacy.Casts(986,new[]{caster.CellId},1,"legacy self range regression").Any()?1:0,0,
        "specific strategy Casts requires native allow_self evidence for positive minRange");

    var selfSupportRequest=JsonDocument.Parse("""{"board":{"actors":[{"id":51,"team":0,"wp":0,"hp":50,"maxHp":100,"states":[]},{"id":52,"team":1,"wp":0,"hp":100,"maxHp":100,"states":[]}]},"spells":[{"id":986,"nativeSupport":{"version":1,"aimKinds":["self"],"effects":[{"nativeReference":986,"targets":["self"],"benefit":"beneficial","kind":"heal","amount":9,"confidence":"known","probability":100}]}}]}""").RootElement;
    var selfSupport=NativeSupportCandidates.Propose(selfSupportRequest,alignmentBoard,caster,
        new[]{certifiedSelfHeal},new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(selfSupport.Any(c=>c.SpellId==986)?1:0,1,
        "native support permits certified self-heal below positive minimum range");
    var selfSupportLegacy=NativeSupportCandidates.Propose(selfSupportRequest,alignmentBoard,caster,
        new[]{uncertifiedSelfHeal},new[]{new CellXYZ(0,0,0),new CellXYZ(2,2,0),new CellXYZ(4,0,0)},_ => (3,0,0),new HashSet<(int,int)>());
    Check(selfSupportLegacy.Any(c=>c.SpellId==986)?1:0,0,
        "native support requires allow_self evidence for positive minRange");

    using (MapGeometry.BeginScope(new GeometryContext(
        new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(2,0,0)},
        new[]{(0,1),(1,0),(1,2),(2,1)})))
    {
        caster.CurrentMP=3; caster.MaxMP=3;
        var mobileSelfBoard=new MonsterTactics.Board { Fighters=new[]{caster,
            new Fighter { Id=52,TeamId=1,CellId=2,CurrentHP=100,MaxHP=100 }} };
        var mobileCells=new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(2,0,0)};
        var mobileProposal=NativeSupportCandidates.Propose(selfSupportRequest,mobileSelfBoard,caster,
            new[]{certifiedSelfHeal},mobileCells,_ => (3,0,0),new HashSet<(int,int)>());
        bool movedSelfCandidate=mobileProposal.Where(c=>c.SpellId==986)
            .Select(c=>JsonSerializer.Serialize(c.Action))
            .Any(json=>json.Contains("\"type\":\"move\"") && json.Contains("[1,0,0]"));
        Check(movedSelfCandidate?1:0,1,
            "support spell986 includes a self-cast candidate anchored after movement");

        var mobileLegacy=NativeSupportCandidates.Propose(selfSupportRequest,mobileSelfBoard,caster,
            new[]{uncertifiedSelfHeal},mobileCells,_ => (3,0,0),new HashSet<(int,int)>());
        Check(mobileLegacy.Any(c=>c.SpellId==986)?1:0,0,
            "support does not invent a moved self anchor when allow_self evidence is absent");

        var noMoveBoard=mobileSelfBoard with { Walkable=_=>false };
        var noMove=NativeSupportCandidates.Propose(selfSupportRequest,noMoveBoard,caster,
            new[]{certifiedSelfHeal},mobileCells,_ => (3,0,0),new HashSet<(int,int)>());
        bool noMoveCandidate=noMove.Where(c=>c.SpellId==986)
            .Select(c=>JsonSerializer.Serialize(c.Action))
            .Any(json=>json.Contains("\"type\":\"cast\"") && json.Contains("[0,0,0]"));
        Check(noMoveCandidate?1:0,1,
            "when movement is unavailable the certified self-cast remains at its current anchor");

        var stationaryFallback=new MonsterTactics.Spell { Id=986,Grade=20,Cost=3,MinRange=0,
            MaxRange=3,Heal=9 };
        var stationary=NativeSupportCandidates.Propose(selfSupportRequest,mobileSelfBoard,caster,
            new[]{stationaryFallback},mobileCells,_ => (3,0,0),new HashSet<(int,int)>());
        Check(stationary.Any(c=>c.SpellId==986 && JsonSerializer.Serialize(c.Action).Contains("\"type\":\"cast\""))?1:0,1,
            "support preserves the existing stationary minRange-zero self-cast fallback");
    }
}
