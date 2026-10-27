using System.Security.Cryptography;
using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;

namespace Wakfu.Jondo;

/// <summary>Bounded upstream plans, rebound to fresh advisory state before every offer.</summary>
internal static class TurnPlans
{
    private sealed record Step(int Spell, int Grade, int From, int Aim, long Target);
    private sealed class Entry(Step[] steps)
    {
        public readonly Step[] Steps = steps;
        public int Index;
        public DateTime LastUsed = DateTime.UtcNow;
        public string OfferedSource = "";
        public string OfferedType = "";
        public int OfferedSpell;
        public int OfferedCount;
    }
    // The host's CoreLock serializes this and the unchanged upstream engine.
    private static readonly Dictionary<string, Entry> Entries = new();
    private static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(5);
    private const int Capacity = 128;

    public static bool TryGet(JsonElement request, MonsterTactics.Board board, Fighter actor,
        IReadOnlyList<MonsterTactics.Spell> spells, out MonsterTactics.Action? step)
    {
        step = null;
        var key = Key(request);
        Cleanup();
        if (key == null || !Entries.TryGetValue(key, out var entry)) return false;
        bool Reject()
        {
            Entries.Remove(key);
            return false;
        }
        if (request.TryGetProperty("excludedActions", out var excluded) && excluded.GetArrayLength() > 0)
            return Reject();
        var pending = entry.Steps[entry.Index];
        if (entry.OfferedType == "cast")
        {
            actor.LanzadosEsteTurno.TryGetValue(entry.OfferedSpell, out int actual);
            if (entry.OfferedSpell != pending.Spell || actual < entry.OfferedCount) return Reject();
            if (actual > entry.OfferedCount)
            {
                // An offer is never an acknowledgement. Only the fresh native
                // committed usage counter can consume a planned cast.
                entry.Index++;
                entry.OfferedType = "";
                if (entry.Index >= entry.Steps.Length) return Reject();
                pending = entry.Steps[entry.Index];
            }
        }
        var spell = spells.SingleOrDefault(s => s.Id == pending.Spell && s.Grade == pending.Grade);
        var target = board.Fighters.FirstOrDefault(f => f.Id == pending.Target && f.IsAlive);
        if (spell == null || target == null || pending.Target != actor.Id && target.CellId != pending.Aim)
            return Reject();
        if (!global::Jondo.Unity.World.Maps.MapGeometry.IsValid(pending.From)
            || !global::Jondo.Unity.World.Maps.MapGeometry.IsValid(pending.Aim)) return Reject();
        // Do not retain hypothetical damage, resources, target objects or scores.
        // Revalidate recomputes the route, legality and value against this frame.
        var rebound = new MonsterTactics.Action(new[] { pending.From }, spell, target,
            pending.Aim, 0, Value: 0);
        step = MonsterTactics.Revalidate(board, actor, rebound);
        if (step == null) return Reject();
        entry.LastUsed = DateTime.UtcNow;
        return true;
    }

    public static void Store(JsonElement request, IReadOnlyList<MonsterTactics.Action> plan)
    {
        var key = Key(request);
        Cleanup();
        if (key == null) return;
        if (plan.Count == 0) { Entries.Remove(key); return; }
        Entries[key] = new Entry(plan.Select(s => new Step(s.Spell.Id, s.Spell.Grade,
            s.From, s.TargetCell, s.Target.Id)).ToArray());
        Cleanup();
    }

    public static void CaptureOffer(JsonElement request, Fighter actor, string type, int? spellId = null)
    {
        var key = Key(request);
        if (key == null || !Entries.TryGetValue(key, out var entry)) return;
        var pending = entry.Steps[entry.Index];
        if (type == "end_turn" || type == "cast" && spellId != pending.Spell)
        { Entries.Remove(key); return; }
        entry.OfferedSource = request.GetProperty("source").GetRawText();
        entry.OfferedType = type;
        entry.OfferedSpell = spellId ?? pending.Spell;
        actor.LanzadosEsteTurno.TryGetValue(entry.OfferedSpell, out entry.OfferedCount);
        entry.LastUsed = DateTime.UtcNow;
    }

    public static void Invalidate(JsonElement request)
    {
        var key = Key(request);
        if (key != null) Entries.Remove(key);
    }

    private static string? Key(JsonElement request)
    {
        if (!request.TryGetProperty("source", out var source)
            || !request.TryGetProperty("board", out var board)
            || !request.TryGetProperty("spells", out var spells)) return null;
        var identity = new List<string>();
        foreach (string name in new[] { "fightInstanceId", "actorId", "turnId", "catalogRevision" })
        {
            if (!source.TryGetProperty(name, out var field) || field.ValueKind is JsonValueKind.Null
                or JsonValueKind.Object or JsonValueKind.Array or JsonValueKind.Undefined) return null;
            identity.Add(field.GetRawText());
        }
        foreach (string name in new[] { "cells", "edges", "portalEdges" })
            identity.Add(board.TryGetProperty(name, out var field) ? field.GetRawText() : "null");
        // Hazard changes can alter the preferred cast origin, not merely its
        // route. Replan on a changed field while retaining reuse for equivalent
        // sparse entries received in a different serialization order.
        var danger = new Dictionary<int, double>();
        if (board.TryGetProperty("movementDanger", out var hazards))
            foreach (var row in hazards.EnumerateArray())
                danger[row.GetProperty("cell").GetInt32()] = row.GetProperty("cost").GetDouble();
        identity.Add(JsonSerializer.Serialize(danger.Where(kv => kv.Value > 0)
            .OrderBy(kv => kv.Key).Select(kv => new { cell = kv.Key, cost = kv.Value })));
        identity.Add(spells.GetRawText());
        return Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(identity)));
    }

    private static void Cleanup()
    {
        var cutoff = DateTime.UtcNow - Lifetime;
        foreach (var key in Entries.Where(p => p.Value.LastUsed < cutoff).Select(p => p.Key).ToArray()) Entries.Remove(key);
        foreach (var key in Entries.OrderBy(p => p.Value.LastUsed).Take(Math.Max(0, Entries.Count - Capacity))
            .Select(p => p.Key).ToArray()) Entries.Remove(key);
    }
}
