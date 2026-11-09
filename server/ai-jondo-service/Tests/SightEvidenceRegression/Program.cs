using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

// Cells 1 and 2 are equally far from the enemy. Cell 1 is observed in sight;
// cell 2 is either unobserved or confirmed hidden. A critically injured actor
// should not treat a missing observation as proof of cover.
JsonElement Request(bool? secondRay, string id)
{
    var rays = new List<object> { new object[] {3,0,true}, new object[] {3,1,true} };
    if (secondRay is bool value) rays.Add(new object[] {3,2,value});
    return JsonSerializer.SerializeToElement(new {
        protocol=1, requestId=id,
        source=new {actorId=1L,fightInstanceId=id,turnId=1,catalogRevision="sight-evidence"},
        board=new {
            cells=new[] {new{id=0,xyz=new[]{0,0,0}},new{id=1,xyz=new[]{-1,0,0}},
                new{id=2,xyz=new[]{1,0,0}},new{id=3,xyz=new[]{0,3,0}}},
            edges=new[]{new[]{0,1},new[]{1,0},new[]{0,2},new[]{2,0}},
            actors=new[]{new{id=1L,team=0,cell=0,hp=10,maxHp=100,ap=0,maxAp=0,mp=1,maxMp=1},
                new{id=2L,team=1,cell=3,hp=100,maxHp=100,ap=6,maxAp=6,mp=0,maxMp=0}},
            lineOfSight=rays,
        },
        spells=Array.Empty<object>(), native=new{usage=Array.Empty<object>()},
        limits=new{budgetMs=500}, excludedActions=Array.Empty<string>()
    });
}
int Destination(bool? secondRay, string id)
{
    var reply=JsonSerializer.SerializeToElement(Planner.Decide(Request(secondRay,id)));
    var action=reply.GetProperty("action");
    if(action.GetProperty("type").GetString()!="move")
        throw new Exception("Expected reposition movement: "+action);
    return action.GetProperty("path").EnumerateArray().Last()[0].GetInt32();
}
if(Destination(null,"unknown") != -1)
    throw new Exception("Unobserved sight was incorrectly treated as confirmed cover");
if(Destination(false,"blocked") != 1)
    throw new Exception("Confirmed blocked sight did not prefer cover");
if(Destination(true,"visible") != -1)
    throw new Exception("Visible alternatives should retain their regular tie ordering");
Console.WriteLine("PASS: unknown, blocked and visible rays remain distinct in host repositioning");

JsonElement AdjacentRequest(string id, bool? visible, bool staticBlocked,
                           bool nativeRule, bool needsLineOfSight)
{
    var board = new Dictionary<string,object> {
        ["cells"] = new[] {
            new { id=0, xyz=new[] { 5,-21,6 } },
            new { id=1, xyz=new[] { 6,-21,1 } },
        },
        ["edges"] = Array.Empty<int[]>(),
        ["actors"] = new[] {
            new { id=1L, team=0, cell=0, hp=100, maxHp=100, ap=3, maxAp=3, mp=0, maxMp=0 },
            new { id=2L, team=1, cell=1, hp=100, maxHp=100, ap=0, maxAp=0, mp=0, maxMp=0 },
        },
    };
    if (visible is bool ray) board["lineOfSight"] = new[] { new object[] { 0,1,ray } };
    if (staticBlocked) board["nativeStaticLosBlocked"] = new[] { new object[] { 0,1,2L } };
    var spell = new Dictionary<string,object> {
        ["id"] = 5767, ["grade"] = 1, ["cost"] = 3, ["minRange"] = 1,
        ["maxRange"] = 1, ["damage"] = 20, ["needsLineOfSight"] = needsLineOfSight,
        ["nativeDirectLosRule"] = nativeRule,
    };
    return JsonSerializer.SerializeToElement(new Dictionary<string,object> {
        ["protocol"] = 1, ["requestId"] = id,
        ["source"] = new { actorId=1L, fightInstanceId=id, turnId=1, catalogRevision="map-1385" },
        ["board"] = board, ["spells"] = new[] { spell },
        ["native"] = new { usage=Array.Empty<object>() },
        ["limits"] = new { budgetMs=500 }, ["excludedActions"] = Array.Empty<string>(),
    });
}
string ActionType(JsonElement request) => JsonSerializer.SerializeToElement(Planner.Decide(request))
    .GetProperty("action").GetProperty("type").GetString()!;
if (ActionType(AdjacentRequest("map1385-blocked", false, true, true, true)) == "cast")
    throw new Exception("Certified blocked static rays must forbid the adjacent LOS cast");
if (ActionType(AdjacentRequest("map1385-visible", true, false, true, true)) != "cast")
    throw new Exception("Mixed native rays proving visibility must permit the adjacent LOS cast");
if (ActionType(AdjacentRequest("map1385-unknown", null, false, true, true)) != "cast")
    throw new Exception("Unmeasured static rays must retain the compatibility fallback");
if (ActionType(AdjacentRequest("map1385-cache-hit", false, false, true, true)) != "cast")
    throw new Exception("A cache hit without static-ray evidence must retain the compatibility fallback");
if (ActionType(AdjacentRequest("map1385-override", false, true, false, true)) != "cast")
    throw new Exception("A target/rule override must not apply the direct-LOS certificate");
if (ActionType(AdjacentRequest("map1385-no-los", false, true, true, false)) != "cast")
    throw new Exception("A spell that does not require LOS must ignore the direct-LOS evidence");
Console.WriteLine("PASS: map 1385 adjacent LOS uses blocked proof, visible proof, unknown/cache fallback, overrides, and no-LOS behavior");

var footprintCells=Enumerable.Range(0,49).Select(i=>new CellXYZ(i%7,i/7,0)).ToArray();
int Foot(int x,int y)=>y*7+x;
var footprintEdges=Enumerable.Range(0,49).SelectMany(i=>Enumerable.Range(0,49)
    .Where(j=>Math.Abs(footprintCells[i].X-footprintCells[j].X)
        +Math.Abs(footprintCells[i].Y-footprintCells[j].Y)==1).Select(j=>(i,j))).ToArray();
using(MapGeometry.BeginScope(new GeometryContext(footprintCells,footprintEdges)))
{
    var attacker=new Fighter { Id=101,TeamId=0,CellId=Foot(0,3),CurrentHP=100,MaxHP=100,
        CurrentAP=3,MaxAP=3,CurrentMP=0,MaxMP=0 };
    var giant=new Fighter { Id=102,TeamId=1,CellId=Foot(2,3),CurrentHP=100,MaxHP=100,
        CurrentAP=0,MaxAP=0,CurrentMP=0,MaxMP=0,NativePhysicalRadius=1,MonsterId=1345 };
    var sideAim=Foot(1,3);
    var giantSpell=new MonsterTactics.Spell { Id=77,Grade=1,Cost=3,MinRange=1,MaxRange=1,Damage=20 };
    var giantBoard=new MonsterTactics.Board { Fighters=new[]{attacker,giant} };
    var giantPlan=new MonsterTactics.Action(new[]{attacker.CellId},giantSpell,giant,sideAim,1,
        Value:20,ActionPoints:3,MovementPoints:0);
    JsonElement PlanRequest(string id)=>JsonSerializer.SerializeToElement(new {
        source=new {actorId=attacker.Id,fightInstanceId=id,turnId=1,catalogRevision="large-target"},
        board=new {cells=footprintCells.Select((p,i)=>new{id=i,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
            edges=footprintEdges.Select(e=>new[]{e.i,e.j}).ToArray(),portalEdges=Array.Empty<int[]>()},
        spells=new[]{new{id=77,grade=1,cost=3,minRange=1,maxRange=1,damage=20}},
    });
    bool Reuse(string id,MonsterTactics.Board current,out MonsterTactics.Action? step)
    {
        var request=PlanRequest(id);
        TurnPlans.Store(request,new[]{giantPlan});
        return TurnPlans.TryGet(request,current,attacker,new[]{giantSpell},out step);
    }
    if(!Reuse("large-target-same",giantBoard,out var rebound)
        || rebound==null || rebound.Target.Id!=giant.Id || rebound.TargetCell!=sideAim
        || rebound.From!=attacker.CellId)
        throw new Exception("Same-anchor large-target side-cell continuation was not rebound");
    Console.WriteLine("PASS: TurnPlans reuses a side-cell aim occupied by the same large target at its anchor");

    giant.CellId=Foot(5,5);
    if(Reuse("large-target-moved",giantBoard,out _))
        throw new Exception("Moved large target incorrectly retained the stale side-cell plan");
    Console.WriteLine("PASS: TurnPlans rejects a stale side-cell plan after the large target moves away");

    giant.CellId=Foot(2,3); giant.CurrentHP=0;
    if(Reuse("large-target-dead",giantBoard,out _))
        throw new Exception("Dead large target incorrectly retained the plan");
    Console.WriteLine("PASS: TurnPlans rejects a dead large target");

    giant.CurrentHP=100; giant.CellId=Foot(5,5);
    var replacement=new Fighter { Id=103,TeamId=1,CellId=sideAim,CurrentHP=100,MaxHP=100 };
    var occupiedBoard=new MonsterTactics.Board { Fighters=new[]{attacker,giant,replacement} };
    if(Reuse("large-target-occupied",occupiedBoard,out _))
        throw new Exception("Another actor occupying the stale side aim incorrectly preserved the plan");
    Console.WriteLine("PASS: TurnPlans rejects an old side aim occupied by a different actor");
}

JsonElement LinearPathRequest(string id,int mp,bool includeEvidence,bool rule,bool moved)
{
    var cells=new[] {
        new{id=0,xyz=new[]{-6,-13,88}},
        new{id=1,xyz=new[]{-6,-17,88}},
        new{id=2,xyz=new[]{-6,-12,88}},
    };
    var edges=moved?new[]{new[]{0,2},new[]{2,0}}:Array.Empty<int[]>();
    var board=new Dictionary<string,object> {
        ["cells"]=cells,["edges"]=edges,["portalEdges"]=Array.Empty<int[]>(),
        ["actors"]=new[] {
            new{id=1L,team=0,cell=0,hp=100,maxHp=100,ap=3,maxAp=3,mp,maxMp=mp,physicalRadius=0},
            new{id=2L,team=1,cell=1,hp=100,maxHp=100,ap=0,maxAp=0,mp=0,maxMp=0,physicalRadius=0},
        },
        ["lineOfSight"]=new[]{new object[]{0,1,true},new object[]{2,1,true}},
    };
    if(includeEvidence) board["nativeLinearPathBlocked"]=new[]{new object[]{0,1,2L}};
    var spell=new Dictionary<string,object> {
        ["id"]=5777,["grade"]=1,["cost"]=3,["minRange"]=1,["maxRange"]=8,
        ["damage"]=20,["needsLineOfSight"]=true,["inLine"]=true,
    };
    if(rule) spell["nativeLinearPathRule"]=true;
    return JsonSerializer.SerializeToElement(new Dictionary<string,object> {
        ["protocol"]=1,["requestId"]=id,
        ["source"]=new{actorId=1L,fightInstanceId=id,turnId=1,catalogRevision="map363-sn"},
        ["board"]=board,["spells"]=new[]{spell},["native"]=new{usage=Array.Empty<object>()},
        ["limits"]=new{budgetMs=500,maxActions=1},["excludedActions"]=Array.Empty<string>(),
    });
}
JsonElement LinearAction(string id,int mp,bool evidence,bool rule,bool moved)
    => JsonSerializer.SerializeToElement(Planner.Decide(LinearPathRequest(id,mp,evidence,rule,moved)))
        .GetProperty("action");
var blockedLinear=LinearAction("map363-sn-blocked",0,true,true,false);
if(blockedLinear.GetProperty("type").GetString()=="cast")
    throw new Exception("Map 363 confirmed Sn path failure must block the original linear cast");
var missingLinear=LinearAction("map363-sn-missing",0,false,true,false);
if(missingLinear.GetProperty("type").GetString()!="cast")
    throw new Exception("Missing Sn evidence must preserve the previous cast fallback");
var legacyLinear=LinearAction("map363-sn-legacy",0,true,false,false);
if(legacyLinear.GetProperty("type").GetString()!="cast")
    throw new Exception("Absent/overridden static Sn rule must preserve the previous cast fallback");
var movedLinear=LinearAction("map363-sn-moved",1,true,true,true);
if(movedLinear.GetProperty("type").GetString()!="move")
    throw new Exception("Original-source Sn rejection must not forbid a hypothetical cast after movement");
Console.WriteLine("PASS: map 363 spell5777 blocks confirmed Sn failure, keeps missing/legacy fallback, and does not reuse proof after movement");
