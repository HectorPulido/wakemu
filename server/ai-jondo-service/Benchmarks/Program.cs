using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Wakfu.Jondo;

// Measures the real host gate and planner with an existing advisory snapshot.
// This does not include snapshot production, network, World commit or client ACK.
var options = ParseArgs(args);
// Compile the actual Host/Program.cs into this runner and bind its existing
// private validator once. A typed delegate avoids reflection in the samples.
var validateKeys = (Action<JsonElement>)typeof(Wakfu.Jondo.Program)
    .GetMethod("UniqueKeys", BindingFlags.NonPublic | BindingFlags.Static)!
    .CreateDelegate(typeof(Action<JsonElement>));
if (options.TryGetValue("check-frame", out var frameFile))
{
    try
    {
        using var frame = JsonDocument.Parse(File.ReadAllBytes(frameFile), new JsonDocumentOptions { MaxDepth = 64 });
        validateKeys(frame.RootElement);
        Console.WriteLine("Frame keys valid");
    }
    catch (JsonException error)
    {
        Console.Error.WriteLine(error.Message);
        Environment.ExitCode = 1;
    }
    return;
}
if (options.ContainsKey("help"))
{
    Console.WriteLine("dotnet run --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- [--scenario melee|crowded|team|team-coordinated] [--input snapshot.json] [--mode same|fresh] [--warmup N] [--samples N] [--concurrency N] [--budget-ms N] [--check-frame frame.json]");
    Console.WriteLine("same repeats the identical snapshot without a commit; fresh uses a new synthetic fight ID for every request. Inspect planReused: false does not guarantee exhaustive search.");
    return;
}
int warmup = Number("warmup", 2, 0, 100), samples = Number("samples", 10, 1, 10000);
int concurrency = Number("concurrency", 1, 1, 64), budget = Number("budget-ms", 1000, 1, 2000);
string scenario = options.GetValueOrDefault("scenario", "melee");
if (scenario is not ("melee" or "crowded" or "team" or "team-coordinated")) throw new ArgumentException("Unknown scenario");
string mode = options.GetValueOrDefault("mode", "same");
if (mode is not ("same" or "fresh")) throw new ArgumentException("Unknown benchmark mode");
string json = options.TryGetValue("input", out var file) ? File.ReadAllText(file) : Fixture(scenario);
var fixture = JsonNode.Parse(json)?.AsObject() ?? throw new ArgumentException("Snapshot must be a JSON object");
if (fixture["limits"] is not JsonObject limits)
{
    limits = new JsonObject();
    fixture["limits"] = limits;
}
limits["budgetMs"] = budget;
// Host receives a framed envelope, parses it, scans duplicate keys recursively,
// validates its envelope, and only then passes the payload to PlanningGate.
byte[] Frame(JsonObject payload) => JsonSerializer.SerializeToUtf8Bytes(new { id = 1, endpoint = "/wakia/decide", payload });
byte[] bytes = Frame(fixture);
string sessionId = Guid.NewGuid().ToString("N");
int frameIndex = 0;
byte[] NextFrame()
{
    if (mode == "same") return bytes;
    var copy = fixture.DeepClone().AsObject();
    if (copy["source"] is not JsonObject source) throw new ArgumentException("Snapshot source is required");
    source["fightInstanceId"] = $"benchmark-{sessionId}-{frameIndex++}";
    return Frame(copy);
}
var gate = new PlanningGate();

async Task<Sample> Measure(byte[] frameBytes)
{
    long start = Stopwatch.GetTimestamp();
    using var document = JsonDocument.Parse(frameBytes, new JsonDocumentOptions { MaxDepth = 64 });
    var frame = document.RootElement;
    validateKeys(frame);
    long id = frame.GetProperty("id").GetInt64();
    if (id <= 0 || frame.EnumerateObject().Count() != 3) throw new JsonException("Invalid frame envelope");
    _ = frame.GetProperty("endpoint").GetString() ?? "";
    var payload = frame.GetProperty("payload");
    var result = await gate.RunAsync(payload, start,
        (request, deadline) => Planner.Decide(request, deadlineTimestamp: deadline));
    var response = JsonSerializer.SerializeToElement(result.Response);
    string? action = response.TryGetProperty("action", out var actionValue)
        && actionValue.TryGetProperty("type", out var type) ? type.GetString() : null;
    string? error = response.TryGetProperty("error", out var errorValue) ? errorValue.GetString() : null;
    string reuse = response.TryGetProperty("planReused", out var reuseValue)
        && reuseValue.ValueKind is JsonValueKind.True or JsonValueKind.False
        ? (reuseValue.GetBoolean() ? "true" : "false") : "missing";
    return new(result.Status, action, error, reuse, frameBytes.Length, result.Timing.ParseMs, result.Timing.QueueWaitMs,
        result.Timing.PlanningMs, result.Timing.TotalMs);
}
for (int i = 0; i < warmup; i++) _ = await Measure(NextFrame());
var results = new List<Sample>(samples);
while (results.Count < samples)
{
    int count = Math.Min(concurrency, samples - results.Count);
    var frames = Enumerable.Range(0, count).Select(_ => NextFrame()).ToArray();
    // Starting workers on the pool gives each request its own receipt time before
    // entering the same production gate; no renewed budget is granted in queue.
    using var ready = new CountdownEvent(count);
    using var start = new ManualResetEventSlim(false);
    var jobs = Enumerable.Range(0, count).Select(_ => Task.Run(async () =>
    {
        ready.Signal();
        start.Wait();
        return await Measure(frames[_]);
    })).ToArray();
    ready.Wait();
    start.Set();
    results.AddRange(await Task.WhenAll(jobs));
}
double Percentile(IEnumerable<double> values, double p)
{
    var sorted = values.Order().ToArray();
    return sorted[(int)Math.Ceiling(p * sorted.Length) - 1];
}
object Distribution(Func<Sample, double> selector) => new
{
    p50 = Percentile(results.Select(selector), 0.50),
    p95 = Percentile(results.Select(selector), 0.95),
    max = results.Max(selector),
};
Console.WriteLine(JsonSerializer.Serialize(new
{
    scope = "in-process host frame parse and duplicate-key validation, gate and planner; excludes snapshot preparation, network, World commit, client ACK and full turn",
    input = file == null ? "synthetic:" + scenario : Path.GetFileName(file),
    mode, warmup, samples, concurrency, budgetMs = budget,
    snapshotBytes = JsonSerializer.SerializeToUtf8Bytes(fixture).Length,
    snapshotBytesScope = "template before synthetic fresh identity",
    frameBytes = results[0].FrameBytes, frameBytesMin = results.Min(r => r.FrameBytes),
    frameBytesMax = results.Max(r => r.FrameBytes),
    counts = results.GroupBy(r => r.Status).ToDictionary(g => g.Key.ToString(), g => g.Count()),
    actions = results.Where(r => r.Action != null).GroupBy(r => r.Action!).ToDictionary(g => g.Key, g => g.Count()),
    planReused = results.GroupBy(r => r.PlanReused).ToDictionary(g => g.Key, g => g.Count()),
    errors = results.Where(r => r.Error != null).GroupBy(r => r.Error!).ToDictionary(g => g.Key, g => g.Count()),
    milliseconds = new { parse = Distribution(r => r.Parse), queue = Distribution(r => r.Queue),
        planning = Distribution(r => r.Planning), total = Distribution(r => r.Total) },
}));

int Number(string key, int fallback, int min, int max) => options.TryGetValue(key, out var raw)
    ? int.TryParse(raw, out int n) && n >= min && n <= max ? n
        : throw new ArgumentException($"--{key} must be between {min} and {max}") : fallback;

static Dictionary<string, string> ParseArgs(string[] args)
{
    var values = new Dictionary<string, string>();
    var accepted = new HashSet<string> { "scenario", "input", "mode", "warmup", "samples", "concurrency", "budget-ms", "check-frame" };
    for (int i = 0; i < args.Length; i++)
    {
        if (args[i] == "--help") { values["help"] = "true"; continue; }
        if (!args[i].StartsWith("--") || !accepted.Contains(args[i][2..]) || i + 1 == args.Length)
            throw new ArgumentException("Unknown or missing argument: " + args[i]);
        if (!values.TryAdd(args[i][2..], args[++i])) throw new ArgumentException("Duplicate argument");
    }
    return values;
}

static string Fixture(string scenario)
{
    int width = scenario == "melee" ? 7 : 15;
    int Cell(int x, int y) => y * width + x;
    var cells = Enumerable.Range(0, width * width).Select(id => new { id, xyz = new[] { id % width, id / width, 0 } }).ToArray();
    var edges = new List<int[]>();
    for (int y = 0; y < width; y++) for (int x = 0; x < width; x++)
    {
        if (x + 1 < width) { edges.Add(new[] { Cell(x, y), Cell(x + 1, y) }); edges.Add(new[] { Cell(x + 1, y), Cell(x, y) }); }
        if (y + 1 < width) { edges.Add(new[] { Cell(x, y), Cell(x, y + 1) }); edges.Add(new[] { Cell(x, y + 1), Cell(x, y) }); }
    }
    int center = width / 2;
    var actors = new List<object> { new { id = 1L, team = 0, cell = Cell(center, center), hp = 500, maxHp = 500, ap = 9, maxAp = 9, mp = 4, maxMp = 4, wp = 6, level = 100 } };
    int[][] offsets = scenario == "melee" ? new[] { new[] { 2, 0 } } : new[] { new[] { 4, 0 }, new[] { -4, 0 }, new[] { 0, 4 }, new[] { 0, -4 }, new[] { 3, 3 }, new[] { -3, -3 } };
    for (int i = 0; i < offsets.Length; i++) actors.Add(new { id = i + 2L, team = 1, cell = Cell(center + offsets[i][0], center + offsets[i][1]), hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3, wp = 6, level = 100 });
    if (scenario is "team" or "team-coordinated")
        actors.Add(new { id = 99L, team = 0, cell = Cell(center - 2, center), hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 3, maxMp = 3, wp = 6, level = 100 });
    var spells = Enumerable.Range(0, scenario == "melee" ? 1 : 5).Select(i => new
    {
        id = 12000 + i, grade = 100, cost = 3, minRange = 1, maxRange = scenario == "melee" ? 1 : 6,
        damage = 20 + i, element = "neutral", needsLineOfSight = false,
        rows = new[] { new { kind = "damage", amount = 20 + i, target = "enemy", fixedCells = new[] { new[] { 0, 0 } } } },
    }).ToArray();
    var result = JsonSerializer.Serialize(new { protocol = 1, requestId = "benchmark", source = new { actorId = 1L,
        fightInstanceId = "benchmark", turnId = 1, catalogRevision = "synthetic", stateRevision = 1, actionId = 0 },
        board = new { cells, edges, actors, round = 1, lineOfSight = Array.Empty<object>() }, spells,
        native = new { usage = Array.Empty<object>() }, excludedActions = Array.Empty<string>() });
    if (scenario != "team-coordinated") return result;
    var snapshot = JsonNode.Parse(result)!.AsObject();
    snapshot["board"]!["coordination"] = JsonSerializer.SerializeToNode(new {
        actorId = 1L, team = 0, focusId = 2L, actorBlocksNativeLos = true,
        corridors = new[] { new { ownerId = 99L, targetId = 2L,
            cells = new[] { Cell(center - 1, center), Cell(center, center), Cell(center + 1, center) } } }
    });
    return snapshot.ToJsonString();
}

internal sealed record Sample(int Status, string? Action, string? Error, string PlanReused, int FrameBytes, double Parse, double Queue, double Planning, double Total);
