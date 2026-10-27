using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

internal static class DirectionalAreaCases
{
    public static int Run(bool geometryOnly=false)
    {
        int checks=0;
        void Check(bool value,string name)
        { checks++;if(!value)throw new Exception("FAIL: "+name); }
        CellXYZ Cell(JsonElement value)=>new(value[0].GetInt32(),value[1].GetInt32(),value[2].GetInt32());
        (int,int) Pair(JsonElement value)=>(value[0].GetInt32(),value[1].GetInt32());
        using var document=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "Fixtures","NativeDirectionalGeometryGoldens.json")));
        var root=document.RootElement;
        Check(root.GetProperty("schema").GetString()=="world-native-directional-geometry-goldens-v1",
            "independent World oracle schema");
        var shapes=root.GetProperty("shapes").EnumerateArray().ToDictionary(
            x=>x.GetProperty("id").GetString()!,x=>x.GetProperty("rawOffsets").EnumerateArray().Select(Pair).ToArray());
        var isotropic=root.GetProperty("shapes").EnumerateArray().ToDictionary(
            x=>x.GetProperty("id").GetString()!,x=>x.GetProperty("isotropic").GetBoolean());
        int memberships=0;
        foreach(var row in root.GetProperty("cases").EnumerateArray())
        {
            string id=row.GetProperty("id").GetString()!;
            string shapeId=row.GetProperty("shapeId").GetString()!;
            var area=new NativeDirectionalArea(shapes[shapeId],true);
            var origin=Cell(row.GetProperty("origin"));var reference=Cell(row.GetProperty("reference"));
            // The isotropic control has no rotation in World. Exercise its
            // local membership through the identity transform; the actual
            // descriptor parser separately rejects isotropic directional DTOs.
            var areaReference=isotropic[shapeId]?new CellXYZ(origin.X-1,origin.Y,origin.Z):reference;
            int direction=row.GetProperty("direction").GetInt32();
            Check(NativeDirectionalArea.Rotation(origin,reference,direction,out var rotation)
                &&rotation==Pair(row.GetProperty("rotation")),"World rotation: "+id);
            Check(area.Forward(origin,areaReference,direction).ToHashSet().SetEquals(
                row.GetProperty("forwardOffsets").EnumerateArray().Select(Pair)),"World forward points: "+id);
            foreach(var witness in row.GetProperty("memberships").EnumerateArray())
            {
                memberships++;
                Check(area.Contains(origin,areaReference,direction,Cell(witness.GetProperty("point")),
                    witness.GetProperty("radius").GetInt32())==witness.GetProperty("contains").GetBoolean(),
                    "World transpose/radius membership: "+id+" "+witness);
            }
        }
        Check(memberships==root.GetProperty("counts").GetProperty("memberships").GetInt32(),
            "every independently exported membership was checked");
        var diagonal=new NativeDirectionalArea(new[]{(1,0)},true);
        Check(!diagonal.Contains(new CellXYZ(0,0,0),new CellXYZ(0,0,9),0,new CellXYZ(1,-1,0),0),
            "coincident diagonal forward enumeration is not transpose membership");
        Check(diagonal.Contains(new CellXYZ(0,0,0),new CellXYZ(0,0,9),0,new CellXYZ(1,0,100),1),
            "target radius expands native local coordinates and ignores altitude");
        Check(!NativeDirectionalArea.Rotation(new CellXYZ(0,0,0),new CellXYZ(0,0,0),8,out _),
            "invalid coincident facing has no invented orientation");
        Console.WriteLine($"PASS: {checks} pure native geometry checks including {memberships} independent World memberships");
        if(geometryOnly)return checks;

        using(var selectors=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "Fixtures","NativeTargetSelectionGoldens.json"))))
        {
            var data=selectors.RootElement;
            var samples=data.GetProperty("cases").EnumerateArray().ToArray();
            var sourceActors=data.GetProperty("actors").EnumerateArray().ToArray();
            var points=sourceActors.Select(a=>Cell(a.GetProperty("position")))
                .Concat(samples.Select(c=>Cell(c.GetProperty("aim")))).Distinct().ToArray();
            int Index(CellXYZ point)=>Array.IndexOf(points,point);
            using var selectorScope=MapGeometry.BeginScope(new GeometryContext(points,Array.Empty<(int,int)>()));
            var actors=sourceActors.Select(a=>new Fighter{Id=a.GetProperty("id").GetInt64(),
                TeamId=a.GetProperty("team").GetInt32(),CellId=Index(Cell(a.GetProperty("position"))),
                CurrentHP=a.GetProperty("hp").GetInt32(),MaxHP=a.GetProperty("maxHp").GetInt32(),
                NativeDirection=a.GetProperty("direction").GetInt32(),
                NativePhysicalRadius=a.GetProperty("physicalRadius").GetInt32(),IsMonster=true}).ToArray();
            foreach(var sample in samples)
            {
                string id=sample.GetProperty("id").GetString()!;
                string shape=sample.GetProperty("shapeId").GetString()!;
                (int,int)[] offsets=shape switch{
                    "point"=>new[]{(0,0)},"circle1"=>new[]{(0,0),(1,0),(-1,0),(0,1),(0,-1)},
                    "rectangle"=>shapes["directedRectangle"],_=>shapes[shape]};
                bool center=sample.GetProperty("nativeAreaCenterOnCaster").GetBoolean();
                bool radius=sample.GetProperty("nativeAreaUseTargetRadius").GetBoolean();
                bool inArea=sample.GetProperty("nativeInArea").GetBoolean();
                var caster=actors.Single(a=>a.Id==sample.GetProperty("casterId").GetInt64());
                int aim=Index(Cell(sample.GetProperty("aim")));
                var recipients=new HashSet<long>();
                foreach(var relation in sample.GetProperty("relations").EnumerateArray())
                {
                    var row=SemanticRows.WithOffsets(SemanticRows.Create("damage",20,relation.GetString()!),offsets);
                    SemanticRows.WithNativeAreaPolicy(row,center,radius);
                    if(shape is not "point" and not "circle1")
                        SemanticRows.WithDirectionalArea(row,offsets,radius,center);
                    NativeAreaPolicy.Bind(row,inArea);
                    foreach(var target in Planner.NativeReach(actors,row,caster,caster.CellId,aim))
                        recipients.Add(target.Id);
                }
                var actual=actors.Where(a=>recipients.Contains(a.Id)).Select(a=>a.Id).ToArray();
                var expected=sample.GetProperty("selectedIds").EnumerateArray().Select(v=>v.GetInt64()).ToArray();
                Check(actual.SequenceEqual(expected),"actual public World recipient selection: "+id+
                    " actual="+string.Join(',',actual)+" expected="+string.Join(',',expected));
            }
            Check(samples.Length==data.GetProperty("counts").GetProperty("cases").GetInt32(),
                "all public World selector cases were consumed");
            Console.WriteLine($"PASS: {samples.Length} independent public World selector cases");
        }

        var cells=(from y in Enumerable.Range(-5,13) from x in Enumerable.Range(-6,15)
                   select new CellXYZ(x,y,0)).ToArray();
        int At(int x,int y)=>Array.FindIndex(cells,p=>p.X==x&&p.Y==y);
        var edges=cells.SelectMany((p,i)=>new[]{(p.X+1,p.Y),(p.X-1,p.Y),(p.X,p.Y+1),(p.X,p.Y-1)}
            .Select(q=>At(q.Item1,q.Item2)).Where(j=>j>=0).Select(j=>(i,j))).ToArray();
        using var scope=MapGeometry.BeginScope(new GeometryContext(cells,edges));
        Fighter F(long id,int team,int x,int y,int mp=0,int radius=0)=>new(){Id=id,TeamId=team,
            CellId=At(x,y),CurrentHP=100,MaxHP=100,CurrentAP=id==1?3:0,MaxAP=3,
            CurrentMP=mp,MaxMP=mp,NativePhysicalRadius=radius,NativeDirection=1,IsMonster=true};
        void Scene(string name,int mp,int radius,bool centerOnCaster=false,bool rectangle=false)
        {
            int casterX=centerOnCaster?-1:-4;
            var caster=F(1,0,casterX,0,mp);var foes=centerOnCaster?
                new[]{F(2,1,0,0),F(3,1,1,1),F(4,1,1,-1)}:
                rectangle?new[]{F(2,1,0,0),F(3,1,2,0),F(4,1,3,0),F(5,1,-3,4)}:
                new[]{F(2,1,0,0,0,radius),F(3,1,2,1),F(4,1,2,-1),F(5,1,-3,4)};
            var ally=rectangle?F(10,0,1,1):null;
            var actors=new[]{caster}.Concat(foes).Concat(ally==null?Array.Empty<Fighter>():new[]{ally}).ToArray();
            foreach(var f in actors)_=MonsterTactics.FootprintAt(f,f.CellId,true).ToArray();
            var offsets=shapes[rectangle?"directedRectangle":"cone3"];
            var row=SemanticRows.WithDirectionalArea(SemanticRows.WithOffsets(
                SemanticRows.Create("damage",20,"enemy"),offsets),offsets,!centerOnCaster,centerOnCaster);
            var rows=new List<SpellEffect>{row};
            if(rectangle)rows.Add(SemanticRows.WithDirectionalArea(SemanticRows.WithOffsets(
                SemanticRows.Create("damage",20,"ally"),offsets),offsets,true));
            var spell=new MonsterTactics.Spell{Id=7991,Grade=1,Cost=3,MinRange=1,MaxRange=8,
                Damage=20,Rows=rows};
            var board=new MonsterTactics.Board{Fighters=actors,Sees=(_,_)=>true,
                Reach=(r,c,f,a)=>Planner.NativeReach(actors,r,c,f,a)};
            var enemies=foes.ToList();var allies=actors.Where(a=>a.TeamId==caster.TeamId).ToList();
            double Value(int from,int aim)=>MonsterTactics.ValueOfCast(board,spell,caster,from,aim,enemies,allies,foes[0]);
            double best=Enumerable.Range(0,cells.Length).Where(from=>MapGeometry.Distance(caster.CellId,from)<=mp
                    &&MonsterTactics.CanOccupy(board,caster,from))
                .SelectMany(from=>Enumerable.Range(0,cells.Length).Where(aim=>MapGeometry.Distance(from,aim) is >=1 and <=8)
                    .Select(aim=>Value(from,aim))).Max();
            var plan=MonsterTactics.PlanTurn(board,caster,new[]{spell},budgetMs:1000);
            Check(plan.Count>0&&Value(plan[0].From,plan[0].TargetCell)>=best-1e-8,
                "directional origin/aim search reaches exhaustive optimum: "+name);
            using(var replay=MonsterTactics.Simulation.Replay(board,caster,plan))
            {
                Check(foes.Count(f=>f.CurrentHP<100)==3,"native directional replay reaches all three actors once: "+name);
                if(ally!=null)Check(ally.CurrentHP==100,"non-square native rectangle avoids actual friendly fire");
            }
            if(centerOnCaster)Check(cells[plan[0].TargetCell].X<cells[plan[0].From].X,
                "NULL selector steers opposite the enemies because reference is aim: "+name);
            Check(caster.CurrentAP==3&&caster.CurrentMP==mp&&caster.CellId==At(casterX,0)
                &&actors.All(f=>f.CurrentHP==100),"directional forecast restores complete source: "+name);
            var request=JsonSerializer.SerializeToElement(new{protocol=1,requestId="directional-"+name,
                source=new{actorId=1L,fightInstanceId="directional-"+name,turnId=1,catalogRevision="directional-oracle-v1"},
                board=new{cells=cells.Select((p,id)=>new{id,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
                    edges=edges.Select(e=>new[]{e.i,e.j}).ToArray(),actors=actors.Select(a=>new{id=a.Id,team=a.TeamId,
                        cell=a.CellId,hp=100,maxHp=100,ap=a.CurrentAP,mp=a.CurrentMP,physicalRadius=a.NativePhysicalRadius,direction=1}).ToArray()},
                spells=new[]{new{id=7991,grade=1,cost=3,minRange=1,maxRange=8,damage=20,
                    rows=rows.Select((r,index)=>new{kind="damage",amount=20,target=index==0?"enemy":"ally",nativeInArea=true,
                        fixedCells=Array.Empty<int[]>(),
                        nativeAreaCenterOnCaster=centerOnCaster,nativeAreaUseTargetRadius=!centerOnCaster,
                        nativeDirectionalArea=new{version=1,isotropic=false,useTargetRadius=!centerOnCaster,centerOnCaster,
                            rawOffsets=offsets.Select(p=>new[]{p.Item1,p.Item2}).ToArray()}}).ToArray()}},
                native=new{usage=Array.Empty<object>()},limits=new{budgetMs=1000}});
            var original=request.GetRawText();var reply=JsonSerializer.SerializeToElement(Planner.Decide(request));
            var action=reply.GetProperty("action");
            Check(action.GetProperty("type").GetString() is "cast" or "move",
                "actual Host retains useful directional choice: "+name);
            if(action.GetProperty("type").GetString()=="cast")
            {
                int aim=At(action.GetProperty("target")[0].GetInt32(),action.GetProperty("target")[1].GetInt32());
                Check(Value(caster.CellId,aim)>=best-1e-8,"actual Host directional optimum: "+name);
            }
            Check(request.GetRawText()==original,"Host leaves directional DTO unchanged: "+name);
        }
        Scene("stationary",0,0);
        Scene("moving-origin",2,0);
        Scene("three-by-three-target",0,1);
        Scene("null-selector-caster-origin",0,0,true);
        Scene("null-selector-moving-origin",2,0,true);
        Scene("non-square-rectangle-friendly-fire",0,0,rectangle:true);
        {
            var walkingCells=new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(1,0,2),
                new CellXYZ(1,-1,2),new CellXYZ(6,7,2),new CellXYZ(7,7,2),new CellXYZ(3,0,0)};
            using var walkingGeometry=MapGeometry.BeginScope(new GeometryContext(walkingCells,
                new[]{(0,1),(1,2),(2,3),(4,5)}));
            var walker=new Fighter{Id=31,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100,
                CurrentAP=3,MaxAP=3,CurrentMP=1,MaxMP=1,NativeDirection=3,IsMonster=true};
            var enemy=new Fighter{Id=32,TeamId=1,CellId=6,CurrentHP=100,MaxHP=100,IsMonster=true};
            var actors=new[]{walker,enemy};
            var board=new MonsterTactics.Board{Fighters=actors,Reach=(r,c,f,a)=>Planner.NativeReach(actors,r,c,f,a)};
            Check(NativeDirectionalArea.DirectionAfterPath(board,new[]{0,1},3)==1,"ordinary east step uses actual World east facing");
            Check(NativeDirectionalArea.DirectionAfterPath(board,new[]{0,1,2},3)==1,"vertical step preserves last real walking facing");
            Check(NativeDirectionalArea.DirectionAfterPath(board,new[]{0,1,2,3},3)==7,"last ordinary step supplies north facing");
            Check(NativeDirectionalArea.DirectionAfterPath(board,new[]{3,4},3)==-1,"unrecognized jump has no invented facing");
            Check(NativeDirectionalArea.DirectionAfterPath(board with{IsPortalTravel=(from,to)=>from==3&&to==4},
                new[]{3,4},3)==3,"source-qualified portal travel preserves native facing");
            Check(NativeDirectionalArea.DirectionAfterPath(board,new[]{3,4,5},3)==1,"actual walk after unknown relocation supplies fresh facing");
            var offsets=shapes["cone3"];
            var row=SemanticRows.WithDirectionalArea(SemanticRows.WithOffsets(
                SemanticRows.Create("damage",20,"enemy"),offsets),offsets,true);
            var spell=new MonsterTactics.Spell{Id=7992,Cost=3,MinRange=0,MaxRange=0,
                Rows=new[]{row},Damage=20};
            var plan=MonsterTactics.PlanTurn(board,walker,new[]{spell},budgetMs:1000);
            Check(plan.Count==1&&plan[0].Path.SequenceEqual(new[]{0,1}),
                "planner walks east before a useful coincident directional cast instead of using stale south facing");
            using(var replay=MonsterTactics.Simulation.Replay(board,walker,plan))
                Check(walker.NativeDirection==1&&enemy.CurrentHP==80,"actual replay uses walking facing for native coincident membership");
            Check(walker.NativeDirection==3&&walker.CellId==0&&walker.CurrentAP==3&&walker.CurrentMP==1&&enemy.CurrentHP==100,
                "directional walking replay restores original direction, position, resources and HP");

            var ally=new Fighter{Id=33,TeamId=0,CellId=6,CurrentHP=100,MaxHP=100,IsMonster=true};
            var supportBoard=board with{Fighters=new[]{walker,ally}};
            var supportSpell=new MonsterTactics.Spell{Id=7993,Cost=3,MinRange=0,MaxRange=0,Utility=1};
            var supportRequest=JsonSerializer.SerializeToElement(new{board=new{actors=new[]{
                new{id=31L,wp=0},new{id=33L,wp=0}}},native=new{turnActions=Array.Empty<object>()},
                spells=new[]{new{id=7993,rows=Array.Empty<object>(),nativeSupport=new{version=1,
                    aimKinds=new[]{"self"},intents=new[]{"state"},summons=Array.Empty<object>(),
                    effects=new[]{new{kind="add_state",stateId=8881,stateLevel=1,targets=new[]{"ally"},
                        benefit="beneficial",probability=100,conditional=false,confidence="known",nativeReference=79930,
                        nativeAreaCenterOnCaster=false,nativeAreaUseTargetRadius=true,
                        nativeDirectionalArea=new{version=1,isotropic=false,centerOnCaster=false,useTargetRadius=true,
                            rawOffsets=offsets.Select(p=>new[]{p.Item1,p.Item2}).ToArray()}}}}}}});
            var candidates=NativeSupportCandidates.Propose(supportRequest,supportBoard,walker,new[]{supportSpell},
                walkingCells,_=>(3,0,0),new HashSet<(int,int)>());
            var supportAction=candidates.Count==0?default:JsonSerializer.SerializeToElement(candidates[0].Action);
            Check(candidates.Count>0&&supportAction.GetProperty("type").GetString()=="move"
                &&supportAction.GetProperty("path").GetArrayLength()==1
                &&supportAction.GetProperty("path")[0].EnumerateArray().Select(p=>p.GetInt32()).SequenceEqual(new[]{1,0,0}),
                "support-only provider values directional benefit using the proposed route's actual walking facing");
            Check(walker.NativeDirection==3&&walker.CellId==0&&walker.CurrentAP==3&&walker.CurrentMP==1,
                "support candidate evaluation restores original actor facing and resources");
        }
        foreach(var invalid in new[]{"{}","{\"version\":2,\"isotropic\":false,\"useTargetRadius\":true,\"rawOffsets\":[[1,0]]}",
            "{\"version\":1,\"isotropic\":false,\"rawOffsets\":[[1,0]]}",
            "{\"version\":1,\"isotropic\":true,\"useTargetRadius\":true,\"rawOffsets\":[[1,0]]}"})
        {
            using var malformed=JsonDocument.Parse(invalid);bool rejected=false;
            try{NativeDirectionalArea.Parse(malformed.RootElement);}catch(ArgumentException){rejected=true;}
            Check(rejected,"malformed native directional DTO fails closed: "+invalid);
        }
        Console.WriteLine($"PASS: {checks} directional geometry checks, including {memberships} independent World memberships");
        return checks;
    }
}
