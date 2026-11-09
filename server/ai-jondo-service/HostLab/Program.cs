using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Wakfu.Jondo;

// Replay prepared, sanitized advisory requests through the actual admission gate
// and host. This does not simulate World commit, client ACKs or native turns.
try
{
    string directory = Path.Combine(AppContext.BaseDirectory, "Scenarios");
    string? selection = null, category = null, requestFile = null, sequenceFile = null;
    int repeat = 1;
    bool list = false;
    for (int i = 0; i < args.Length; i++)
    {
        string Next() => ++i < args.Length ? args[i] : throw new ArgumentException("Missing option value");
        switch (args[i])
        {
            case "--dir": directory = Next(); break;
            case "--request": requestFile = Next(); break;
            case "--sequence": sequenceFile = Next(); break;
            case "--scenario": selection = Next(); break;
            case "--category": category = Next(); break;
            case "--list": list = true; break;
            case "--repeat": repeat = int.Parse(Next()); break;
            default: throw new ArgumentException("Unknown option " + args[i]);
        }
    }
    if (repeat is < 1 or > 1000) throw new ArgumentException("Repeat must be between 1 and 1000");
    if (sequenceFile != null)
    {
        if (requestFile != null || selection != null || category != null || list || repeat != 1)
            throw new ArgumentException("--sequence cannot be combined with request, filters, --list or --repeat");
        using var sequence = JsonDocument.Parse(File.ReadAllText(sequenceFile));
        if (sequence.RootElement.ValueKind != JsonValueKind.Array || sequence.RootElement.GetArrayLength() == 0)
            throw new ArgumentException("Sequence must be a nonempty array");
        var steps = sequence.RootElement.EnumerateArray().ToArray();
        var requests = steps.Select(step => step.GetProperty("request")).ToArray();
        foreach (var request in requests) TurnPlans.Invalidate(request);
        bool allPassed = true;
        try
        {
            for (int i = 0; i < steps.Length; i++)
            {
                var request = requests[i];
                var expected = steps[i].GetProperty("expect");
                if (expected.ValueKind != JsonValueKind.Object) throw new ArgumentException("Sequence expectation must be an object");
                var fields = expected.EnumerateObject().Select(p => p.Name).ToArray();
                if (fields.Length == 0 || fields.Distinct().Count() != fields.Length
                    || fields.Any(f => f is not ("type" or "spellId" or "planReused" or "pathFirst")))
                    throw new ArgumentException("Invalid sequence expectation");
                if (expected.TryGetProperty("type", out var typeValue)
                    && (typeValue.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(typeValue.GetString())))
                    throw new ArgumentException("Invalid expected action type");
                if (expected.TryGetProperty("spellId", out var spellValue)
                    && (spellValue.ValueKind != JsonValueKind.Number || !spellValue.TryGetInt32(out _)))
                    throw new ArgumentException("Invalid expected spell ID");
                if (expected.TryGetProperty("planReused", out var reusedValue)
                    && reusedValue.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new ArgumentException("Invalid expected planReused");
                if (expected.TryGetProperty("pathFirst", out var firstCell)
                    && (firstCell.ValueKind != JsonValueKind.Array || firstCell.GetArrayLength() != 3
                        || firstCell.EnumerateArray().Any(v => v.ValueKind != JsonValueKind.Number || !v.TryGetInt32(out _))))
                    throw new ArgumentException("Invalid expected pathFirst");
                var gate = new PlanningGate();
                var result = await gate.RunAsync(request, Stopwatch.GetTimestamp(),
                    (payload, deadline) => Planner.Decide(payload, deadline));
                var response = JsonSerializer.SerializeToElement(result.Response);
                var failures = new List<string>();
                if (result.Status != 200) failures.Add("unexpected status");
                else
                {
                    if (!JsonNode.DeepEquals(JsonNode.Parse(response.GetProperty("source").GetRawText()),
                        JsonNode.Parse(request.GetProperty("source").GetRawText())))
                        failures.Add("source identity changed");
                    var action = response.GetProperty("action");
                    if (expected.TryGetProperty("type", out var type) && action.GetProperty("type").GetString() != type.GetString())
                        failures.Add("unexpected action type");
                    if (expected.TryGetProperty("spellId", out var spell)
                        && (!action.TryGetProperty("spellId", out var actual) || actual.ValueKind != JsonValueKind.Number
                            || !actual.TryGetInt32(out int actualId) || actualId != spell.GetInt32()))
                        failures.Add("unexpected spell");
                    if (expected.TryGetProperty("planReused", out var reused)
                        && response.GetProperty("planReused").GetBoolean() != reused.GetBoolean())
                        failures.Add("unexpected continuation reuse");
                    if (expected.TryGetProperty("pathFirst", out var pathFirst)
                        && (!action.TryGetProperty("path", out var path) || path.ValueKind != JsonValueKind.Array
                            || path.GetArrayLength() == 0
                            || !JsonNode.DeepEquals(JsonNode.Parse(path[0].GetRawText()), JsonNode.Parse(pathFirst.GetRawText()))))
                        failures.Add("unexpected first path cell");
                }
                allPassed &= failures.Count == 0;
                Console.WriteLine(JsonSerializer.Serialize(new { step = i + 1, passed = failures.Count == 0,
                    failures, status = result.Status, response,
                    scope = "C# host sequence over supplied snapshots; excludes World commits and client" }));
            }
        }
        finally { foreach (var request in requests) TurnPlans.Invalidate(request); }
        return allPassed ? 0 : 1;
    }
    if (requestFile != null)
    {
        if (selection != null || category != null || list)
            throw new ArgumentException("--request cannot be combined with scenario filters or --list");
        using var input = JsonDocument.Parse(File.ReadAllText(requestFile));
        var request = input.RootElement;
        if (request.ValueKind != JsonValueKind.Object)
            throw new ArgumentException("Request must be a protocol object");
        bool success = true;
        for (int sample = 0; sample < repeat; sample++)
        {
            TurnPlans.Invalidate(request);
            try
            {
                var gate = new PlanningGate();
                var result = await gate.RunAsync(request, Stopwatch.GetTimestamp(),
                    (payload, deadline) => Planner.Decide(payload, deadline));
                success &= result.Status == 200;
                Console.WriteLine(JsonSerializer.Serialize(new { sample = sample + 1, status = result.Status,
                    response = result.Response, milliseconds = result.Timing.TotalMs,
                    scope = "actual C# gate and host; excludes World validation, commit, network and client" }));
            }
            finally { TurnPlans.Invalidate(request); }
        }
        return success ? 0 : 1;
    }
    var files = Directory.GetFiles(directory, "*.json").Order(StringComparer.Ordinal).ToArray();
    if (files.Length == 0) throw new ArgumentException("No host scenarios found");
    var names = new HashSet<string>(StringComparer.Ordinal);
    bool passed = true;
    int selected = 0;
    foreach (var file in files)
    {
        using var fixture = JsonDocument.Parse(File.ReadAllText(file));
        foreach (var item in fixture.RootElement.EnumerateArray())
        {
            string name = item.GetProperty("name").GetString() ?? throw new ArgumentException("Scenario lacks name");
            string kind = item.GetProperty("category").GetString() ?? throw new ArgumentException("Scenario lacks category");
            if (!names.Add(name)) throw new ArgumentException("Duplicate host scenario: " + name);
            if (selection != null && selection != name || category != null && category != kind) continue;
            selected++;
            if (list) { Console.WriteLine(name + "\t" + kind); continue; }
            var request = item.GetProperty("request");
            var expected = item.GetProperty("expect");
            if (expected.ValueKind != JsonValueKind.Object)
                throw new ArgumentException("Scenario expectations must be an object: " + name);
            var allowed = new HashSet<string>(StringComparer.Ordinal)
                { "status", "types", "spellId", "targetId", "targetCell", "targetIdAbsent", "pathExcludes", "pathEndsAt", "diagnosticContains" };
            var fields = expected.EnumerateObject().Select(property => property.Name).ToArray();
            if (fields.Length == 0 || fields.Distinct(StringComparer.Ordinal).Count() != fields.Length
                || fields.Any(field => !allowed.Contains(field)))
                throw new ArgumentException("Invalid or empty scenario expectations: " + name);
            if (expected.TryGetProperty("types", out var expectedTypes)
                && (expectedTypes.ValueKind != JsonValueKind.Array || expectedTypes.GetArrayLength() == 0
                    || expectedTypes.EnumerateArray().Any(type => type.ValueKind != JsonValueKind.String
                        || string.IsNullOrWhiteSpace(type.GetString()))))
                throw new ArgumentException("Invalid expected action types: " + name);
            if (expected.TryGetProperty("status", out var expectedStatus)
                && expectedStatus.GetInt32() != 200 && fields.Any(field => field != "status"))
                throw new ArgumentException("Non-success status cannot assert an action: " + name);
            if (expected.TryGetProperty("targetCell", out var expectedCell)
                && (expectedCell.ValueKind != JsonValueKind.Array || expectedCell.GetArrayLength() != 3
                    || expectedCell.EnumerateArray().Any(v => v.ValueKind != JsonValueKind.Number || !v.TryGetInt32(out _))))
                throw new ArgumentException("Invalid expected target cell: " + name);
            if (expected.TryGetProperty("targetIdAbsent", out var absent)
                && (absent.ValueKind != JsonValueKind.True || expected.TryGetProperty("targetId", out _)))
                throw new ArgumentException("Invalid or conflicting targetIdAbsent: " + name);
            if (expected.TryGetProperty("targetId", out var expectedTarget)
                && (expectedTarget.ValueKind != JsonValueKind.Number || !expectedTarget.TryGetInt64(out _)))
                throw new ArgumentException("Invalid expected targetId: " + name);
            var failures = new List<string>();
            object? firstAction = null;
            var timings = new List<double>();
            for (int sample = 0; sample < repeat; sample++)
            {
                // Each repetition starts a fresh independent decision; no prior
                // offer or speculative continuation may leak between samples.
                TurnPlans.Invalidate(request);
                var original = request.GetRawText();
                var gate = new PlanningGate();
                var result = await gate.RunAsync(request, Stopwatch.GetTimestamp(),
                    (payload, deadline) => Planner.Decide(payload, deadline));
                TurnPlans.Invalidate(request);
                timings.Add(result.Timing.TotalMs);
                var response = JsonSerializer.SerializeToElement(result.Response);
                int status = expected.TryGetProperty("status", out var statusValue) ? statusValue.GetInt32() : 200;
                if (result.Status != status) { failures.Add($"status {result.Status} != {status}"); continue; }
                if (request.GetRawText() != original) failures.Add("planner mutated request");
                if (status != 200) continue;
                if (!JsonNode.DeepEquals(JsonNode.Parse(response.GetProperty("source").GetRawText()),
                    JsonNode.Parse(request.GetProperty("source").GetRawText())))
                    failures.Add("source identity changed");
                var action = response.GetProperty("action");
                firstAction ??= action.Clone();
                string type = action.GetProperty("type").GetString() ?? "";
                if (expected.TryGetProperty("types", out var types)
                    && !types.EnumerateArray().Any(t => t.GetString() == type)) failures.Add("unexpected action type " + type);
                if (expected.TryGetProperty("spellId", out var spell)
                    && (!action.TryGetProperty("spellId", out var actualSpell) || actualSpell.GetInt32() != spell.GetInt32()))
                    failures.Add("unexpected spell");
                if (expected.TryGetProperty("targetId", out var target)
                    && (!action.TryGetProperty("targetId", out var actualTarget)
                        || actualTarget.ValueKind != JsonValueKind.Number
                        || !actualTarget.TryGetInt64(out var actualIdentity) || actualIdentity != target.GetInt64()))
                    failures.Add("unexpected target");
                if (expected.TryGetProperty("targetCell", out var targetCell)
                    && (!action.TryGetProperty("target", out var actualCell)
                        || !JsonNode.DeepEquals(JsonNode.Parse(actualCell.GetRawText()), JsonNode.Parse(targetCell.GetRawText()))))
                    failures.Add("unexpected target cell");
                if (expected.TryGetProperty("targetIdAbsent", out _)
                    && (type != "cast" || action.TryGetProperty("targetId", out var targetIdentity)
                        && targetIdentity.ValueKind != JsonValueKind.Null))
                    failures.Add("target actor should be absent");
                if (expected.TryGetProperty("pathExcludes", out var forbidden))
                {
                    if (!action.TryGetProperty("path", out var path) || path.ValueKind != JsonValueKind.Array)
                        failures.Add("action lacks path");
                    else if (path.EnumerateArray().Any(cell => forbidden.EnumerateArray().Any(blocked =>
                        JsonNode.DeepEquals(JsonNode.Parse(cell.GetRawText()), JsonNode.Parse(blocked.GetRawText())))))
                        failures.Add("path crossed a forbidden cell");
                }
                if (expected.TryGetProperty("pathEndsAt", out var destination))
                {
                    if (!action.TryGetProperty("path", out var path) || path.ValueKind != JsonValueKind.Array
                        || path.GetArrayLength() == 0
                        || !JsonNode.DeepEquals(JsonNode.Parse(path[path.GetArrayLength() - 1].GetRawText()),
                            JsonNode.Parse(destination.GetRawText())))
                        failures.Add("path did not end at expected cell");
                }
                if (expected.TryGetProperty("diagnosticContains", out var diagnostic)
                    && !response.GetProperty("diagnostics").EnumerateArray().Any(d =>
                        (d.GetString() ?? "").Contains(diagnostic.GetString() ?? "", StringComparison.Ordinal)))
                    failures.Add("expected diagnostic missing");
            }
            passed &= failures.Count == 0;
            Console.WriteLine(JsonSerializer.Serialize(new { scenario = name, category = kind, passed = failures.Count == 0,
                failures = failures.Distinct(), samples = repeat, action = firstAction,
                milliseconds = new { min = timings.Min(), max = timings.Max() },
                scope = "actual C# gate and host on a prepared synthetic snapshot; excludes World validation, commit, network and client" }));
        }
    }
    if (selected == 0) throw new ArgumentException("No matching host scenarios");
    return passed ? 0 : 1;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.Message);
    return 2;
}
