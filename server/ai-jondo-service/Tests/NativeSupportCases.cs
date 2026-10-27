using System.Text.Json;
using Wakfu.Jondo;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class NativeSupportCases
{
    private sealed class Fixture
    {
        public Dictionary<string,object> Self=Actor(1,0,0),Enemy=Actor(2,1,4),Ally=Actor(3,0,2);
        public List<object> Spells=new(),History=new(),Excluded=new();
        public Dictionary<string,object> Support=new(){["version"]=1,["aimKinds"]=new[]{"emptyCell"},
            ["intents"]=new[]{"summon"},["effects"]=System.Array.Empty<object>(),
            ["summons"]=new object[]{new{reference=2975,level=1,friendly=true,benefit="beneficial",probability=100,conditional=false,confidence="known"}},
            ["candidateCells"]=new[]{1,3},["facts"]=new{leadership=(int?)null,summonCount=(int?)null,summonCountsComplete=false}};
        public Fixture(){Self["mp"]=0;Spells.Add(SupportSpell());}
        public Dictionary<string,object> SupportSpell()=>new(){["id"]=7001,["grade"]=1,["cost"]=3,
            ["nativeCosts"]=new{ap=3,mp=0,wp=0},["minRange"]=1,["maxRange"]=3,["utility"]=1,
            ["needsFreeCell"]=true,["rows"]=System.Array.Empty<object>(),["nativeSupport"]=Support};
        public JsonElement Request()
        {
            var cells=Enumerable.Range(0,5).Select(i=>new{id=i,xyz=new[]{i,0,0}}).ToArray();
            var body=new{protocol=1,requestId=Guid.NewGuid().ToString(),
                source=new{actorId=1L,fightInstanceId=Guid.NewGuid().ToString(),turnId=1,catalogRevision="qa-support-v1"},
                board=new{cells,edges=Enumerable.Range(0,4).SelectMany(i=>new[]{new[]{i,i+1},new[]{i+1,i}}).ToArray(),
                    actors=new[]{Self,Enemy,Ally},round=1,lineOfSight=Enumerable.Range(0,5).SelectMany(a=>Enumerable.Range(0,5).Select(b=>new object[]{a,b,true})).ToArray()},
                spells=Spells,native=new{usage=System.Array.Empty<object>(),turnActions=History},excludedActions=Excluded,limits=new{budgetMs=200}};
            return JsonSerializer.SerializeToElement(body);
        }
        public JsonElement Decide()
        {
            var request=Request();var before=request.GetRawText();
            var reply=JsonSerializer.SerializeToElement(Planner.Decide(request));
            if(before!=request.GetRawText())throw new Exception("support provider mutated native request");
            return reply;
        }
        public Dictionary<string,object> CurrentSpell= new();
        public void StateSupport(string relation="ally",string benefit="beneficial",string confidence="known",int probability=100)
        {
            Support["aimKinds"]=new[]{relation};Support["intents"]=new[]{"state"};Support["summons"]=System.Array.Empty<object>();
            Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{relation},benefit,probability,conditional=confidence=="conditional",confidence,nativeReference=9001}};
            Spells.Clear();CurrentSpell=SupportSpell();CurrentSpell["needsFreeCell"]=false;CurrentSpell["maxRange"]=5;Spells.Add(CurrentSpell);
        }
    }
    private static Dictionary<string,object> Actor(long id,int team,int cell)=>new(){["id"]=id,["team"]=team,["cell"]=cell,["hp"]=100,["maxHp"]=100,
        ["ap"]=6,["maxAp"]=6,["mp"]=0,["maxMp"]=0,["wp"]=0,["level"]=10,["states"]=System.Array.Empty<object>()};
    private static bool IsSupport(JsonElement reply)=>reply.GetProperty("strategyId").GetString()=="native-support";
    private static JsonElement Action(JsonElement r)=>r.GetProperty("action");
    public static int Run()
    {
        int count=0;void Check(bool ok,string reason){if(!ok)throw new Exception("NativeSupport: "+reason);count++;}
        var f=new Fixture();var r=f.Decide();
        Check(IsSupport(r)&&Action(r).GetProperty("type").GetString()=="cast","generic non-self native invocation chosen without summon simulator");
        Check(Action(r).GetProperty("target")[0].GetInt32()==1,"summon uses an actually empty aim");
        Check(r.GetProperty("source").GetProperty("actorId").GetInt64()==1,"support response preserves source identity");
        f=new();f.Ally["cell"]=1;f.Enemy["cell"]=3;r=f.Decide();Check(!IsSupport(r),"occupied summon cells not offered");
        f=new();f.Self["ap"]=2;r=f.Decide();Check(!IsSupport(r),"unaffordable summon absent");
        f=new();var free=(Dictionary<string,object>)f.Spells[0];free["cost"]=0;free["nativeCosts"]=new{ap=0,mp=0,wp=0};
        f.History.Add(new{type="cast",spellId=7001});r=f.Decide();Check(!IsSupport(r),"zero AP history prevents repeated unsupported cast");
        f=new();f.StateSupport();r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("targetId").GetInt64()==3,"beneficial state aims at ally");
        f=new();f.StateSupport();f.Ally["states"]=new[]{new{reference=8800,level=1}};r=f.Decide();Check(!IsSupport(r),"already satisfied state does not receive invented additional benefit");
        f=new();f.StateSupport(benefit:"unknown");r=f.Decide();Check(!IsSupport(r),"unknown state benefit is not assumed positive");
        f=new();f.StateSupport(relation:"enemy");r=f.Decide();Check(!IsSupport(r),"beneficial enemy state not rewarded");
        f=new();f.StateSupport(relation:"enemy",benefit:"harmful");r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("targetId").GetInt64()==2,"harmful state can target enemy");
        f=new();f.StateSupport(probability:0);r=f.Decide();Check(!IsSupport(r),"zero probability grants no support value");
        f=new();f.StateSupport();f.CurrentSpell["minRange"]=0;f.CurrentSpell["maxRange"]=0;f.Support["aimKinds"]=new[]{"self"};
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{"enemy"},benefit="harmful",probability=100,confidence="known",conditional=false,nativeReference=9001,fixedCells=new[]{new[]{4,0}}}};
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==0,"self-aim aura values actual enemy footprint");
        f=new();f.StateSupport();f.Ally["hp"]=10;f.Support["intents"]=new[]{"heal"};
        f.Support["effects"]=new object[]{new{kind="heal",amount=20,percent=true,percentBase="maximum_hp",targets=new[]{"ally"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001}};
        r=f.Decide();Check(IsSupport(r),"native percentage heal can aid injured ally without simulated native effects");
        f.Ally["hp"]=100;r=f.Decide();Check(!IsSupport(r),"full HP target produces no invented healing benefit");
        f=new();r=f.Decide();f.Excluded.Add(Action(r).Clone());r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==3,"native rejected summon aim has independent legal fallback aim");
        f=new();f.StateSupport();f.CurrentSpell["rows"]=new[]{new{kind="gain_ap",amount=1,target="ally",nativeReference=9001}};
        r=f.Decide();Check(!IsSupport(r),"already projected numeric effect is not counted again by support provider");
        f=new();var unsupported=(Dictionary<string,object>)f.Spells[0];unsupported["nativeSupport"]=new{version=2};r=f.Decide();Check(!IsSupport(r),"unknown capability schema does not invent candidates");
        void Attack(Fixture fixture)=>fixture.Spells.Add(new{id=7002,grade=1,cost=3,minRange=1,maxRange=5,damage=8,
            rows=new[]{new{kind="damage",amount=8,target="enemy",nativeReference=9100}}});
        f=new();f.StateSupport();Attack(f);r=f.Decide();Check(IsSupport(r),"known support benefit can outrank modest ordinary attack");
        f=new();f.StateSupport(confidence:"conditional");Attack(f);r=f.Decide();Check(!IsSupport(r),"conditional support confidence does not outrank confirmed attack");
        f=new();f.StateSupport(probability:25);Attack(f);r=f.Decide();Check(!IsSupport(r),"support probability affects comparison with confirmed ordinary action");
        f=new();f.Support["summons"]=new object[]{new{reference=2975,probability=100,confidence="known",friendly=false,benefit="harmful"}};
        r=f.Decide();Check(!IsSupport(r),"enemy-affiliation summon not rewarded as friendly summon");
        f=new();f.StateSupport();f.Ally["states"]=new[]{new{reference=8800,level=0}};
        f.Support["effects"]=new object[]{new{kind="remove_state",stateId=8800,amount=(int?)null,presentOn=new[]{3L},targets=new[]{"ally"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001}};
        r=f.Decide();Check(IsSupport(r),"native observed level-zero state can be removed without double-inverting benefit");
        f=new();f.StateSupport();f.Support["effects"]=new object[]{
            new{kind="stat_gain",statId=20,amount=10,percent=false,targets=new[]{"ally"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001},
            new{kind="stat_loss",statId=29,amount=50,percent=false,targets=new[]{"ally"},benefit="harmful",probability=100,confidence="known",conditional=false,nativeReference=9002}};
        r=f.Decide();Check(!IsSupport(r),"mixed support subtracts harmful side effects on allies");
        f=new();f.StateSupport();f.CurrentSpell["rows"]=new[]{new{kind="damage",amount=100,target="ally",nativeReference=9002}};
        r=f.Decide();Check(!IsSupport(r),"mixed native damage rows retain friendly fire penalty");
        f=new();f.StateSupport();f.Ally["states"]=new[]{new{reference=8800,level=0}};
        r=f.Decide();Check(!IsSupport(r),"already present level-zero buff does not receive repeated benefit");
        f=new();f.StateSupport();f.Ally["states"]=new[]{new{reference=8800,level=2}};
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,increaseOn=new[]{3L},targets=new[]{"ally"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001}};
        r=f.Decide();Check(IsSupport(r),"source-attested native stacking increase remains eligible even when increment is below current level");
        f=new();f.StateSupport();f.Support["effects"]=new object[]{new{kind="stat_gain",statId=20,amount=10,amountKnown=false,targets=new[]{"ally"},benefit="beneficial",probability=100,confidence="conditional",conditional=true,nativeReference=9001}};
        r=f.Decide();Check(!IsSupport(r),"native runner callback amount does not become a numeric support prediction");
        var line=Enumerable.Range(0,5).Select(x=>new CellXYZ(x,0,0)).ToArray();
        using(MapGeometry.BeginScope(new GeometryContext(line,Enumerable.Range(0,4).SelectMany(x=>new[]{(x,x+1),(x+1,x)}))))
        {
            var caster=new Fighter{Id=1,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100,CurrentAP=6,MaxAP=6};
            var enemy=new Fighter{Id=2,TeamId=1,CellId=4,CurrentHP=100,MaxHP=100};
            var ally=new Fighter{Id=3,TeamId=0,CellId=2,CurrentHP=100,MaxHP=100};
            var board=new MonsterTactics.Board{Fighters=new[]{caster,enemy,ally}};
            var spell=new MonsterTactics.Spell{Id=7001,Grade=1,Cost=3,MinRange=1,MaxRange=3,Utility=1,NeedsFreeCell=true};
            var request=new Fixture().Request();int probes=0;
            var partial=NativeSupportCandidates.Propose(request,board,caster,new[]{spell},line,_=>(3,0,0),new(),()=>++probes<=2);
            Check(partial.Count>0,"soft exploration stop retains already evaluated useful support candidate");
            Check(caster.CellId==0&&caster.CurrentAP==6&&enemy.CurrentHP==100,"soft stop leaves actual actor state untouched");
        }
        f=new();f.Support["summons"]=new object[]{
            new{reference=2975,probability=100,confidence="known",friendly=true,benefit="beneficial"},
            new{reference=2976,probability=100,confidence="known",friendly=false,benefit="harmful"}};
        r=f.Decide();Check(!IsSupport(r),"mixed friendly and hostile summon consequences are compared together");
        f=new();f.StateSupport("self");f.CurrentSpell["minRange"]=1;f.CurrentSpell["maxRange"]=1;f.CurrentSpell["needsFreeCell"]=true;
        f.Support["aimKinds"]=new[]{"self","emptyCell"};f.Support["candidateCells"]=new[]{1};f.Support["castAnchorRequired"]=true;
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{"self"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001,inArea=false,fixedCells=new[]{new[]{0,0}}}};
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1,"global self recipient can use required non-self cast anchor without inventing range zero");
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{"self"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001,inArea=true,fixedCells=new[]{new[]{0,0}}}};
        f.Support["castAnchorRequired"]=false;r=f.Decide();Check(!IsSupport(r),"area-restricted self recipient is not granted a buff outside its native effect area");
        f=new();f.StateSupport("self");f.Self["hp"]=40;f.CurrentSpell["minRange"]=1;f.CurrentSpell["maxRange"]=1;f.CurrentSpell["needsFreeCell"]=true;
        f.CurrentSpell["rows"]=new[]{new{kind="heal",amount=20,target="self",nativeReference=9001,nativeInArea=false,fixedCells=new[]{new[]{0,0}}}};
        f.Support["aimKinds"]=new[]{"self","emptyCell"};f.Support["candidateCells"]=new[]{1};f.Support["castAnchorRequired"]=true;f.Support["effects"]=System.Array.Empty<object>();
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1,"already projected global self heal retains legal anchor candidate without duplicate support value");
        f.CurrentSpell["rows"]=new[]{new{kind="gain_ap",amount=2,target="self",nativeReference=9001,nativeInArea=false,fixedCells=new[]{new[]{0,0}}}};
        f.Self["ap"]=3;r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1,"global AP preparation keeps exact native range and numeric row valuation");
        f=new();f.StateSupport("self");f.Ally["cell"]=1;f.Enemy["cell"]=2;
        f.CurrentSpell["minRange"]=1;f.CurrentSpell["maxRange"]=1;f.CurrentSpell["needsFreeCell"]=false;
        f.Support["aimKinds"]=new[]{"self","emptyCell"};f.Support["candidateCells"]=System.Array.Empty<int>();f.Support["castAnchorRequired"]=true;
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{"self"},benefit="beneficial",probability=100,confidence="known",conditional=false,nativeReference=9001,inArea=false,fixedCells=new[]{new[]{0,0}}}};
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1,"global self buff can use occupied legal cast anchor when native free-cell gate is absent");
        f=new();f.StateSupport("self",benefit:"unknown");f.CurrentSpell["minRange"]=1;f.CurrentSpell["maxRange"]=1;f.CurrentSpell["needsFreeCell"]=true;
        f.Support["aimKinds"]=new[]{"self","emptyCell"};f.Support["candidateCells"]=new[]{1};f.Support["castAnchorRequired"]=true;
        f.Support["effects"]=new object[]{new{kind="add_state",stateId=8800,stateLevel=1,targets=new[]{"self"},benefit="unknown",probability=100,confidence="known",conditional=false,nativeReference=9001,inArea=false}};
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1&&r.GetProperty("strategyReason").GetString()!.Contains("without predicting unknown effects"),"pure native mechanic retains existing exploratory utility through an actual legal cast anchor");
        f.History.Add(new{type="cast",spellId=7001});r=f.Decide();Check(!IsSupport(r),"paid unknown mechanic anchor cannot repeatedly consume AP after committed cast history");
        f.History.Clear();Attack(f);r=f.Decide();Check(!IsSupport(r),"unknown mechanic anchor gets no invented bonus over a useful attack");
        f=new();f.StateSupport("self",benefit:"unknown");f.Ally["cell"]=1;f.Enemy["cell"]=2;
        f.CurrentSpell["minRange"]=1;f.CurrentSpell["maxRange"]=1;f.CurrentSpell["needsFreeCell"]=false;
        f.Support["aimKinds"]=new[]{"self","emptyCell"};f.Support["candidateCells"]=System.Array.Empty<int>();f.Support["castAnchorRequired"]=true;
        f.Support["effects"]=new object[]{new{kind="remove_state",stateId=8800,targets=new[]{"self"},benefit="unknown",probability=100,confidence="known",conditional=false,nativeReference=9001,inArea=false}};
        r=f.Decide();Check(IsSupport(r)&&Action(r).GetProperty("target")[0].GetInt32()==1&&Action(r).GetProperty("targetId").GetInt64()==3,"boxed global self mechanic retains existing caster utility with actual occupied anchor identity");
        return count;
    }
}
