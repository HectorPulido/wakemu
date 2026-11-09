using Jondo.Unity.Server.Managers;
using System.Text.Json;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

// Focused regression for sequential direct-health valuation and its fallback.
internal static class MixedHealthRegression
{
    public static void Run()
    {
        using var geometry=MapGeometry.BeginScope(new GeometryContext(
            new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0)},new[]{(0,1),(1,0)}));
        Fighter Actor(long id,int team,int cell)=>new(){Id=id,TeamId=team,CellId=cell,
            CurrentHP=100,MaxHP=100,CurrentAP=6,MaxAP=6,CurrentMP=0,MaxMP=0,
            NativeHpMinimum=0,NativeHpFrozen=false,NativeHpRawMode="bounded",NativeUndead=false,
            NativeIsCarried=false,NativeHealingResistanceEnabled=false,NativeVirtualHpFrozen=false,
            NativeStats=new Dictionary<int,int>{{87,0},{32,0},{92,0},{97,0},{100,0}},IsMonster=true,
            NativeArmorAuthority=new NativePoolAuthority(0,int.MaxValue,false),
            NativeBarrierAuthority=new NativePoolAuthority(0,int.MaxValue,false),
            NativeVirtualHpAuthority=new NativePoolAuthority(0,0,false)};
        var caster=Actor(1,0,0);var enemy=Actor(2,1,1);var fighters=new[]{caster,enemy};
        var board=new MonsterTactics.Board{Fighters=fighters,Sees=(_,_)=>true,NativeHealthReachStable=true,
            Reach=(row,source,from,aim)=>Planner.NativeReach(fighters,row,source,from,aim)};
        var hit=SemanticRows.Create("damage",10,"enemy",nativeCoefficientMask:0);
        var heal=SemanticRows.Create("heal",10,"enemy",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(hit,0,10);NativeEffectAmounts.Bind(heal,0,10,1);
        var spell=new MonsterTactics.Spell{Id=9190,Grade=1,Cost=3,MinRange=0,MaxRange=3,
            Damage=10,Heal=10,NativeDirectHealthSequence=true,Rows=new[]{hit,heal}};
        var step=new MonsterTactics.Action(new[]{0},spell,enemy,1,1,ActionPoints:6,MovementPoints:0);
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{step}))
            if(enemy.CurrentHP!=100)throw new Exception("Expected damage 10 and healing 10 to leave enemy HP at 100");
        double value=MonsterTactics.ValueOfRows(board,spell,caster,0,1,new(){enemy});
        if(Math.Abs(value)>1e-9)
            throw new Exception($"Expected net-zero health value; got {value}");
        var reverse=new MonsterTactics.Spell{Id=9191,Grade=1,Cost=3,MinRange=0,MaxRange=3,
            Damage=10,Heal=10,NativeDirectHealthSequence=true,Rows=new[]{heal,hit}};
        if(MonsterTactics.ValueOfRows(board,reverse,caster,0,1,new(){enemy})!=10)
            throw new Exception("Healing a full enemy before damage must preserve damage value");
        if(MonsterTactics.ValueOfRows(board,spell,caster,0,1,new(){enemy},allowHealthSequence:false)!=10)
            throw new Exception("Portal and other disabled contexts must keep the existing valuation");
        var uncertain=SemanticRows.Create("damage",10,"enemy",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(uncertain,0,10,probability:.5);
        var risky=new MonsterTactics.Spell{Id=9192,Grade=1,Cost=3,MinRange=0,MaxRange=3,
            Damage=10,Heal=10,NativeDirectHealthSequence=true,Rows=new[]{uncertain,heal}};
        double fallback=MonsterTactics.ValueOfRows(board,risky,caster,0,1,new(){enemy},allowHealthSequence:false);
        if(MonsterTactics.ValueOfRows(board,risky,caster,0,1,new(){enemy})!=fallback)
            throw new Exception("Uncertain damage must retain probabilistic fallback");
        var groupedHit=new SpellEffect{EffectId=96,NativeCoefficientMask=0,DiceNum=10,DiceSide=10,
            TargetMask="A",Forma='P',Triggers="I",Sorteo=1};
        NativeEffectAmounts.Bind(groupedHit,0,10);
        var grouped=new MonsterTactics.Spell{Id=9193,Grade=1,Cost=3,MinRange=0,MaxRange=3,
            Damage=10,Heal=10,NativeDirectHealthSequence=true,Rows=new[]{groupedHit,heal}};
        fallback=MonsterTactics.ValueOfRows(board,grouped,caster,0,1,new(){enemy},allowHealthSequence:false);
        if(fallback<=0 || MonsterTactics.ValueOfRows(board,grouped,caster,0,1,new(){enemy})!=fallback)
            throw new Exception("Random-group damage must retain the existing fallback");
        enemy.CurrentHP=5;
        fallback=MonsterTactics.ValueOfRows(board,spell,caster,0,1,new(){enemy},allowHealthSequence:false);
        if(MonsterTactics.ValueOfRows(board,spell,caster,0,1,new(){enemy})!=fallback)
            throw new Exception("Lethal damage must retain the existing fallback");
        if(enemy.CurrentHP!=5||caster.CurrentHP!=100)
            throw new Exception("Sequential scoring must not mutate fighters");
        if (HostChoice(true,false)!=2 || HostChoice(true,true)!=1 || HostChoice(false,false)!=1)
            throw new Exception("Host must use certified root order and preserve fallback without the certificate");
        Console.WriteLine("Sequential health valuation regression passed");
    }

    private static long HostChoice(bool certified, bool reverse)
    {
        Dictionary<string,object> Health(string kind)
        {
            var row=new Dictionary<string,object>{["kind"]=kind,["amount"]=10,["target"]="enemy",
                ["element"]="physical",["fixedCells"]=Array.Empty<int[]>(),["nativeInArea"]=true,
                ["probability"]=100,["conditional"]=false,["nativeCoefficientMask"]=0,
                ["nativeBase"]=new{version=1,kind=0,value=10,sourceBindingKnown=true},
                ["nativeHealthGeometry"]=new{version=1,fixedCells=new[]{new[]{0,0}},nativeInArea=true,
                    nativeAreaCenterOnCaster=false,nativeAreaUseTargetRadius=true}};
            if(kind=="heal") row["nativeHealing"]=new{version=1,element=1};
            return row;
        }
        var hit=Health("damage");var heal=Health("heal");
        var mixed=new Dictionary<string,object>{["id"]=1,["grade"]=1,["cost"]=3,["minRange"]=1,
            ["maxRange"]=1,["damage"]=10,["heal"]=10,["element"]="physical",
            ["rows"]=reverse?new[]{heal,hit}:new[]{hit,heal}};
        if(certified)mixed["nativeDirectHealthSequence"]=true;
        var attack=new{id=2,grade=1,cost=3,minRange=1,maxRange=1,damage=6,element="physical",
            rows=new[]{new{kind="damage",amount=6,target="enemy",fixedCells=new[]{new[]{0,0}}}}};
        Dictionary<string,object> Actor(long id,int team,int cell)=>new(){["id"]=id,["team"]=team,["cell"]=cell,
            ["hp"]=100,["maxHp"]=100,["ap"]=3,["maxAp"]=3,["mp"]=0,["maxMp"]=0,["wp"]=0,
            ["stats"]=new Dictionary<string,int>{{"87",0},{"32",0},{"92",0},{"97",0},{"100",0}},
            ["nativeHp"]=new{version=1,minimum=0,frozen=false,rawCurrentMode="bounded",rawCurrent=(int?)null},
            ["nativeUndead"]=false,["nativeIsCarried"]=false,["nativeHealingResistanceEnabled"]=false,
            ["nativeVirtualHpFrozen"]=false};
        var request=JsonSerializer.SerializeToElement(new {protocol=1,requestId="direct-health-order",
            source=new{actorId=1L},board=new{cells=new[]{new{id=0,xyz=new[]{0,0,0}},new{id=1,xyz=new[]{1,0,0}}},
                edges=new[]{new[]{0,1},new[]{1,0}},round=1,actors=new[]{Actor(1,0,0),Actor(2,1,1)},
                lineOfSight=new[]{new object[]{0,1,true},new object[]{1,0,true}}},
            spells=new object[]{mixed,attack},native=new{usage=Array.Empty<object>()},
            excludedActions=Array.Empty<string>(),limits=new{budgetMs=1000}});
        var result=JsonSerializer.SerializeToElement(Planner.Decide(request));
        return result.GetProperty("action").GetProperty("spellId").GetInt64();
    }
}
