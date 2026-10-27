namespace Wakfu.Jondo;

internal static class SupremeMechanicAis
{
    public static IEnumerable<ISpecificAi> Create()
    {
        yield return new MoonAi();
        yield return new TalKashaAi();
        yield return new NoxAi();
    }

    private sealed class MoonAi : ISpecificAi
    {
        public string Id => "ful-moon-native-mechanics";
        public IReadOnlyList<int> References => new[] { 3870 };
        private static readonly HashSet<int> Totems = new() { 3993, 3995, 3996, 3997 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            if (!c.Self.Has(4214)) yield break;
            var props = c.Actors.Where(a => Totems.Contains(a.Reference) && a.Hp > 0 && a.Has(4226)
                && (a.SummonerId == c.Self.Id || (a.SummonerId == 0 && a.Team == c.Self.Team))).ToArray();
            // A single native hammer is demonstrated on a full-health prop.
            // The players finish its threshold; repeating it can destroy it.
            var untouched = props.Where(a => !a.Has(4227) && a.Hp == a.MaxHp && a.Hp > 1).ToArray();
            if (untouched.Length > 0)
            {
                foreach (var action in c.Casts(5693, untouched.Select(a => a.Cell), 130,
                    "Assist an untouched Moon totem with its native hammer"))
                    yield return action;
                yield break;
            }

            if (!Totems.All(reference => props.Any(a => a.Reference == reference && a.Has(4227)))
                || !c.Enemies.Any(a => a.Hp > 0 && a.State(4211) >= 5))
                yield break;
            var borders = c.AreaCells(1085).ToHashSet();
            var glyphs = c.AreaCells(1086).ToHashSet();
            if (c.Self.State(4212) < 5)
            {
                // The original border awards boss moons only to team zero.
                if (c.Self.Team != 0 || borders.Count == 0) yield break;
                if (borders.Contains(c.Self.Cell))
                {
                    // Leaving then re-entering a real border earns the next
                    // grade. A snapshot after each paid action stops at five.
                    foreach (var action in c.Moves(cell =>
                        !borders.Contains(cell) && c.Distance(c.Self.Cell, cell) == 1 ? 100 : double.NegativeInfinity,
                        "Leave Moon's border before earning its next moon grade", 120))
                        yield return action;
                }
                else
                {
                    var distance = borders.Min(cell => c.Distance(c.Self.Cell, cell));
                    foreach (var action in c.Moves(cell =>
                    {
                        var remaining = borders.Min(border => c.Distance(cell, border));
                        return remaining < distance ? 100 - remaining : double.NegativeInfinity;
                    }, "Approach the original Moon border to earn moon grades", 120))
                        yield return action;
                }
                yield break;
            }

            if (glyphs.Count == 0 || glyphs.Contains(c.Self.Cell)) yield break;
            var glyphDistance = glyphs.Min(cell => c.Distance(c.Self.Cell, cell));
            foreach (var action in c.Moves(cell =>
            {
                var remaining = glyphs.Min(glyph => c.Distance(cell, glyph));
                return remaining < glyphDistance ? 100 - remaining : double.NegativeInfinity;
            }, "Return Moon to its original glyph after preparing the phase", 125))
                yield return action;
        }
    }

    private sealed class TalKashaAi : ISpecificAi
    {
        public string Id => "tal-kasha-native-wakfu";
        public IReadOnlyList<int> References => new[] { 5500 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            if (!c.Self.Has(8231) || c.Self.Wp >= 20 || c.TurnHasMoved) yield break;
            var enemies = c.Enemies.Where(a => a.Hp > 0).ToArray();
            if (enemies.Length == 0) yield break;
            // Genuine committed movement earns native WP and can trigger
            // 8147/8148. The planner never casts those callbacks itself.
            foreach (var action in c.Moves(cell =>
            {
                if (c.Distance(c.Self.Cell, cell) != 1) return double.NegativeInfinity;
                return 100 - enemies.Min(a => c.Distance(cell, a.Cell));
            }, "Earn Tal Kasha's native Wakfu with one useful paid step", 110))
                yield return action;
        }
    }

    private sealed class NoxAi : ISpecificAi
    {
        public string Id => "nox-native-calendar";
        public IReadOnlyList<int> References => new[] { 5664 };

        public IEnumerable<SpecificAction> Propose(SpecificContext c)
        {
            // The published v4 calendar drives 401544/401749 at owned turn
            // boundaries. Walking to force 8978/8979 would replay the wrong
            // trigger. Weapon 8981's triggered spell 8432 needs a positive
            // native hit/area preview before it justifies a movement override.
            yield break;
        }
    }
}
