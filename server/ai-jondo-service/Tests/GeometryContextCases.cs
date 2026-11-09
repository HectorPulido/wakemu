using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class GeometryContextCases
{
    public static int Run()
    {
        int checks = 0;
        void Check(bool okay, string message)
        {
            if (!okay) throw new Exception("FAIL: " + message);
            Console.WriteLine("PASS: " + message);
            checks++;
        }

        var cells = Enumerable.Range(0, 6).Select(x => new CellXYZ(x, 0, 0)).ToArray();
        var orderedEdges = new[] { (0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (4, 3), (2, 0) };
        var noisyEdges = new[] { (2, 3), (0, 2), (3, 4), (1, 3), (0, 1), (2, 3), (4, 3), (2, 0) };
        using (MapGeometry.BeginScope(new GeometryContext(cells, orderedEdges)))
        {
            Check(MapGeometry.GetNeighbors(0).SequenceEqual(new[] { 1, 2 }),
                "neighbors retain ascending order and discard repeated directed edges");
            Check(MapGeometry.GetNeighbors(4).SequenceEqual(new[] { 3 })
                && !MapGeometry.HasDirectedEdge(3, 0),
                "reverse edges are not inferred and explicit reverse edges remain directed");
            Check(MapGeometry.GetNeighbors(5).SequenceEqual(Array.Empty<int>()),
                "a valid node without outgoing edges remains an isolated node");
            Check(MapGeometry.GetNeighbors(99).SequenceEqual(Array.Empty<int>())
                && !MapGeometry.HasDirectedEdge(-1, 0),
                "invalid neighbor queries stay empty and invalid edges stay absent");
            Check(MapGeometry.FindShortestPath(0, 3).SequenceEqual(new[] { 0, 1, 3 }),
                "BFS tie breaking follows sorted neighbor order");
        }
        using (MapGeometry.BeginScope(new GeometryContext(cells, noisyEdges)))
        {
            Check(MapGeometry.GetNeighbors(0).SequenceEqual(new[] { 1, 2 })
                && MapGeometry.FindShortestPath(0, 3).SequenceEqual(new[] { 0, 1, 3 }),
                "shuffled duplicated edges preserve exact neighbors and BFS path");
        }

        bool invalidEdgeRejected = false;
        try { _ = new GeometryContext(cells, new[] { (0, 6) }); }
        catch (ArgumentException) { invalidEdgeRejected = true; }
        Check(invalidEdgeRejected, "out-of-range topology edge is rejected");
        bool duplicateCellRejected = false;
        try { _ = new GeometryContext(new[] { cells[0], cells[0] }, Array.Empty<(int, int)>()); }
        catch (ArgumentException) { duplicateCellRejected = true; }
        Check(duplicateCellRejected, "duplicate XYZ cells are rejected");

        JsonElement Request(string instance, int[][] edges) => JsonSerializer.SerializeToElement(new
        {
            protocol = 1,
            requestId = instance,
            source = new { actorId = 1L, fightInstanceId = instance, turnId = 1, catalogRevision = "geometry-v1" },
            board = new
            {
                cells = Enumerable.Range(0, 4).Select(id => new { id, xyz = new[] { id, 0, 0 } }).ToArray(),
                edges,
                actors = new[]
                {
                    new { id = 1L, team = 0, cell = 0, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3 },
                    new { id = 2L, team = 1, cell = 3, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 0, maxMp = 0 },
                },
                lineOfSight = Enumerable.Range(0, 4)
                    .SelectMany(from => Enumerable.Range(0, 4).Select(to => new object[] { from, to, true }))
                    .ToArray(),
            },
            spells = new[] { new
            {
                id = 8080, grade = 1, cost = 3, minRange = 1, maxRange = 1, damage = 20,
                rows = new[] { new { kind = "damage", amount = 20, target = "enemy", fixedCells = new[] { new[] { 0, 0 } } } },
            } },
            native = new { usage = Array.Empty<object>() },
            excludedActions = Array.Empty<string>(),
            limits = new { budgetMs = 1000 },
        });

        var clean = Request("geometry-clean", new[] { new[] { 0, 1 }, new[] { 1, 2 }, new[] { 2, 3 },
            new[] { 1, 0 }, new[] { 2, 1 }, new[] { 3, 2 } });
        var noisy = Request("geometry-noisy", new[] { new[] { 2, 3 }, new[] { 1, 0 }, new[] { 0, 1 },
            new[] { 2, 1 }, new[] { 2, 3 }, new[] { 1, 2 }, new[] { 3, 2 } });
        var cleanAction = JsonSerializer.SerializeToElement(Wakfu.Jondo.Planner.Decide(clean)).GetProperty("action");
        var noisyAction = JsonSerializer.SerializeToElement(Wakfu.Jondo.Planner.Decide(noisy)).GetProperty("action");
        Check(cleanAction.GetRawText() == noisyAction.GetRawText(),
            "real Host action is identical for sorted edges and shuffled duplicates");
        return checks;
    }
}
