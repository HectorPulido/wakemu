using System.Diagnostics;
using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Wakfu.Jondo;

internal static class Planner
{
    public const string Upstream = "cc58d8996d952f3adff2f6a14f13bdd39964506c";
    // Upstream contains shared immutable spell-analysis dictionaries. Its
    // synchronous planner is isolated from concurrent mutation here.
    private static readonly object CoreLock = new();

    private static int Int(JsonElement v, string key, int fallback = 0) => v.TryGetProperty(key, out var p) ? p.GetInt32() : fallback;
    private static long Long(JsonElement v, string key) => v.GetProperty(key).GetInt64();
    private static bool Bool(JsonElement v, string key, bool fallback = false) => v.TryGetProperty(key, out var p) ? p.GetBoolean() : fallback;
    private static double Number(JsonElement v, string key) => v.TryGetProperty(key, out var p) ? p.GetDouble() : 0;
    private static string Text(JsonElement v, string key, string fallback = "") => v.TryGetProperty(key, out var p) ? p.GetString() ?? fallback : fallback;

    // Inform observers about incomplete native projections without changing
    // candidate values or inventing effects. Bound output for large books.
    private static void RecordProjectionUnknowns(JsonElement spell, List<string> diagnostics,
        ref int remaining, ref bool truncated)
    {
        if (!spell.TryGetProperty("unknownProjection", out var unknown)) return;
        if (remaining == 0)
        {
            if (unknown.ValueKind != JsonValueKind.Array || unknown.GetArrayLength() > 0) truncated = true;
            return;
        }
        string prefix = $"native projection spell {Int(spell, "id")} grade {Int(spell, "grade", 1)}: ";
        if (unknown.ValueKind != JsonValueKind.Array)
        {
            diagnostics.Add(prefix + "invalid unknownProjection");
            remaining--;
            return;
        }
        foreach (var reason in unknown.EnumerateArray())
        {
            if (remaining == 0) { truncated = true; break; }
            string value = reason.ValueKind == JsonValueKind.String
                ? reason.GetString() ?? "" : "invalid unknownProjection entry";
            if (value.Length > 256) { value = value[..256] + "…"; truncated = true; }
            diagnostics.Add(prefix + value);
            remaining--;
        }
    }

    public static object Decide(JsonElement request, long? deadlineTimestamp = null)
    {
        int RemainingBudget()
        {
            if (deadlineTimestamp == null) return 2000;
            double remaining = (deadlineTimestamp.Value - Stopwatch.GetTimestamp()) * 1000.0 / Stopwatch.Frequency;
            if (remaining < 1) throw new TimeoutException("WakIA decision deadline reached");
            return (int)Math.Min(2000, remaining);
        }
        bool CanFinish() => deadlineTimestamp == null
            || Stopwatch.GetTimestamp() < deadlineTimestamp.Value - Stopwatch.Frequency / 200;
        _ = RemainingBudget();
        if (Int(request, "protocol") != 1) throw new ArgumentException("WakIA protocol 1 is required");
        var source = request.GetProperty("source");
        long actorId = Long(source, "actorId");
        var boardData = request.GetProperty("board");
        var cells = boardData.GetProperty("cells").EnumerateArray().Select((v, i) =>
        {
            if (Int(v, "id", -1) != i) throw new ArgumentException("Native cell IDs must be dense and ordered");
            int x = 0, y = 0, z = 0, count = 0;
            foreach (var n in v.GetProperty("xyz").EnumerateArray())
            {
                int value = n.GetInt32();
                if (count == 0) x = value;
                else if (count == 1) y = value;
                else if (count == 2) z = value;
                count++;
            }
            if (count != 3) throw new ArgumentException("A native cell requires XYZ");
            return new CellXYZ(x, y, z);
        }).ToArray();
        var edges = boardData.GetProperty("edges").EnumerateArray().Select(v =>
        {
            if (v.GetArrayLength() != 2) throw new ArgumentException("Invalid directed edge");
            return (v[0].GetInt32(), v[1].GetInt32());
        }).ToArray();
        var fighters = new List<Fighter>();
        var hidden = new HashSet<long>();
        var nativeBodyActors = new HashSet<long>();
        foreach (var data in boardData.GetProperty("actors").EnumerateArray())
        {
            int cell = Int(data, "cell", -1);
            if (cell < 0 || cell >= cells.Length) throw new ArgumentException("Actor outside native cell table");
            var f = new Fighter { Id = Long(data, "id"), TeamId = Int(data, "team"), CellId = cell,
                CurrentHP = Int(data, "hp"), MaxHP = Int(data, "maxHp"), CurrentAP = Int(data, "ap"),
                MaxAP = Int(data, "maxAp", Int(data, "ap")), CurrentMP = Int(data, "mp"),
                MaxMP = Int(data, "maxMp", Int(data, "mp")), Level = Int(data, "level", 1),
                IsMonster = Bool(data, "isMonster", true), MonsterId = Int(data, "monsterRef"), Range = Int(data, "rangeBonus"),
                NativeDirection = Int(data, "direction", -1), NativePhysicalRadius = Int(data, "physicalRadius"),
                NativeVirtualHpMax = Int(data, "virtualHpMax") };
            if (data.TryGetProperty("registeredSummon", out var registered))
            {
                if (registered.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new ArgumentException("Invalid native summon registration");
                f.NativeRegisteredSummon = registered.GetBoolean();
                if (f.NativeRegisteredSummon == true && data.TryGetProperty("summonerId", out var owner)
                    && owner.ValueKind != JsonValueKind.Null)
                {
                    if (owner.ValueKind != JsonValueKind.Number || !owner.TryGetInt64(out long ownerId))
                        throw new ArgumentException("Invalid native summon owner");
                    f.Invocador = ownerId;
                }
            }
            if(data.TryGetProperty("nativeHp",out var nativeHp))
            {
                if(Int(nativeHp,"version")!=1||!nativeHp.TryGetProperty("minimum",out var minimum)
                    ||!minimum.TryGetInt32(out int floor)||floor<0||floor>f.CurrentHP||f.CurrentHP>f.MaxHP
                    ||!nativeHp.TryGetProperty("frozen",out var frozen)
                    ||frozen.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new ArgumentException("Invalid native HP1 authority");
                string mode=Text(nativeHp,"rawCurrentMode");
                if(!nativeHp.TryGetProperty("rawCurrent",out var raw)
                    ||mode=="bounded"&&raw.ValueKind!=JsonValueKind.Null
                    ||mode is not ("bounded" or "fresh" or "copied")
                    ||mode!="bounded"&&!raw.TryGetInt32(out _))
                    throw new ArgumentException("Invalid native HP1 raw mode");
                f.NativeHpMinimum=floor;f.NativeHpFrozen=frozen.GetBoolean();f.NativeHpRawMode=mode;
                f.NativeHpRawCurrent=mode=="bounded"?null:raw.GetInt32();
                if(!NativeHpForecast.Known(f))throw new ArgumentException("Native HP1 raw/effective mismatch");
            }
            if(data.TryGetProperty("nativeUndead",out var undead))
            {
                if(undead.ValueKind is not (JsonValueKind.True or JsonValueKind.False))throw new ArgumentException("Unknown native undead flag");
                f.NativeUndead=undead.GetBoolean();
            }
            if(data.TryGetProperty("nativeIsCarried",out var isCarried))
            {
                if(isCarried.ValueKind is not (JsonValueKind.True or JsonValueKind.False))throw new ArgumentException("Unknown native carry authority");
                f.NativeIsCarried=isCarried.GetBoolean();
            }
            if(data.TryGetProperty("nativeHealingResistanceEnabled",out var resistanceEnabled))
            {
                if(resistanceEnabled.ValueKind is not (JsonValueKind.True or JsonValueKind.False))throw new ArgumentException("Unknown native healing resistance policy");
                f.NativeHealingResistanceEnabled=resistanceEnabled.GetBoolean();
            }
            if(data.TryGetProperty("nativeVirtualHpFrozen",out var virtualFrozen))
            {
                if(virtualFrozen.ValueKind is not (JsonValueKind.True or JsonValueKind.False))throw new ArgumentException("Unknown native virtual HP mutability");
                f.NativeVirtualHpFrozen=virtualFrozen.GetBoolean();
            }
            if(data.TryGetProperty("nativeHealingResistance",out var healResistance))
            {
                if(!healResistance.TryGetProperty("enabled",out var enabled)||enabled.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                    ||!healResistance.TryGetProperty("frozen",out var resFrozen)||resFrozen.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                    ||!healResistance.TryGetProperty("minimum",out var low)||!low.TryGetInt32(out int minimumResistance)
                    ||!healResistance.TryGetProperty("maximum",out var high)||!high.TryGetInt32(out int maximumResistance)
                    ||minimumResistance>maximumResistance)
                    throw new ArgumentException("Unknown native healing resistance authority");
                f.NativeHealingResistanceEnabled=enabled.GetBoolean();f.NativeHealingResistanceFrozen=resFrozen.GetBoolean();
                f.NativeHealingResistanceMinimum=minimumResistance;f.NativeHealingResistanceMaximum=maximumResistance;
            }
            if (data.TryGetProperty("stats", out var nativeStats))
                f.NativeStats = nativeStats.EnumerateObject().ToDictionary(
                    pair => int.Parse(pair.Name, System.Globalization.CultureInfo.InvariantCulture),
                    pair => pair.Value.GetInt32());
            if(f.NativeHealingResistanceMinimum is int resMinimum
                &&(f.NativeStats==null||!f.NativeStats.TryGetValue(32,out int currentResistance)
                    ||currentResistance<resMinimum||currentResistance>f.NativeHealingResistanceMaximum))
                throw new ArgumentException("Native healing resistance current/bounds mismatch");
            NativePoolAuthority? Pool(string name,int stat)
            {
                if(!data.TryGetProperty(name,out var definition))return null;
                if(Int(definition,"version")!=1||!definition.TryGetProperty("minimum",out var lower)||!lower.TryGetInt32(out int minimum)
                    ||!definition.TryGetProperty("maximum",out var upper)||!upper.TryGetInt32(out int maximum)
                    ||!definition.TryGetProperty("frozen",out var isFrozen)||isFrozen.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                    ||minimum<0||f.NativeStats==null||!f.NativeStats.TryGetValue(stat,out int current)
                    ||minimum>current||current>maximum)
                    throw new ArgumentException("Invalid native absorption-pool authority");
                return new NativePoolAuthority(minimum,maximum,isFrozen.GetBoolean());
            }
            f.NativeArmorAuthority=Pool("nativeArmor",97);f.NativeBarrierAuthority=Pool("nativeBarrier",100);
            f.NativeVirtualHpAuthority=Pool("nativeVirtualHp",92);
            if(f.NativeVirtualHpAuthority is {} virtualAuthority)
            {
                if(f.NativeVirtualHpFrozen!=null&&f.NativeVirtualHpFrozen!=virtualAuthority.Frozen
                    ||f.NativeVirtualHpMax!=virtualAuthority.Maximum)
                    throw new ArgumentException("Conflicting native virtual HP authority");
                f.NativeVirtualHpFrozen=virtualAuthority.Frozen;
            }
            if (data.TryGetProperty("physicalRadius", out _)) nativeBodyActors.Add(f.Id);
            if (Int(data, "armor") > 0) f.Escudar(Int(data, "armor"), 0);
            if (data.TryGetProperty("extraCells", out var extra))
                foreach (var occupied in extra.EnumerateArray())
                {
                    int other = occupied.GetInt32();
                    if (other < 0 || other >= cells.Length) throw new ArgumentException("Actor footprint outside native geometry");
                    f.ExtraCells.Add(other);
                }
            if (Bool(data, "hidden")) hidden.Add(f.Id);
            fighters.Add(f);
        }
        if (fighters.Select(f => f.Id).Distinct().Count() != fighters.Count) throw new ArgumentException("Duplicate actor identity");
        var actor = fighters.Single(f => f.Id == actorId);
        int rootWp = boardData.GetProperty("actors").EnumerateArray()
            .Where(data => Long(data, "id") == actorId).Select(data => Math.Max(0, Int(data, "wp"))).Single();
        actor.NativeCurrentWp = rootWp;
        if (!actor.IsAlive) throw new ArgumentException("WakIA requires a living source actor");
        var portalEdges = boardData.TryGetProperty("portalEdges", out var gateData)
            ? gateData.EnumerateArray().Select(p => (Int(p, "fromCell", -1), Int(p, "toCell", -1))).ToHashSet()
            : new HashSet<(int, int)>();
        var context = new GeometryContext(cells, edges.Concat(portalEdges), cells[actor.CellId].Z);
        lock (CoreLock)
        {
            _ = RemainingBudget();
            using var scope = MapGeometry.BeginScope(context);
            // Freeze native shapes before hypothetical movement inside this geometry scope.
            foreach (var fighter in fighters)
                _ = MonsterTactics.FootprintAt(fighter, fighter.CellId, nativeBodyActors.Contains(fighter.Id)).ToArray();
            var diagnostics = new List<string>();
            int projectionDiagnosticRemaining = 64;
            bool projectionDiagnosticsTruncated = false;
            var spells = new List<MonsterTactics.Spell>();
            var nativeCosts = new Dictionary<(int Spell, int Grade), (int Ap, int Mp, int Wp)>();
            foreach (var data in request.GetProperty("spells").EnumerateArray())
            {
                RecordProjectionUnknowns(data, diagnostics, ref projectionDiagnosticRemaining, ref projectionDiagnosticsTruncated);
                var cost = data.TryGetProperty("nativeCosts", out var costs)
                    ? (Ap: Int(costs, "ap", Int(data, "cost")), Mp: Int(costs, "mp"), Wp: Int(costs, "wp"))
                    : (Ap: Int(data, "cost"), Mp: 0, Wp: 0);
                if (cost.Ap < 0 || cost.Mp < 0 || cost.Wp < 0)
                    throw new ArgumentException("Negative native casting cost");
                nativeCosts[(Int(data, "id"), Int(data, "grade", 1))] = cost;
                // No WP-gain primitive is projected: a spell needing more WP
                // than this source owns cannot become affordable in this plan.
                if (cost.Wp > rootWp) continue;
                var rows = new List<SpellEffect>();
                if (data.TryGetProperty("rows", out var rowData))
                foreach (var row in rowData.EnumerateArray())
                {
                    try
                    {
                        var health=NativeEffectAmounts.ReadDescriptor(row);
                        var geometry=NativeEffectAmounts.Geometry(row);
                        var footprint = geometry.TryGetProperty("fixedCells", out var offsets)
                            ? offsets.EnumerateArray().Select(v => (Dx: v[0].GetInt32(), Dy: v[1].GetInt32())).ToArray() : null;
                        int radius = footprint == null ? Int(row, "zoneRadius")
                            : footprint.Select(p => Math.Abs(p.Dx) + Math.Abs(p.Dy)).DefaultIfEmpty(0).Max();
                        string kind = Text(row, "kind");
                        var projected = SemanticRows.Create(kind, Int(row, "amount"), Text(row, "target", "enemy"),
                            Element(row), radius, Int(row, "stateId"),
                            nativeCoefficientMask: Int(row, "nativeCoefficientMask", 3),
                            nativeDamageFlags: row.TryGetProperty("nativeDamageFlags", out var flags)
                                ? flags.EnumerateArray().Select(flag => flag.GetInt32()).ToArray() : null,
                            nativeLocalization: Bool(row, "nativeLocalization"));
                        if (kind is "gain_ap" or "gain_mp" or "remove_ap" or "remove_mp"
                            || health == null && kind is "damage" or "heal")
                        {
                            bool hasProbability = row.TryGetProperty("probability", out var probability);
                            bool hasCondition = row.TryGetProperty("conditional", out var condition);
                            if (hasProbability || hasCondition)
                            {
                                if (hasProbability && (probability.ValueKind != JsonValueKind.Number
                                    || !probability.TryGetDouble(out _) || !double.IsFinite(probability.GetDouble())))
                                    throw new ArgumentException("Invalid native application probability");
                                if (hasCondition && condition.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                                    throw new ArgumentException("Invalid native application condition evidence");
                                double chance = hasProbability ? Math.Clamp(probability.GetDouble() / 100.0, 0, 1) : 1;
                                SemanticRows.WithApplicationEvidence(projected, chance,
                                    !hasProbability || !hasCondition || condition.GetBoolean());
                            }
                        }
                        if (footprint != null) SemanticRows.WithOffsets(projected, footprint);
                        bool hasCenter=geometry.TryGetProperty("nativeAreaCenterOnCaster",out var areaCenter);
                        bool hasRadius=geometry.TryGetProperty("nativeAreaUseTargetRadius",out var areaRadius);
                        if(hasCenter||hasRadius)
                        {
                            if(!hasCenter||!hasRadius||footprint==null
                                ||areaCenter.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                                ||areaRadius.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                                ||areaCenter.GetBoolean()==areaRadius.GetBoolean())
                                throw new ArgumentException("Incomplete native area anchor/radius contract");
                            SemanticRows.WithNativeAreaPolicy(projected,areaCenter.GetBoolean(),areaRadius.GetBoolean());
                        }
                        if(geometry.TryGetProperty("nativeDirectionalArea",out var nativeArea))
                        {
                            if(footprint==null || footprint.Length!=0)
                                throw new ArgumentException("Invalid native directional area contract");
                            var parsed=NativeDirectionalArea.Parse(nativeArea);
                            if(!hasCenter||!hasRadius||parsed.CenterOnCaster!=areaCenter.GetBoolean()
                                ||parsed.UseTargetRadius!=areaRadius.GetBoolean())
                                throw new ArgumentException("Conflicting native area anchor/radius contract");
                            SemanticRows.WithDirectionalArea(projected,parsed.Raw,parsed.UseTargetRadius,parsed.CenterOnCaster);
                        }
                        NativeAreaPolicy.Bind(projected, Bool(geometry, "nativeInArea", true));
                        if(health!=null)NativeEffectAmounts.Bind(projected,health.Kind,health.Value,health.HealingElement,health.Probability,health.EligibilityKnown,health.SourceBindingKnown,health.TargetNotCarried);
                        rows.Add(projected);
                    }
                    catch (NotSupportedException e) { diagnostics.Add(e.Message); }
                }
                spells.Add(new MonsterTactics.Spell { Id = Int(data, "id"), Grade = Int(data, "grade", 1),
                    Cost = cost.Ap, MinRange = Int(data, "minRange"), MaxRange = Int(data, "maxRange"),
                    NeedsLineOfSight = Bool(data, "needsLineOfSight"), NativeDirectLosRule = Bool(data, "nativeDirectLosRule"), NativeLinearPathRule = Bool(data, "nativeLinearPathRule"), NativeDiagonal = data.TryGetProperty("nativeDiagonal", out var diagonal) && diagonal.ValueKind is JsonValueKind.True or JsonValueKind.False ? diagonal.GetBoolean() : null, NativeAllowSelf = data.TryGetProperty("nativeAllowSelf", out var allowSelf) && allowSelf.ValueKind is JsonValueKind.True or JsonValueKind.False ? allowSelf.GetBoolean() : null,
                    InLine = Bool(data, "inLine"),
                    PerTurn = Int(data, "perTurn"), PerTarget = Int(data, "perTarget"), Interval = Int(data, "interval"), RangeBoostable = Bool(data, "rangeBoostable"),
                    NeedsFreeCell = Bool(data, "needsFreeCell"), Damage = Number(data, "damage"), Element = Element(data),
                    Heal = Number(data, "heal"), Removal = Int(data, "removal"), Buff = Int(data, "buff"),
                    Summons = Bool(data, "summons"), HurtsAllies = Bool(data, "hurtsAllies"),
                    UtilityOnEnemies = Bool(data, "utilityOnEnemies"),
                    Utility = Number(data, "utility"), Zone = Int(data, "zone"), Rows = rows,
                    NativeDirectHealthSequence = Bool(data, "nativeDirectHealthSequence")
                        && data.TryGetProperty("rows", out var rawRows) && rawRows.ValueKind == JsonValueKind.Array
                        && rows.Count == rawRows.GetArrayLength(),
                    NativeNoSelfHeal = Bool(data, "nativeNoSelfHeal")
                        && data.TryGetProperty("rows", out var healRows) && healRows.ValueKind == JsonValueKind.Array
                        && rows.Count == healRows.GetArrayLength() });
            }
            if (projectionDiagnosticsTruncated) diagnostics.Add("native projection diagnostics truncated");
            using var rowScope = SpellEffects.BeginScope(spells.ToDictionary(s => (s.Id, s.Grade), s => s.Rows));
            if (request.TryGetProperty("native", out var native)) ApplyUsage(native, actor);
            var los = new HashSet<(int, int)>();
            var staticLosBlocked = new HashSet<(int From,int To,long Target)>();
            if (boardData.TryGetProperty("nativeStaticLosBlocked", out var staticRays))
            foreach (var ray in staticRays.EnumerateArray())
            {
                if (ray.ValueKind != JsonValueKind.Array || ray.GetArrayLength() != 3)
                    throw new ArgumentException("Invalid native static LOS evidence");
                int from=ray[0].GetInt32(), to=ray[1].GetInt32(); long target=ray[2].GetInt64();
                if (from != actor.CellId || !MapGeometry.IsValid(to)
                    || !fighters.Any(f => f.Id == target && f.IsAlive && f.CellId == to)
                    || MapGeometry.Distance(from,to)!=1 || !staticLosBlocked.Add((from,to,target)))
                    throw new ArgumentException("Unbound native static LOS evidence");
            }
            var linearPathBlocked = new HashSet<(int From,int To,long Target)>();
            if (boardData.TryGetProperty("nativeLinearPathBlocked", out var snRows))
            {
                if (snRows.ValueKind != JsonValueKind.Array || snRows.GetArrayLength() > 8)
                    throw new ArgumentException("Invalid native linear path evidence");
                foreach (var row in snRows.EnumerateArray())
                {
                    if (row.ValueKind != JsonValueKind.Array || row.GetArrayLength() != 3)
                        throw new ArgumentException("Invalid native linear path evidence");
                    int from = row[0].GetInt32(), to = row[1].GetInt32(); long target = row[2].GetInt64();
                    if (from != actor.CellId || !MapGeometry.IsValid(to)
                        || !fighters.Any(f => f.Id == target && f.IsAlive && f.CellId == to)
                        || MapGeometry.Distance(from, to) is < 1 or > 8
                        || !linearPathBlocked.Add((from,to,target)))
                        throw new ArgumentException("Unbound native linear path evidence");
                }
            }
            var sightEvidence = new Dictionary<(int, int), bool?>();
            bool hasLos = boardData.TryGetProperty("lineOfSight", out var pairs);
            if (hasLos) foreach (var pair in pairs.EnumerateArray())
                if (pair.GetArrayLength() == 3)
                {
                    var key = (pair[0].GetInt32(), pair[1].GetInt32());
                    bool visible = pair[2].GetBoolean();
                    if (sightEvidence.TryGetValue(key, out bool? previous))
                        sightEvidence[key] = previous == visible ? visible : null;
                    else sightEvidence[key] = visible;
                    if (visible) los.Add(key);
                }
            var tackle = new Dictionary<int, Tackle.Loss>();
            if (boardData.TryGetProperty("tackle", out var losses))
                foreach (var loss in losses.EnumerateArray()) tackle[Int(loss, "cell")] = new Tackle.Loss(Int(loss, "ap"), Int(loss, "mp"));
            var danger = new Dictionary<int, double>();
            if (boardData.TryGetProperty("movementDanger", out var dangerData))
                foreach (var row in dangerData.EnumerateArray())
                {
                    int cell = Int(row, "cell", -1);
                    double cost = Number(row, "cost");
                    if (cell < 0 || cell >= cells.Length || !double.IsFinite(cost) || cost < 0)
                        throw new ArgumentException("Invalid advisory movement danger");
                    danger[cell] = cost;
                }
            var blockedMovementAnchors = new HashSet<int>();
            var blockedMovementGoals = new HashSet<int>();
            int? movementPermissionOrigin = null;
            if (boardData.TryGetProperty("movementPermissions", out var movement))
            {
                if (Long(movement, "actorId") != actorId)
                    throw new ArgumentException("Movement permissions belong to another actor");
                movementPermissionOrigin = actor.CellId;
                foreach (var (key, target) in new[] { ("blockedAnchors", blockedMovementAnchors), ("blockedGoals", blockedMovementGoals) })
                    foreach (var entry in movement.GetProperty(key).EnumerateArray())
                    {
                        int cell = entry.GetInt32();
                        if (cell < 0 || cell >= cells.Length || !target.Add(cell))
                            throw new ArgumentException("Invalid actor movement permission cell");
                    }
            }
            TeamCoordination.Context? team = null;
            if (boardData.TryGetProperty("coordination", out _))
            {
                var teamActors = fighters.Where(f => !hidden.Contains(f.Id)).ToDictionary(
                    f => f.Id, f => new TeamCoordination.Actor(f.Id, f.TeamId, f.CurrentHP, f.CellId));
                team = TeamCoordination.Read(boardData, actorId, actor.TeamId, teamActors,
                    cells.Select(cell => (cell.X, cell.Y)).ToArray());
            }
            var estimatedSummonBooks = new Dictionary<long, IReadOnlyList<MonsterTactics.Spell>>();
            if (request.TryGetProperty("native", out var nativeEstimates)
                && nativeEstimates.TryGetProperty("estimatedSummonBooks", out var estimatedBooks)
                && estimatedBooks.ValueKind == JsonValueKind.Array)
            {
                foreach (var book in estimatedBooks.EnumerateArray().Take(4))
                {
                    long id = Long(book, "actorId");
                    var summon = fighters.SingleOrDefault(f => f.Id == id);
                    if (summon == null || !summon.IsAlive || !summon.EsInvocado || summon.Invocador != actorId
                        || summon.TeamId != actor.TeamId || hidden.Contains(id)
                        || !book.TryGetProperty("spells", out var estimatedRows) || estimatedRows.ValueKind != JsonValueKind.Array)
                        continue;
                    var estimates = new List<MonsterTactics.Spell>();
                    foreach (var row in estimatedRows.EnumerateArray().Take(16))
                    {
                        int idValue = Int(row, "id"), level = Int(row, "grade", -1);
                        if (!row.TryGetProperty("cost", out var costField) || costField.ValueKind != JsonValueKind.Number
                            || !costField.TryGetInt32(out int cost)) continue;
                        int minimum = Int(row, "minRange", -1), maximum = Int(row, "maxRange", -1);
                        double damage = Number(row, "damage");
                        int mask = Int(row, "nativeCoefficientMask", -1);
                        if (idValue <= 0 || level < 0 || cost < 0 || minimum < 0 || maximum < minimum
                            || maximum > 128 || !double.IsFinite(damage) || damage <= 0 || damage > 1000000
                            || mask < 0 || mask > 3 || !row.TryGetProperty("nativeDamageFlags", out var flags)
                            || flags.ValueKind != JsonValueKind.Array || flags.GetArrayLength() > 32
                            || flags.EnumerateArray().Any(flag => flag.ValueKind != JsonValueKind.Number || !flag.TryGetInt32(out _))
                            || !row.TryGetProperty("nativeLocalization", out var localization)
                            || localization.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                            continue;
                        try {
                            var element = Element(row);
                            var projected = SemanticRows.Create("damage", (int)damage, "enemy", element, 0, 0,
                                nativeCoefficientMask:mask, nativeDamageFlags:flags.EnumerateArray().Select(flag=>flag.GetInt32()).ToArray(),
                                nativeLocalization:localization.GetBoolean());
                            estimates.Add(new MonsterTactics.Spell { Id=idValue, Grade=level, Cost=cost,
                                MinRange=minimum, MaxRange=maximum, Damage=damage, Element=element,
                                Rows=new List<SpellEffect>{projected} });
                        }
                        catch (NotSupportedException) { }
                    }
                    if (estimates.Count > 0) estimatedSummonBooks[id] = estimates;
                }
                if (estimatedSummonBooks.Count > 0)
                    diagnostics.Add("summon forecast uses previous spell projections as estimates; future criteria and LOS are unknown");
            }
            var board = new MonsterTactics.Board { Fighters = fighters, Round = Int(boardData, "round"),
                TeamFocusId = team?.FocusId, TeamReservedXY = team?.Reserved ?? new HashSet<(int, int)>(),
                TeamCorridors = team?.Corridors,
                ActorBlocksNativeLos = team?.BlocksLos,
                IsPortalTravel=(from,to)=>portalEdges.Contains((from,to)),
                SearchContinues = CanFinish,
                MovementDanger = danger.Values.Any(cost => cost > 0)
                    ? cell => danger.GetValueOrDefault(cell) : null,
                TrackResourceRoutes = tackle.Values.Any(loss => loss.ActionPoints > 0 || loss.MovementPoints > 0),
                SpellMovementCost = spell => nativeCosts[(spell.Id, spell.Grade)].Mp,
                SpellWakfuCost = spell => nativeCosts[(spell.Id, spell.Grade)].Wp,
                HasEstimatedSummonBook = estimatedSummonBooks.Count > 0,
                NativeMovementPermissionOrigin = movementPermissionOrigin,
                NativeMovementPermissionActorId = movementPermissionOrigin.HasValue ? actorId : null,
                MovementAnchorAllowed = (who, cell) => who.Id != actorId || !blockedMovementAnchors.Contains(cell),
                MovementGoalAllowed = (who, cell) => who.Id != actorId || !blockedMovementGoals.Contains(cell),
                Walkable = MapGeometry.IsValid, Sees = (from, to) => hasLos && los.Contains((from, to)),
                SightEvidence = (from, to) => sightEvidence.TryGetValue((from, to), out bool? visible) ? visible : null,
                NativeStaticLosActorId = actorId, NativeStaticLosOrigin = actor.CellId,
                NativeStaticLosBlocked = staticLosBlocked,
                NativeLinearPathBlocked = linearPathBlocked,
                Reach = (row, caster, from, aim) => NativeReach(fighters, row, caster, from, aim),
                NativeHealthReachStable = true,
                TackleAt = (who, cell, ap, mp) => tackle.TryGetValue(cell, out var loss)
                    ? new Tackle.Loss(Math.Min(ap, loss.ActionPoints), Math.Min(mp, loss.MovementPoints)) : Tackle.Loss.None,
                Hidden = f => hidden.Contains(f.Id), SpellsOf = f => f.Id == actorId ? spells : new List<MonsterTactics.Spell>(),
                SummonEstimatedSpellsOf = f => estimatedSummonBooks.TryGetValue(f.Id, out var rows) ? rows : Array.Empty<MonsterTactics.Spell>() };
            int budget = 2000;
            if (request.TryGetProperty("limits", out var limits)) budget = Math.Clamp(Int(limits, "budgetMs", 2000), 1, 2000);
            var excluded = request.TryGetProperty("excludedActions", out var rejected)
                ? rejected.EnumerateArray().Select(v => v.ValueKind == JsonValueKind.String ? v.GetString()! : Canonical(v)).ToHashSet()
                : new HashSet<string>();
            (int Ap, int Mp, int Wp) Costs(MonsterTactics.Spell spell) => nativeCosts[(spell.Id, spell.Grade)];
            bool Allowed(MonsterTactics.Spell spell)
            {
                var cost = Costs(spell);
                // CurrentAP/MP are the upstream simulation's mutable values,
                // so a preparation may make a later cast affordable.
                return cost.Ap <= actor.CurrentAP && cost.Mp <= actor.CurrentMP && cost.Wp <= actor.NativeCurrentWp;
            }
            bool Affordable(MonsterTactics.Action option, int wpSpent = 0)
            {
                var cost = Costs(option.Spell);
                return cost.Ap <= option.ActionPoints
                    && cost.Mp <= option.MovementPoints
                    && (long)cost.Wp + wpSpent <= rootWp;
            }
            List<MonsterTactics.Action> AffordablePrefix(IEnumerable<MonsterTactics.Action> options)
            {
                var prefix = new List<MonsterTactics.Action>();
                int wpSpent = 0;
                foreach (var option in options)
                {
                    if (!Affordable(option, wpSpent)) break;
                    prefix.Add(option);
                    var cost = Costs(option.Spell);
                    wpSpent += cost.Wp;
                }
                return prefix;
            }
            // The request is immutable throughout this decision. Reuse its
            // continuation key only within this call, never across snapshots.
            var requestKey = new Lazy<string?>(() => TurnPlans.Key(request));
            var started = Stopwatch.StartNew();
            var strategy = SpecificAis.Resolve(actor.MonsterId);
            if (strategy != null)
            {
                _ = RemainingBudget();
                var special = new SpecificContext(request, board, actor, spells, cells, Costs, portalEdges);
                var candidates = strategy.Propose(special)
                    .Where(p => double.IsFinite(p.Score) && !excluded.Contains(Canonical(p.Action)))
                    .OrderByDescending(p => p.Score).GroupBy(p => Canonical(p.Action)).Select(g => g.First()).ToList();
                if (special.SuppressedSpells.Count > 0)
                {
                    spells = spells.Where(s => !special.SuppressedSpells.ContainsKey(s.Id)).ToList();
                    diagnostics.AddRange(special.SuppressedSpells.Select(p => $"specific-ai suppress {p.Key}: {p.Value}"));
                }
                if (candidates.Count > 0)
                {
                    // Re-evaluate native phase facts after every actual commit.
                    // A custom action never inherits a hypothetical beam tail.
                    TurnPlans.Invalidate(request, requestKey);
                    var chosen = candidates[0];
                    var secondary = candidates.Skip(1).Take(3).Select(p => p.Action).ToList();
                    var keys = new HashSet<string>(excluded) { Canonical(chosen.Action) };
                    secondary = secondary.Where(p => keys.Add(Canonical(p))).ToList();
                    // A conditional native rejection can immediately fall back
                    // without another full beam search or an invalid cast loop.
                    var ordinary = CanFinish() ? MonsterTactics.Next(board, actor, spells) : null;
                    if (ordinary != null && Affordable(ordinary))
                    {
                        var backup = Step(ordinary, actor, cells, portalEdges, fighters);
                        if (keys.Add(Canonical(backup))) secondary.Add(backup);
                    }
                    var chosenJson = JsonSerializer.SerializeToElement(chosen.Action);
                    TurnPlans.CaptureOffer(request, actor, Text(chosenJson, "type"),
                        chosenJson.TryGetProperty("spellId", out var offeredSpell) ? offeredSpell.GetInt32() : null, requestKey);
                    return new { protocol = 1, requestId = Text(request, "requestId"), source = source.Clone(),
                        action = chosen.Action, alternatives = secondary, upstream = Upstream,
                        elapsedMs = started.Elapsed.TotalMilliseconds, plannedCasts = 0, planReused = false,
                        strategyId = strategy.Id, strategyMode = "specific", strategyReason = chosen.Reason,
                        prediction = "advisory; World native authority validates and commits", diagnostics };
                }
            }
            int supportAllowance = Math.Min(100, Math.Max(1, RemainingBudget() / 4));
            long supportDeadline = Stopwatch.GetTimestamp()
                + (long)(supportAllowance * (Stopwatch.Frequency / 1000.0));
            var supportCandidates = NativeSupportCandidates.Propose(request, board, actor, spells, cells, Costs, portalEdges,
                    () => deadlineTimestamp == null || CanFinish() && Stopwatch.GetTimestamp() < supportDeadline)
                .Where(p => double.IsFinite(p.Score) && !excluded.Contains(Canonical(p.Action)))
                .GroupBy(p => Canonical(p.Action)).Select(g => g.First()).OrderByDescending(p => p.Score).ToList();
            NativeSupportCandidates.Candidate? selectedSupport = null;
            bool reused = TurnPlans.TryGet(request, board, actor, spells, out var continuation, requestKey);
            if (reused && !Affordable(continuation!))
            {
                TurnPlans.Invalidate(request, requestKey);
                reused = false;
            }
            int remaining = RemainingBudget();
            int completionReserve = deadlineTimestamp == null ? 0 : Math.Clamp(remaining / 5, 5, 50);
            budget = Math.Min(budget, Math.Max(1, remaining - completionReserve));
            long searchDeadline = Stopwatch.GetTimestamp()
                + (long)(budget * (Stopwatch.Frequency / 1000.0));
            var plan = reused ? new List<MonsterTactics.Action> { continuation! }
                : AffordablePrefix(MonsterTactics.PlanTurn(board, actor, spells, Allowed, budgetMs: budget,
                    continueSearch: () => deadlineTimestamp == null
                        || CanFinish() && Stopwatch.GetTimestamp() < searchDeadline));
            if (!reused) TurnPlans.Store(request, plan, requestKey);
            var alternatives = new List<object>();
            object? action = null;
            if (plan.Count > 0)
            {
                var proposal = Step(plan[0], actor, cells, portalEdges, fighters);
                if (!excluded.Contains(Canonical(proposal))) action = proposal;
            }
            if (supportCandidates.Count > 0 && (action == null || supportCandidates[0].Score > plan[0].Score))
            {
                if (action != null) alternatives.Add(action);
                selectedSupport = supportCandidates[0];
                action = selectedSupport.Action;
                // A native support proposal has no fabricated future creature
                // or buff state. Re-read actual World facts after its commit.
                TurnPlans.Invalidate(request, requestKey);
                reused = false;
            }
            if (action == null && CanFinish())
            {
                var immediate = MonsterTactics.Next(board, actor, spells);
                if (immediate != null && Affordable(immediate))
                {
                    var proposal = Step(immediate, actor, cells, portalEdges, fighters);
                    if (!excluded.Contains(Canonical(proposal))) action = proposal;
                }
            }
            if (action == null && CanFinish())
                foreach (var option in DiverseOptions(board, actor, spells).Where(option => Affordable(option)))
                {
                    var proposal = Step(option, actor, cells, portalEdges, fighters);
                    if (!excluded.Contains(Canonical(proposal))) { action = proposal; break; }
                }
            if (action == null && CanFinish())
            {
                var path = MonsterTactics.Reposition(board, actor, spells);
                if (path.Count > 1)
                {
                    object proposal = Movement(path, cells, portalEdges);
                    if (!excluded.Contains(Canonical(proposal))) action = proposal;
                }
            }
            action ??= new { type = "end_turn" };
            var selected = JsonSerializer.SerializeToElement(action);
            TurnPlans.CaptureOffer(request, actor, Text(selected, "type"),
                selected.TryGetProperty("spellId", out var selectedSpell) ? selectedSpell.GetInt32() : null, requestKey);
            // A rejected native choice can try another root option without
            // adopting a later step from a hypothetical beam sequence.
            var offered = new HashSet<string>(excluded) { Canonical(action) };
            foreach (var existing in alternatives) offered.Add(Canonical(existing));
            foreach (var candidate in supportCandidates)
                if (alternatives.Count < 16 && offered.Add(Canonical(candidate.Action))) alternatives.Add(candidate.Action);
            foreach (var option in (CanFinish() ? DiverseOptions(board, actor, spells)
                    : Enumerable.Empty<MonsterTactics.Action>()).Where(option => Affordable(option)))
            {
                if (alternatives.Count >= 16) break;
                var proposal = Step(option, actor, cells, portalEdges, fighters);
                if (offered.Add(Canonical(proposal))) alternatives.Add(proposal);
                if (alternatives.Count >= 16) break;
            }
            return new { protocol = 1, requestId = Text(request, "requestId"), source = source.Clone(), action,
                alternatives,
                upstream = Upstream, elapsedMs = started.Elapsed.TotalMilliseconds, plannedCasts = selectedSupport == null ? plan.Count : 0,
                planReused = reused,
                strategyId = selectedSupport != null ? "native-support" : strategy?.Id ?? "normal-jondo",
                strategyMode = selectedSupport != null ? "native-support" : strategy == null ? "normal" : "normal-fallback",
                strategyReason = selectedSupport?.Reason ?? (strategy == null ? "No specific profile" : "Native mechanic prerequisites do not request an override"),
                prediction = "advisory; World native authority validates and commits", diagnostics };
        }
    }

    internal static IReadOnlyList<Fighter> NativeReach(IReadOnlyList<Fighter> fighters, SpellEffect row, Fighter caster, int from, int aim)
    {
        // Recipient relations and area membership are separate native bits.
        // Without the in-area bit, a self recipient remains the caster even
        // when a positive-range cast is aimed elsewhere. Read live simulation
        // positions for area-restricted rows rather than frozen target sets.
        bool inArea = NativeAreaPolicy.InArea(row);
        bool native=SemanticRows.DirectionalArea(row)!=null||SemanticRows.HasNativeAreaPolicy(row);
        var area = inArea && !native
            ? global::Jondo.Unity.Server.Managers.EffectEngine.CasillasDelEfecto(row, from, aim,caster.NativeDirection).ToHashSet()
            : null;
        bool Eligible(Fighter who) => row.TargetMask switch
        {
            "C" or "c" => who.Id == caster.Id,
            "a" => who.Id != caster.Id && who.TeamId == caster.TeamId,
            "A" => who.TeamId != caster.TeamId,
            _ => false,
        };
        return fighters.Where(f => f.IsAlive && Eligible(f)
            && (!inArea || (native
                ? SemanticRows.TryNativeContains(row,caster,from,aim,f,out bool contains)&&contains
                : MonsterTactics.FootprintAt(f, f == caster ? from : f.CellId).Any(area!.Contains)))).ToList();
    }

    private static IEnumerable<MonsterTactics.Action> DiverseOptions(MonsterTactics.Board board, Fighter actor, IReadOnlyList<MonsterTactics.Spell> spells)
    {
        var ranked = MonsterTactics.Options(board, actor, spells).OrderByDescending(o => o.Score).ToList();
        var first = ranked.GroupBy(o => o.Spell.Id).Select(g => g.First()).ToList();
        return first.Concat(ranked.Where(o => !first.Contains(o)));
    }

    private static object Step(MonsterTactics.Action step, Fighter actor, CellXYZ[] cells, HashSet<(int, int)> gates, IReadOnlyList<Fighter> fighters)
    {
        if (step.Path.Count > 1) return Movement(step.Path, cells, gates);
        return new { type = "cast", spellId = step.Spell.Id, level = step.Spell.Grade,
            target = XYZ(cells[step.TargetCell]), targetId = fighters.FirstOrDefault(f => f.IsAlive && MonsterTactics.FootprintAt(f, f.CellId).Contains(step.TargetCell))?.Id };
    }
    private static object Movement(IReadOnlyList<int> path, CellXYZ[] cells, HashSet<(int, int)> gates)
    {
        if (gates.Contains((path[0], path[1])))
            return new { type = "portal_travel", destination = XYZ(cells[path[1]]) };
        var walked = new List<int[]>();
        for (int i = 1; i < path.Count; i++)
        {
            if (gates.Contains((path[i - 1], path[i]))) break;
            walked.Add(XYZ(cells[path[i]]));
        }
        return new { type = "move", path = walked };
    }
    private static int[] XYZ(CellXYZ p) => new[] { p.X, p.Y, p.Z };
    private static ElementType Element(JsonElement value)
    {
        if (!value.TryGetProperty("element", out var element)) return ElementType.Physical;
        if (element.ValueKind == JsonValueKind.Number)
        {
            int raw = element.GetInt32();
            if (raw is >= 0 and <= 6) return (ElementType)raw;
            throw new NotSupportedException("Unknown advisory element number");
        }
        return (element.GetString() ?? "physical").ToLowerInvariant() switch
        {
            "earth" => ElementType.Earth, "fire" => ElementType.Fire,
            "water" => ElementType.Water, "air" => ElementType.Air,
            "light" => ElementType.Light, "stasis" => ElementType.Stasis,
            "physical" or "none" or "neutral" => ElementType.Physical,
            _ => throw new NotSupportedException("Unknown advisory native element"),
        };
    }
    private static void ApplyUsage(JsonElement native, Fighter actor)
    {
        if (!native.TryGetProperty("usage", out var usage)) return;
        foreach (var item in usage.EnumerateArray())
        {
            int spell = Int(item, "spellId");
            actor.LanzadosEsteTurno[spell] = Int(item, "count");
            actor.Recarga[spell] = Int(item, "remainingCooldown");
            if (item.TryGetProperty("targetId", out var target))
                actor.LanzadosPorObjetivo[(spell, target.GetInt64())] = Int(item, "targetCount");
        }
    }
    private static string Canonical(object value)
    {
        var json = value is JsonElement e ? e : JsonSerializer.SerializeToElement(value);
        return json.ValueKind switch
        {
            JsonValueKind.Object => "{" + string.Join(",", json.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal)
                .Select(p => JsonSerializer.Serialize(p.Name) + ":" + Canonical(p.Value))) + "}",
            JsonValueKind.Array => "[" + string.Join(",", json.EnumerateArray().Select(v => Canonical(v))) + "]",
            _ => json.GetRawText()
        };
    }
}
