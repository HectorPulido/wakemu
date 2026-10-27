using System;
using System.Collections.Generic;
using System.Linq;
using Jondo.Unity.World.Maps;

namespace Jondo.Unity.World.Fights;

// Data surface required by the literal upstream planner. Routing comes only
// from native receipts; Dofus owner-count, nearest-chain and vector rules do not.
public sealed class Portal
{
    public int Id { get; set; }
    public long Owner { get; init; }
    public int Cell { get; init; }
    public int LayingSpell { get; init; }
    public int Grade { get; init; }
    public int DiceNum { get; init; }
    public int DiceSide { get; init; }
    public int Value { get; init; }
    public bool Used { get; set; }
    public long NeutralisedBy { get; set; }
    public bool Active { get; set; }
    public override string ToString() => $"native portal {Id} on {Cell}";
}

public sealed class PortalNetwork
{
    // API compatibility only: native capacities are already resolved by World.
    public const int PerOwner = int.MaxValue;
    private readonly List<Portal> portals = new();
    public IReadOnlyList<Portal> All => portals;
    public int Count => portals.Count;
    public Portal? At(int cell) => portals.FirstOrDefault(p => p.Cell == cell);
    public Portal? ById(int id) => portals.FirstOrDefault(p => p.Id == id);
    public Portal? Displaced(long owner) => null;
    public void Add(Portal portal)
    {
        if (portals.Any(p => p.Cell == portal.Cell || p.Id == portal.Id))
            throw new ArgumentException("Duplicate native portal cell or identity");
        portals.Add(portal);
    }
    public bool Remove(Portal portal) => portals.Remove(portal);

    public void SetNativeRoute(int entry, int exit, bool useOnce = false)
    {
        if (!MapGeometry.IsValid(entry) || !MapGeometry.IsValid(exit) || entry == exit)
            throw new ArgumentException("Invalid native portal endpoints");
        var route = new NativePortalRoute(entry, exit, useOnce);
        var routes = MapGeometry.Context.PortalRoutes;
        if (routes.TryGetValue(entry, out var existing) && existing != route)
            throw new ArgumentException("Ambiguous native portal route");
        routes[entry] = route;
        foreach (int cell in new[] { entry, exit })
            if (At(cell) == null)
                Add(new Portal { Id = portals.Count == 0 ? 1 : portals.Max(p => p.Id) + 1, Cell = cell });
        At(entry)!.Active = true;
    }

    public static bool Usable(Portal? portal, Func<int, long>? occupantOf, long ignoring = 0)
    {
        if (portal == null || !MapGeometry.TryPortalRoute(portal.Cell, out var route)) return false;
        if (route.UseOnce && portal.Used) return false;
        long occupant = occupantOf?.Invoke(portal.Cell) ?? 0;
        return occupant == 0 || occupant == ignoring;
    }

    public bool ShouldBeActive(Portal portal, Func<int, long>? occupantOf, long ignoring = 0)
    {
        if (!Usable(portal, occupantOf, ignoring)
            || !MapGeometry.TryPortalRoute(portal.Cell, out var route)) return false;
        var exit = At(route.To);
        // The supplied directed route determines the destination. There is no
        // invented owner gate, nearest-neighbor ordering or four-portal limit.
        if (exit == null || route.UseOnce && exit.Used) return false;
        long occupant = occupantOf?.Invoke(exit.Cell) ?? 0;
        return occupant == 0 || occupant == ignoring;
    }

    public List<Portal> Refresh(Func<int, long>? occupantOf)
    {
        var changed = new List<Portal>();
        foreach (var portal in portals.OrderBy(p => p.Id))
        {
            bool active = ShouldBeActive(portal, occupantOf);
            if (portal.Active == active) continue;
            portal.Active = active; changed.Add(portal);
        }
        return changed;
    }

    public void TurnBegins(long fighter)
    {
        // Only reset receipt-declared once-per-turn consumption. Native state
        // and neutralization are refreshed by the next World decision frame.
        foreach (var portal in portals)
            if (MapGeometry.TryPortalRoute(portal.Cell, out var route) && route.UseOnce) portal.Used = false;
    }

    public List<Portal> Chain(Portal? entry, Func<int, long>? occupantOf, long traveller = 0)
    {
        var chain = new List<Portal>();
        if (entry == null || !ShouldBeActive(entry, occupantOf, traveller)) return chain;
        chain.Add(entry);
        if (MapGeometry.TryPortalRoute(entry.Cell, out var route) && At(route.To) is { } exit)
            chain.Add(exit);
        return chain;
    }

    public static int Projection(int casterCell, int entryCell, int exitCell)
        => MapGeometry.TryPortalProjection(casterCell, entryCell, exitCell, out var projection)
            ? projection.Landing : -1;

    public static int CellsBetween(IReadOnlyList<Portal>? chain)
    {
        int distance = 0;
        for (int index = 1; index < (chain?.Count ?? 0); index++)
            distance += MapGeometry.Distance(chain![index - 1].Cell, chain[index].Cell);
        return distance;
    }

    public static int BonusPercent(IReadOnlyList<Portal>? chain)
    {
        // A routing edge alone proves no damage amplification. Return only a
        // bonus that all complete native projection receipts agree on.
        if (chain == null || chain.Count < 2) return 0;
        int entry = chain[0].Cell, exit = chain[^1].Cell;
        var bonuses = MapGeometry.Context.PortalProjections.Values
            .Where(p => p.Entry == entry && p.Exit == exit).Select(p => p.BonusPercent).Distinct().ToArray();
        return bonuses.Length == 1 ? bonuses[0] : 0;
    }
}
