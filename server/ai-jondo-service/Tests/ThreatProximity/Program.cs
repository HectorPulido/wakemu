using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

using var geometry = MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(8, 8, 0),
            new CellXYZ(7, 0, 0), new CellXYZ(int.MaxValue, 0, 0) },
    Array.Empty<(int, int)>()));
var bot = new Fighter { Id=1, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
    CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0 };
var foe = new Fighter { Id=2, TeamId=1, CellId=1, CurrentHP=100, MaxHP=100,
    CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0 };
void Check(bool actual, string description)
{
    if (!actual) throw new Exception("FAIL: " + description);
    Console.WriteLine("PASS: " + description);
}
Check(MonsterTactics.ThreatProximity(bot, foe) == 16,
    "zero radii preserve center distance");
bot.NativePhysicalRadius = 1; foe.NativePhysicalRadius = 2;
Check(MonsterTactics.ThreatProximity(bot, foe) == 10,
    "native radii subtract independently on both axes");
Check(MonsterTactics.ThreatProximity(foe, bot) == 10,
    "actor-to-actor proximity is symmetric");
foe.CellId = 2;
var board = new MonsterTactics.Board { Fighters = new[] { bot, foe } };
using (var sim = MonsterTactics.Simulation.Replay(board, bot, Array.Empty<MonsterTactics.Action>()))
{
    double bodyRisk = MonsterTactics.Danger(sim, bot);
    bot.NativePhysicalRadius = 0; foe.NativePhysicalRadius = 0;
    double centerRisk = MonsterTactics.Danger(sim, bot);
    Check(bodyRisk > centerRisk, "large bodies increase threat when their footprints approach");
}
bot.NativePhysicalRadius = -1; foe.NativePhysicalRadius = 2;
Check(MonsterTactics.ThreatProximity(bot, foe) == 7,
    "invalid or signed negative radius preserves earlier conservative estimate");
bot.NativePhysicalRadius = 1; foe.NativePhysicalRadius = 128;
Check(MonsterTactics.ThreatProximity(bot, foe) == 7,
    "out-of-range radius preserves earlier estimate");
foe.CellId = 3; foe.NativePhysicalRadius = 127; bot.NativePhysicalRadius = 127;
Check(MonsterTactics.ThreatProximity(bot, foe) == int.MaxValue - 254,
    "large coordinates and radii do not overflow");
foe.CellId = -1;
Check(MonsterTactics.ThreatProximity(bot, foe) == 999,
    "invalid geometry preserves existing distance fallback");

using (MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0),
            new CellXYZ(-1, 0, 0), new CellXYZ(0, 1, 0),
            new CellXYZ(0, -1, 0), new CellXYZ(6, 0, 0) },
    new[] { (0, 1), (0, 2), (0, 3), (0, 4), (1, 0) })))
{
    var trapped = new Fighter { Id=10, TeamId=0, CellId=0, CurrentHP=100, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=2, MaxMP=2 };
    var attacker = new Fighter { Id=11, TeamId=1, CellId=5, CurrentHP=100, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0 };
    var blocked = new MonsterTactics.Board { Fighters=new[] { trapped, attacker },
        NativeMovementPermissionOrigin=0, NativeMovementPermissionActorId=10,
        MovementAnchorAllowed=(_, _) => false };
    using (var sim = MonsterTactics.Simulation.Replay(blocked, trapped, Array.Empty<MonsterTactics.Action>()))
    {
        Check(MonsterTactics.Danger(sim, trapped, 2) == MonsterTactics.Danger(sim, trapped, 0),
            "forbidden native neighbors do not grant fictitious MP escape");
        trapped.CellId = 1;
        Check(MonsterTactics.Danger(sim, trapped, 2) < MonsterTactics.Danger(sim, trapped, 0),
            "permissions from the original cell do not certify a hypothetical position");
        trapped.CellId = 0;
    }
    var unknown = blocked with { NativeMovementPermissionOrigin=null };
    using (var sim = MonsterTactics.Simulation.Replay(unknown, trapped, Array.Empty<MonsterTactics.Action>()))
        Check(MonsterTactics.Danger(sim, trapped, 2) < MonsterTactics.Danger(sim, trapped, 0),
            "missing native permission evidence preserves the earlier estimate");
    var otherActor = blocked with { NativeMovementPermissionActorId=99 };
    using (var sim = MonsterTactics.Simulation.Replay(otherActor, trapped, Array.Empty<MonsterTactics.Action>()))
        Check(MonsterTactics.Danger(sim, trapped, 2) < MonsterTactics.Danger(sim, trapped, 0),
            "another actor's permissions do not certify this actor");
    var open = blocked with { MovementAnchorAllowed=(_, cell) => cell == 1 };
    using (var sim = MonsterTactics.Simulation.Replay(open, trapped, Array.Empty<MonsterTactics.Action>()))
        Check(MonsterTactics.Danger(sim, trapped, 2) < MonsterTactics.Danger(sim, trapped, 0),
            "an allowed neighboring anchor retains the existing escape estimate");
}

using (MapGeometry.BeginScope(new GeometryContext(
    new[] { new CellXYZ(0, 0, 0), new CellXYZ(1, 0, 0) },
    new[] { (0, 1), (1, 0) })))
{
    var guarded = new Fighter { Id=30, TeamId=0, CellId=0, CurrentHP=20, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0 };
    var threat = new Fighter { Id=31, TeamId=1, CellId=1, CurrentHP=100, MaxHP=100,
        CurrentAP=6, MaxAP=6, CurrentMP=0, MaxMP=0,
        NativeStats = new Dictionary<int,int> { [20]=0,[21]=0,[22]=0,[23]=0,[24]=0 } };
    var sameDomain = new Dictionary<int,int> { [20]=0,[21]=0,[22]=346,[23]=0,[24]=0 };
    threat.NativeStats = sameDomain;
    Check(Math.Abs(MonsterTactics.NativeThreatPotential(threat) - 1.865) < 1e-9,
        "observed water mastery raises danger by the bounded native potential factor");
    sameDomain[21] = 346;
    Check(Math.Abs(MonsterTactics.NativeThreatPotential(threat) - 1.865) < 1e-9,
        "equal mastery in a second elemental domain is not double-counted");
    sameDomain[21] = 0; sameDomain[23] = 399;
    Check(Math.Abs(MonsterTactics.NativeThreatPotential(threat) - 1.9975) < 1e-9,
        "a different higher elemental domain determines the bounded maximum");
    var sameSnapshot = new Dictionary<int,int>(sameDomain);

    using var sim = MonsterTactics.Simulation.Replay(
        new MonsterTactics.Board { Fighters = new[] { guarded, threat } }, guarded,
        Array.Empty<MonsterTactics.Action>());
    double highDomainRisk = MonsterTactics.Danger(sim, guarded);
    Check(sameDomain.OrderBy(pair=>pair.Key).SequenceEqual(sameSnapshot.OrderBy(pair=>pair.Key)),
        "danger weighting leaves the observed native stats unchanged");
    threat.NativeStats = new Dictionary<int,int> {
        [20]=int.MaxValue,[21]=int.MaxValue,[22]=int.MaxValue,[23]=int.MaxValue,[24]=int.MaxValue,
    };
    double extremeRisk = MonsterTactics.Danger(sim, guarded);
    Check(double.IsFinite(extremeRisk) && Math.Abs(extremeRisk / highDomainRisk - 2.0 / 1.9975) < 1e-9,
        "extreme integer stats saturate at twice neutral danger without overflow");
    var extremeStats = (Dictionary<int,int>)threat.NativeStats!;
    var preserved = new Dictionary<int,int>(extremeStats);
    threat.NativeStats = new Dictionary<int,int> {
        [20]=int.MinValue,[21]=int.MinValue,[22]=int.MinValue,[23]=int.MinValue,[24]=int.MinValue,
    };
    Check(MonsterTactics.NativeThreatPotential(threat) == 1,
        "negative extreme mastery clamps to neutral danger");
    threat.NativeStats = new Dictionary<int,int> { [20]=0,[21]=0,[22]=346,[23]=0 };
    Check(MonsterTactics.NativeThreatPotential(threat) == 1,
        "incomplete elemental stat evidence falls back to neutral danger");
    threat.NativeStats = extremeStats;
    Check(extremeStats.OrderBy(pair=>pair.Key).SequenceEqual(preserved.OrderBy(pair=>pair.Key))
          && extremeStats.Count == preserved.Count,
        "threat scoring does not mutate native stat dictionaries");

    var invisible = sim.Board with { Hidden = fighter => fighter.Id == threat.Id };
    using var hiddenSim = MonsterTactics.Simulation.Replay(invisible, guarded, Array.Empty<MonsterTactics.Action>());
    threat.NativeStats = sameDomain;
    Check(MonsterTactics.Danger(hiddenSim, guarded) == 0,
        "invisible enemies do not contribute weighted threat");
}
