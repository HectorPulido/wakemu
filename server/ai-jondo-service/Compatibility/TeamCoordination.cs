using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace Wakfu.Jondo;

public sealed record TeamCorridor(long OwnerId, int OwnerCell, long TargetId, int TargetCell,
    IReadOnlySet<(int X, int Y)> Cells);

/// <summary>
/// Small, advisory utility for coordination facts confirmed by World. The host
/// must supply only current, validated encounter-local facts: a projected or
/// rejected action must never update the shared focus or reserved corridors.
/// </summary>
internal static class TeamCoordination
{
    internal readonly record struct Actor(long Id, int Team, int Hp, int Cell = -1, int Armor = 0);
    internal sealed record Context(long? FocusId, IReadOnlySet<(int X, int Y)> Reserved, bool? BlocksLos,
        IReadOnlyList<TeamCorridor> Corridors);

    // Optional advice is fail-closed: a malformed or foreign field must not
    // interrupt a real turn or introduce information about hidden fighters.
    internal static Context Read(JsonElement board, long actorId, int team,
        IReadOnlyDictionary<long, Actor> visible,
        IReadOnlyList<(int X, int Y)> cells)
    {
        var reserved = new HashSet<(int X, int Y)>();
        var accepted = new List<TeamCorridor>();
        Context Empty() => new(null, reserved, null, accepted);
        if (!board.TryGetProperty("coordination", out var data)
            || data.ValueKind != JsonValueKind.Object
            || !data.TryGetProperty("actorId", out var id) || id.ValueKind != JsonValueKind.Number || !id.TryGetInt64(out long owner)
            || owner != actorId
            || !data.TryGetProperty("team", out var side) || side.ValueKind != JsonValueKind.Number || !side.TryGetInt32(out int sourceTeam)
            || sourceTeam != team)
            return Empty();
        long? focus = null;
        if (data.TryGetProperty("focusId", out var focusValue)
            && focusValue.ValueKind == JsonValueKind.Number && focusValue.TryGetInt64(out long focusId)
            && visible.TryGetValue(focusId, out var focusActor) && focusActor.Team != team && focusActor.Hp > 0)
            focus = focusId;
        bool? blocks = data.TryGetProperty("actorBlocksNativeLos", out var block)
            && block.ValueKind is JsonValueKind.True or JsonValueKind.False ? block.GetBoolean() : null;
        if (data.TryGetProperty("corridors", out var corridors) && corridors.ValueKind == JsonValueKind.Array
            && corridors.GetArrayLength() <= 64)
        {
            foreach (var row in corridors.EnumerateArray())
            {
                if (row.ValueKind != JsonValueKind.Object
                    || !row.TryGetProperty("ownerId", out var ownerValue) || ownerValue.ValueKind != JsonValueKind.Number || !ownerValue.TryGetInt64(out long rowOwner)
                    || rowOwner == actorId || !visible.TryGetValue(rowOwner, out var ally) || ally.Team != team || ally.Hp <= 0
                    || !row.TryGetProperty("targetId", out var targetValue) || targetValue.ValueKind != JsonValueKind.Number || !targetValue.TryGetInt64(out long target)
                    || !visible.TryGetValue(target, out var enemy) || enemy.Team == team || enemy.Hp <= 0
                    || !row.TryGetProperty("cells", out var rowCells) || rowCells.ValueKind != JsonValueKind.Array
                    || rowCells.GetArrayLength() > cells.Count)
                    continue;
                var rowPoints = new List<(int X, int Y)>();
                bool valid = true;
                foreach (var entry in rowCells.EnumerateArray())
                {
                    if (entry.ValueKind != JsonValueKind.Number || !entry.TryGetInt32(out int cell) || cell < 0 || cell >= cells.Count) { valid = false; break; }
                    rowPoints.Add(cells[cell]);
                }
                if (valid)
                {
                    var points = rowPoints.ToHashSet();
                    reserved.UnionWith(points);
                    accepted.Add(new(rowOwner, ally.Cell, target, enemy.Cell, points));
                }
            }
        }
        return new(focus, reserved, blocks, accepted);
    }

    // Match the existing native tactical policy: focus contributes a small
    // share of actual health and armor loss, so it cannot reward a cast that
    // leaves both unchanged.
    internal static double FocusValue(long? focusId, int team, Actor before, Actor after)
    {
        if (focusId is null || before.Id != focusId || before.Id != after.Id
            || before.Team == team || after.Team != before.Team || before.Hp <= 0)
            return 0;
        long loss = Math.Max(0L, (long)before.Hp - Math.Max(0, after.Hp));
        long armorLoss = Math.Max(0L, (long)Math.Max(0, before.Armor) - Math.Max(0, after.Armor));
        return (loss + armorLoss) * 0.05;
    }

    /// <summary>
    /// Compare occupancy of confirmed native line-of-sight probes before and
    /// after a candidate. XY is deliberate: a native ray is blocked by an XY
    /// footprint across walkable heights. An actor that does not block LOS has
    /// no corridor cost. Scoring a delta avoids repeated penalties while the
    /// actor remains in the same position.
    /// </summary>
    internal static double CorridorValue(
        IReadOnlySet<(int X, int Y)> reserved,
        IEnumerable<(int X, int Y)> beforeFootprint,
        IEnumerable<(int X, int Y)> afterFootprint,
        bool blocksNativeLos)
    {
        if (!blocksNativeLos || reserved.Count == 0) return 0;
        bool before = beforeFootprint.Any(reserved.Contains);
        bool after = afterFootprint.Any(reserved.Contains);
        return 5.0 * (Convert.ToInt32(before) - Convert.ToInt32(after));
    }
}
