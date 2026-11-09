using System.Text.Json;
using System.Text.Json.Nodes;
using Wakfu.Jondo;

static JsonElement Request(long owner = 1, bool hidden = false, long estimatedId = 3,
    int spellId = 5228, int grade = 20, int estimatedCost = 1, int damage = 18,
    int minimum = 1, int maximum = 1) =>
    JsonSerializer.SerializeToElement(new
    {
        protocol = 1, requestId = "summon-estimate-host", source = new { actorId = 1L },
        board = new
        {
            cells = Enumerable.Range(0, 3).Select(i => new { id = i, xyz = new[] { i, 0, 0 } }).ToArray(),
            edges = new[] { new[] { 0, 1 }, new[] { 1, 0 }, new[] { 1, 2 }, new[] { 2, 1 } }, round = 1,
            actors = new object[]
            {
                new { id = 1L, team = 1, cell = 0, hp = 60, maxHp = 60, ap = 0, mp = 0, maxAp = 6, maxMp = 3 },
                new { id = 2L, team = 0, cell = 2, hp = 100, maxHp = 100, ap = 0, mp = 0, maxAp = 6, maxMp = 3 },
                new { id = 3L, team = 1, cell = 1, hp = 30, maxHp = 30, ap = 0, mp = 0, maxAp = 6, maxMp = 3,
                    registeredSummon = true, summonerId = owner, hidden }
            }
        },
        spells = Array.Empty<object>(),
        native = new
        {
            usage = Array.Empty<object>(),
            estimatedSummonBooks = new[] { new { actorId = estimatedId,
                spells = new[] { new { id = spellId, grade, cost = estimatedCost, minRange = minimum, maxRange = maximum, damage, element = "fire",
                    nativeCoefficientMask = 3, nativeDamageFlags = new[] { 22 }, nativeLocalization = true } } } }
        },
        excludedActions = Array.Empty<string>(), limits = new { budgetMs = 1000 }
    });

static bool HasEstimateDiagnostic(JsonElement request)
{
    var result = JsonSerializer.SerializeToElement(Planner.Decide(request));
    return result.GetProperty("diagnostics").EnumerateArray()
        .Any(v => v.GetString()!.StartsWith("summon forecast uses previous spell projections", StringComparison.Ordinal));
}

if (args.Length == 2 && args[0] == "--snapshot")
{
    using var document = JsonDocument.Parse(File.ReadAllBytes(args[1]));
    var result = JsonSerializer.SerializeToElement(Planner.Decide(document.RootElement));
    if (!result.GetProperty("diagnostics").EnumerateArray().Any(v =>
        v.GetString()!.StartsWith("summon forecast uses previous spell projections", StringComparison.Ordinal)))
        throw new Exception("Host did not accept the native summon estimate");
    Console.WriteLine("PASS: Host accepted the unmodified native summon snapshot");
    Console.WriteLine("Action: " + result.GetProperty("action"));
    return;
}
if (args.Length != 0) throw new ArgumentException("Use --snapshot <path> or no arguments");

if (!HasEstimateDiagnostic(Request()))
    throw new Exception("Host failed to accept the owned, visible summon estimate in the producer DTO shape");
if (HasEstimateDiagnostic(Request(owner: 99)))
    throw new Exception("Host accepted an estimate for a summon controlled by another actor");
if (HasEstimateDiagnostic(Request(hidden: true)))
    throw new Exception("Host accepted an estimate for a hidden summon");
if (HasEstimateDiagnostic(Request(estimatedId: 99)))
    throw new Exception("Host accepted an estimate whose actor identity is absent from the board");
if (!HasEstimateDiagnostic(Request(spellId: 7969, grade: 1, estimatedCost: 0, damage: 25, minimum: 2, maximum: 16)))
    throw new Exception("Host rejected the profile5522 free native spell7969 estimate");
if (HasEstimateDiagnostic(Request(spellId: 7969, grade: 1, estimatedCost: -1, damage: 25, minimum: 2, maximum: 16)))
    throw new Exception("Host accepted a negative-cost native summon estimate");
var missingCost = JsonNode.Parse(Request(spellId: 7969, grade: 1, estimatedCost: 0, damage: 25,
    minimum: 2, maximum: 16).GetRawText())!;
missingCost["native"]!["estimatedSummonBooks"]![0]!["spells"]![0]!.AsObject().Remove("cost");
if (HasEstimateDiagnostic(JsonSerializer.SerializeToElement(missingCost)))
    throw new Exception("Host treated a missing summon estimate cost as zero");
Console.WriteLine("PASS: Host requires an explicit nonnegative AP cost and honors owned summon identity and visibility");
