using System.Text.Json;
using Wakfu.Jondo;

static JsonElement Request(object unknown, string id)
{
    return JsonSerializer.SerializeToElement(new
    {
        protocol = 1, requestId = id,
        source = new { actorId = 1L, fightInstanceId = id, turnId = 1 },
        board = new
        {
            cells = new[] { new { id = 0, xyz = new[] { 0, 0, 0 } }, new { id = 1, xyz = new[] { 1, 0, 0 } } },
            edges = new[] { new[] { 0, 1 }, new[] { 1, 0 } },
            actors = new[]
            {
                new { id = 1L, team = 1, cell = 0, hp = 100, maxHp = 100, ap = 3, mp = 0 },
                new { id = 2L, team = 0, cell = 1, hp = 100, maxHp = 100, ap = 3, mp = 0 },
            },
            lineOfSight = new[] { new object[] { 0, 1, true } },
        },
        spells = new[] { new
        {
            id = 42, grade = 3, cost = 3, minRange = 1, maxRange = 1, damage = 20,
            unknownProjection = unknown,
            rows = new[] { new { kind = "damage", amount = 20, target = "enemy" } },
        } },
        native = new { usage = Array.Empty<object>() },
        excludedActions = Array.Empty<string>(), limits = new { budgetMs = 500 },
    });
}

static JsonElement Decide(object unknown, string id) => JsonSerializer.SerializeToElement(Planner.Decide(Request(unknown, id)));
static string[] Diagnostics(JsonElement result) => result.GetProperty("diagnostics").EnumerateArray().Select(x => x.GetString()!).ToArray();
static void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
    Console.WriteLine("PASS: " + message);
}

var baseline = Decide(Array.Empty<string>(), "projection-baseline");
var unknown = Decide(new[] { "conditional_effect:166935", "unsupported_semantic_family:175" }, "projection-unknown");
var messages = Diagnostics(unknown);
Check(messages.Contains("native projection spell 42 grade 3: conditional_effect:166935")
      && messages.Contains("native projection spell 42 grade 3: unsupported_semantic_family:175"),
      "partial native projection reasons identify their spell and grade");
Check(baseline.GetProperty("action").GetRawText() == unknown.GetProperty("action").GetRawText(),
      "reporting unknown projection does not alter selected action");
var malformed = Decide("not-an-array", "projection-malformed");
Check(Diagnostics(malformed).Contains("native projection spell 42 grade 3: invalid unknownProjection"),
      "malformed advisory diagnostics are visible without inventing an effect");
var bounded = Decide(Enumerable.Repeat("reason", 100).ToArray(), "projection-bounded");
Check(Diagnostics(bounded).Length == 65 && Diagnostics(bounded)[^1] == "native projection diagnostics truncated",
      "diagnostic output is bounded and signals truncation");
