using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Serialization;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

// This lab runs the production planner and its private advisory replay. Its
// outcomes are not a substitute for World validation of actual game rules.
try
{
    var options = Options.Parse(args);
    var json = new JsonSerializerOptions { PropertyNameCaseInsensitive = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow };
    var files = Directory.GetFiles(options.Directory, "*.json").OrderBy(x => x).ToArray();
    if (files.Length == 0) throw new ArgumentException("No scenario JSON files found");
    var scenarios = files.SelectMany(file => JsonSerializer.Deserialize<Scenario[]>(File.ReadAllText(file), json)
        ?? throw new ArgumentException($"Empty scenario file: {file}")).ToArray();
    if (scenarios.GroupBy(s => s.Name).Any(g => g.Count() != 1))
        throw new ArgumentException("Scenario names must be unique");
    var selected = scenarios.Where(s => (options.Name == null || s.Name == options.Name)
        && (options.Category == null || s.Category == options.Category)).ToArray();
    if (selected.Length == 0) throw new ArgumentException("No matching scenarios");
    if (options.List)
    {
        foreach (var scenario in selected) Console.WriteLine($"{scenario.Name}\t{scenario.Category}");
        return 0;
    }
    bool passed = true;
    foreach (var scenario in selected)
    {
        scenario.Validate();
        for (int i = 0; i < options.Warmup; i++) Run(scenario, options.BudgetMs);
        var samples = Enumerable.Range(0, options.Repeat).Select(_ => Run(scenario, options.BudgetMs)).ToArray();
        var times = samples.Select(s => s.ElapsedMs).OrderBy(x => x).ToArray();
        var failures = samples.SelectMany(s => s.Failures).Distinct().ToArray();
        passed &= failures.Length == 0;
        Console.WriteLine(JsonSerializer.Serialize(new {
            scenario = scenario.Name, category = scenario.Category, passed = failures.Length == 0,
            failures, samples = samples.Length, planningMs = new {
                min = times[0], p50 = Percentile(times, 0.5), p95 = Percentile(times, 0.95), max = times[^1] },
            actions = samples[0].Actions, outcome = samples[0].Outcome,
            scope = "C# production planner and private advisory replay; excludes World, native commit, network and client"
        }));
    }
    return passed ? 0 : 1;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.Message);
    return 2;
}

static double Percentile(double[] sorted, double p) => sorted[Math.Max(0, (int)Math.Ceiling(sorted.Length * p) - 1)];

static Result Run(Scenario scenario, int budgetMs)
{
    var cells = scenario.Cells is null
        ? Enumerable.Range(0, scenario.Length).Select(x => new CellXYZ(x, 0, 0)).ToArray()
        : scenario.Cells.Select(c => new CellXYZ(c[0], c[1], c[2])).ToArray();
    var edges = scenario.Edges is null
        ? Enumerable.Range(0, cells.Length - 1).SelectMany(x => new[] { (x, x + 1), (x + 1, x) })
        : scenario.Edges.Select(e => (e[0], e[1]));
    using var geometry = MapGeometry.BeginScope(new GeometryContext(cells, edges));
    var fighters = scenario.Actors.Select(a => new Fighter { Id = a.Id, TeamId = a.Team, CellId = a.Cell,
        CurrentHP = a.Hp, MaxHP = a.MaxHp, CurrentAP = a.Ap, MaxAP = a.Ap, CurrentMP = a.Mp,
        MaxMP = a.Mp, Level = 10, IsMonster = true }).ToArray();
    var actor = fighters.Single(f => f.Id == scenario.ActorId);
    var source = fighters.Select(f => (f.Id, f.CurrentHP, f.CurrentAP, f.CurrentMP, f.CellId)).ToArray();
    var board = new MonsterTactics.Board { Fighters = fighters,
        Reach = (row, caster, from, aim) => Wakfu.Jondo.Planner.NativeReach(fighters, row, caster, from, aim) };
    var spells = scenario.Spells.Select(s => new MonsterTactics.Spell {
        Id = s.Id, Grade = 1, Cost = s.Cost, MinRange = s.MinRange, MaxRange = s.MaxRange,
        Damage = s.Kind == "damage" ? s.Amount : 0, Heal = s.Kind == "heal" ? s.Amount : 0,
        Buff = s.Kind == "gain_ap" ? s.Amount : 0, PerTurn = s.PerTurn, PerTarget = s.PerTarget,
        Zone = s.Zone, HurtsAllies = s.HurtsAllies,
        Rows = s.HurtsAllies && s.Kind == "damage"
            ? new[] { SemanticRows.Create(s.Kind, s.Amount, "enemy", zoneRadius: s.Zone),
                SemanticRows.Create(s.Kind, s.Amount, "ally", zoneRadius: s.Zone) }
            : new[] { SemanticRows.Create(s.Kind, s.Amount, s.Target, zoneRadius: s.Zone) } }).ToArray();
    var turns = scenario.Turns ?? new[] { scenario.ActorId };
    var actions = new List<object>();
    var actionPaths = new List<int[]>();
    var actionIdentities = new List<(long Actor, int Spell, long Target)>();
    int actionCount = 0;
    double elapsedMs = 0;
    int enemyDamage = 0, allyDamage = 0, allyHealing = 0;
    Dictionary<long, int> finalHp = new();
    void Turn(int index)
    {
        if (index == turns.Length)
        {
            foreach (var (fighter, original) in fighters.Zip(source))
            {
                int delta = fighter.CurrentHP - original.CurrentHP;
                if (fighter.TeamId == actor.TeamId) { allyDamage += Math.Max(0, -delta); allyHealing += Math.Max(0, delta); }
                else enemyDamage += Math.Max(0, -delta);
            }
            finalHp = fighters.ToDictionary(f => f.Id, f => f.CurrentHP);
            return;
        }
        var current = fighters.Single(f => f.Id == turns[index]);
        if (!current.IsAlive) { Turn(index + 1); return; }
        var allowed = scenario.Actors.Single(a => a.Id == current.Id).SpellIds;
        var book = allowed is null ? spells : spells.Where(s => allowed.Contains(s.Id)).ToArray();
        var clock = Stopwatch.StartNew();
        var plan = MonsterTactics.PlanTurn(board, current, book, budgetMs: budgetMs);
        clock.Stop();
        elapsedMs += clock.Elapsed.TotalMilliseconds;
        actionCount += plan.Count;
        actionIdentities.AddRange(plan.Select(a => (current.Id, a.Spell.Id, a.Target.Id)));
        actionPaths.AddRange(plan.Select(a => a.Path.ToArray()));
        actions.AddRange(plan.Select(a => new { actor = current.Id, spell = a.Spell.Id, target = a.Target.Id,
            targetCell = a.TargetCell, path = a.Path.ToArray(), score = a.Score, value = a.Value }));
        using (MonsterTactics.Simulation.Replay(board, current, plan)) Turn(index + 1);
    }
    Turn(0);
    var failures = new List<string>();
    if (!source.SequenceEqual(fighters.Select(f => (f.Id, f.CurrentHP, f.CurrentAP, f.CurrentMP, f.CellId))))
        failures.Add("planning or replay changed the source state");
    var expected = scenario.Expect;
    if (enemyDamage < expected.EnemyDamageAtLeast) failures.Add($"enemy damage {enemyDamage} < {expected.EnemyDamageAtLeast}");
    if (allyHealing < expected.AllyHealingAtLeast) failures.Add($"ally healing {allyHealing} < {expected.AllyHealingAtLeast}");
    if (expected.AllyDamageAtMost is int maxDamage && allyDamage > maxDamage) failures.Add($"ally damage {allyDamage} > {maxDamage}");
    if (expected.ActionsAtMost is int maxActions && actionCount > maxActions) failures.Add($"actions {actionCount} > {maxActions}");
    if (expected.ActionPrefix is { } prefix
        && (actionIdentities.Count < prefix.Length || prefix.Where((item, i) =>
            actionIdentities[i].Actor != item.Actor || actionIdentities[i].Spell != item.Spell
            || item.Target is long target && actionIdentities[i].Target != target).Any()))
        failures.Add("action prefix did not match");
    if (expected.PathPrefix is { } pathPrefix
        && (actionPaths.Count == 0 || actionPaths[0].Length < pathPrefix.Length
            || !actionPaths[0].Take(pathPrefix.Length).SequenceEqual(pathPrefix)))
        failures.Add("first action path prefix did not match");
    foreach (var (id, minimum) in expected.HpAtLeast)
        if (!finalHp.TryGetValue(id, out int hp) || hp < minimum) failures.Add($"actor {id} HP is below {minimum} or missing");
    foreach (var (id, maximum) in expected.HpAtMost)
        if (!finalHp.TryGetValue(id, out int hp) || hp > maximum) failures.Add($"actor {id} HP is above {maximum} or missing");
    return new Result(elapsedMs, actions,
        new { enemyDamage, allyDamage, allyHealing, finalHp }, failures);
}

record Result(double ElapsedMs, object Actions, object Outcome, List<string> Failures);
sealed class Scenario
{
    public string Name { get; set; } = "";
    public string Category { get; set; } = "";
    public int Length { get; set; }
    public int[][]? Cells { get; set; }
    public int[][]? Edges { get; set; }
    public long ActorId { get; set; } = 1;
    public long[]? Turns { get; set; }
    public Actor[] Actors { get; set; } = Array.Empty<Actor>();
    public Spell[] Spells { get; set; } = Array.Empty<Spell>();
    public Expectation Expect { get; set; } = new();
    public void Validate()
    {
        int count = Cells?.Length ?? Length;
        if (string.IsNullOrWhiteSpace(Name) || string.IsNullOrWhiteSpace(Category) || count < 2 || count > 1000
            || Cells?.Any(c => c.Length != 3) == true
            || (Cells is null) != (Edges is null)
            || Edges?.Any(e => e.Length != 2 || e[0] < 0 || e[1] < 0 || e[0] >= count || e[1] >= count) == true
            || Actors.Length == 0 || Actors.GroupBy(a => a.Id).Any(g => g.Count() != 1)
            || Actors.Count(a => a.Id == ActorId) != 1
            || Turns is { Length: 0 } || Turns?.Distinct().Count() != Turns?.Length
            || Turns?.Any(id => !Actors.Any(a => a.Id == id)) == true
            || Actors.Any(a => a.SpellIds?.Any(id => !Spells.Any(s => s.Id == id)) == true)
            || Expect.ActionPrefix is { Length: 0 }
            || Expect.PathPrefix is { Length: 0 }
            || Expect.PathPrefix?.Any(cell => cell < 0 || cell >= count) == true
            || Expect.ActionPrefix?.Any(a => !Actors.Any(actor => actor.Id == a.Actor)
                || !Spells.Any(spell => spell.Id == a.Spell)
                || a.Target is long id && !Actors.Any(actor => actor.Id == id)) == true
            || Actors.Any(a => a.Cell < 0 || a.Cell >= count || a.Hp <= 0 || a.Hp > a.MaxHp || a.Ap < 0 || a.Mp < 0)
            || Spells.Any(s => s.Kind is not ("damage" or "heal" or "gain_ap") || s.Target is not ("enemy" or "ally" or "self")
                || s.Amount <= 0 || s.Cost < 0 || s.Zone < 0 || s.MinRange < 0 || s.MaxRange < s.MinRange))
            throw new ArgumentException($"Invalid scenario: {Name}");
    }
}
sealed class Actor { public long Id { get; set; } public int Team { get; set; } public int Cell { get; set; }
    public int Hp { get; set; } public int MaxHp { get; set; } = 100; public int Ap { get; set; } public int Mp { get; set; }
    public int[]? SpellIds { get; set; } }
sealed class Spell { public int Id { get; set; } public string Kind { get; set; } = ""; public string Target { get; set; } = "";
    public int Amount { get; set; } public int Cost { get; set; } public int MinRange { get; set; } public int MaxRange { get; set; }
    public int PerTurn { get; set; } public int PerTarget { get; set; } public int Zone { get; set; } public bool HurtsAllies { get; set; } }
sealed class Expectation { public int EnemyDamageAtLeast { get; set; } public int AllyHealingAtLeast { get; set; }
    public int? AllyDamageAtMost { get; set; } public int? ActionsAtMost { get; set; }
    public ExpectedAction[]? ActionPrefix { get; set; } public int[]? PathPrefix { get; set; }
    public Dictionary<long, int> HpAtLeast { get; set; } = new(); public Dictionary<long, int> HpAtMost { get; set; } = new(); }
sealed class ExpectedAction { public long Actor { get; set; } public int Spell { get; set; } public long? Target { get; set; } }
sealed record Options(string Directory, string? Name, string? Category, int Repeat, int Warmup, int BudgetMs, bool List)
{
    public static Options Parse(string[] args)
    {
        string directory = Path.Combine(AppContext.BaseDirectory, "Scenarios"); string? name = null, category = null;
        int repeat = 3, warmup = 1, budget = 200; bool list = false;
        for (int i = 0; i < args.Length; i++)
        {
            string Next() => ++i < args.Length ? args[i] : throw new ArgumentException("Missing option value");
            switch (args[i])
            {
                case "--dir": directory = Next(); break; case "--scenario": name = Next(); break;
                case "--category": category = Next(); break; case "--repeat": repeat = int.Parse(Next()); break;
                case "--warmup": warmup = int.Parse(Next()); break; case "--budget-ms": budget = int.Parse(Next()); break;
                case "--list": list = true; break;
                default: throw new ArgumentException($"Unknown option: {args[i]}");
            }
        }
        if (repeat is < 1 or > 10000 || warmup is < 0 or > 1000 || budget is < 1 or > 10000)
            throw new ArgumentException("Invalid repeat, warmup or budget");
        return new(directory, name, category, repeat, warmup, budget, list);
    }
}
