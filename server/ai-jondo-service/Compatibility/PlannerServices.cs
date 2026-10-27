using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Jondo.Unity.Server.Managers;

// These adapters consume normalized advisory semantics, never Wakfu effect IDs.
// World remains the authority for eligibility, effects and action publication.
public static class SpellEffects
{
    private static readonly AsyncLocal<Dictionary<(int,int), IReadOnlyList<SpellEffect>>?> Rows = new();
    public static void Bind(Dictionary<(int,int), IReadOnlyList<SpellEffect>> rows) => Rows.Value = rows;
    public static IDisposable BeginScope(Dictionary<(int,int), IReadOnlyList<SpellEffect>> rows)
    {
        var previous=Rows.Value;
        Rows.Value=rows;
        return new Restore(()=>Rows.Value=previous);
    }
    public static IReadOnlyList<SpellEffect> De(int id, int grade) =>
        Rows.Value != null && Rows.Value.TryGetValue((id,grade),out var rows) ? rows : Array.Empty<SpellEffect>();
    private sealed class Restore(Action restore) : IDisposable
    {
        private bool disposed;
        public void Dispose() { if (!disposed) {disposed=true;restore();} }
    }
}
public static class DatabaseManager
{
    public static (int Characteristic,int Sign) EffectMeta(int effect) => effect switch
    {
        111 => (1,1), 101 => (1,-1), 128 => (23,1), 127 => (23,-1),
        _ => (0,0),
    };
}
public static class SpellCriteria
{
    public static bool Allows(Fighter who,int spell,int grade) => true;
}
public static class SpellStates
{
    public sealed class State
    {
        public bool Invulnerable {get;init;}
        public bool InvulnerableMelee {get;init;}
        public bool InvulnerableRange {get;init;}
        public bool CantDealDamage {get;init;}
        public bool CantBeMoved {get;init;}
        public bool CantBePushed {get;init;}
        public bool CantSwitchPosition {get;init;}
        public bool Incurable {get;init;}
        public bool PreventsSpellCast {get;init;}
        public bool PreventsFight {get;init;}
        public bool CantTackle {get;init;}
        public bool CantBeTackled {get;init;}
        public bool CantUsePortals {get;init;}
    }
    public static State? Of(int id) => null;
    public static bool ShieldsFromBlow(Fighter who,int distance) => false;
    public static bool KeepsFromDealingDamage(Fighter who) => false;
    public static bool PinsInPlace(Fighter who) => false;
    public static bool KeepsOutOfPortals(Fighter who) => false;
}
public sealed class Summon
{
    public int Vida {get;init;}
    public int HechizoPropio {get;init;}
    public int GradoDelHechizoPropio {get;init;}
    public bool VidaFija {get;init;}
}
public static class Summons
{
    public static Summon? De(int id,int grade) => throw Unsupported("summoning");
    public static int VidaDelInvocado(int life,int level,bool fixedLife) => throw Unsupported("summoning");
    public static void Characteristics(Fighter summon,Summon recipe,Fighter caster) => throw Unsupported("summoning");
    private static NotSupportedException Unsupported(string name) => new($"Unprojected native semantic: {name}");
}
public static class Bombs
{
    public static bool Is(int id) => false;
    public static int Explosion(int id) => throw new NotSupportedException("Unprojected bomb explosion");
}
public sealed class BombWall
{
    public int Template {get;init;}
    public List<Fighter> Bombs {get;init;} = new();
    public HashSet<int> Cells {get;init;} = new();
}
public static class BombWalls
{
    public const int KabumState = -1, MaxGap = 0, MinGap = 0;
    public static readonly Dictionary<int,int> WallSpell = new();
    public static List<BombWall> Of(IReadOnlyList<Fighter> fighters,Fighter caster) => new();
    public static BombWall? Covering(IReadOnlyList<Fighter> fighters,Fighter caster,int cell) => null;
    public static IEnumerable<Fighter> LasDelMismoMuro(IReadOnlyList<Fighter> fighters,Fighter bomb) => Array.Empty<Fighter>();
}
public static class Combo
{
    public static int PercentOf(Fighter fighter) => 0;
}
