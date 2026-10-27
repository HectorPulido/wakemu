using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

internal static class FootprintCases
{
    public static int Run()
    {
var cells=Enumerable.Range(0,49).Select(i=>new CellXYZ(i%7,i/7,0)).ToArray();
int At(int x,int y)=>y*7+x;
var edges=Enumerable.Range(0,49).SelectMany(i=>Enumerable.Range(0,49).Where(j=>Math.Abs(cells[i].X-cells[j].X)+Math.Abs(cells[i].Y-cells[j].Y)==1).Select(j=>(i,j))).ToArray();
int checks=0;
void Check(bool value,string name){if(!value)throw new Exception(name);checks++;Console.WriteLine("PASS: "+name);}
Fighter F(long id,int team,int x,int y,int radius=0,int mp=0)=>new(){Id=id,TeamId=team,CellId=At(x,y),NativePhysicalRadius=radius,CurrentHP=100,MaxHP=100,CurrentAP=6,MaxAP=6,CurrentMP=mp,MaxMP=mp};
using(MapGeometry.BeginScope(new GeometryContext(cells,edges)))
{
var self=F(1,0,2,2,1,2); self.ExtraCells.AddRange(Enumerable.Range(1,3).SelectMany(y=>Enumerable.Range(1,3).Select(x=>At(x,y))).Where(c=>c!=self.CellId));
var original=self.ExtraCells.ToArray();var board=new MonsterTactics.Board{Fighters=new[]{self}};
Check(MonsterTactics.Routes(board,self).ContainsKey(At(3,2)),"3x3 own overlap should allow step");
Check(MonsterTactics.Routes(board,self).ContainsKey(At(4,2)),"3x3 should translate through own old edge");
Check(!MonsterTactics.Routes(board,self).ContainsKey(At(0,2)),"3x3 must not clip map edge");
foreach(bool weighted in new[]{false,true}){
var blocker=F(2,1,4,3);var blocked=board with{Fighters=new[]{self,blocker},MovementDanger=weighted? _=>1:null};
Check(!MonsterTactics.Routes(blocked,self).ContainsKey(At(3,2)),"translated body corner hits other actor");
Check(!MonsterTactics.Routes(board with{Walkable=c=>c!=At(4,3),MovementDanger=weighted? _=>1:null},self).ContainsKey(At(3,2)),"translated body corner hits terrain");
}
Check(!MonsterTactics.CanOccupy(board with{Walkable=c=>c!=At(4,3)},self,At(3,2)),"all cells walkable required");
self.CellId=At(3,2);
Check(board.Occupied(At(4,3)),"simulated footprint translates");
Check(!board.Occupied(At(1,2)),"simulated footprint vacates old tail");
self.CellId=At(2,2);
Check(self.ExtraCells.SequenceEqual(original),"shape capture did not mutate ExtraCells");
var attacker=F(10,0,0,3);var giant=F(11,1,2,3,1);
var row=SemanticRows.Create("damage",20,"enemy");
var fight=new MonsterTactics.Board{Fighters=new[]{attacker,giant},Sees=(_,_)=>true,Reach=(r,c,f,a)=>Planner.NativeReach(new[]{attacker,giant},r,c,f,a)};
var spell=new MonsterTactics.Spell{Id=77,Grade=1,Cost=3,MinRange=1,MaxRange=1,Damage=20,Rows=new[]{row}};
Check(Planner.NativeReach(new[]{attacker,giant},row,attacker,attacker.CellId,At(1,3)).Count==1,"point hits occupied side of 3x3");
var opts=MonsterTactics.Options(fight,attacker,new[]{spell});
Check(opts.Any(o=>o.Target==giant&&o.TargetCell==At(1,3)),"3x3 side aim emitted");
Check(MonsterTactics.Revalidate(fight,attacker,opts.First())!=null,"side target survives continuation revalidation");
var plan=MonsterTactics.PlanTurn(fight,attacker,new[]{spell},budgetMs:1000);
Check(plan.Count==2,"side target supports two-cast replay");
Check(giant.CurrentHP==100&&attacker.CurrentAP==6,"private replay fully restored HP/AP");
Check(self.ExtraCells.SequenceEqual(original)&&self.CellId==At(2,2),"planning retained source shape and anchor");
var tooFar=spell;
var largeSource=F(30,0,2,2,1);var distant=F(31,1,4,2);
Check(!MonsterTactics.Options(fight with{Fighters=new[]{largeSource,distant},Reach=(r,c,f,a)=>Planner.NativeReach(new[]{largeSource,distant},r,c,f,a)},largeSource,new[]{tooFar}).Any(),"large source must not extend spell range from body side");
}

var raised=cells.Concat(cells.Select(p=>new CellXYZ(p.X,p.Y,1))).ToArray();
int raisedAnchor=49+At(3,2);
var layered=F(99,0,2,2,1,1);
using(MapGeometry.BeginScope(new GeometryContext(raised,new[]{(At(2,2),raisedAnchor)})))
{
    Check(MonsterTactics.Routes(new MonsterTactics.Board{Fighters=new[]{layered}},layered).ContainsKey(raisedAnchor),
        "complete 3x3 body follows an explicit directed height edge");
}
using(MapGeometry.BeginScope(new GeometryContext(raised,new[]{(raisedAnchor,At(2,2))})))
{
    Check(!MonsterTactics.Routes(new MonsterTactics.Board{Fighters=new[]{layered}},layered).ContainsKey(raisedAnchor),
        "large-body routing never invents a reverse height edge");
}
var missingCorner=raised.Where(p=>p!=new CellXYZ(4,3,1)).ToArray();
using(MapGeometry.BeginScope(new GeometryContext(missingCorner,new[]{(At(2,2),raisedAnchor)})))
{
    Check(MonsterTactics.Routes(new MonsterTactics.Board{Fighters=new[]{layered}},layered).ContainsKey(raisedAnchor),
        "a missing corner altitude is legal when its native XY column remains walkable");
}
using(MapGeometry.BeginScope(new GeometryContext(raised,Array.Empty<(int,int)>())))
{
    Check(!MonsterTactics.Routes(new MonsterTactics.Board{Fighters=new[]{layered}},layered).ContainsKey(raisedAnchor),
        "height-adjacent cells without an owned edge remain unreachable");
}
var request=JsonSerializer.SerializeToElement(new{
    protocol=1,requestId="actual-host-large-target",source=new{actorId=10L},
    board=new{cells=cells.Select((p,i)=>new{id=i,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
        edges=edges.Select(p=>new[]{p.i,p.j}).ToArray(),round=1,
        actors=new[]{new{id=10L,team=0,cell=At(0,3),hp=100,maxHp=100,ap=3,mp=0,physicalRadius=0},
            new{id=11L,team=1,cell=At(2,3),hp=100,maxHp=100,ap=0,mp=0,physicalRadius=1}}},
    spells=new[]{new{id=77,grade=1,cost=3,minRange=1,maxRange=1,damage=20,
        element="physical",rows=new[]{new{kind="damage",amount=20,target="enemy",fixedCells=new[]{new[]{0,0}}}}}},
    native=new{usage=Array.Empty<object>()},limits=new{budgetMs=100,maxActions=1}});
var answer=JsonSerializer.SerializeToElement(Planner.Decide(request)).GetProperty("action");
Check(answer.GetProperty("type").GetString()=="cast"
    &&answer.GetProperty("targetId").GetInt64()==11
    &&answer.GetProperty("target")[0].GetInt32()==1,
    "actual Host casts at the adjacent side and retains the large target identity");
var stacked=Enumerable.Range(0,25).Select(i=>new CellXYZ(i%5,i/5,(i%5+i/5)%2==0?0:4))
    .Concat(new[]{new CellXYZ(3,2,9),new CellXYZ(1,1,9)}).ToArray();
int Find(int x,int y,int z)=>Array.FindIndex(stacked,p=>p==new CellXYZ(x,y,z));
int from=Find(1,1,0),to=Find(2,1,4);
var mover=F(50,0,0,0,1,1);mover.CellId=from;
using(MapGeometry.BeginScope(new GeometryContext(stacked,new[]{(from,to)})))
{
 var board=new MonsterTactics.Board{Fighters=new[]{mover}};
 Check(MonsterTactics.Routes(board,mover).ContainsKey(to),"native body uses XY terrain columns while anchor climbs its native edge");
 Check(MonsterTactics.FootprintAt(mover,from).Contains(Find(1,1,9)),"native body occupies stacked altitude in same XY");
 var blocker=F(51,1,0,0);blocker.CellId=Find(3,2,9);
 Check(!MonsterTactics.Routes(board with{Fighters=new[]{mover,blocker}},mover).ContainsKey(to),"body collision remains XY across other altitude");
 Check(!MonsterTactics.CanOccupy(board with{Walkable=c=>stacked[c].X!=3||stacked[c].Y!=2},mover,to),"native body column needs some walkable geometry");
 var point=F(52,0,0,0);point.CellId=from;
 _=MonsterTactics.FootprintAt(point,from,true).ToArray();
 Check(MonsterTactics.FootprintAt(point,from).Contains(Find(1,1,9)),"explicit native radius zero still occupies XY column");
 var legacy=F(53,0,0,0);legacy.CellId=from;
 Check(!MonsterTactics.FootprintAt(legacy,from).Contains(Find(1,1,9)),"legacy missing native radius preserves XYZ point semantics");
}
var clipped=stacked.Where(p=>p.X!=3||p.Y!=2).ToArray();
int cf=Array.FindIndex(clipped,p=>p==stacked[from]),ct=Array.FindIndex(clipped,p=>p==stacked[to]);
mover.CellId=cf;
using(MapGeometry.BeginScope(new GeometryContext(clipped,new[]{(cf,ct)})))
 Check(!MonsterTactics.Routes(new MonsterTactics.Board{Fighters=new[]{mover}},mover).ContainsKey(ct),"missing entire native XY body column rejects movement");

return checks;
    }
}
