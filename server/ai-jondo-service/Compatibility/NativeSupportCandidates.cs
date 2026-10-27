using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Wakfu.Jondo;

/// <summary>Native support advice only. Never simulates a summon or grants a state.</summary>
internal static class NativeSupportCandidates
{
    internal sealed record Candidate(object Action, int SpellId, double Score, string Reason);
    private static string Text(JsonElement v, string key) => v.TryGetProperty(key, out var p) && p.ValueKind == JsonValueKind.String ? p.GetString()! : "";
    private static int Int(JsonElement v, string key, int fallback = 0) => v.TryGetProperty(key, out var p) && p.ValueKind == JsonValueKind.Number && p.TryGetInt32(out int n) ? n : fallback;
    private static bool Flag(JsonElement v, string key) => v.TryGetProperty(key, out var p) && p.ValueKind == JsonValueKind.True;
    private static IEnumerable<JsonElement> Array(JsonElement v, string key) => v.TryGetProperty(key, out var p) && p.ValueKind == JsonValueKind.Array ? p.EnumerateArray() : Enumerable.Empty<JsonElement>();
    private static bool Names(JsonElement v, string key, string name) => Array(v, key).Any(p => p.ValueKind == JsonValueKind.String && p.GetString() == name);

    internal static IReadOnlyList<Candidate> Propose(JsonElement request, MonsterTactics.Board board, Fighter actor,
        IReadOnlyList<MonsterTactics.Spell> spells, CellXYZ[] cells,
        Func<MonsterTactics.Spell, (int Ap, int Mp, int Wp)> costs, HashSet<(int, int)> gates, Func<bool>? canExplore = null)
    {
        var rawActors = request.GetProperty("board").GetProperty("actors").EnumerateArray()
            .ToDictionary(a => a.GetProperty("id").GetInt64());
        var self = rawActors[actor.Id];
        int wp = Int(self, "wp");
        var history = request.TryGetProperty("native", out var native) ? Array(native, "turnActions").ToArray() : System.Array.Empty<JsonElement>();
        KeyValuePair<int, MonsterTactics.Route>[]? origins = null;
        var candidates = new List<Candidate>();
        IReadOnlyList<Candidate> Finish() => candidates.OrderByDescending(c => c.Score).Take(16).ToArray();
        var enemies = board.Fighters.Where(f => f.IsAlive && f.TeamId != actor.TeamId && !board.Hidden(f)).ToList();
        var allies = board.Fighters.Where(f => f.IsAlive && f.TeamId == actor.TeamId).ToList();
        foreach (var rawSpell in request.GetProperty("spells").EnumerateArray().Take(64))
        {
            if (canExplore?.Invoke() == false) return Finish();
            int id = Int(rawSpell, "id");
            var spell = spells.FirstOrDefault(s => s.Id == id);
            if (spell == null || !rawSpell.TryGetProperty("nativeSupport", out var support)
                || Int(support, "version") != 1 || actor.Recarga.GetValueOrDefault(id) > 0) continue;
            int count = Math.Max(actor.LanzadosEsteTurno.GetValueOrDefault(id), history.Count(a => Text(a, "type") == "cast" && Int(a, "spellId") == id));
            var cost = costs(spell);
            if (cost.Ap > actor.CurrentAP || cost.Mp > actor.CurrentMP || cost.Wp > wp
                || spell.PerTurn > 0 && count >= spell.PerTurn || cost.Ap == 0 && count > 0) continue;
            // This provider supplies missing support semantics; ordinary numeric
            // rows retain their existing multi-action planner and healing logic.
            var projected = Array(rawSpell, "rows").Select(r => Int(r, "nativeReference", -1)).Where(r => r >= 0).ToHashSet();
            var effects = Array(support, "effects").Where(e => !projected.Contains(Int(e, "nativeReference", -2))).Take(32).ToArray();
            var summons = Array(support, "summons").Take(8).ToArray();
            bool anchorOnly = Flag(support, "castAnchorRequired") && (spell.HasRows || spell.Utility > 0);
            if (effects.Length == 0 && summons.Length == 0 && !anchorOnly) continue;
            origins ??= MonsterTactics.Routes(board, actor).OrderBy(p => p.Value.Steps).ThenBy(p => p.Value.Danger).Take(128).ToArray();
            var aims = new HashSet<int>();
            foreach (var target in board.Fighters.Where(f => f.IsAlive))
            {
                string relation = target.Id == actor.Id ? "self" : target.TeamId == actor.TeamId ? "ally" : "enemy";
                if (Names(support, "aimKinds", relation) || Flag(support, "castAnchorRequired") && !spell.NeedsFreeCell)
                    foreach (int cell in MonsterTactics.FootprintAt(target, target.CellId).Where(MapGeometry.IsValid)) aims.Add(cell);
            }
            if (Names(support, "aimKinds", "emptyCell"))
                foreach (var c in Array(support, "candidateCells").Take(32))
                    if (c.TryGetInt32(out int cell) && MapGeometry.IsValid(cell)) aims.Add(cell);
            var bestByAim = new Dictionary<int, Candidate>();
            foreach (int fixedAim in aims.OrderBy(c => MapGeometry.Distance(actor.CellId, c)).Take(48))
            foreach (var (from, route) in origins)
            {
                if (canExplore?.Invoke() == false)
                {
                    candidates.AddRange(bestByAim.Values);
                    return Finish();
                }
                if (cost.Ap > route.ActionPoints || cost.Mp > route.MovementPoints) continue;
                // A zero-range aura is aimed at the hypothetical source anchor,
                // regardless of its effect recipient relations.
                int aim = spell.MaxRange == 0 && Names(support, "aimKinds", "self") ? from : fixedAim;
                int distance = MapGeometry.Distance(from, aim);
                int maximum = spell.MaxRange + (spell.RangeBoostable ? actor.Range : 0);
                if (distance < spell.MinRange || distance > maximum) continue;
                var p = cells[from]; var q = cells[aim];
                if (spell.InLine && p.X != q.X && p.Y != q.Y) continue;
                if (spell.NeedsLineOfSight && from != aim && !board.Sees(from, aim)) continue;
                Fighter? target = board.Fighters.FirstOrDefault(f => f.IsAlive
                    && MonsterTactics.FootprintAt(f, f == actor ? from : f.CellId).Contains(aim));
                if (spell.NeedsFreeCell && target != null) continue;
                if (target != null && spell.PerTarget > 0
                    && actor.LanzadosPorObjetivo.GetValueOrDefault((id, target.Id)) >= spell.PerTarget) continue;
                int previousDirection=actor.NativeDirection;
                actor.NativeDirection=NativeDirectionalArea.DirectionAfterPath(board,route.Path,previousDirection);
                try
                {
                    double supportValue = Value(support, effects, summons, target, actor, rawActors, board.Fighters, from, aim, count);
                    if ((!anchorOnly && !(supportValue > 0)) || !double.IsFinite(supportValue)) continue;
                    // Existing pure-mechanic utility is exploration, not proof of a
                    // repeatable benefit. Do not spend paid AP on that same unknown
                    // effect again this turn; fresh typed benefit can still qualify.
                    if (supportValue <= 0 && !spell.HasRows && count > 0) continue;
                    // Existing damage/heal rows retain their normal native-aware
                    // estimate, including harm to allies; never score a mixed cast
                    // as though only its beneficial support component existed.
                    bool pureSelfUtilityAnchor = anchorOnly && !spell.HasRows && !spell.Offensive
                        && spell.Heal <= 0 && spell.Buff <= 0 && !spell.UtilityOnEnemies;
                    // A global self effect still benefits its caster when its legal
                    // cast anchor is occupied by somebody else. Preserve that
                    // existing utility valuation, but keep the real action target.
                    var valueTarget = pureSelfUtilityAnchor ? actor : target ?? actor;
                    double value = supportValue + MonsterTactics.ValueOfCast(board, spell, actor, from, aim, enemies, allies, valueTarget);
                    if (!(value > 0) || !double.IsFinite(value)) continue;
                    double score = value / Math.Max(1, cost.Ap)
                        * Math.Max(0.1, 1 - 0.06 * (route.Steps + route.LostToTackles(actor))) / (1 + 0.06 * route.Danger);
                    object action = route.Path.Count > 1 ? Movement(route.Path, cells, gates)
                        : new { type = "cast", spellId = id, level = spell.Grade, target = new[] { q.X, q.Y, q.Z }, targetId = target?.Id };
                    string reason = supportValue > 0
                        ? "Typed native support candidate; benefit is advisory, effects remain native"
                        : "Native cast-anchor candidate; preserves existing utility without predicting unknown effects";
                    var proposal = new Candidate(action, id, score, reason);
                    if (!bestByAim.TryGetValue(aim, out var best) || score > best.Score) bestByAim[aim] = proposal;
                }
                finally { actor.NativeDirection=previousDirection; }
            }
            candidates.AddRange(bestByAim.Values);
        }
        return Finish();
    }

    private static double Confidence(JsonElement effect)
    {
        double probability = effect.TryGetProperty("probability", out var p) && p.ValueKind == JsonValueKind.Number
            ? Math.Clamp(p.GetDouble(), 0, 100) / 100.0 : 0;
        string confidence = Text(effect, "confidence");
        return probability * (confidence == "known" && !Flag(effect, "conditional") && !Flag(effect, "triggered") && !Flag(effect, "fromState") ? 1 : confidence is "known" or "conditional" ? 0.25 : 0);
    }

    private static double Value(JsonElement support, JsonElement[] effects, JsonElement[] summons, Fighter? target,
        Fighter actor, IReadOnlyDictionary<long, JsonElement> rawActors, IReadOnlyList<Fighter> fighters, int from, int aim, int castCount)
    {
        double value = 0;
        string relation = target == null ? "emptyCell" : target.Id == actor.Id ? "self" : target.TeamId == actor.TeamId ? "ally" : "enemy";
        // A role bonus ranks only real authored summon capabilities; it is not
        // a prediction of an invented creature's HP, spells or future damage.
        if (target == null || target.Id == actor.Id && Names(support, "aimKinds", "self"))
            foreach (var summon in summons.Where(s => Int(s, "reference") > 0
                && Text(s, "benefit") is "beneficial" or "harmful"))
            {
                double sign = Text(summon, "benefit") == "beneficial" ? 1 : -1;
                double duplicate = 1;
                if (sign > 0 && support.TryGetProperty("facts", out var facts)
                    && Array(facts, "ownedLiving").Any(a => Int(a, "reference") == Int(summon, "reference"))) duplicate = 0.5;
                value += sign * (40 + actor.Level * 0.5) * Confidence(summon) * duplicate / (1 + castCount);
            }
        foreach (var effect in effects)
        {
            var geometry=NativeEffectAmounts.Geometry(effect,true);
            bool wrapped=effect.TryGetProperty("nativeHealthGeometry",out _);
            bool hasCenter=geometry.TryGetProperty("nativeAreaCenterOnCaster",out var nativeCenter);
            bool hasRadius=geometry.TryGetProperty("nativeAreaUseTargetRadius",out var nativeRadius);
            if((hasCenter||hasRadius)&&(!hasCenter||!hasRadius
                ||nativeCenter.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                ||nativeRadius.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                ||nativeCenter.GetBoolean()==nativeRadius.GetBoolean()))
                throw new ArgumentException("Incomplete native support area anchor/radius contract");
            var recipients = target == null ? Enumerable.Empty<Fighter>() : new[] { target }.AsEnumerable();
            if (geometry.TryGetProperty(wrapped?"nativeInArea":"inArea", out var inArea) && inArea.ValueKind == JsonValueKind.False)
                recipients = fighters.Where(f => f.IsAlive);
            else if(geometry.TryGetProperty("nativeDirectionalArea",out var directionalDescriptor))
            {
                var native=NativeDirectionalArea.Parse(directionalDescriptor);
                if(!hasCenter||!hasRadius||native.CenterOnCaster!=nativeCenter.GetBoolean()
                    ||native.UseTargetRadius!=nativeRadius.GetBoolean())
                    throw new ArgumentException("Conflicting native support area anchor/radius contract");
                recipients=fighters.Where(f=>f.IsAlive&&native.Contains(MapGeometry.Context.Cells[native.CenterOnCaster?from:aim],
                    MapGeometry.Context.Cells[native.CenterOnCaster?aim:from],actor.NativeDirection,
                    MapGeometry.Context.Cells[f==actor?from:f.CellId],native.UseTargetRadius?f.NativePhysicalRadius:0));
            }
            else if (geometry.TryGetProperty("fixedCells", out var offsets) && offsets.ValueKind == JsonValueKind.Array)
            {
                var center = MapGeometry.CellToPoint(hasCenter&&nativeCenter.GetBoolean()?from:aim);
                var area = offsets.EnumerateArray().Where(p => p.ValueKind == JsonValueKind.Array && p.GetArrayLength() == 2)
                    .Select(p => (X: center.X + p[0].GetInt32(), Y: center.Y + p[1].GetInt32())).ToHashSet();
                if(hasCenter)
                    recipients=fighters.Where(f=>
                    {
                        if(!f.IsAlive)return false;
                        int radius=nativeRadius.GetBoolean()?f.NativePhysicalRadius:0;
                        if(radius is <-128 or >127)return false;
                        radius=Math.Max(0,radius);var point=MapGeometry.CellToPoint(f==actor?from:f.CellId);
                        return area.Any(p=>Math.Abs((long)point.X-p.X)<=radius&&Math.Abs((long)point.Y-p.Y)<=radius);
                    });
                else recipients = fighters.Where(f => f.IsAlive && MonsterTactics.FootprintAt(f, f == actor ? from : f.CellId)
                        .Where(MapGeometry.IsValid).Any(c => area.Contains(MapGeometry.CellToPoint(c))));
            }
            foreach (var recipient in recipients)
            {
                if (!rawActors.TryGetValue(recipient.Id, out var raw)) continue;
                relation = recipient.Id == actor.Id ? "self" : recipient.TeamId == actor.TeamId ? "ally" : "enemy";
                if (!Names(effect, "targets", relation)) continue;
                string benefit = Text(effect, "benefit"), kind = Text(effect, "kind");
                bool beneficial = benefit == "beneficial", harmful = benefit == "harmful";
                if (!beneficial && !harmful) continue;
                double sign = relation == "enemy" ? (harmful ? 1 : -1) : (beneficial ? 1 : -1);
                double weight = Confidence(effect);
                if (weight <= 0) continue;
                if (kind is "add_state" or "remove_state")
                {
                    int state = Int(effect, "stateId");
                    var existing = Array(raw, "states").Where(s => Int(s, "reference") == state).ToArray();
                    bool present = existing.Length > 0 || Array(effect, "presentOn").Any(a => a.ValueKind == JsonValueKind.Number && a.GetInt64() == recipient.Id);
                    bool increaseProven = Array(effect, "increaseOn").Any(a => a.ValueKind == JsonValueKind.Number && a.GetInt64() == recipient.Id);
                    // Presence and level are distinct: level zero can still be
                    // a real native buff. Existing states earn additional value
                    // only from a source-attested stacking increase for this target.
                    if (state <= 0 || kind == "add_state" && present && !increaseProven || kind == "remove_state" && !present) continue;
                    value += sign * 16 * weight;
                }
                else if (kind == "heal")
                {
                    double amount = Math.Max(0, Int(effect, "amount"));
                    if (Flag(effect, "percent"))
                    {
                        if (Text(effect, "percentBase") != "maximum_hp") continue;
                        amount = recipient.MaxHP * amount / 100.0;
                    }
                    value += sign * Math.Min(Math.Max(0, recipient.MaxHP - recipient.CurrentHP), amount)
                        * (recipient.CurrentHP * 2 < recipient.MaxHP ? 1.5 : 1) * weight;
                }
                else if (kind is "stat_gain" or "stat_loss")
                {
                    if (effect.TryGetProperty("amountKnown", out var known) && known.ValueKind == JsonValueKind.False) continue;
                    double amount = Math.Abs((double)Int(effect, "amount"));
                    int stat = Int(effect, "statId", -1);
                    if (Flag(effect, "percent"))
                    {
                        if (!raw.TryGetProperty("stats", out var stats) || !stats.TryGetProperty(stat.ToString(), out var current)) continue;
                        amount = Math.Abs(current.GetDouble() * amount / 100.0);
                    }
                    if (stat == 2) amount = Math.Min(amount, Math.Max(0, kind == "stat_loss" ? recipient.CurrentAP : recipient.MaxAP - recipient.CurrentAP));
                    if (stat == 3) amount = Math.Min(amount, Math.Max(0, kind == "stat_loss" ? recipient.CurrentMP : recipient.MaxMP - recipient.CurrentMP));
                    value += sign * Math.Min(40, amount * (stat == 2 ? 20 : stat == 3 ? 12 : 1)) * weight;
                }
            }
        }
        return value;
    }

    private static object Movement(IReadOnlyList<int> path, CellXYZ[] cells, HashSet<(int, int)> gates)
    {
        int[] Xyz(int cell) => new[] { cells[cell].X, cells[cell].Y, cells[cell].Z };
        if (gates.Contains((path[0], path[1]))) return new { type = "portal_travel", destination = Xyz(path[1]) };
        var walked = new List<int[]>();
        for (int i = 1; i < path.Count; i++)
        {
            if (gates.Contains((path[i - 1], path[i]))) break;
            walked.Add(Xyz(path[i]));
        }
        return new { type = "move", path = walked };
    }
}
