using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Wakfu.Jondo;

internal interface ISpecificAi
{
    string Id { get; }
    IReadOnlyList<int> References { get; }
    IEnumerable<SpecificAction> Propose(SpecificContext context);
}

internal sealed record SpecificAction(object Action, double Score, string Reason);

internal sealed class SpecificActor
{
    public JsonElement Raw { get; }
    public long Id => Raw.GetProperty("id").GetInt64();
    public int Reference => SpecificContext.Int(Raw, "monsterRef");
    public int Team => SpecificContext.Int(Raw, "team");
    public int Cell => SpecificContext.Int(Raw, "cell", -1);
    public int Hp => SpecificContext.Int(Raw, "hp");
    public int MaxHp => SpecificContext.Int(Raw, "maxHp");
    public int Wp => SpecificContext.Int(Raw, "wp");
    public int Direction => SpecificContext.Int(Raw, "direction", -1);
    public bool Player => Raw.TryGetProperty("isPlayer", out var p) && p.ValueKind == JsonValueKind.True;
    public long SummonerId => Raw.TryGetProperty("summonerId", out var p) && p.ValueKind == JsonValueKind.Number ? p.GetInt64() : 0;
    private readonly Dictionary<int, int> states = new();
    public SpecificActor(JsonElement raw)
    {
        Raw = raw;
        if (raw.TryGetProperty("states", out var entries))
            foreach (var state in entries.EnumerateArray())
            {
                int reference = SpecificContext.Int(state, "reference");
                states[reference] = states.GetValueOrDefault(reference) + SpecificContext.Int(state, "level");
            }
    }
    public int State(int reference) => states.GetValueOrDefault(reference);
    public bool Has(int reference) => states.ContainsKey(reference);
    public int Stat(int reference) => Raw.TryGetProperty("stats", out var stats)
        && stats.TryGetProperty(reference.ToString(), out var v) ? v.GetInt32() : 0;
}

/// <summary>Read-only advisory snapshot plus existing native-topology routes.</summary>
internal sealed class SpecificContext
{
    public JsonElement Request { get; }
    public MonsterTactics.Board Board { get; }
    public Fighter Actor { get; }
    public CellXYZ[] Cells { get; }
    public IReadOnlyList<MonsterTactics.Spell> Spells { get; }
    public IReadOnlyList<SpecificActor> Actors { get; }
    public SpecificActor Self { get; }
    public JsonElement RawSelf => Self.Raw;
    public IEnumerable<SpecificActor> Enemies => Actors.Where(a => a.Hp > 0 && a.Team != Self.Team && a.Player);
    public IEnumerable<SpecificActor> Allies => Actors.Where(a => a.Hp > 0 && a.Team == Self.Team);
    public int Round => Int(Request.GetProperty("board"), "round");
    private readonly Func<MonsterTactics.Spell, (int Ap, int Mp, int Wp)> costs;
    private readonly HashSet<(int, int)> gates;
    private readonly Dictionary<int, string> suppressed = new();
    private Dictionary<int, MonsterTactics.Route>? routes;
    public IReadOnlyDictionary<int, MonsterTactics.Route> Routes => routes ??= MonsterTactics.Routes(Board, Actor);
    public IReadOnlyDictionary<int, string> SuppressedSpells => suppressed;
    private IEnumerable<JsonElement> TurnActions => Request.TryGetProperty("native", out var n)
        && n.TryGetProperty("turnActions", out var a) ? a.EnumerateArray() : Enumerable.Empty<JsonElement>();
    public bool TurnHasMoved => TurnActions.Any(a => Text(a, "type") is "move" or "portal_travel");
    public int TurnCastCount(int spell) => Math.Max(Actor.LanzadosEsteTurno.GetValueOrDefault(spell),
        TurnActions.Count(a => Text(a, "type") == "cast" && Int(a, "spellId") == spell));
    public IEnumerable<int> SpecialAimCells => Request.TryGetProperty("native", out var n)
        && n.TryGetProperty("specialAimCells", out var cells)
        ? cells.EnumerateArray().Select(c => c.GetInt32()).Where(Valid)
        : Enumerable.Range(0, Cells.Length).Where(c => !Occupied(c, Self.Cell));

    public SpecificContext(JsonElement request, MonsterTactics.Board board, Fighter actor,
        IReadOnlyList<MonsterTactics.Spell> spells, CellXYZ[] cells,
        Func<MonsterTactics.Spell, (int Ap, int Mp, int Wp)> nativeCosts, HashSet<(int, int)> portalEdges)
    {
        Request = request; Board = board; Actor = actor; Spells = spells; Cells = cells;
        costs = nativeCosts; gates = portalEdges;
        Actors = request.GetProperty("board").GetProperty("actors").EnumerateArray().Select(a => new SpecificActor(a)).ToArray();
        Self = Actors.Single(a => a.Id == actor.Id);
    }

    public bool NativeFlag(string name) => Request.TryGetProperty("native", out var n)
        && n.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True;
    public void SuppressSpell(int spell, string reason) => suppressed[spell] = reason;
    public SpecificAction EndTurn(double priority, string reason) => new(new { type = "end_turn" }, priority, reason);
    public IEnumerable<int> AreaCells(int reference) => Areas(reference)
        .SelectMany(a => a.TryGetProperty("cells", out var cells) ? cells.EnumerateArray().Select(c => c.GetInt32()) : Enumerable.Empty<int>())
        .Where(Valid).Distinct();
    public IEnumerable<int> AreaAnchors(int reference) => Areas(reference).Select(a => Int(a, "cell", -1)).Where(Valid).Distinct();
    private IEnumerable<JsonElement> Areas(int reference) => Request.GetProperty("board").TryGetProperty("mechanicAreas", out var rows)
        ? rows.EnumerateArray().Where(a => Int(a, "reference") == reference) : Enumerable.Empty<JsonElement>();
    public int Distance(int from, int to) => Valid(from) && Valid(to)
        ? Math.Abs(Cells[from].X - Cells[to].X) + Math.Abs(Cells[from].Y - Cells[to].Y) : int.MaxValue;
    private bool Valid(int cell) => cell >= 0 && cell < Cells.Length;

    public bool Behind(SpecificActor target, int sourceCell)
    {
        if (!Valid(sourceCell) || !Valid(target.Cell) || target.Direction is < 0 or > 7 || sourceCell == target.Cell) return false;
        // Same float32 normalization and thresholds as native Sl.o. This is
        // positional advice; World still evaluates the actual movement event.
        (int X, int Y)[] vectors = { (1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1) };
        float dx = unchecked(Cells[target.Cell].X - Cells[sourceCell].X);
        float dy = unchecked(Cells[target.Cell].Y - Cells[sourceCell].Y);
        float length = (float)Math.Sqrt((float)(dx * dx) + (float)(dy * dy));
        if (length != 0) { float reciprocal = 1f / length; dx *= reciprocal; dy *= reciprocal; }
        var v = vectors[target.Direction];
        return (float)((float)(dx * v.X) + (float)(dy * v.Y)) >= 0.72;
    }

    /// <summary>Candidate-only casts; no projected summon execution or state gifts.</summary>
    public IEnumerable<SpecificAction> Casts(int spellId, IEnumerable<int> aimCells, double priority, string reason,
        Func<int, int, double>? quality = null)
    {
        var spell = Spells.FirstOrDefault(s => s.Id == spellId);
        if (spell == null || Actor.Recarga.GetValueOrDefault(spellId) > 0
            || spell.PerTurn > 0 && TurnCastCount(spellId) >= spell.PerTurn) yield break;
        var cost = costs(spell);
        if (cost.Ap > Actor.CurrentAP || cost.Mp > Actor.CurrentMP || cost.Wp > Self.Wp) yield break;
        foreach (int aim in aimCells.Where(Valid).Distinct().Take(32))
        {
            var target = Board.Fighters.FirstOrDefault(f => f.IsAlive && f.Occupies(aim));
            if (target != null && spell.PerTarget > 0
                && Actor.LanzadosPorObjetivo.GetValueOrDefault((spellId, target.Id)) >= spell.PerTarget) continue;
            SpecificAction? best = null;
            foreach (var (from, route) in Routes)
            {
                if (cost.Ap > route.ActionPoints || cost.Mp > route.MovementPoints) continue;
                int distance = Distance(from, aim);
                int maximum = spell.MaxRange + (spell.RangeBoostable ? Actor.Range : 0);
                if (distance < spell.MinRange || distance > maximum) continue;
                if (spell.InLine && Cells[from].X != Cells[aim].X && Cells[from].Y != Cells[aim].Y) continue;
                if (spell.NeedsFreeCell && Occupied(aim, from)) continue;
                if (spell.NeedsLineOfSight && from != aim && !Board.Sees(from, aim)) continue;
                double value = quality?.Invoke(from, aim) ?? 0;
                if (!double.IsFinite(value)) continue;
                double score = priority + value - route.Steps * 0.02 - route.Danger * 0.05 - route.LostToTackles(Actor) * 0.1;
                object action = route.Path.Count > 1 ? Movement(route.Path)
                    : new { type = "cast", spellId, level = spell.Grade, target = XYZ(aim), targetId = target?.Id };
                var proposal = new SpecificAction(action, score, reason);
                if (best == null || best.Score < score) best = proposal;
            }
            if (best != null) yield return best;
        }
    }

    public IEnumerable<SpecificAction> Moves(Func<int, double> value, string reason, double priority, bool oncePerTurn = true)
    {
        if (oncePerTurn && TurnHasMoved) yield break;
        foreach (var (cell, route) in Routes)
        {
            if (route.Path.Count < 2) continue;
            double rank = value(cell);
            if (!double.IsFinite(rank)) continue;
            yield return new SpecificAction(Movement(route.Path), priority + rank
                - route.Steps * 0.02 - route.Danger * 0.05 - route.LostToTackles(Actor) * 0.1, reason);
        }
    }

    private bool Occupied(int cell, int sourceOrigin)
    {
        if (Board.Fighters.Any(f => f.IsAlive && f.Id != Actor.Id && f.Occupies(cell))) return true;
        if (cell == sourceOrigin) return true;
        var origin = Cells[sourceOrigin]; var own = Cells[Self.Cell]; var aim = Cells[cell];
        return Actor.ExtraCells.Any(other => Cells[other].X - own.X + origin.X == aim.X
            && Cells[other].Y - own.Y + origin.Y == aim.Y);
    }
    private object Movement(IReadOnlyList<int> path)
    {
        if (gates.Contains((path[0], path[1]))) return new { type = "portal_travel", destination = XYZ(path[1]) };
        var walked = new List<int[]>();
        for (int i = 1; i < path.Count; i++)
        {
            if (gates.Contains((path[i - 1], path[i]))) break;
            walked.Add(XYZ(path[i]));
        }
        return new { type = "move", path = walked };
    }
    private int[] XYZ(int cell) => new[] { Cells[cell].X, Cells[cell].Y, Cells[cell].Z };
    internal static int Int(JsonElement v, string key, int fallback = 0) => v.TryGetProperty(key, out var p) && p.ValueKind == JsonValueKind.Number ? p.GetInt32() : fallback;
    private static string Text(JsonElement v, string key) => v.TryGetProperty(key, out var p) ? p.GetString() ?? "" : "";
}

internal static class SpecificAis
{
    private static readonly IReadOnlyDictionary<int, ISpecificAi> Profiles = BasicMechanicAis.Create()
        .Concat(SupremeMechanicAis.Create()).SelectMany(p => p.References.Select(r => (r, p))).ToDictionary(v => v.r, v => v.p);
    public static ISpecificAi? Resolve(int reference) => Profiles.GetValueOrDefault(reference);
    public static IReadOnlyCollection<int> References => Profiles.Keys.ToArray();
}
