using System.Diagnostics;
using System.Text.Json;
using Wakfu.Jondo;

internal static class PlannerDeadlineCases
{
    public static int Run()
    {
        int checks = 0;
        var gate = new PlanningGate();
        foreach (int budget in new[] { 250, 500, 2000 })
        {
            using var document = JsonDocument.Parse(JsonSerializer.Serialize(Request(budget)));
            var request = document.RootElement;
            string before = request.GetRawText();
            var result = gate.RunAsync(request, Stopwatch.GetTimestamp(),
                (payload, deadline) => Planner.Decide(payload, deadlineTimestamp: deadline))
                .GetAwaiter().GetResult();
            var response = JsonSerializer.SerializeToElement(result.Response);
            if (result.Status != 200)
                throw new Exception($"FAIL: actual planner discarded its best prefix at budget {budget}: {response}");
            checks++;
            if (response.GetProperty("action").GetProperty("type").GetString() == "end_turn")
                throw new Exception($"FAIL: actual budgeted planner lost every valid attack prefix at {budget}ms: {response}");
            checks++;
            if (request.GetRawText() != before || response.GetProperty("source").GetRawText()
                != request.GetProperty("source").GetRawText())
                throw new Exception("FAIL: bounded planning changed its source custody");
            checks++;
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                kind = "actual_planner_bounded_search", budgetMs = budget,
                status = result.Status, action = response.GetProperty("action"),
                timing = result.Timing,
                scope = "actual Host/Gate/Core over a synthetic high-branching advisory board; not a native encounter",
            }));
            Console.WriteLine($"PASS: actual planner retains an unchanged-source useful prefix within {budget}ms admission");
        }
        return checks;
    }

    private static object Request(int budget)
    {
        const int width = 21;
        int Cell(int x, int y) => y * width + x;
        var cells = Enumerable.Range(0, width * width)
            .Select(id => new { id, xyz = new[] { id % width, id / width, 0 } }).ToArray();
        var edges = new List<int[]>();
        for (int y = 0; y < width; y++)
            for (int x = 0; x < width; x++)
            {
                if (x + 1 < width) { edges.Add(new[] { Cell(x, y), Cell(x + 1, y) }); edges.Add(new[] { Cell(x + 1, y), Cell(x, y) }); }
                if (y + 1 < width) { edges.Add(new[] { Cell(x, y), Cell(x, y + 1) }); edges.Add(new[] { Cell(x, y + 1), Cell(x, y) }); }
            }
        var actors = new List<object>
        {
            new { id = 1L, team = 0, cell = Cell(10, 10), hp = 1000, maxHp = 1000,
                ap = 18, maxAp = 18, mp = 6, maxMp = 6, wp = 6, level = 100 },
        };
        int[][] enemies = { new[] { 15, 10 }, new[] { 5, 10 }, new[] { 10, 15 }, new[] { 10, 5 },
            new[] { 14, 14 }, new[] { 6, 14 }, new[] { 14, 6 }, new[] { 6, 6 } };
        for (int i = 0; i < enemies.Length; i++)
            actors.Add(new { id = 2L + i, team = 1, cell = Cell(enemies[i][0], enemies[i][1]),
                hp = 10000, maxHp = 10000, ap = 6, maxAp = 6, mp = 0, maxMp = 0, wp = 6, level = 100 });
        var spells = Enumerable.Range(0, 12).Select(index => new
        {
            id = 12000 + index, grade = 100, cost = 1 + index % 3, minRange = 1, maxRange = 8,
            damage = 12 + index, element = "neutral", needsLineOfSight = false,
            rows = new[] { new { kind = "damage", amount = 12 + index, target = "enemy", fixedCells = new[] { new[] { 0, 0 } } } },
        }).ToArray();
        return new
        {
            protocol = 1, requestId = "deadline-" + budget,
            source = new { actorId = 1L, fightInstanceId = "deadline-" + budget,
                turnId = 1, catalogRevision = "bounded-search-fixture", stateRevision = 1, actionId = 0 },
            board = new { cells, edges, actors, round = 1, lineOfSight = Array.Empty<object>() },
            spells, native = new { usage = Array.Empty<object>() },
            excludedActions = Array.Empty<string>(), limits = new { budgetMs = budget },
        };
    }
}
