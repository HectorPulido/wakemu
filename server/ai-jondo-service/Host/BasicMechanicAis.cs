namespace Wakfu.Jondo;

/// <summary>
/// Native mechanic priorities for ordinary controller and linked-summon actors.
/// Every proposal is an ordinary advisory action; World retains cast authority.
/// </summary>
internal static class BasicMechanicAis
{
    public static IEnumerable<ISpecificAi> Create()
    {
        yield return new SecurityWaves();
        yield return new GelaxWaves();
        yield return new AtesLinkedSummon();
        yield return new OmebaTentacles();
        yield return new BulbAttackerMark();
        yield return new BrizlonPrisoner();
    }

    private sealed class SecurityWaves : ISpecificAi
    {
        public string Id => "security-waves";
        public IReadOnlyList<int> References { get; } = new[] { 2431 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            // 2120 is an explicit native self-kill, not an ordinary filler cast.
            c.SuppressSpell(2120, "security controller must reach its native WP terminal");
            if (c.Self.Wp <= 0) yield break;

            foreach (int spell in new[] { 3574, 3575, 3576 })
                foreach (var action in c.Casts(spell, new[] { c.Self.Cell }, 100,
                    "spend native WP on an available security wave"))
                    yield return action;
        }
    }

    private sealed class GelaxWaves : ISpecificAi
    {
        private static readonly HashSet<int> Thresholds = new() { 4, 7, 10, 13, 16, 18, 20 };

        public string Id => "gelax-waves";
        public IReadOnlyList<int> References { get; } = new[] { 2448 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            // The native counter belongs to the encounter, not necessarily the portal.
            var counters = c.Actors.Where(a => a.Hp > 0 && a.Has(1872)).ToArray();
            if (counters.Length != 1 || !Thresholds.Contains(counters[0].State(1872)))
            {
                c.SuppressSpell(3720, "no unique authored Gelax wave threshold");
                yield break;
            }

            foreach (var action in c.Casts(3720, new[] { c.Self.Cell }, 100,
                "produce the current native Gelax wave"))
                yield return action;
        }
    }

    private sealed class AtesLinkedSummon : ISpecificAi
    {
        public string Id => "ates-linked-summon";
        public IReadOnlyList<int> References { get; } = new[] { 2977 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            bool ownLinkAlive = c.Actors.Any(a => a.Hp > 0 && a.Reference == 2975
                && a.SummonerId == c.Self.Id);
            if (!c.Self.Has(2719) || ownLinkAlive)
            {
                c.SuppressSpell(4258, ownLinkAlive
                    ? "Ates already has its living linked summon"
                    : "Ates invulnerability gate is not active");
                yield break;
            }
            if (c.TurnCastCount(4258) > 0 || !c.Enemies.Any(a => a.Hp > 0)) yield break;

            // Spell4258 retains its native free-cell, linear, LOS and Leadership gates.
            // Prefer a reachable offering to players; never create the creature directly.
            foreach (var action in c.Casts(4258,
                c.SpecialAimCells.OrderBy(cell => c.Distance(c.Self.Cell, cell)), 100,
                "offer the linked creature for the native vulnerability mechanic",
                (_, aim) => -c.Enemies.Where(a => a.Hp > 0)
                    .Select(a => c.Distance(aim, a.Cell)).DefaultIfEmpty(0).Min()))
                yield return action;
        }
    }

    private sealed class OmebaTentacles : ISpecificAi
    {
        public string Id => "omeba-tentacles";
        public IReadOnlyList<int> References { get; } = new[] { 3022 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            // IsSpecificArea(655) names an authored anchor. The generic utility
            // projection must not retarget this spell at a player or empty ground.
            c.SuppressSpell(4189, "Omeba tentacles require an authored area655 anchor");
            var anchors = c.AreaAnchors(655).Where(cell => !c.Actors.Any(a => a.Hp > 0
                && a.Reference == 3023 && a.SummonerId == c.Self.Id && a.Cell == cell));
            foreach (var action in c.Casts(4189, anchors, 100,
                "restore a tentacle on its current native anchor"))
                yield return action;
        }
    }

    private sealed class BulbAttackerMark : ISpecificAi
    {
        public string Id => "bulb-attacker-mark";
        public IReadOnlyList<int> References { get; } = new[] { 5039, 5040 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            if (!c.Self.Has(5935)) yield break;
            var unmarked = c.Enemies.Where(a => a.Hp > 0 && !a.Has(5937)).ToArray();
            if (unmarked.Length == 0) yield break;

            // Only6761 grants5937;6762 is pure damage and6763 is a dodge debuff.
            foreach (var action in c.Casts(6761, unmarked.Select(a => a.Cell), 100,
                "give an unmarked attacker the native state5937"))
                yield return action;

            if (c.TurnHasMoved || !c.Self.Has(5936)) yield break;
            int closest = unmarked.Min(a => c.Distance(c.Self.Cell, a.Cell));
            foreach (var action in c.Moves(cell =>
            {
                if (!c.Routes.TryGetValue(cell, out var route) || route.Steps == 0
                    || !unmarked.Any(a => c.Behind(a, cell))) return double.NegativeInfinity;
                int distance = unmarked.Min(a => c.Distance(cell, a.Cell));
                // A single useful approach may also supply the movement trigger.
                // Do not walk away solely to manufacture repeated callback traffic.
                return distance <= closest ? 1d / (distance + 1) : double.NegativeInfinity;
            }, "approach behind an unmarked player for the native movement trigger", 90))
                yield return action;
        }
    }

    private sealed class BrizlonPrisoner : ISpecificAi
    {
        public string Id => "brizlon-prisoner";
        public IReadOnlyList<int> References { get; } = new[] { 4251, 4280 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            int spell = c.Self.Reference == 4251 ? 6011 : 6085;
            // This zero-AP spell is a guarded mechanic, not a generic utility
            // filler. Rejected advice and an unchanged AP total cannot retry it
            // after an actual committed cast in the same native turn.
            c.SuppressSpell(spell, "Brizlon trap requires an unprepared player and an unused native cast");
            if (!c.Self.Has(4710) || c.TurnCastCount(spell) > 0) yield break;

            var ownTraps = OwnTrapCells(c).ToHashSet();
            var targets = c.Enemies.Where(a => !a.Has(4713) && !a.Has(4712)
                && a.Raw.TryGetProperty("isCarrying", out var carrying)
                && carrying.ValueKind == System.Text.Json.JsonValueKind.False
                && !ownTraps.Contains(a.Cell));
            // Both original spells permit an occupied aim: their point315
            // creates1173, then the real area-entry/turn-start chain transforms
            // the player. The AI does not grant6007 or remove protection itself.
            foreach (var action in c.Casts(spell, targets.Select(a => a.Cell), 115,
                "offer the native prisoner transformation to an unprepared player"))
                yield return action;
        }

        private static IEnumerable<int> OwnTrapCells(SpecificContext c)
        {
            var board = c.Request.GetProperty("board");
            if (!board.TryGetProperty("mechanicAreas", out var areas)
                || areas.ValueKind != System.Text.Json.JsonValueKind.Array) yield break;
            foreach (var area in areas.EnumerateArray())
            {
                if (SpecificContext.Int(area, "reference") != 1173
                    || !area.TryGetProperty("ownerId", out var owner)
                    || owner.ValueKind != System.Text.Json.JsonValueKind.Number
                    || owner.GetInt64() != c.Self.Id) continue;
                if (area.TryGetProperty("cells", out var cells)
                    && cells.ValueKind == System.Text.Json.JsonValueKind.Array)
                    foreach (var cell in cells.EnumerateArray())
                        if (cell.ValueKind == System.Text.Json.JsonValueKind.Number)
                            yield return cell.GetInt32();
                int anchor = SpecificContext.Int(area, "cell", -1);
                if (anchor >= 0) yield return anchor;
            }
        }
    }
}
