using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Wakfu.Jondo;

/// <summary>Scores bounded native counterfactuals, discounting partial benefits; never certifies a cast.</summary>
internal static class NativeTrapForecast
{
    internal readonly record struct Candidate(int Aim, double Value, bool Partial);

    private static bool Integer(JsonElement value, string name, out int result)
    {
        result = 0;
        return value.TryGetProperty(name, out var field) && field.ValueKind == JsonValueKind.Number
            && field.TryGetInt32(out result);
    }
    private static bool Identity(JsonElement value, string name, out long result)
    {
        result = 0;
        return value.TryGetProperty(name, out var field) && field.ValueKind == JsonValueKind.Number
            && field.TryGetInt64(out result);
    }
    private static bool Same(JsonElement left, JsonElement right, string name)
        => left.TryGetProperty(name, out var a) && right.TryGetProperty(name, out var b)
           && a.ValueKind == b.ValueKind && a.ValueKind is JsonValueKind.String or JsonValueKind.Number
           && a.GetRawText() == b.GetRawText();

    private static bool DirectedStep(JsonElement request, int from, int to)
    {
        if (!request.TryGetProperty("board", out var board) || board.ValueKind != JsonValueKind.Object
            || !board.TryGetProperty("edges", out var edges) || edges.ValueKind != JsonValueKind.Array) return false;
        foreach (var edge in edges.EnumerateArray())
            if (edge.ValueKind == JsonValueKind.Array && edge.GetArrayLength() == 2
                && edge[0].ValueKind == JsonValueKind.Number && edge[0].TryGetInt32(out int a)
                && edge[1].ValueKind == JsonValueKind.Number && edge[1].TryGetInt32(out int b)
                && a == from && b == to) return true;
        return false;
    }

    internal static IReadOnlyList<Candidate> Read(JsonElement request, JsonElement spell,
        JsonElement support, MonsterTactics.Board board, Fighter actor)
    {
        var accepted = new List<Candidate>();
        if (!request.TryGetProperty("source", out var source) || source.ValueKind != JsonValueKind.Object
            || !source.TryGetProperty("nativeIdentity", out var identity) || identity.ValueKind != JsonValueKind.String
            || string.IsNullOrEmpty(identity.GetString())
            || !source.TryGetProperty("fightInstanceId", out var encounter) || encounter.ValueKind != JsonValueKind.String
            || string.IsNullOrEmpty(encounter.GetString()) || !Integer(source, "turnId", out _)
            || !Identity(source, "actorId", out long sourceActor) || sourceActor != actor.Id
            || !Integer(spell, "id", out int spellId) || !Integer(spell, "grade", out int grade)
            || !support.TryGetProperty("trapForecasts", out var forecasts) || forecasts.ValueKind != JsonValueKind.Array
            || forecasts.GetArrayLength() > 16) return accepted;
        var living = board.Fighters.Where(f => f.IsAlive).ToDictionary(f => f.Id);
        if (living.Values.Any(f => board.Hidden(f))) return accepted;
        foreach (var forecast in forecasts.EnumerateArray())
        {
            if (forecast.ValueKind != JsonValueKind.Object
                || !forecast.TryGetProperty("complete", out var completeness)
                || completeness.ValueKind is not (JsonValueKind.True or JsonValueKind.False)) continue;
            bool partial = completeness.ValueKind == JsonValueKind.False;
            if (partial && (!forecast.TryGetProperty("recipientsComplete", out var recipients)
                || recipients.ValueKind != JsonValueKind.True
                || !forecast.TryGetProperty("unrepresentedHarmsDetected", out var harms)
                || harms.ValueKind != JsonValueKind.False)) continue;
            if (forecast.ValueKind != JsonValueKind.Object || !Integer(forecast, "version", out int version) || version != 1
                || !forecast.TryGetProperty("certainty", out var certainty) || certainty.ValueKind != JsonValueKind.String
                || certainty.GetString() != "one_native_counterfactual_route"
                || !Same(source, forecast, "nativeIdentity") || !Same(source, forecast, "fightInstanceId")
                || !Same(source, forecast, "turnId")
                || !Integer(forecast, "spellId", out int id) || id != spellId
                || !Integer(forecast, "grade", out int level) || level != grade
                || !Integer(forecast, "fromCell", out int from) || from != actor.CellId
                || !Integer(forecast, "aimCell", out int aim) || !MapGeometry.IsValid(aim)
                || !Identity(forecast, "triggerActorId", out long triggerId)
                || !living.TryGetValue(triggerId, out var trigger) || trigger.TeamId == actor.TeamId
                || !Integer(forecast, "triggerMpBefore", out int triggerMp) || triggerMp < 1 || triggerMp > 255
                || !Integer(forecast, "triggerCell", out int triggerCell) || !MapGeometry.IsValid(triggerCell)
                || triggerCell == trigger.CellId || !DirectedStep(request, trigger.CellId, triggerCell)
                || !forecast.TryGetProperty("triggerPath", out var path) || path.ValueKind != JsonValueKind.Array
                || path.GetArrayLength() != 1
                || path.EnumerateArray().Any(p => p.ValueKind != JsonValueKind.Number || !p.TryGetInt32(out int n) || !MapGeometry.IsValid(n))
                || path[path.GetArrayLength() - 1].GetInt32() != triggerCell
                || !forecast.TryGetProperty("deltas", out var deltas) || deltas.ValueKind != JsonValueKind.Array
                || deltas.GetArrayLength() != living.Count) continue;
            var seen = new HashSet<long>();
            double value = 0;
            bool valid = true;
            foreach (var row in deltas.EnumerateArray())
            {
                if (row.ValueKind != JsonValueKind.Object || !Identity(row, "actorId", out long victimId)
                    || !living.TryGetValue(victimId, out var victim) || !seen.Add(victimId)
                    || !Integer(row, "hp", out int hp) || !Integer(row, "armor", out int armor)
                    || !Integer(row, "ap", out int ap) || !Integer(row, "mp", out int mp)
                    || !Integer(row, "maxApDelta", out int maxAp) || !Integer(row, "maxMpDelta", out int maxMp)
                    || !Integer(row, "apMaxDuration", out int apDuration) || !Integer(row, "mpMaxDuration", out int mpDuration)
                    || new[] { hp, armor, ap, mp, maxAp, maxMp }.Any(v => Math.Abs((long)v) > 1000000)
                    || apDuration is < 0 or > 1000 || mpDuration is < 0 or > 1000
                    || maxAp != 0 && apDuration == 0 || maxMp != 0 && mpDuration == 0
                    || maxAp != 0 && ap != 0 && Math.Sign(maxAp) != Math.Sign(ap)
                    || maxMp != 0 && mp != 0 && Math.Sign(maxMp) != Math.Sign(mp))
                { valid = false; break; }
                // A current-resource clamp caused by the maximum change is one
                // effect, not a second removal. Reuse the planner's weights and
                // its existing 1.3 duration factor for retained stat effects.
                double apValue = maxAp == 0 ? ap : Math.Sign(maxAp) * Math.Max(Math.Abs((long)ap), Math.Abs((long)maxAp)) * (apDuration >= 2 ? 1.3 : 1);
                double mpValue = maxMp == 0 ? mp : Math.Sign(maxMp) * Math.Max(Math.Abs((long)mp), Math.Abs((long)maxMp)) * (mpDuration >= 2 ? 1.3 : 1);
                double sign = victim.TeamId == actor.TeamId ? 1 : -1;
                foreach (double part in new[] { (double)hp, armor * MonsterTactics.StatWeight(96),
                    apValue * MonsterTactics.StatWeight(1), mpValue * MonsterTactics.StatWeight(23) })
                {
                    double contribution = sign * part;
                    value += partial && contribution > 0 ? contribution * NativeSupportCandidates.PartialConfidence : contribution;
                }
            }
            if (!valid || seen.Count != living.Count) continue;
            double odds = MonsterTactics.TrapOdds(board, new[] { triggerCell }, trigger.CellId, triggerMp, actor.CellId);
            value *= odds;
            if (double.IsFinite(value)) accepted.Add(new Candidate(aim, value, partial));
        }
        return accepted;
    }
}
