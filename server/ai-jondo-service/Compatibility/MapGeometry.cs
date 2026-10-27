using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace Jondo.Unity.World.Maps;

public readonly record struct CellXYZ(int X, int Y, int Z);
public readonly record struct NativePortalRoute(int From, int To, bool UseOnce = false);
public readonly record struct NativePortalProjection(int Caster, int Entry, int Exit, int Landing, int BonusPercent = 0);

/// <summary>Private complete topology supplied for one advisory request.</summary>
public sealed class GeometryContext
{
    public IReadOnlyList<CellXYZ> Cells { get; }
    public int? OriginZ { get; }
    internal readonly Dictionary<(int X, int Y), int[]> AtXY;
    internal readonly int[][] Neighbors;
    internal readonly Dictionary<int, NativePortalRoute> PortalRoutes;
    internal readonly Dictionary<(int, int, int), NativePortalProjection> PortalProjections;

    public GeometryContext(IReadOnlyList<CellXYZ> cells,
        IEnumerable<(int From, int To)> directedEdges, int? originZ = null,
        IEnumerable<NativePortalRoute>? portalRoutes = null,
        IEnumerable<NativePortalProjection>? portalProjections = null)
    {
        // The unchanged core's sight memo uses from * MaxCells + to as Int32.
        if (cells.Count > 46340) throw new ArgumentException("Topology exceeds the literal core's collision-free cell-key capacity");
        var copy = cells.ToArray();
        if (copy.Distinct().Count() != copy.Length) throw new ArgumentException("Duplicate XYZ cell");
        Cells = Array.AsReadOnly(copy);
        OriginZ = originZ;
        AtXY = copy.Select((p, id) => (p, id)).GroupBy(v => (v.p.X, v.p.Y))
            .ToDictionary(g => g.Key, g => g.Select(v => v.id).ToArray());
        var next = Enumerable.Range(0, copy.Length).Select(_ => new HashSet<int>()).ToArray();
        foreach (var (from, to) in directedEdges)
        {
            RequireCell(from); RequireCell(to);
            next[from].Add(to);
        }
        Neighbors = next.Select(v => v.OrderBy(n => n).ToArray()).ToArray();
        PortalRoutes = new();
        foreach (var route in portalRoutes ?? Array.Empty<NativePortalRoute>())
        {
            RequireCell(route.From); RequireCell(route.To);
            if (!PortalRoutes.TryAdd(route.From, route)) throw new ArgumentException("Ambiguous native portal route");
        }
        PortalProjections = new();
        foreach (var projection in portalProjections ?? Array.Empty<NativePortalProjection>())
        {
            RequireCell(projection.Caster); RequireCell(projection.Entry);
            RequireCell(projection.Exit); RequireCell(projection.Landing);
            if (!PortalProjections.TryAdd((projection.Caster, projection.Entry, projection.Exit), projection))
                throw new ArgumentException("Ambiguous native portal projection");
        }
    }

    private void RequireCell(int cell)
    {
        if (cell < 0 || cell >= Cells.Count) throw new ArgumentException("Topology reference outside the complete cell table");
    }
}

/// <summary>Geometry compatibility boundary; never uses Dofus's 560-cell grid.</summary>
public static class MapGeometry
{
    private sealed record Scope(GeometryContext Context, int? OriginZ);
    private static readonly AsyncLocal<Scope?> Current = new();
    private static Scope Active => Current.Value ?? throw new InvalidOperationException("Missing request-scoped native geometry");
    public static GeometryContext Context => Active.Context;
    public static int MaxCells => Context.Cells.Count;

    public static IDisposable BeginScope(GeometryContext context)
    {
        var previous = Current.Value;
        Current.Value = new Scope(context, context.OriginZ);
        return new RestoreScope(previous);
    }

    public static IDisposable WithOriginZ(int? z)
    {
        var previous = Active;
        Current.Value = previous with { OriginZ = z };
        return new RestoreScope(previous);
    }

    private sealed class RestoreScope(Scope? previous) : IDisposable
    {
        private bool disposed;
        public void Dispose()
        {
            if (disposed) return;
            Current.Value = previous;
            disposed = true;
        }
    }

    public static bool IsValid(int cell) => cell >= 0 && cell < MaxCells;
    public static (int X, int Y) CellToPoint(int cell) => IsValid(cell)
        ? (Context.Cells[cell].X, Context.Cells[cell].Y) : (int.MinValue, int.MinValue);
    public static CellXYZ CellToXYZ(int cell) => IsValid(cell) ? Context.Cells[cell]
        : throw new ArgumentOutOfRangeException(nameof(cell));

    public static int PointToCell(int x, int y)
    {
        if (!Context.AtXY.TryGetValue((x, y), out var candidates)) return -1;
        if (candidates.Length == 1) return candidates[0];
        if (Active.OriginZ is not int z) return -1;
        foreach (var cell in candidates) if (Context.Cells[cell].Z == z) return cell;
        return -1;
    }

    public static int PointToCell(int x, int y, int z)
    {
        if (!Context.AtXY.TryGetValue((x, y), out var candidates)) return -1;
        foreach (var cell in candidates) if (Context.Cells[cell].Z == z) return cell;
        return -1;
    }

    public static IEnumerable<int> GetNeighbors(int cell) => IsValid(cell)
        ? Context.Neighbors[cell] : Array.Empty<int>();
    public static bool HasDirectedEdge(int from, int to) => IsValid(from) && IsValid(to)
        && Array.BinarySearch(Context.Neighbors[from], to) >= 0;

    // Range metric, not BFS movement distance: obstacles must not inflate range.
    public static int Distance(int a, int b)
    {
        if (!IsValid(a) || !IsValid(b)) return 999;
        var p = Context.Cells[a]; var q = Context.Cells[b];
        return (int)Math.Min(int.MaxValue, Math.Abs((long)p.X - q.X) + Math.Abs((long)p.Y - q.Y));
    }

    public static int Reflejar(int cell, int pivot)
    {
        if (!IsValid(cell) || !IsValid(pivot)) return -1;
        var p = Context.Cells[cell]; var q = Context.Cells[pivot];
        long x = 2L * q.X - p.X, y = 2L * q.Y - p.Y;
        if (x < int.MinValue || x > int.MaxValue || y < int.MinValue || y > int.MaxValue) return -1;
        return PointToCell((int)x, (int)y);
    }

    public static bool TryPortalRoute(int from, out NativePortalRoute route) => Context.PortalRoutes.TryGetValue(from, out route);
    public static bool TryPortalProjection(int caster, int entry, int exit, out NativePortalProjection projection)
        => Context.PortalProjections.TryGetValue((caster, entry, exit), out projection);

    public static List<int> FindShortestPath(int start, int target, HashSet<int>? walkableCells = null,
        HashSet<int>? occupiedCells = null)
    {
        if (!IsValid(start) || !IsValid(target)) return new();
        var parent = new Dictionary<int, int> { [start] = start };
        var pending = new Queue<int>(); pending.Enqueue(start);
        while (pending.Count > 0 && !parent.ContainsKey(target))
        {
            int at = pending.Dequeue();
            foreach (int next in GetNeighbors(at))
            {
                if (parent.ContainsKey(next) || walkableCells != null && !walkableCells.Contains(next)
                    || occupiedCells?.Contains(next) == true) continue;
                parent[next] = at; pending.Enqueue(next);
            }
        }
        if (!parent.ContainsKey(target)) return new();
        var path = new List<int>();
        for (int at = target; ; at = parent[at]) { path.Add(at); if (at == start) break; }
        path.Reverse(); return path;
    }
}
