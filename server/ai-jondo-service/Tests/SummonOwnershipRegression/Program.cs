using System.Text.Json;
using System.Text.Json.Nodes;
using System.Diagnostics;
using Wakfu.Jondo;
using Jondo.Unity.World.Fights;

static JsonElement Request(object? registered, object? owner, string id)
{
    var candidate = new Dictionary<string, object?> { ["id"] = 2L, ["team"] = 0, ["cell"] = 1, ["hp"] = 100, ["maxHp"] = 100, ["ap"] = 6, ["maxAp"] = 6, ["mp"] = 0 };
    if (!Equals(registered, "absent")) candidate["registeredSummon"] = registered;
    if (!Equals(owner, "absent")) candidate["summonerId"] = owner;
    return JsonSerializer.SerializeToElement(new {
        protocol = 1, requestId = id,
        source = new { actorId = 1L, fightInstanceId = id, turnId = 1 },
        board = new {
            cells = new[] { new { id = 0, xyz = new[] { 0, 0, 0 } }, new { id = 1, xyz = new[] { 1, 0, 0 } }, new { id = 2, xyz = new[] { -1, 0, 0 } } },
            edges = new[] { new[] { 0, 1 }, new[] { 1, 0 }, new[] { 0, 2 }, new[] { 2, 0 } },
            actors = new object[] { new { id = 1L, team = 1, cell = 0, hp = 100, maxHp = 100, ap = 3, mp = 0 }, candidate,
                new { id = 3L, team = 0, cell = 2, hp = 100, maxHp = 100, ap = 6, maxAp = 6, mp = 0 } },
            lineOfSight = new[] { new object[] { 0, 1, true }, new object[] { 0, 2, true } },
        },
        spells = new[] { new { id = 42, grade = 1, cost = 3, minRange = 1, maxRange = 1, removal = 6,
            rows = new[] { new { kind = "remove_ap", amount = 6, target = "enemy" } } } },
        native = new { usage = Array.Empty<object>() }, excludedActions = Array.Empty<string>(), limits = new { budgetMs = 500 },
    });
}

static long Target(object? registered, object? owner, string id)
{
    var result = JsonSerializer.SerializeToElement(Planner.Decide(Request(registered, owner, id)));
    return result.GetProperty("action").GetProperty("targetId").GetInt64();
}

var legacy = new Fighter { Invocador = 7 };
if (!legacy.EsInvocado || new Fighter { NativeRegisteredSummon = true }.EsInvocado != true ||
    new Fighter { NativeRegisteredSummon = false, Invocador = 7 }.EsInvocado)
    throw new Exception("Registration and ownership must remain independent");
if (Target("absent", "absent", "absent") != 2 ||
    Target(false, 33L, "companion") != 2 ||
    Target(true, null, "owner-unknown") != 3 ||
    Target(true, 33L, "registered") != 3 ||
    Target(true, "absent", "owner-absent") != 3)
    throw new Exception("Host must prioritize control against the non-summon without guessing ownership");
try
{
    Planner.Decide(Request(true, "invalid-owner", "invalid-owner"));
    throw new Exception("Invalid summon owner was accepted");
}
catch (ArgumentException) { }
Console.WriteLine("PASS: host distinguishes registered summons, unknown owners, companions and absent metadata");

// The host does not supply a native summon spellbook or behavior. Certifying an
// owned summon must not invoke unsupported behavior or invent its future damage.
static JsonElement OwnedRequest(object? owner, string id)
{
    var node = JsonNode.Parse(Request(true, owner, id).GetRawText())!;
    node["board"]!["actors"]![1]!["team"] = 1;
    return JsonSerializer.SerializeToElement(node);
}
static double Measure(object? owner, string label)
{
    var timings = new List<double>();
    for (int i = 0; i < 24; i++)
    {
        var request = OwnedRequest(owner, label + i);
        var start = Stopwatch.GetTimestamp();
        var reply = JsonSerializer.SerializeToElement(Planner.Decide(request));
        if (reply.GetProperty("action").GetProperty("targetId").GetInt64() != 3)
            throw new Exception("Owned summons must not make a legal enemy disappear");
        if (i >= 4) timings.Add(Stopwatch.GetElapsedTime(start).TotalMilliseconds);
    }
    timings.Sort();
    return timings[timings.Count / 2];
}
var ownerUnknownMs = Measure(null, "own-unknown-");
var ownerKnownMs = Measure(1L, "own-known-");
Console.WriteLine($"PASS: owned summon without projected behavior; p50 unknown={ownerUnknownMs:F3}ms known={ownerKnownMs:F3}ms (synthetic, not a full turn)");

static long SelectedControl(double uncertainPercent, bool conditional)
{
    var node = JsonNode.Parse(Request("absent", "absent", "control-probability-" + uncertainPercent + "-" + conditional).GetRawText())!;
    node["spells"] = JsonSerializer.SerializeToNode(new object[] {
        new { id=40, grade=1, cost=3, minRange=1, maxRange=1, removal=6,
            rows=new[] { new { kind="remove_ap", amount=6, target="enemy", probability=uncertainPercent, conditional } } },
        new { id=41, grade=1, cost=3, minRange=1, maxRange=1, removal=6,
            rows=new[] { new { kind="remove_ap", amount=6, target="enemy", probability=100, conditional=false } } },
    });
    var reply = JsonSerializer.SerializeToElement(Planner.Decide(JsonSerializer.SerializeToElement(node)));
    return reply.GetProperty("action").GetProperty("spellId").GetInt64();
}
long probabilitySelection = SelectedControl(25, false), conditionalSelection = SelectedControl(100, true);
if (probabilitySelection != 41 || conditionalSelection != 41)
    throw new Exception($"Host must not treat uncertain projected control as guaranteed: probability={probabilitySelection}, conditional={conditionalSelection}");
Console.WriteLine("PASS: host accounts for uncertainty of projected control");
