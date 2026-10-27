using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

internal static class AoeQualityCases
{
    public static int Run()
    {
        int checks=0;var failures=new List<string>();
        void Check(bool ok,string name)
        { checks++;Console.WriteLine((ok?"PASS: ":"FAIL: ")+name);if(!ok)failures.Add(name); }
        var cells=(from y in Enumerable.Range(-5,13) from x in Enumerable.Range(-3,12)
                   select new CellXYZ(x,y,0)).ToArray();
        int At(int x,int y)=>Array.FindIndex(cells,p=>p.X==x&&p.Y==y);
        var edges=cells.SelectMany((p,i)=>new[]{(p.X+1,p.Y),(p.X-1,p.Y),(p.X,p.Y+1),(p.X,p.Y-1)}
            .Select(q=>At(q.Item1,q.Item2)).Where(j=>j>=0).Select(j=>(i,j))).ToArray();
        // Exact native anu circle, anw cross and anx diagonal offsets exported
        // by combat_effect_targets.area_offsets; no legacy zone approximation.
        var circle1=(from y in Enumerable.Range(-1,3) from x in Enumerable.Range(-1,3)
                     where Math.Abs(x)+Math.Abs(y)<=1 select (x,y)).ToArray();
        var circle2=(from y in Enumerable.Range(-2,5) from x in Enumerable.Range(-2,5)
                     where Math.Abs(x)+Math.Abs(y)<=2 select (x,y)).ToArray();
        var cross2=Enumerable.Range(-2,5).SelectMany(n=>new[]{(n,0),(0,n)}).Distinct().ToArray();
        var diagonal2=Enumerable.Range(-2,5).Select(n=>(n,n)).ToArray();
        Fighter F(long id,int team,int x,int y,int radius=0)=>new(){Id=id,TeamId=team,
            CellId=At(x,y),NativePhysicalRadius=radius,CurrentHP=100,MaxHP=100,
            CurrentAP=team==0&&id==1?3:0,MaxAP=3,CurrentMP=0,MaxMP=0,Level=10,IsMonster=true};
        void Scene(string name,(int,int)[] offsets,Fighter[] opponents,int expectedHits,bool friendly=false)
        {
            using var geometry=MapGeometry.BeginScope(new GeometryContext(cells,edges));
            var caster=F(1,0,2,-4);var actors=new[]{caster}.Concat(opponents).ToArray();
            foreach(var actor in actors)_=MonsterTactics.FootprintAt(actor,actor.CellId,true).ToArray();
            var rows=new List<SpellEffect>{SemanticRows.WithOffsets(SemanticRows.Create("damage",20,"enemy"),offsets)};
            if(friendly)rows.Add(SemanticRows.WithOffsets(SemanticRows.Create("damage",20,"ally"),offsets));
            var spell=new MonsterTactics.Spell{Id=7801,Grade=1,Cost=3,MinRange=1,MaxRange=12,
                Damage=20,Rows=rows};
            var board=new MonsterTactics.Board{Fighters=actors,Sees=(_,_)=>true,
                Reach=(r,c,f,a)=>Planner.NativeReach(actors,r,c,f,a)};
            var enemies=actors.Where(f=>f.TeamId!=caster.TeamId).ToList();
            var allies=actors.Where(f=>f.TeamId==caster.TeamId).ToList();
            double Value(int aim)=>MonsterTactics.ValueOfCast(board,spell,caster,caster.CellId,aim,enemies,allies,enemies[0]);
            var best=Enumerable.Range(0,cells.Length).Where(a=>MapGeometry.Distance(caster.CellId,a) is >=1 and <=12)
                .OrderByDescending(Value).First();
            var plan=MonsterTactics.PlanTurn(board,caster,new[]{spell},budgetMs:1000);
            int selected=plan.Count>0?plan[0].TargetCell:-1;
            int hits=selected<0?0:Planner.NativeReach(actors,rows[0],caster,caster.CellId,selected).Count;
            string detail=$"{name}: chosen={(selected<0?"none":cells[selected].ToString())} hits={hits}, best={cells[best]} value={(selected<0?0:Value(selected))}/{Value(best)}";
            Console.WriteLine("EVIDENCE: "+detail);
            Check(selected>=0&&Value(selected)>=Value(best)-1e-8&&hits==expectedHits,"whole-turn AoE maximizes useful recipients: "+detail);
            using(var sim=MonsterTactics.Simulation.Replay(board,caster,plan))
                Check(enemies.Count(f=>f.CurrentHP==80)==expectedHits,"AoE replay damages each recipient exactly once: "+name);
            Check(caster.CurrentAP==3&&actors.All(a=>a.CurrentHP==100),"AoE forecast restores source HP/AP: "+name);
            var request=JsonSerializer.SerializeToElement(new{protocol=1,requestId="aoe-"+name,
                source=new{actorId=1L,fightInstanceId="aoe-"+name,turnId=1,catalogRevision="aoe-exact-offsets-v1"},
                board=new{cells=cells.Select((p,id)=>new{id,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
                    edges=edges.Select(e=>new[]{e.i,e.j}).ToArray(),
                    actors=actors.Select(a=>new{id=a.Id,team=a.TeamId,cell=a.CellId,hp=100,maxHp=100,
                        ap=a.CurrentAP,mp=0,physicalRadius=a.NativePhysicalRadius}).ToArray()},
                spells=new[]{new{id=7801,grade=1,cost=3,minRange=1,maxRange=12,damage=20,
                    rows=rows.Select((r,i)=>new{kind="damage",amount=20,target=i==0?"enemy":"ally",
                        nativeInArea=true,fixedCells=offsets.Select(o=>new[]{o.Item1,o.Item2}).ToArray()}).ToArray()}},
                native=new{usage=Array.Empty<object>()},limits=new{budgetMs=1000}});
            string original=request.GetRawText();
            var action=JsonSerializer.SerializeToElement(Planner.Decide(request)).GetProperty("action");
            int hostAim=action.GetProperty("type").GetString()=="cast"?
                At(action.GetProperty("target")[0].GetInt32(),action.GetProperty("target")[1].GetInt32()):-1;
            Check(hostAim>=0&&Value(hostAim)>=Value(best)-1e-8,"actual Host exact fixedCells selects maximum-value AoE: "+name+" action="+action);
            Check(request.GetRawText()==original,"Host preserves original AoE snapshot: "+name);
        }
        Scene("three-versus-one",circle1,new[]{F(2,1,0,0),F(3,1,1,0),F(4,1,0,1),F(5,1,6,4)},3);
        Scene("empty-neighbor-center",circle1,new[]{F(2,1,0,0),F(3,1,2,0),F(4,1,1,1)},3);
        Scene("friendly-fire",circle1,new[]{F(2,1,0,0),F(3,1,1,0),F(4,1,0,1),F(5,0,0,-1)},2,true);
        Scene("large-body-counted-once",circle1,new[]{F(2,1,0,0,1),F(3,1,4,0),F(4,1,6,0)},2);
        Scene("circle-radius-two-gap",circle2,new[]{F(2,1,0,0),F(3,1,4,0)},2);
        Scene("cross-radius-two-gap",cross2,new[]{F(2,1,0,0),F(3,1,4,0)},2);
        Scene("diagonal-radius-two-gap",diagonal2,new[]{F(2,1,0,0),F(3,1,4,4)},2);
        using(MapGeometry.BeginScope(new GeometryContext(cells,edges)))
        {
            var caster=F(1,0,2,-4);var foes=new[]{F(2,1,0,0),F(3,1,4,0)};
            var actors=new[]{caster}.Concat(foes).ToArray();
            var wide=(from y in Enumerable.Range(-20,41) from x in Enumerable.Range(-20,41)
                      where Math.Abs(x)+Math.Abs(y)<=20 select (x,y)).ToArray();
            var row=SemanticRows.WithOffsets(SemanticRows.Create("damage",20,"enemy"),wide);
            var spell=new MonsterTactics.Spell{Id=7802,Grade=1,Cost=3,MinRange=1,MaxRange=12,
                Damage=20,Rows=new[]{row}};
            int polls=0,reachCalls=0;
            var board=new MonsterTactics.Board{Fighters=actors,Sees=(_,_)=>true,
                Reach=(r,c,f,a)=>{reachCalls++;return Planner.NativeReach(actors,r,c,f,a);}};
            var plan=MonsterTactics.PlanTurn(board,caster,new[]{spell},budgetMs:1000,
                continueSearch:()=>++polls<100);
            Check(plan.Count==1&&reachCalls>0,"inverse-area deadline retains an already evaluated ordinary cast");
            Check(polls<110&&reachCalls<30,"wide native inverse work cooperatively stops within the deterministic polling bound");
            Check(caster.CurrentAP==3&&foes.All(f=>f.CurrentHP==100),"interrupted inverse-area search restores source HP/AP");
            var many=cells.Where(p=>p.Y>=0).Take(70).Select((p,i)=>F(i+2,1,p.X,p.Y)).Prepend(caster).ToArray();
            board=board with{Fighters=many,Reach=(r,c,f,a)=>Planner.NativeReach(many,r,c,f,a)};
            var timer=System.Diagnostics.Stopwatch.StartNew();
            var stressed=MonsterTactics.PlanTurn(board,caster,new[]{spell},budgetMs:100);
            Check(timer.ElapsedMilliseconds<1000&&stressed.Count>0,
                "70 actors / 841 native offsets retain a useful answer within a bounded short-budget search; elapsedMs="+timer.ElapsedMilliseconds);
            Check(caster.CurrentAP==3&&many.All(f=>f.CurrentHP==100),"high-branch native-area planning restores source HP/AP");
        }
        if(failures.Count>0)throw new Exception($"{failures.Count}/{checks} AoE quality checks failed:\n"+string.Join("\n",failures));
        return checks;
    }
}
