using System.Text.Json;
using Wakfu.Jondo;

internal static class SpecificAiCases
{
    private sealed class Fixture
    {
        public Dictionary<string,object> Self=Actor(-1,0,0,0), Enemy=Actor(10,0,4,1,true);
        public List<object> Actors=new(),Spells=new(),Areas=new(),History=new(),Usage=new();
        public Dictionary<string,object> Board=new(),Native=new();
        public Fixture(int reference,int mp=0)
        {
            Self["monsterRef"]=reference;Self["mp"]=mp;Self["maxMp"]=mp;
            Actors.Add(Self);Actors.Add(Enemy);Spells.Add(Spell(91001,1,1,9,damage:5));
            Board=new(){["cells"]=Enumerable.Range(0,15).Select(id=>new{id,xyz=new[]{id%5,id/5,0}}).ToArray(),
                ["edges"]=Enumerable.Range(0,15).SelectMany(id=>new[]{id-1,id+1,id-5,id+5}.Where(to=>to>=0&&to<15&&Math.Abs(id%5-to%5)+Math.Abs(id/5-to/5)==1).Select(to=>new[]{id,to})).ToArray(),
                ["actors"]=Actors,["round"]=1,["mechanicAreas"]=Areas,
                ["lineOfSight"]=Enumerable.Range(0,15).SelectMany(a=>Enumerable.Range(0,15).Select(b=>new object[]{a,b,true})).ToArray()};
            Native=new(){["usage"]=Usage,["turnActions"]=History,["specialAimCells"]=new[]{1,5}};
        }
        public Dictionary<string,object> Body()=>new(){["protocol"]=1,["requestId"]=Guid.NewGuid().ToString(),
            ["source"]=new{actorId=-1L,fightInstanceId=Guid.NewGuid().ToString(),turnId=1,catalogRevision="qa-specific-v1"},
            ["board"]=Board,["spells"]=Spells,["native"]=Native,["excludedActions"]=Excluded,["limits"]=new{budgetMs=1000}};
        public List<string> Excluded=new();
        public JsonElement Decide()
        {
            var request=JsonSerializer.SerializeToElement(Body());var before=request.GetRawText();
            var reply=JsonSerializer.SerializeToElement(Planner.Decide(request));
            if(request.GetRawText()!=before)throw new Exception("Specific AI mutated request DTO");
            return reply;
        }
        public void Area(int reference,int cell)=>Areas.Add(new{reference,cell,cells=new[]{cell},ownerId=-1L});
    }
    private static Dictionary<string,object> Actor(long id,int reference,int cell,int team,bool player=false,long summoner=0)=>new()
    { ["id"]=id,["monsterRef"]=reference,["cell"]=cell,["team"]=team,["hp"]=1000,["maxHp"]=1000,
      ["ap"]=12,["maxAp"]=12,["mp"]=0,["maxMp"]=0,["wp"]=3,["maxWp"]=20,["level"]=200,
      ["isPlayer"]=player,["summonerId"]=summoner,["direction"]=1,["states"]=Array.Empty<object>(),["stats"]=new Dictionary<string,int>() };
    private static void States(Dictionary<string,object> actor,params (int Reference,int Level)[] values)
        =>actor["states"]=values.Select(v=>new{reference=v.Reference,level=v.Level}).ToArray();
    private static object Spell(int id,int ap,int min,int max,int mp=0,int wp=0,int damage=0,bool free=false,bool los=false,bool line=false,int perTurn=0,int perTarget=0)
        =>new{id,grade=1,cost=ap,nativeCosts=new{ap,mp,wp},minRange=min,maxRange=max,damage,
            needsFreeCell=free,needsLineOfSight=los,inLine=line,perTurn,perTarget,
            rows=damage>0?new[]{new{kind="damage",amount=damage,target="enemy",fixedCells=new[]{new[]{0,0}}}}:Array.Empty<object>()};
    private static JsonElement Action(JsonElement reply)=>reply.GetProperty("action");
    private static bool Cast(JsonElement reply,int spell,long? target=null)=>Action(reply).GetProperty("type").GetString()=="cast"
        &&Action(reply).GetProperty("spellId").GetInt32()==spell
        &&(!target.HasValue||Action(reply).GetProperty("targetId").GetInt64()==target.Value);
    private static bool Specific(JsonElement reply)=>reply.GetProperty("strategyMode").GetString()=="specific";
    private static string Key(JsonElement action)=>JsonSerializer.Serialize(new SortedDictionary<string,JsonElement>(action.EnumerateObject().ToDictionary(p=>p.Name,p=>p.Value.Clone()),StringComparer.Ordinal));
    private static Fixture Moon(bool marked=false,int mp=0)
    {
        var f=new Fixture(3870,mp);States(f.Self,(4214,1));
        foreach(var pair in new[]{(3993,5),(3995,6),(3996,7),(3997,8)})
        {var prop=Actor(100+pair.Item2,pair.Item1,pair.Item2,0,summoner:-1);prop["hp"]=5000;prop["maxHp"]=5000;
         States(prop,marked?new[]{(4226,1),(4227,1)}:new[]{(4226,1)});f.Actors.Add(prop);}
        f.Spells.Add(Spell(5693,2,1,9,damage:10,perTurn:2,perTarget:1));return f;
    }
    private static Fixture Brizlon(int reference,bool ownMechanic=true)
    {
        var f=new Fixture(reference);States(f.Self,(4710,1));f.Enemy["isCarrying"]=false;
        if(ownMechanic)f.Spells.Add(Spell(reference==4251?6011:6085,0,4,25,los:true,perTurn:1));
        return f;
    }
    private static void BrizlonCases(Action<bool,string> check)
    {
        foreach(int reference in new[]{4251,4280})
        {
            int spell=reference==4251?6011:6085;
            var f=Brizlon(reference);f.Self["ap"]=0;var r=f.Decide();
            check(Specific(r)&&Cast(r,spell,10),"Brizlon preserves its owned zero-AP prisoner offer "+reference);
            foreach(int state in new[]{4713,4712})
            {
                f=Brizlon(reference);States(f.Enemy,(state,1));r=f.Decide();
                check(!Specific(r)&&!Cast(r,spell)&&Cast(r,91001),"Brizlon falls back when the player already has "+state+" "+reference);
            }
            f=Brizlon(reference);States(f.Self);r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon does not place another mechanic after its protection ends "+reference);
            f=Brizlon(reference);f.Enemy["isPlayer"]=false;r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon requires an actual enemy player "+reference);
            f=Brizlon(reference);f.Enemy["isCarrying"]=true;r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon excludes a carrying player "+reference);
            f=Brizlon(reference);f.Enemy.Remove("isCarrying");r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon does not invent unknown carrying eligibility "+reference);
            f=Brizlon(reference);f.Enemy["cell"]=3;r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon keeps the original minimum range four "+reference);
            f=Brizlon(reference);f.Board["lineOfSight"]=Array.Empty<object>();r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon requires measured native line of sight "+reference);
            f=Brizlon(reference);f.Area(1173,4);r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"Brizlon does not duplicate its own trap covering the player "+reference);
            f=Brizlon(reference);f.Areas.Add(new{reference=1173,cell=4,cells=new[]{4},ownerId=-2L});r=f.Decide();
            check(Specific(r)&&Cast(r,spell,10),"Brizlon does not confuse another owner's trap with its own "+reference);
            f=Brizlon(reference);f.History.Add(new{type="cast",spellId=spell});r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"committed turn history stops a zero-AP Brizlon retry "+reference);
            f=Brizlon(reference);f.Usage.Add(new{spellId=spell,count=1,remainingCooldown=0});r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell),"native spell usage stops a second Brizlon cast "+reference);
            f=Brizlon(reference);f.History.Add(new{type="cast",spellId=91001});r=f.Decide();
            check(Specific(r)&&Cast(r,spell,10),"an unrelated actual cast does not consume the Brizlon mechanic "+reference);
            f=Brizlon(reference,false);r=f.Decide();
            check(!Specific(r)&&!Cast(r,spell)&&Cast(r,91001),"Brizlon does not manufacture a missing owned mechanic spell "+reference);
            f=Brizlon(reference);var first=f.Decide();f.Excluded.Add(Key(Action(first)));r=f.Decide();
            check(!Specific(r)&&Cast(r,91001)&&!r.GetProperty("alternatives").EnumerateArray().Any(a=>a.TryGetProperty("spellId",out var id)&&id.GetInt32()==spell),
                "rejected Brizlon advice falls back without resurfacing the zero-AP spell "+reference);
            f=Brizlon(reference);States(f.Enemy,(4712,1));var second=Actor(11,0,9,1,true);second["isCarrying"]=false;f.Actors.Add(second);r=f.Decide();
            check(Specific(r)&&Cast(r,spell,11),"Brizlon offers another eligible player instead of the existing prisoner "+reference);
        }
    }
    public static int Run()
    {
        int checks=0;void Check(bool ok,string name){if(!ok)throw new Exception("FAIL: "+name);Console.WriteLine("PASS: "+name);checks++;}
        var mapping=new Dictionary<int,string>{{2431,"security-waves"},{2448,"gelax-waves"},{2977,"ates-linked-summon"},{3022,"omeba-tentacles"},{5039,"bulb-attacker-mark"},{5040,"bulb-attacker-mark"},{3870,"ful-moon-native-mechanics"},{5500,"tal-kasha-native-wakfu"},{5664,"nox-native-calendar"},{4251,"brizlon-prisoner"},{4280,"brizlon-prisoner"}};
        foreach(var (reference,id) in mapping)
            Check(new Fixture(reference).Decide().GetProperty("strategyId").GetString()==id,"profile mapping stays explicit for reference"+reference);
        var f=new Fixture(999999);f.Spells.Add(Spell(3574,3,0,0,wp:1));var r=f.Decide();
        Check(Cast(r,91001)&&r.GetProperty("strategyId").GetString()=="normal-jondo","unknown monster keeps the ordinary planner");
        f=new Fixture(2431);f.Self["ap"]=4;f.Spells.Add(Spell(3574,3,0,0,wp:1,perTurn:1));f.Spells.Add(Spell(2120,1,0,0,damage:900));r=f.Decide();
        Check(Specific(r)&&Cast(r,3574,-1),"security spends real WP on a wave instead of suicide");
        foreach(var resource in new[]{"ap","wp"})
        {var limited=new Fixture(2431);limited.Self[resource]=resource=="ap"?1:0;limited.Spells.Add(Spell(3574,3,0,0,wp:1));limited.Spells.Add(Spell(2120,1,0,0,damage:900));var a=limited.Decide();Check(!Specific(a)&&!Cast(a,3574)&&!Cast(a,2120),"security respects missing "+resource+" without inventing a terminal cast");}
        f=new Fixture(2431);f.Spells.Add(Spell(3574,3,0,0,wp:1));f.Spells.Add(Spell(3575,3,0,0,wp:1));f.Usage.Add(new{spellId=3574,count=0,remainingCooldown=10});
        Check(Cast(f.Decide(),3575),"native cooldown redirects security to another owned wave");
        f=new Fixture(2431);f.Spells.Add(Spell(3574,3,0,0,wp:1));var first=f.Decide();f.Excluded.Add(Key(Action(first)));r=f.Decide();
        Check(!Specific(r)&&Cast(r,91001),"a rejected specific action falls back to a different ordinary action");
        f=new Fixture(2448);f.Spells.Add(Spell(3720,0,0,0,perTurn:1));States(f.Enemy,(1872,4));
        Check(Specific(f.Decide())&&Cast(f.Decide(),3720,-1),"Gelax casts at one authored counter threshold");
        foreach(var grade in new[]{3,5,21}){States(f.Enemy,(1872,grade));Check(!Specific(f.Decide())&&!Cast(f.Decide(),3720),"Gelax never forces an off-threshold wave"+grade);}
        States(f.Enemy,(1872,4));var counter=Actor(11,0,9,1,true);States(counter,(1872,7));f.Actors.Add(counter);
        Check(!Specific(f.Decide()),"ambiguous live Gelax counter holders prevent a forced wave");
        f=new Fixture(2977);States(f.Self,(2719,1));f.Spells.Add(Spell(4258,2,1,3,free:true,los:true,line:true));
        Check(Specific(f.Decide())&&Cast(f.Decide(),4258),"Ates offers its native linked summon while its gate is active");
        var link=Actor(20,2975,7,0,summoner:-2);f.Actors.Add(link);Check(Specific(f.Decide()),"an unrelated same-species summon does not block Ates");
        link["summonerId"]=-1L;Check(!Specific(f.Decide()),"Ates does not replace its own living linked summon");
        link["hp"]=0;Check(Specific(f.Decide()),"a dead linked summon can be replaced");States(f.Self);Check(!Specific(f.Decide())&&!Cast(f.Decide(),4258),"Ates stops offering the linked summon after its gate disappears");
        f=new Fixture(2977);States(f.Self,(2719,1));f.Spells.Add(Spell(4258,2,1,3,free:true,los:true,line:true));f.Native["specialAimCells"]=new[]{6};
        Check(!Specific(f.Decide()),"native linear restrictions reject a diagonal summon aim");
        f.Native["specialAimCells"]=new[]{1};f.Board["lineOfSight"]=Array.Empty<object>();Check(!Specific(f.Decide()),"unknown LOS never becomes a legal special cast");
        f=new Fixture(3022);f.Spells.Add(Spell(4189,2,1,40,perTurn:3));
        Check(!Specific(f.Decide())&&!Cast(f.Decide(),4189),"Omeba never substitutes arbitrary ground for area655");f.Area(655,6);r=f.Decide();
        Check(Specific(r)&&Cast(r,4189)&&Action(r).GetProperty("target").EnumerateArray().Select(v=>v.GetInt32()).SequenceEqual(new[]{1,1,0}),"Omeba targets the actual655 anchor");
        f.Usage.Add(new{spellId=4189,count=3,remainingCooldown=0});Check(!Specific(f.Decide()),"Omeba preserves its native three-cast limit");
        foreach(int reference in new[]{5039,5040}){f=new Fixture(reference);States(f.Self,(5935,1));f.Spells.Add(Spell(6761,4,1,9));f.Spells.Add(Spell(6762,1,1,9,damage:100));Check(Specific(f.Decide())&&Cast(f.Decide(),6761,10),"bulb native5937 mark beats the damage-only spell"+reference);States(f.Enemy,(5937,1));Check(!Specific(f.Decide()),"bulb does not remark an already marked player"+reference);}
        f=new Fixture(5039,1);States(f.Self,(5935,1),(5936,1));r=f.Decide();Check(Specific(r)&&Action(r).GetProperty("type").GetString()=="move","bulb uses a useful behind-player movement when its native mark listener is active");f.History.Add(new{type="move"});Check(!Specific(f.Decide()),"native history stops a second forced bulb movement");
        f=new Fixture(2977);States(f.Self,(2719,1));f.Spells.Add(Spell(4258,2,1,3,mp:1,free:true,los:true,line:true));
        Check(!Specific(f.Decide()),"specific casts cannot spend missing native MP");f.Self["mp"]=1;f.Self["maxMp"]=1;
        Check(Specific(f.Decide())&&Cast(f.Decide(),4258),"an affordable native MP cast remains available without walking away its MP");
        f=Moon();var enemyProp=Actor(90,3993,1,1);enemyProp["hp"]=5000;enemyProp["maxHp"]=5000;States(enemyProp,(4226,1));f.Actors.Insert(2,enemyProp);r=f.Decide();
        Check(Specific(r)&&Cast(r,5693)&&Action(r).GetProperty("targetId").GetInt64()>=100,"Moon hammers its own full-health prop rather than an enemy lookalike");
        f=Moon();foreach(var a in f.Actors.OfType<Dictionary<string,object>>().Where(a=>(int)a["monsterRef"] is 3993 or 3995 or 3996 or 3997))a["hp"]=4999;
        Check(!Specific(f.Decide()),"Moon does not repeat a hammer on a damaged prop without4227");
        f=Moon(true);Check(!Specific(f.Decide()),"Moon never hammers a4227 prop again");
        f=Moon(true,1);States(f.Self,(4214,1),(4212,0));States(f.Enemy,(4211,5));f.Area(1085,1);r=f.Decide();Check(Specific(r)&&Action(r).GetProperty("type").GetString()=="move","Moon uses an actual border only after all four props and player moons are ready");f.History.Add(new{type="move"});Check(!Specific(f.Decide()),"native history bounds Moon forced movement to one paid step sequence per turn");
        f=Moon(true,1);States(f.Self,(4214,1),(4212,5));States(f.Enemy,(4211,5));f.Area(1086,1);Check(Specific(f.Decide()),"Moon returns toward its original1086 glyph after earning five moons");f.Self["cell"]=1;Check(!Specific(f.Decide()),"Moon stops its forced stroll once already on1086");
        f=Moon(true,1);States(f.Self,(4214,1));f.Area(1085,1);
        Check(!Specific(f.Decide()),"Moon cannot force border farming before a player has five moons");
        States(f.Enemy,(4211,5));f.Areas.Clear();Check(!Specific(f.Decide()),"Moon does not invent border cells when1085 is absent");
        f.Area(1085,1);f.Self["team"]=1;f.Enemy["team"]=0;
        Check(!Specific(f.Decide()),"Moon border farming is restricted to its native team-zero contract");
        f=new Fixture(5500,1);f.Self["wp"]=19;Check(!Specific(f.Decide()),"Tal Kasha requires its original8231 listener before forcing Wakfu movement");
        f=new Fixture(5500,1);States(f.Self,(8231,1));f.Self["wp"]=19;Check(Specific(f.Decide()),"Tal Kasha gains native Wakfu with one useful paid move below20");f.Self["wp"]=20;Check(!Specific(f.Decide()),"Tal Kasha stops forcing movement at20WP");f.Self["wp"]=19;f.History.Add(new{type="portal_travel"});Check(!Specific(f.Decide()),"portal movement history also blocks a second Tal Kasha forced step");
        f=new Fixture(5664,1);States(f.Self,(8978,1),(8979,1));f.Native["noxCalendarManaged"]=true;r=f.Decide();Check(!Specific(r)&&r.GetProperty("strategyId").GetString()=="nox-native-calendar","managed Nox calendar never receives a forced phase stroll");
        BrizlonCases(Check);
        return checks;
    }
}
