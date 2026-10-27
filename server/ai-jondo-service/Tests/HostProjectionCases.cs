using System.Text.Json;
using Wakfu.Jondo;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class HostProjectionCases
{
    public static int Run()
    {
        var request=JsonSerializer.SerializeToElement(new
        {
            protocol=1,requestId="native-three-relations",source=new{actorId=1L},
            board=new
            {
                cells=new[]{new{id=0,xyz=new[]{0,0,0}},new{id=1,xyz=new[]{1,0,0}}},
                edges=new[]{new[]{0,1},new[]{1,0}},round=1,
                actors=new[]{new{id=1L,team=1,cell=0,hp=66,maxHp=66,ap=3,mp=0,maxAp=6,maxMp=3,level=10},
                             new{id=2L,team=0,cell=1,hp=100,maxHp=100,ap=6,mp=0,maxAp=6,maxMp=3,level=10}},
                lineOfSight=new[]{new object[]{0,1,true},new object[]{1,0,true}},
            },
            spells=new[]{new
            {
                id=5767,grade=10,cost=3,minRange=1,maxRange=1,damage=10,element="neutral",
                rows=new[]{
                    new{kind="damage",amount=10,target="enemy",fixedCells=new[]{new[]{0,0}}},
                    new{kind="damage",amount=10,target="ally",fixedCells=new[]{new[]{0,0}}},
                    new{kind="damage",amount=10,target="self",fixedCells=new[]{new[]{0,0}}},
                },
            }},
            native=new{usage=Array.Empty<object>()},excludedActions=Array.Empty<string>(),limits=new{budgetMs=1000},
        });
        string original=request.GetRawText();
        var result=JsonSerializer.SerializeToElement(Planner.Decide(request));
        if(result.GetProperty("action").GetProperty("type").GetString()!="cast"
           || result.GetProperty("action").GetProperty("targetId").GetInt64()!=2)
            throw new Exception("Native three-relation rows must attack the enemy without inventing self damage: "+result);
        if(request.GetRawText()!=original)throw new Exception("Host mutated original source DTO");
        Console.WriteLine("PASS: actual Host plans an enemy cast from native enemy/ally/self rows");
        return 1 + SimulationCases() + ResourceCases();
    }
    private static int SimulationCases()
    {
        using var geometry=MapGeometry.BeginScope(new GeometryContext(
            new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0)},new[]{(0,1),(1,0)}));
        var caster=new Fighter{Id=1,TeamId=1,CellId=0,CurrentHP=66,MaxHP=66,CurrentAP=6,MaxAP=6};
        var enemy=new Fighter{Id=2,TeamId=0,CellId=1,CurrentHP=100,MaxHP=100,CurrentAP=6,MaxAP=6};
        var fighters=new[]{caster,enemy};
        var board=new MonsterTactics.Board{Fighters=fighters,
            Reach=(row,who,from,aim)=>Planner.NativeReach(fighters,row,who,from,aim)};
        var rows=new[]{"enemy","ally","self"}.Select(relation=>
            SemanticRows.WithOffsets(SemanticRows.Create("damage",10,relation),new[]{(0,0)})).ToArray();
        var attack=new MonsterTactics.Spell{Id=5767,Grade=10,Cost=3,Damage=10,Rows=rows};
        var step=new MonsterTactics.Action(new[]{0},attack,enemy,1,10,10,6,0);
        using(var sim=MonsterTactics.Simulation.Replay(board,caster,new[]{step}))
            if(caster.CurrentHP!=66 || enemy.CurrentHP!=90)
                throw new Exception($"Native host reach invented or duplicated damage: own={caster.CurrentHP},enemy={enemy.CurrentHP}");
        if(caster.CurrentHP!=66 || enemy.CurrentHP!=100)throw new Exception("Host reach simulation failed to rewind");
        Console.WriteLine("PASS: actual Host reach predicts 10 enemy damage and no caster damage, then rewinds");
        var self=new MonsterTactics.Action(new[]{0},attack,caster,0,10,10,6,0);
        using(var sim=MonsterTactics.Simulation.Replay(board,caster,new[]{self}))
            if(caster.CurrentHP!=56 || enemy.CurrentHP!=100)
                throw new Exception($"Native ally/self relations must be disjoint: own={caster.CurrentHP}");
        Console.WriteLine("PASS: native ally and self relations do not double-count the caster");
        caster.CurrentHP=20;
        var heal=new MonsterTactics.Spell{Id=7,Grade=1,Cost=2,Heal=25,
            Rows=new[]{SemanticRows.Create("heal",25,"self")}};
        using(var sim=MonsterTactics.Simulation.Replay(board,caster,new[]{
            new MonsterTactics.Action(new[]{0},heal,caster,0,25,25,6,0)}))
            if(caster.CurrentHP!=45)throw new Exception("Native self healing did not reach caster inside area");
        var setup=new MonsterTactics.Spell{Id=8,Grade=1,Cost=2,Buff=4,
            Rows=new[]{SemanticRows.Create("gain_ap",4,"self")}};
        using(var sim=MonsterTactics.Simulation.Replay(board,caster,new[]{
            new MonsterTactics.Action(new[]{0},setup,caster,0,4,4,6,0)}))
            if(caster.CurrentAP!=8)throw new Exception("Native self AP preparation did not reach caster inside area");
        if(caster.CurrentAP!=6 || caster.CurrentHP!=20)throw new Exception("Self support simulation failed to rewind");
        Console.WriteLine("PASS: actual Host reach preserves self heal and AP preparation inside the caster area");
        return 3;
    }

    private static object ResourceSpell(int id,int damage,int ap,int mp=0,int wp=0,int range=1,
                                       bool preparation=false)
    {
        return new {id,grade=1,cost=ap,nativeCosts=new{ap,mp,wp},minRange=preparation?0:1,
            maxRange=preparation?0:range,damage,element="neutral",buff=preparation?4:0,
            rows=new[]{new{kind=preparation?"gain_ap":"damage",amount=preparation?4:damage,
                          target=preparation?"self":"enemy",fixedCells=new[]{new[]{0,0}}}}};
    }
    private static JsonElement ResourceRequest(string encounter,int ap,int mp,int wp,int target,
                                              object[] spells,int actorCell=0)
    {
        return JsonSerializer.SerializeToElement(new
        {
            protocol=1,requestId=encounter,source=new{actorId=1L,fightInstanceId=encounter,turnId=1,
                catalogRevision="resources-v1",stateRevision=actorCell,actionId=actorCell},
            board=new
            {
                cells=Enumerable.Range(0,4).Select(id=>new{id,xyz=new[]{id,0,0}}).ToArray(),
                edges=Enumerable.Range(0,3).SelectMany(x=>new[]{new[]{x,x+1},new[]{x+1,x}}).ToArray(),
                actors=new[]{new{id=1L,team=1,cell=actorCell,hp=66,maxHp=66,ap,mp,wp,maxAp=6,maxMp=3,level=10},
                             new{id=2L,team=0,cell=target,hp=100,maxHp=100,ap=6,mp=0,wp=0,maxAp=6,maxMp=3,level=10}},
            },spells,native=new{usage=Array.Empty<object>()},excludedActions=Array.Empty<string>(),limits=new{budgetMs=1000},
        });
    }
    private static JsonElement Decide(JsonElement request)=>JsonSerializer.SerializeToElement(Planner.Decide(request));
    private static bool IsSpell(JsonElement action,int id)=>action.GetProperty("type").GetString()=="cast"
        && action.GetProperty("spellId").GetInt32()==id;
    private static int ResourceCases()
    {
        int count=0;
        void Check(bool okay,string message)
        {
            if(!okay)throw new Exception(message);
            count++;Console.WriteLine("PASS: "+message);
        }
        object cheap=ResourceSpell(1,5,3,range:3);
        var wp=Decide(ResourceRequest("zero-wp",6,0,0,1,new[]{cheap,ResourceSpell(2,30,3,wp:1)}));
        Check(IsSpell(wp.GetProperty("action"),1) && !wp.GetProperty("alternatives").EnumerateArray().Any(a=>IsSpell(a,2)),
              "zero WP excludes the unaffordable spell from primary and alternatives");
        var mp=Decide(ResourceRequest("zero-mp",6,0,0,1,new[]{cheap,ResourceSpell(2,30,3,mp:1)}));
        Check(IsSpell(mp.GetProperty("action"),1) && !mp.GetProperty("alternatives").EnumerateArray().Any(a=>IsSpell(a,2)),
              "zero MP excludes cast costs from primary and alternatives");
        var walk=Decide(ResourceRequest("walk-consumes-cast-mp",6,1,0,2,new[]{cheap,ResourceSpell(2,30,3,mp:1)}));
        Check(IsSpell(walk.GetProperty("action"),1),
              "walking cannot consume MP reserved for the planned cast when an immediate attack is affordable");
        var walkingAffordable=Decide(ResourceRequest("walk-plus-cast-affordable",6,2,0,2,
            new[]{ResourceSpell(2,30,3,mp:1)}));
        Check(walkingAffordable.GetProperty("action").GetProperty("type").GetString()=="move"
              && walkingAffordable.GetProperty("action").GetProperty("path").GetArrayLength()==1,
              "one MP walk plus one MP cast retains the legal move-attack prefix");
        var preparation=Decide(ResourceRequest("ap-preparation-preserved",6,0,0,1,
            new[]{ResourceSpell(2,30,4),ResourceSpell(3,0,2,preparation:true)}));
        Check(IsSpell(preparation.GetProperty("action"),3) && preparation.GetProperty("plannedCasts").GetInt32()>=3,
              "native affordability preserves AP preparation for two subsequent attacks");
        foreach(bool wpCost in new[]{false,true})
        {
            var constrained=Decide(ResourceRequest(wpCost?"wp-prefix":"mp-prefix",6,1,1,1,
                new[]{ResourceSpell(2,30,3,mp:wpCost?0:1,wp:wpCost?1:0)}));
            Check(IsSpell(constrained.GetProperty("action"),2) && constrained.GetProperty("plannedCasts").GetInt32()==1,
                  "planned prefix accounts for cumulative "+(wpCost?"WP":"MP")+" cast expenditure");
        }
        object[] cachedSpells={cheap,ResourceSpell(2,30,3,mp:1)};
        var first=Decide(ResourceRequest("cached-move-resources",6,2,0,2,cachedSpells));
        Check(first.GetProperty("action").GetProperty("type").GetString()=="move",
              "resource continuation test begins with a published move proposal");
        var next=Decide(ResourceRequest("cached-move-resources",6,0,0,2,cachedSpells,actorCell:1));
        Check(IsSpell(next.GetProperty("action"),1) && !next.GetProperty("planReused").GetBoolean(),
              "cached movement continuation is rejected when fresh MP cannot pay its cast");
        return count;
    }

}
