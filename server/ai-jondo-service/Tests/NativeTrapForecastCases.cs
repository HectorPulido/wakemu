using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

internal static class NativeTrapForecastCases
{
    private static Fighter Make(long id, int team, int cell) => new()
    {
        Id = id, TeamId = team, CellId = cell, CurrentHP = 100, MaxHP = 100,
        CurrentAP = 6, MaxAP = 6, CurrentMP = 3, MaxMP = 3,
    };

    public static int Run()
    {
        int checks = 0;
        void Check(bool condition, string label)
        {
            if (!condition) throw new Exception("NativeTrapForecast: " + label);
            checks++;
        }

        using var geometry = MapGeometry.BeginScope(new GeometryContext(
            Enumerable.Range(0, 5).Select(x => new CellXYZ(x, 0, 0)).ToArray(),
            Enumerable.Range(0, 4).SelectMany(x => new[] { (x, x + 1), (x + 1, x) })));
        var caster = Make(1, 0, 0);
        var enemy = Make(2, 1, 4);
        var ally = Make(3, 0, 2);
        var board = new MonsterTactics.Board { Fighters = new[] { caster, enemy, ally } };
        var source = new { actorId = 1L, nativeIdentity = "native-A", fightInstanceId = "fight-A", turnId = 7 };
        var spell = JsonSerializer.SerializeToElement(new { id = 7001, grade = 2 });

        object Forecast(bool complete = true, string nativeIdentity = "native-A", long allyHp = 0,
            int enemyHp = 0, int ap = 0, int maxAp = 0, int apDuration = 0,
            int mp = 0, int maxMp = 0, int mpDuration = 0,
            bool recipientsComplete = true, bool? unrepresentedHarmsDetected = false,
            int triggerCell = 3, int triggerMpBefore = 3, int[]? triggerPath = null) => new
        {
            version = 1, certainty = "one_native_counterfactual_route", complete,
            recipientsComplete, unrepresentedHarmsDetected,
            nativeIdentity, fightInstanceId = "fight-A", turnId = 7,
            spellId = 7001, grade = 2, fromCell = 0, aimCell = 1,
            triggerActorId = 2L, triggerPath = triggerPath ?? new[] { 3 }, triggerCell, triggerMpBefore,
            deltas = new object[]
            {
                new { actorId = 1L, hp = 0, armor = 0, ap = 0, mp = 0, maxApDelta = 0, maxMpDelta = 0, apMaxDuration = 0, mpMaxDuration = 0 },
                new { actorId = 2L, hp = enemyHp, armor = 0, ap = 0, mp = 0, maxApDelta = 0, maxMpDelta = 0, apMaxDuration = 0, mpMaxDuration = 0 },
                new { actorId = 3L, hp = allyHp, armor = 0, ap, mp, maxApDelta = maxAp, maxMpDelta = maxMp, apMaxDuration = apDuration, mpMaxDuration = mpDuration },
            }
        };
        IReadOnlyList<NativeTrapForecast.Candidate> Read(object? forecast, int[][]? directedEdges = null)
        {
            var request = JsonSerializer.SerializeToElement(new { source, board = new { edges = directedEdges ?? new[] { new[] { 4, 3 } } } });
            var support = JsonSerializer.SerializeToElement(new { trapForecasts = forecast == null ? Array.Empty<object>() : new[] { forecast } });
            return NativeTrapForecast.Read(request, spell, support, board, caster);
        }
        IReadOnlyList<NativeSupportCandidates.Candidate> Propose(object? forecast)
        {
            var trapForecasts = forecast == null ? Array.Empty<object>() : new[] { forecast };
            var support = new
            {
                version = 1, aimKinds = Array.Empty<string>(), intents = Array.Empty<string>(),
                effects = Array.Empty<object>(), summons = Array.Empty<object>(), candidateCells = Array.Empty<int>(),
                trapForecasts
            };
            var rawSpell = new
            {
                id = 7001, grade = 2, cost = 3, minRange = 1, maxRange = 3,
                nativeCosts = new { ap = 3, mp = 0, wp = 0 }, rows = Array.Empty<object>(), nativeSupport = support
            };
            var rawActors = new[]
            {
                new { id = 1L, team = 0, cell = 0, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3, wp = 0, states = Array.Empty<object>() },
                new { id = 2L, team = 1, cell = 4, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3, wp = 0, states = Array.Empty<object>() },
                new { id = 3L, team = 0, cell = 2, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3, wp = 0, states = Array.Empty<object>() },
            };
            var request = JsonSerializer.SerializeToElement(new
            {
                source, board = new { actors = rawActors, edges = new[] { new[] { 4, 3 } } }, spells = new[] { rawSpell }
            });
            var spells = new[] { new MonsterTactics.Spell { Id = 7001, Grade = 2, Cost = 3, MinRange = 1, MaxRange = 3 } };
            var cells = Enumerable.Range(0, 5).Select(x => new CellXYZ(x, 0, 0)).ToArray();
            return NativeSupportCandidates.Propose(request, board, caster, spells, cells,
                _ => (3, 0, 0), new HashSet<(int, int)>());
        }

        Check(Read(null).Count == 0, "absent forecasts produce no candidate");
        Check(Read(Forecast(nativeIdentity: "stale-native")).Count == 0, "stale native identity is rejected");
        Check(Read(Forecast(enemyHp: -10)).Count == 1, "valid single directed movement edge is accepted");
        Check(Read(Forecast(), Array.Empty<int[]>()).Count == 0, "missing directed movement edge is rejected");
        Check(Read(Forecast(), new[] { new[] { 3, 4 } }).Count == 0, "inverse-only movement edge is rejected");
        Check(Read(Forecast(triggerCell: 4, triggerPath: new[] { 4 })).Count == 0,
            "no-op movement onto the current cell is rejected");
        Check(Read(Forecast(triggerMpBefore: 0)).Count == 0, "movement with zero starting MP is rejected");
        Check(Read(Forecast(triggerPath: new[] { 2, 3 })).Count == 0, "multi-step path is rejected by single-step contract");
        Check(Propose(Forecast(enemyHp: -10)).Count > 0, "current forecast flows through NativeSupportCandidates into a real cast candidate");
        Check(Propose(null).Count == 0 && Propose(Forecast(nativeIdentity: "stale-native")).Count == 0,
            "absent and stale forecasts fall back without trap candidates");
        var uncertifiedPartial = new
        {
            version = 1, certainty = "one_native_counterfactual_route", complete = false,
            nativeIdentity = "native-A", fightInstanceId = "fight-A", turnId = 7,
            spellId = 7001, grade = 2, fromCell = 0, aimCell = 1,
            triggerActorId = 2L, triggerPath = new[] { 3 }, triggerCell = 3, triggerMpBefore = 3,
            deltas = Array.Empty<object>()
        };
        Check(Read(uncertifiedPartial).Count == 0, "partial record missing recipient and harm-detection status is rejected");
        Check(Read(Forecast(complete: false, unrepresentedHarmsDetected: true)).Count == 0,
            "partial record is rejected when unrepresented harms were detected");
        Check(Read(Forecast(complete: false, unrepresentedHarmsDetected: null)).Count == 0,
            "partial record with unknown harm-detection status is rejected");
        Check(Read(Forecast(complete: false, recipientsComplete: false)).Count == 0,
            "partial record with incomplete recipient coverage is rejected");

        var partialBenefits = JsonSerializer.SerializeToElement(Forecast(complete: false, enemyHp: -10));
        var benefit = Read(partialBenefits).Single();
        double expectedBenefit = 10 * MonsterTactics.TrapOdds(board, new[] { 3 }, 4, 3, 0)
            * NativeSupportCandidates.PartialConfidence;
        Check(benefit.Partial && Math.Abs(benefit.Value - expectedBenefit) < 1e-9,
            "partial beneficial enemy delta receives confidence discount");

        var partialAllyHarm = JsonSerializer.SerializeToElement(Forecast(complete: false, allyHp: -10));
        var harm = Read(partialAllyHarm).Single();
        double expectedHarm = -10 * MonsterTactics.TrapOdds(board, new[] { 3 }, 4, 3, 0);
        Check(harm.Value == expectedHarm, "partial record retains full penalty for harm to an ally");

        var retained = Read(Forecast(complete: true, ap: -2, maxAp: -2, apDuration: 2,
            mp: -1, maxMp: -1, mpDuration: 2)).Single();
        double retainedExpected = (-2 * MonsterTactics.StatWeight(1) - MonsterTactics.StatWeight(23)) * 1.3
            * MonsterTactics.TrapOdds(board, new[] { 3 }, 4, 3, 0);
        Check(Math.Abs(retained.Value - retainedExpected) < 1e-9,
            "current AP clamp and retained AP maximum are valued once, with duration weighting");
        return checks;
    }
}
