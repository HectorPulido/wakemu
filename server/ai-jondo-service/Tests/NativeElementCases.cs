using System.Text.Json;
using Wakfu.Jondo;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class NativeElementCases
{
    public static int Run()
    {
        int checks=0;
        void Check(bool value,string name)
        {
            if (!value) throw new Exception("FAIL: "+name);
            checks++; Console.WriteLine("PASS: "+name);
        }
        using var geometry=MapGeometry.BeginScope(new GeometryContext(
            new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(0,1,0)},
            new[]{(0,1),(1,0),(0,2),(2,0)}));
        var source=new Fighter{Id=1,CellId=0,CurrentHP=100,MaxHP=100,
            NativeStats=new Dictionary<int,int>{{21,100},{22,200},{23,300},{24,400}}};
        var target=new Fighter{Id=2,CellId=1,CurrentHP=1000,MaxHP=1000,
            NativeDirection=5,NativeStats=new Dictionary<int,int>{{28,0},{29,0},{30,0},{31,0}}};
        double Estimate(ElementType element,SpellEffect? row=null)
        {
            if(!NativeDamageCalculator.TryEstimate(100,element,source,target,row,out double value))
                throw new Exception("Complete native stats failed estimation");
            return value;
        }
        foreach(var (element,expected) in new[]{(ElementType.Fire,200d),(ElementType.Water,300d),
            (ElementType.Earth,400d),(ElementType.Air,500d),(ElementType.Light,500d),(ElementType.Stasis,500d)})
            Check(Math.Abs(Estimate(element)-expected)<0.001,"native distinct element mastery "+element);
        target.NativeStats=new Dictionary<int,int>{{28,200},{29,100},{30,-100},{31,0}};
        Check(Math.Abs(Estimate(ElementType.Light)-500)<0.001,"Light defends against its selected mastery element");
        Check(Math.Abs(Estimate(ElementType.Stasis)-625)<0.001,"Stasis selects strongest mastery and weakest resistance independently");
        Check(NativeDamageCalculator.HighestMastery(new Dictionary<int,int>{{24,50},{23,50},{22,50},{21,50}})==ElementType.Fire,
            "native mastery ties use Fire first regardless dictionary order");
        Check(NativeDamageCalculator.LowestResistance(new Dictionary<int,int>{{31,50},{30,50},{29,50},{28,50}})==ElementType.Fire,
            "native resistance ties use Fire first regardless dictionary order");
        target.NativeStats=new Dictionary<int,int>{{28,0},{29,0},{30,0},{31,0}};
        var localized=new SpellEffect{NativeLocalization=true};
        target.NativeDirection=1;
        Check(NativeDamageCalculator.Facing(source,target)=="BACK" && Math.Abs(Estimate(ElementType.Fire,localized)-250)<0.001,
            "localized native back hit includes the actual facing multiplier");
        target.NativeDirection=3;
        Check(NativeDamageCalculator.Facing(source,target)=="SIDE" && Math.Abs(Estimate(ElementType.Fire,localized)-220)<0.001,
            "localized native side hit includes the actual facing multiplier");
        target.NativeDirection=1;
        Check(Math.Abs(Estimate(ElementType.Fire)-200)<0.001,"unlocalized row does not borrow a back multiplier");
        Check(Math.Abs(Estimate(ElementType.Fire,new SpellEffect{NativeCoefficientMask=0})-100)<0.001,
            "coefficient mask zero excludes mastery and resistance");
        Check(Math.Abs(Estimate(ElementType.Fire,new SpellEffect{NativeCoefficientMask=2})-100)<0.001,
            "resistance-only coefficient does not borrow mastery");
        source.NativeStats=new Dictionary<int,int>{{21,100},{22,200},{23,300},{24,400},{48,50},{11,900}};
        Check(Math.Abs(Estimate(ElementType.Fire)-300)<0.001,"spell-container direct final damage uses48 rather than indirect11");
        source.NativeStats=null;
        Check(!NativeDamageCalculator.TryEstimate(100,ElementType.Light,source,target,null,out _),
            "missing native stats preserve the legacy advisory fallback");
        foreach(string element in new[]{"light","stasis"})
        {
            var result=JsonSerializer.SerializeToElement(Planner.Decide(Request(element)));
            long expectedTarget=element=="light"?3:2;
            Check(result.GetProperty("action").GetProperty("type").GetString()=="cast"
                && result.GetProperty("action").GetProperty("targetId").GetInt64()==expectedTarget,
                "actual Host "+element+" target choice follows native elemental defenses");
        }
        return checks + WorldGoldens();
    }

    private static int WorldGoldens()
    {
        using var document=JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory,"Fixtures","NativeElementGoldens.json")));
        int checks=0;
        foreach(var data in document.RootElement.GetProperty("cases").EnumerateArray())
        {
            CellXYZ Cell(string name)
            {
                var v=data.GetProperty(name);
                return new CellXYZ(v[0].GetInt32(),v[1].GetInt32(),v[2].GetInt32());
            }
            Dictionary<int,int> Stats(string name)=>data.GetProperty(name).EnumerateObject()
                .ToDictionary(p=>int.Parse(p.Name),p=>p.Value.GetInt32());
            using var geometry=MapGeometry.BeginScope(new GeometryContext(
                new[]{Cell("sourceCell"),Cell("targetCell")},Array.Empty<(int,int)>()));
            var source=new Fighter{Id=1,CellId=0,CurrentHP=data.GetProperty("sourceHp").GetInt32(),
                MaxHP=data.GetProperty("sourceMaxHp").GetInt32(),NativeStats=Stats("sourceStats")};
            var target=new Fighter{Id=2,CellId=1,CurrentHP=1000,MaxHP=1000,
                NativeDirection=data.GetProperty("direction").GetInt32(),NativeStats=Stats("targetStats")};
            var row=new SpellEffect{NativeCoefficientMask=data.GetProperty("coefficientMask").GetInt32(),
                NativeLocalization=data.GetProperty("localized").GetBoolean(),
                NativeDamageFlags=data.GetProperty("flags").EnumerateArray().Select(x=>x.GetInt32()).ToArray()};
            var element=Enum.Parse<ElementType>(data.GetProperty("element").GetString()!,true);
            bool supported=NativeDamageCalculator.TryEstimate(data.GetProperty("base").GetDouble(),
                element,source,target,row,out double value);
            double low=data.GetProperty("low").GetDouble(),high=data.GetProperty("high").GetDouble();
            string label=data.GetProperty("label").GetString()!;
            if(!supported || value<low-0.001 || value>high+0.001
                || NativeDamageCalculator.Facing(source,target)!=data.GetProperty("facing").GetString())
                throw new Exception($"World native golden {label}: estimate={value}, bounds=[{low},{high}]");
            checks++;Console.WriteLine("PASS: actual World native golden "+label);
        }
        return checks;
    }

    private static JsonElement Request(string element)
    {
        var actors=new[]{
            new{id=1L,team=1,cell=0,hp=1000,maxHp=1000,ap=3,mp=0,maxAp=3,maxMp=0,level=100,
                stats=new Dictionary<string,int>{{"21",100},{"22",200},{"23",300},{"24",400}}},
            new{id=2L,team=0,cell=1,hp=1000,maxHp=1000,ap=0,mp=0,maxAp=0,maxMp=0,level=100,
                stats=new Dictionary<string,int>{{"28",200},{"29",200},{"30",0},{"31",300}}},
            new{id=3L,team=0,cell=2,hp=1000,maxHp=1000,ap=0,mp=0,maxAp=0,maxMp=0,level=100,
                stats=new Dictionary<string,int>{{"28",200},{"29",200},{"30",200},{"31",100}}},
        };
        return JsonSerializer.SerializeToElement(new{
            protocol=1,requestId="native-elements-"+element,source=new{actorId=1L},
            board=new{cells=new[]{new{id=0,xyz=new[]{0,0,0}},new{id=1,xyz=new[]{1,0,0}},new{id=2,xyz=new[]{0,1,0}}},
                edges=new[]{new[]{0,1},new[]{1,0},new[]{0,2},new[]{2,0}},round=1,actors,
                lineOfSight=new[]{new object[]{0,1,true},new object[]{0,2,true}}},
            spells=new[]{new{id=70001,grade=100,cost=3,minRange=1,maxRange=2,damage=10,element,
                rows=new[]{new{kind="damage",amount=10,target="enemy",element,
                    coefficientMask=3,fixedCells=new[]{new[]{0,0}}}}}},
            native=new{usage=Array.Empty<object>()},limits=new{budgetMs=100,maxActions=1}});
    }
}
