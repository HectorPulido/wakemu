using Jondo.Unity.World.Combat;
using Jondo.Unity.World.Maps;
using System.Runtime.CompilerServices;
using Jondo.Unity.World.Fights;

namespace Jondo.Unity.Server.Managers;

/// <summary>Translate explicitly named native advisory semantics to planner symbols.</summary>
public static class SemanticRows
{
    private sealed record Offsets(IReadOnlyList<(int Dx,int Dy)> Cells);
    private static readonly ConditionalWeakTable<SpellEffect,Offsets> Zones = new();
    private static readonly ConditionalWeakTable<SpellEffect,NativeDirectionalArea> Directional = new();
    private sealed record AreaPolicy(bool CenterOnCaster,bool UseTargetRadius);
    private static readonly ConditionalWeakTable<SpellEffect,AreaPolicy> AreaPolicies = new();
    internal static SpellEffect WithDirectionalArea(SpellEffect row,IReadOnlyList<(int Dx,int Dy)> raw,bool useTargetRadius,bool centerOnCaster=false)
    { Directional.Add(row,new NativeDirectionalArea(raw,useTargetRadius,centerOnCaster));return row; }
    internal static void WithNativeAreaPolicy(SpellEffect row,bool centerOnCaster,bool useTargetRadius)
        => AreaPolicies.Add(row,new AreaPolicy(centerOnCaster,useTargetRadius));
    internal static bool CenterOnCaster(SpellEffect row)
        => AreaPolicies.TryGetValue(row,out var policy)?policy.CenterOnCaster:DirectionalArea(row)?.CenterOnCaster??false;
    internal static bool HasNativeAreaPolicy(SpellEffect row)=>AreaPolicies.TryGetValue(row,out _);
    internal static bool TryNativeContains(SpellEffect row,Fighter caster,int from,int aim,Fighter target,out bool contains)
    {
        var native=DirectionalArea(row);
        bool hasPolicy=AreaPolicies.TryGetValue(row,out var policy);
        contains=false;
        if(native==null&&!hasPolicy)return false;
        bool onCaster=hasPolicy?policy!.CenterOnCaster:native!.CenterOnCaster;
        bool useRadius=hasPolicy?policy!.UseTargetRadius:native!.UseTargetRadius;
        var origin=MapGeometry.Context.Cells[onCaster?from:aim];
        var reference=MapGeometry.Context.Cells[onCaster?aim:from];
        var point=MapGeometry.Context.Cells[target==caster?from:target.CellId];
        int radius=useRadius?target.NativePhysicalRadius:0;
        if(native!=null)contains=native.Contains(origin,reference,caster.NativeDirection,point,radius);
        else if(Zones.TryGetValue(row,out var offsets))
        {
            if(radius is <-128 or >127)return true;
            radius=Math.Max(0,radius);
            long x=(long)point.X-origin.X,y=(long)point.Y-origin.Y;
            foreach(var offset in offsets.Cells)
                if(Math.Abs(x-offset.Dx)<=radius&&Math.Abs(y-offset.Dy)<=radius){contains=true;break;}
        }
        return true;
    }
    internal static NativeDirectionalArea? DirectionalArea(SpellEffect row)
        => Directional.TryGetValue(row,out var area)?area:null;
    public static SpellEffect WithOffsets(SpellEffect row,IReadOnlyList<(int Dx,int Dy)> offsets)
    {
        Zones.Add(row,new Offsets(Array.AsReadOnly(offsets.ToArray())));
        return row;
    }
    internal static IReadOnlyList<(int Dx,int Dy)>? NativeOffsets(SpellEffect row)
        => Zones.TryGetValue(row,out var offsets) ? offsets.Cells : null;
    internal static bool TryProjectedZone(SpellEffect row,int aim,out List<int> cells)
    {
        cells=new();
        if (!Zones.TryGetValue(row,out var offsets)) return false;
        if (!MapGeometry.IsValid(aim)) return true;
        var origin=MapGeometry.Context.Cells[aim];
        foreach (var (dx,dy) in offsets.Cells)
        {
            int cell=MapGeometry.PointToCell(origin.X+dx,origin.Y+dy,origin.Z);
            if (cell>=0 && !cells.Contains(cell)) cells.Add(cell);
        }
        return true;
    }
    public static ElementType NativeElementOf(SpellEffect row, ElementType fallback)
        => row.NativeElement ?? fallback;

    public static SpellEffect Create(string kind,int amount,string target,
        ElementType element=ElementType.Physical,int zoneRadius=0,int stateId=0,
        IReadOnlyList<int>? fixedCells=null, int nativeCoefficientMask=3,
        IReadOnlyList<int>? nativeDamageFlags=null, bool nativeLocalization=false)
    {
        if (amount<0 || zoneRadius<0) throw new ArgumentException("Negative semantic amount/radius");
        string mask=target switch
        {
            "enemy"=>"A", "ally"=>"a", "self"=>"C",
            _=>throw new NotSupportedException("Native target condition has not been projected"),
        };
        int symbol=kind switch
        {
            "damage"=>element switch
            {
                ElementType.Water=>96, ElementType.Earth=>97, ElementType.Air=>98,
                ElementType.Fire=>99,
                ElementType.Physical or ElementType.Light or ElementType.Stasis=>100,
                _=>throw new ArgumentException("Unknown semantic element"),
            },
            "heal"=>EffectSupport.FireHeal,
            "gain_ap"=>111, "remove_ap"=>101,
            "gain_mp"=>128, "remove_mp"=>127,
            "add_state"=>EffectSupport.AddState,
            "remove_state"=>EffectSupport.RemoveState,
            _=>throw new NotSupportedException("Native effect semantic has not been projected: "+kind),
        };
        if (kind is "add_state" or "remove_state" && stateId<=0)
            throw new ArgumentException("A semantic state needs its native marker identity");
        return new SpellEffect
        {
            EffectId=symbol, NativeElement=kind == "damage" ? element : null,
            NativeCoefficientMask=nativeCoefficientMask,
            NativeDamageFlags=nativeDamageFlags ?? Array.Empty<int>(), NativeLocalization=nativeLocalization,
            DiceNum=amount, DiceSide=amount, Value=stateId,
            Element=(int)element, TargetMask=mask, Forma=fixedCells!=null ? ';' : zoneRadius>0 ? 'C':'P',
            Tamano=zoneRadius, CeldasFijas=fixedCells?.ToList() ?? new(), Triggers="I",
        };
    }
}
