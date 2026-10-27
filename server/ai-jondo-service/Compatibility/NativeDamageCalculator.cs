using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Maps;

namespace Jondo.Unity.World.Fights;

/// <summary>Advisory normal-cast arithmetic from Wakemu fau/eYE; never commits damage.</summary>
public static class NativeDamageCalculator
{
    // Native eYE tie order is FIRE, WATER, EARTH, AIR.
    private static readonly (ElementType Element,int Mastery,int Resistance)[] Elements =
    {
        (ElementType.Fire,21,28), (ElementType.Water,22,29),
        (ElementType.Earth,23,30), (ElementType.Air,24,31),
    };
    private static readonly (int X,int Y)[] Directions =
        {(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1)};
    public static ElementType HighestMastery(IReadOnlyDictionary<int,int> stats)
    {
        ElementType selected=ElementType.Physical;int highest=int.MinValue;bool found=false;
        foreach (var candidate in Elements)
            if (stats.TryGetValue(candidate.Mastery,out int value) && (!found || value>highest))
            {selected=candidate.Element;highest=value;found=true;}
        if (!found) throw new ArgumentException("Missing native elemental mastery");
        return selected;
    }
    public static ElementType LowestResistance(IReadOnlyDictionary<int,int> stats)
    {
        ElementType selected=ElementType.Physical;int lowest=int.MaxValue;bool found=false;
        foreach (var candidate in Elements)
            if (stats.TryGetValue(candidate.Resistance,out int value) && (!found || value<lowest))
            {selected=candidate.Element;lowest=value;found=true;}
        if (!found) throw new ArgumentException("Missing native elemental resistance");
        return selected;
    }
    private static int MasteryStat(ElementType element) => element switch
    {
        ElementType.Fire=>21,ElementType.Water=>22,ElementType.Earth=>23,ElementType.Air=>24,_=>0,
    };
    private static int ResistanceStat(ElementType element) => element switch
    {
        ElementType.Fire=>28,ElementType.Water=>29,ElementType.Earth=>30,ElementType.Air=>31,_=>0,
    };
    public static double ResistanceMultiplier(int points)
    {
        double value=Math.Pow((double)0.8f,(float)((float)points/100f));
        return Math.Max(0.1,Math.Ceiling(value*100.0)/100.0);
    }
    public static string Facing(Fighter source,Fighter target)
    {
        if (target.NativeDirection<0 || target.NativeDirection>7) return "FRONT";
        var a=MapGeometry.Context.Cells[source.CellId];
        var b=MapGeometry.Context.Cells[target.CellId];
        float dx=unchecked(b.X-a.X),dy=unchecked(b.Y-a.Y);
        if (dx==0 && dy==0) return "FRONT";
        float inverse=1f/(float)Math.Sqrt((float)(dx*dx+dy*dy));
        dx*=inverse; dy*=inverse;
        var direction=Directions[target.NativeDirection];
        float dot=(float)(dx*direction.X+dy*direction.Y);
        return (double)dot<=-0.7 ? "FRONT" : (double)dot>=0.72 ? "BACK" : "SIDE";
    }
    public static bool TryEstimate(double baseDamage,ElementType element,Fighter source,Fighter target,
        SpellEffect? row,out double damage)
    {
        damage=0;
        if (source.NativeStats==null || target.NativeStats==null) return false;
        if (baseDamage<0) throw new ArgumentException("Negative native base damage");
        var offense=source.NativeStats;var defense=target.NativeStats;
        int Get(IReadOnlyDictionary<int,int> stats,int id)=>stats.TryGetValue(id,out int value)?value:0;
        int mask=row?.NativeCoefficientMask ?? 3;
        if (mask is <0 or >3) throw new ArgumentException("Unknown native damage coefficient mask");
        ElementType attack=element is ElementType.Light or ElementType.Stasis ? HighestMastery(offense) : element;
        ElementType defend=element==ElementType.Stasis ? LowestResistance(defense) : attack;
        string location=element==ElementType.Physical || row?.NativeLocalization!=true ? "FRONT" : Facing(source,target);
        var flags=row?.NativeDamageFlags ?? Array.Empty<int>();
        var a=MapGeometry.Context.Cells[source.CellId];var b=MapGeometry.Context.Cells[target.CellId];
        int radius=source.NativePhysicalRadius+target.NativePhysicalRadius;
        int distance=Math.Max(0,Math.Abs(a.X-b.X)-radius)+Math.Max(0,Math.Abs(a.Y-b.Y)-radius);
        bool forced=flags.Contains(23)||flags.Contains(24);
        bool melee=flags.Contains(23)||(!forced && distance<=2);
        bool ranged=flags.Contains(24)||(!forced && distance>2);
        int mastery=0,resistance=0;
        if ((mask&1)!=0)
        {
            mastery=Get(offense,20)+Get(offense,102);
            if (location=="BACK") mastery+=Get(offense,16);
            if (flags.Contains(22)) mastery+=Get(offense,105);
            if (flags.Contains(4)) mastery+=Get(offense,106);
            if (melee) mastery+=Get(offense,103);
            if (ranged) mastery+=Get(offense,104);
            float maximum=source.MaxHP+source.NativeVirtualHpMax;
            if (maximum>0 && (float)((float)((source.CurrentHP+(source.NativeForecastVirtualHp??Get(offense,92)))/maximum)*100f)<50f)
                mastery+=Get(offense,107);
            int selected=MasteryStat(attack);
            if (selected!=0) mastery+=Math.Min(50000,Get(offense,selected));
        }
        if ((mask&2)!=0)
        {
            resistance=Get(defense,27);
            int selected=ResistanceStat(defend);
            if (selected!=0) resistance+=Get(defense,selected);
            if (location=="BACK") resistance+=Get(defense,17);
        }
        float factor=(float)(1f+(float)((float)mastery/100f));
        factor=(float)(factor*ResistanceMultiplier(resistance));
        float value=(float)((float)baseDamage*factor);
        value=(float)(value*(float)((100+(location=="BACK"?25:location=="SIDE"?10:0))/100f));
        // These projected rows belong to a selected spell container11: direct,
        // noncritical native casting, as ordinary_container_type declares.
        int final=(mask&1)!=0 ? Math.Max(-50,Get(offense,48)) : 0;
        int finalResistance=(mask&2)!=0 ? Get(defense,49) : 0;
        value=(float)(value*(float)((100+final-finalResistance)/100f));
        // Keep the expected fractional result; World owns stochastic rounding,
        // block, armor, reaction, and encounter-specific damage policies.
        damage=Math.Max(1,value);
        return true;
    }
}
