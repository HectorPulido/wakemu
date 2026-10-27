using System.Runtime.CompilerServices;
using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Maps;

namespace Jondo.Unity.World.Fights;

/// <summary>A private advisory distribution; never samples authoritative RNG.</summary>
internal sealed class NativeAmountForecast
{
    internal readonly record struct Outcome(double Amount,double Probability);
    internal IReadOnlyList<Outcome> Outcomes { get; }
    internal NativeAmountForecast(IEnumerable<Outcome> outcomes)
        => Outcomes=outcomes.Where(x=>x.Probability>0).GroupBy(x=>x.Amount)
            .Select(g=>new Outcome(g.Key,g.Sum(x=>x.Probability))).ToArray();
    internal double Mean=>Outcomes.Sum(x=>x.Amount*x.Probability);
    internal double Minimum=>Outcomes.Count==0?0:Outcomes.Min(x=>x.Amount);
    internal double ProbabilityAtLeast(double amount)=>Outcomes.Where(x=>x.Amount>=amount).Sum(x=>x.Probability);
    internal NativeAmountForecast Map(Func<double,double> value)
        => new(Outcomes.Select(x=>new Outcome(value(x.Amount),x.Probability)));
    internal static NativeAmountForecast Exact(double value)=>new(new[]{new Outcome(value,1)});
    internal static NativeAmountForecast Rounded(float value,bool minimumOne)
    {
        if(!float.IsFinite(value))throw new ArgumentException("Nonfinite native amount");
        double lower=Math.Floor(value),fraction=value-lower;
        double Clamp(double number)=>minimumOne?Math.Max(1,number):number;
        return new(new[]{new Outcome(Clamp(lower),1-fraction),new Outcome(Clamp(lower+1),fraction)});
    }
}

/// <summary>Stateless evaluated eXt parameter metadata, resolved against live simulation HP1.</summary>
internal static class NativeEffectAmounts
{
    internal sealed record Descriptor(int Kind,int Value,int? HealingElement,double Probability,bool EligibilityKnown,bool SourceBindingKnown,bool TargetNotCarried);
    private static readonly ConditionalWeakTable<SpellEffect,Descriptor> Metadata=new();
    internal static Descriptor? ReadDescriptor(JsonElement row)
    {
        bool hasBase=row.TryGetProperty("nativeBase",out var basis),hasHeal=row.TryGetProperty("nativeHealing",out var healing);
        if(!hasBase&&!hasHeal)return null;
        string kind=row.GetProperty("kind").GetString()??"";
        if(!hasBase||basis.GetProperty("version").GetInt32()!=1||kind is not ("damage" or "heal")
            ||!basis.GetProperty("kind").TryGetInt32(out int mode)||mode is <0 or >6
            ||!basis.GetProperty("value").TryGetInt32(out int value)||hasHeal!=(kind=="heal"))
            throw new ArgumentException("Invalid native amount descriptor");
        // An unchanged classic damage row may carry an audited base hint.
        // Its existing numeric value and geometry remain the legacy contract;
        // it is not upgraded into a new typed health forecast implicitly.
        if(kind=="damage"&&mode==0&&!row.TryGetProperty("nativeHealthGeometry",out _)
            &&row.TryGetProperty("amount",out var oldAmount)&&oldAmount.TryGetInt32(out int constant)
            &&constant==value&&constant>=0)return null;
        int? element=null;
        if(hasHeal)
        {
            if(healing.GetProperty("version").GetInt32()!=1||!healing.GetProperty("element").TryGetInt32(out int nativeElement)
                ||nativeElement is <1 or >6)throw new ArgumentException("Unknown native healing descriptor");
            element=nativeElement;
        }
        if(!row.TryGetProperty("probability",out var probability)||!probability.TryGetDouble(out double percent)
            ||!double.IsFinite(percent))throw new ArgumentException("Unknown native health application probability");
        bool eligible=row.TryGetProperty("conditional",out var conditional)&&conditional.ValueKind==JsonValueKind.False;
        bool binding=basis.TryGetProperty("sourceBindingKnown",out var known)&&known.ValueKind==JsonValueKind.True;
        bool notCarried=false;
        if(row.TryGetProperty("nativeHealthEligibility",out var guard))
        {
            if(guard.GetProperty("version").GetInt32()!=1||!guard.TryGetProperty("targetNotCarried",out var predicate)
                ||predicate.ValueKind!=JsonValueKind.True||guard.EnumerateObject().Count()!=2)
                throw new ArgumentException("Unknown native health eligibility guard");
            notCarried=true;
        }
        return new Descriptor(mode,value,element,Math.Clamp((float)percent/100.0,0,1),eligible,binding,notCarried);
    }
    internal static JsonElement Geometry(JsonElement row,bool support=false)
    {
        var descriptor=ReadDescriptor(row);
        if(descriptor==null)
        {
            if(row.TryGetProperty("nativeHealthGeometry",out _))throw new ArgumentException("Health geometry lacks validated amount metadata");
            return row;
        }
        // Old peers must observe a genuinely empty area, including for global
        // or directional effects. Never expose their recognized geometry there.
        if(!row.TryGetProperty("fixedCells",out var empty)||empty.ValueKind!=JsonValueKind.Array||empty.GetArrayLength()!=0
            ||!row.TryGetProperty(support?"inArea":"nativeInArea",out var closed)||closed.ValueKind!=JsonValueKind.True
            ||row.TryGetProperty("nativeDirectionalArea",out _)||row.TryGetProperty("nativeAreaCenterOnCaster",out _)
            ||row.TryGetProperty("nativeAreaUseTargetRadius",out _)
            ||!row.TryGetProperty("nativeHealthGeometry",out var geometry)||geometry.GetProperty("version").GetInt32()!=1
            ||!geometry.TryGetProperty("fixedCells",out var offsets)||offsets.ValueKind!=JsonValueKind.Array
            ||!geometry.TryGetProperty("nativeInArea",out var inArea)||inArea.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            ||!geometry.TryGetProperty("nativeAreaCenterOnCaster",out var center)||center.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            ||!geometry.TryGetProperty("nativeAreaUseTargetRadius",out var radius)||radius.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            ||center.GetBoolean()==radius.GetBoolean())
            throw new ArgumentException("Invalid closed native health geometry envelope");
        return geometry;
    }
    internal static void Bind(SpellEffect row,int kind,int value,int? healingElement=null,double probability=1,bool eligibilityKnown=true,bool sourceBindingKnown=true,bool targetNotCarried=false)
    {
        if(kind is <0 or >6||healingElement is <1 or >6)throw new ArgumentException("Unknown native amount descriptor");
        if(!double.IsFinite(probability)||probability is <0 or >1)throw new ArgumentException("Unknown native health probability");
        Metadata.Add(row,new Descriptor(kind,value,healingElement,probability,eligibilityKnown,sourceBindingKnown,targetNotCarried));
    }
    internal static bool Has(SpellEffect row)=>Metadata.TryGetValue(row,out _);
    internal static bool IsDamage(SpellEffect row)=>Metadata.TryGetValue(row,out var data)&&data.HealingElement==null;
    internal static bool IsHealing(SpellEffect row)=>Metadata.TryGetValue(row,out var data)&&data.HealingElement!=null;
    internal static NativeAmountForecast Base(int kind,int value,Fighter source,Fighter target,bool allowSigned=false)
    {
        if(kind is <0 or >6)throw new ArgumentException("Unknown native HP base kind");
        if(kind==0)
        {
            if(value<0&&!allowSigned)throw new ArgumentException("Negative native base");
            return NativeAmountForecast.Exact(value);
        }
        var actor=kind<=3?source:target;
        if(actor.CurrentHP<0||actor.MaxHP<0||actor.CurrentHP>actor.MaxHP)
            throw new ArgumentException("Missing effective HP1 context");
        int hp=((kind-1)%3) switch {0=>actor.MaxHP,1=>actor.CurrentHP,_=>actor.MaxHP-actor.CurrentHP};
        int product=unchecked(hp*value);
        float amount=(float)((float)product/100f);
        var result=NativeAmountForecast.Rounded(amount,false);
        if(!allowSigned&&result.Minimum<0)throw new ArgumentException("Unsupported negative native percent result");
        return result;
    }
    internal static NativeAmountForecast? Estimate(SpellEffect row,Fighter source,Fighter target,double bonus=0)
    {
        if(!Metadata.TryGetValue(row,out var descriptor)||!descriptor.EligibilityKnown&&!descriptor.TargetNotCarried)return null;
        if(descriptor.TargetNotCarried&&target.NativeIsCarried!=false)return null;
        if(!descriptor.SourceBindingKnown)return null;
        try
        {
            var bases=Base(descriptor.Kind,descriptor.Value,source,target,descriptor.HealingElement!=null);
            var outcomes=new List<NativeAmountForecast.Outcome>();
            foreach(var item in bases.Outcomes)
            {
                NativeAmountForecast next;
                if(descriptor.HealingElement is int element)
                {
                    if(source.NativeStats==null||target.NativeStats==null||!target.NativeStats.ContainsKey(32)||target.NativeUndead==null
                        ||target.NativeHealingForecastUncertain||target.NativeUndead==true&&!row.NativeDamageFlags.Contains(33))return null;
                    next=NativeHealingCalculator.Estimate((int)item.Amount,element,source,target,row);
                }
                else
                {
                    var damageElement=SemanticRows.NativeElementOf(row,(ElementType)row.Element);
                    if(!NativeDamageCalculator.TryEstimate(item.Amount+bonus,damageElement,source,target,row,out double raw))return null;
                    next=NativeAmountForecast.Rounded((float)raw,true);
                    if(!row.NativeDamageFlags.Contains(2))
                    {
                        if(target.NativeStats==null||!target.NativeStats.TryGetValue(87,out int block))return null;
                        double probability=Math.Clamp(block,0,100)/100.0;
                        next=new NativeAmountForecast(next.Outcomes.SelectMany(x=>new[]{
                            new NativeAmountForecast.Outcome(x.Amount,x.Probability*(1-probability)),
                            new NativeAmountForecast.Outcome(Math.Ceiling((float)((float)x.Amount*0.8f)),x.Probability*probability)}));
                    }
                }
                outcomes.AddRange(next.Outcomes.Select(x=>new NativeAmountForecast.Outcome(x.Amount,x.Probability*item.Probability)));
            }
            if(outcomes.Any(x=>x.Amount<0||x.Amount>int.MaxValue))return null;
            return new NativeAmountForecast(outcomes.Select(x=>new NativeAmountForecast.Outcome(x.Amount,x.Probability*descriptor.Probability))
                .Append(new NativeAmountForecast.Outcome(0,1-descriptor.Probability)));
        }
        catch(ArgumentException){return null;}
    }
}

/// <summary>Native PA1 consumption with explicit frozen/minimum/raw authority.</summary>
internal sealed record NativePoolAuthority(int Minimum,int Maximum,bool Frozen);
internal static class NativeHpForecast
{
    internal readonly record struct Shift(int Current,int? Raw);
    internal static bool Known(Fighter target)=>target.NativeHpMinimum is int minimum
        &&target.NativeHpFrozen!=null&&minimum>=0&&minimum<=target.CurrentHP&&target.CurrentHP<=target.MaxHP
        &&(target.NativeHpRawMode=="bounded"&&target.NativeHpRawCurrent==null
            ||target.NativeHpRawMode is "fresh" or "copied"&&target.NativeHpRawCurrent is int raw
                &&raw>=0&&Math.Clamp(raw,minimum,target.MaxHP)==target.CurrentHP);
    internal static Shift Apply(Fighter target,int amount,bool subtract)
    {
        if(!Known(target)||amount<0||target.NativeHpFrozen==true)return new(target.CurrentHP,target.NativeHpRawCurrent);
        int minimum=target.NativeHpMinimum!.Value;
        if(target.NativeHpRawMode=="bounded")
            return new((int)Math.Clamp(subtract?(long)target.CurrentHP-amount:(long)target.CurrentHP+amount,minimum,target.MaxHP),null);
        int raw=target.NativeHpRawCurrent!.Value;
        int requested=subtract?(amount>target.CurrentHP-minimum?minimum:unchecked(raw-amount))
            :(amount>target.MaxHP-target.CurrentHP?target.MaxHP:unchecked(raw+amount));
        int after=Math.Max(minimum,requested); // Original HP hard maximum is Int32.MaxValue.
        return new(Math.Clamp(after,minimum,target.MaxHP),after);
    }
    internal static bool CanDie(Fighter target)=>Known(target)&&target.NativeHpMinimum==0&&target.NativeHpFrozen==false;
    internal static int Barrier(Fighter source)=>Math.Max(0,source.NativeForecastBarrier??source.NativeStats?.GetValueOrDefault(100)??0);
    internal static int Armor(Fighter target)=>Math.Max(0,target.NativeForecastArmor
        ??(target.NativeStats!=null&&target.NativeStats.TryGetValue(97,out int armor)?armor:target.PuntosDeEscudo));
    internal static int Virtual(Fighter target)=>Math.Max(0,target.NativeForecastVirtualHp??target.NativeStats?.GetValueOrDefault(92)??0);
    internal readonly record struct Absorption(int Remaining,int Barrier,int Armor,int Virtual);
    private static int PoolAfter(Fighter actor,int current,int requested,NativePoolAuthority? authority)
    {
        if(authority==null||authority.Frozen
            ||current<authority.Minimum||current>authority.Maximum)return current;
        // Damage consumption SETS the computed remaining97/92/100 value,
        // including set_copied_current. Unlike HP/virtual healing SHIFT, this
        // does not subtract from an unknown copied raw operand.
        return Math.Max(authority.Minimum,current-requested);
    }
    internal static Absorption Absorb(int amount,Fighter source,Fighter target,SpellEffect row)
    {
        int barrier=Barrier(source),armor=Armor(target),virtualHp=Virtual(target),remaining=Math.Max(0,amount);
        if(!row.NativeDamageFlags.Contains(28))
        {
            int taken=source.NativeBarrierAuthority?.Frozen==true?0:Math.Min(barrier,remaining/2);
            barrier=PoolAfter(source,barrier,taken,source.NativeBarrierAuthority);remaining-=taken;
            taken=target.NativeArmorAuthority?.Frozen==true?0:Math.Min(armor,remaining);
            armor=PoolAfter(target,armor,taken,target.NativeArmorAuthority);remaining-=taken;
        }
        bool frozen=target.NativeVirtualHpAuthority?.Frozen??target.NativeVirtualHpFrozen??false;
        int absorbed=frozen?0:Math.Min(virtualHp,remaining);
        virtualHp=PoolAfter(target,virtualHp,absorbed,target.NativeVirtualHpAuthority);remaining-=absorbed;
        return new(remaining,barrier,armor,virtualHp);
    }
    internal static NativeAmountForecast DamageLoss(NativeAmountForecast amount,Fighter source,Fighter target,SpellEffect row)
        => amount.Map(value=>target.CurrentHP-Apply(target,Absorb((int)value,source,target,row).Remaining,true).Current);
    internal static double DamagePreparation(NativeAmountForecast amount,Fighter source,Fighter target,SpellEffect row)
    {
        if(!Known(target))return 0;
        double total=0;
        foreach(var outcome in amount.Outcomes)
        {
            var consumed=Absorb((int)outcome.Amount,source,target,row);
            var shifted=Apply(target,consumed.Remaining,true);
            int hpLoss=target.CurrentHP-shifted.Current;
            int rawLoss=target.NativeHpRawCurrent is int raw&&shifted.Raw is int after?Math.Max(0,raw-after):hpLoss;
            // Armor/virtual depletion is useful preparation, not a defeat.
            // Raw over-maximum HP is a smaller, proven preparation benefit.
            total+=outcome.Probability*(Armor(target)-consumed.Armor+Virtual(target)-consumed.Virtual
                +Math.Min(target.CurrentHP,Math.Max(0,rawLoss-hpLoss))*0.1);
        }
        return total;
    }
    internal readonly record struct Healing(Shift Hp,int Virtual,int Applied,bool ExactResistanceInput);
    internal static Healing ConsumeHealing(Fighter target,int amount)
    {
        var hp=Apply(target,amount,false);int currentVirtual=Virtual(target);
        if(!Known(target))return new(hp,currentVirtual,0,false);
        int hpActual=target.NativeHpRawMode=="bounded"?hp.Current-target.CurrentHP
            :unchecked(hp.Raw!.Value-target.NativeHpRawCurrent!.Value);
        long remaining=(long)amount-hpActual;
        int capacity=Math.Max(0,target.NativeVirtualHpMax-currentVirtual);
        bool? frozen=target.NativeVirtualHpAuthority?.Frozen??target.NativeVirtualHpFrozen;
        bool bounded=target.NativeHpRawMode is "bounded" or "fresh"
            &&target.NativeVirtualHpAuthority is {} authority&&currentVirtual>=authority.Minimum
            &&currentVirtual<=authority.Maximum&&authority.Maximum==target.NativeVirtualHpMax;
        bool ordinary=target.NativeHpRawMode is "bounded" or "fresh";
        // Even a full copied virtual pool may collapse an over-maximum raw
        // operand on positive SHIFT. Zero capacity alone does not prove its
        // signed applied delta, which feeds healing resistance afterward.
        bool exact=frozen==true||remaining==0||ordinary&&capacity==0||frozen==false&&bounded;
        int restored=frozen==false&&bounded?(int)Math.Min(Math.Max(0,remaining),capacity):0;
        return new(hp,currentVirtual+restored,unchecked(hpActual+restored),exact);
    }
    internal static NativeAmountForecast HealingGain(NativeAmountForecast amount,Fighter target)
        => amount.Map(value=>{var restored=ConsumeHealing(target,(int)value);
            return restored.Hp.Current-target.CurrentHP+restored.Virtual-Virtual(target);});
}

/// <summary>Native fat/eXs healing. Element1 is non-elemental;6 is Light, never damage Stasis.</summary>
internal static class NativeHealingCalculator
{
    internal static NativeAmountForecast Amount(int basis,int element,IReadOnlyDictionary<int,int> source,
        IReadOnlyDictionary<int,int> target,int mask,bool singleTarget,bool area,bool melee,bool ranged,bool berserk,int? resistanceOverride=null)
    {
        if(element is <1 or >6||mask is <0 or >3)throw new ArgumentException("Unknown native healing mode");
        int Get(IReadOnlyDictionary<int,int> stats,int key)=>stats.TryGetValue(key,out int value)?value:0;
        int mastery=0,final=0;
        if((mask&1)!=0)
        {
            mastery=Get(source,20)+Get(source,18)+Get(source,102)
                +(singleTarget?Get(source,105):0)+(area?Get(source,106):0)
                +(melee?Get(source,103):0)+(ranged?Get(source,104):0)+(berserk?Get(source,107):0);
            int elemental=element switch {2=>21,3=>23,4=>22,5=>24,_=>0};
            if(element==6)elemental=NativeDamageCalculator.HighestMastery(source) switch
                {ElementType.Fire=>21,ElementType.Water=>22,ElementType.Earth=>23,ElementType.Air=>24,_=>0};
            if(elemental!=0)mastery+=Math.Min(50000,Get(source,elemental));
            final=Get(source,114);
        }
        float value=(float)((float)basis*(float)(1f+(float)((float)mastery/100f)));
        value=(float)((double)(float)(value*(float)(100+final))/100.0);
        int resistance=(mask&2)!=0?(int)(float)((float)(resistanceOverride??Get(target,32))/10f):0;
        float resisted=(float)((float)(value*(float)resistance)/100f);
        value=(float)(value-resisted);
        return NativeAmountForecast.Rounded(value,true);
    }
    internal static NativeAmountForecast Estimate(int basis,int element,Fighter source,Fighter target,SpellEffect row)
    {
        var a=MapGeometry.Context.Cells[source.CellId];var b=MapGeometry.Context.Cells[target.CellId];
        int radius=source.NativePhysicalRadius+target.NativePhysicalRadius;
        int distance=Math.Max(0,Math.Abs(a.X-b.X)-radius)+Math.Max(0,Math.Abs(a.Y-b.Y)-radius);
        var flags=row.NativeDamageFlags;bool forced=flags.Contains(23)||flags.Contains(24);
        bool melee=flags.Contains(23)||!forced&&distance<=2,ranged=flags.Contains(24)||!forced&&distance>2;
        int virtualCurrent=NativeHpForecast.Virtual(source);
        float maximum=source.MaxHP+source.NativeVirtualHpMax;
        bool berserk=maximum>0&&(float)((float)((source.CurrentHP+virtualCurrent)/maximum)*100f)<50f;
        return Amount(basis,element,source.NativeStats!,target.NativeStats!,row.NativeCoefficientMask,
            flags.Contains(22),flags.Contains(4),melee,ranged,berserk,target.NativeForecastHealResistance);
    }
    internal static int ResistanceAfter(int actualHeal,int maximumHp,int current,bool enabled,bool frozen,int minimum,int maximum)
    {
        if(maximumHp<0)throw new ArgumentException("Invalid native healing maximum");
        if(current<minimum||current>maximum)throw new ArgumentException("Unknown native healing resistance bounds");
        if(!enabled||frozen)return current;
        if(maximumHp<=0)throw new ArgumentException("Unknown native healing maximum");
        float increment=(float)((float)((float)((float)actualHeal/(float)maximumHp)/5f)*1000f);
        float changed=(float)((float)current+increment);
        // Java f2i saturates outside the signed-int domain.
        int truncated=changed>=int.MaxValue?int.MaxValue:changed<=int.MinValue?int.MinValue:(int)changed;
        return Math.Clamp(truncated,minimum,maximum);
    }
}
