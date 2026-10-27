using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class HazardRouteCases
{
    public static int Run()
    {
        int checks = 0;
        void Check(bool condition, string name)
        {
            if (!condition) throw new Exception("FAIL: " + name);
            Console.WriteLine("PASS: " + name); checks++;
        }
        // Same landing, two genuinely directed paths: two steps over danger,
        // or four ordinary steps. Hazard affects preference, never resources.
        var cells = new[] { new CellXYZ(0,0,0), new CellXYZ(1,0,0), new CellXYZ(2,0,0),
            new CellXYZ(0,1,0), new CellXYZ(1,1,0), new CellXYZ(2,1,0), new CellXYZ(3,0,0) };
        var edges = new[] { (0,1), (1,2), (0,3), (3,4), (4,5), (5,2) };
        using (MapGeometry.BeginScope(new GeometryContext(cells, edges)))
        {
            var actor = Actor(4);
            var ordinary = new MonsterTactics.Board { Fighters = new[] { actor } };
            var dangerous = ordinary with { MovementDanger = cell => cell == 1 ? 3 : 0 };
            var baseline = MonsterTactics.Routes(ordinary,actor)[2];
            var safe = MonsterTactics.Routes(dangerous,actor)[2];
            Check(baseline.Path.SequenceEqual(new[]{0,1,2}) && baseline.MovementPoints == 2,
                  "no hazard retains the original short path and actual MP");
            Check(safe.Path.SequenceEqual(new[]{0,3,4,5,2}) && safe.Danger == 0
                  && safe.MovementPoints == 0 && safe.ActionPoints == 6,
                  "affordable safe detour wins without replacing actual AP or MP with danger");
            actor.CurrentMP = 2;
            var unavoidable = MonsterTactics.Routes(dangerous,actor)[2];
            Check(unavoidable.Path.SequenceEqual(new[]{0,1,2}) && unavoidable.Danger == 3
                  && unavoidable.MovementPoints == 0,
                  "MP-limited unavoidable hazardous route remains legal and reachable");
            Check(!MonsterTactics.Routes(dangerous,Actor(4,2)).ContainsKey(0),
                  "hazard routing never invents reverse directed edges");
            actor = Actor(4);
            var enemy = new Fighter { Id=2,TeamId=1,CellId=6,CurrentHP=100,MaxHP=100 };
            var hit = new MonsterTactics.Spell { Id=901,Grade=1,Cost=3,MinRange=1,MaxRange=1,Damage=20,
                Rows=new[]{SemanticRows.Create("damage",20,"enemy")} };
            var attackBoard = dangerous with { Fighters=new[]{actor,enemy},
                SpellMovementCost = spell => spell.Id == 901 ? 2 : 0 };
            var options = MonsterTactics.Options(attackBoard,actor,new[]{hit});
            Check(options.Any(option => option.From == 2 && option.Path.SequenceEqual(new[]{0,1,2})),
                  "short hazardous arrival survives when safe arrival cannot pay the spell MP");
            var distantActor = Actor(1);
            var obstructed = dangerous with { Fighters=new[]{distantActor,enemy},
                MovementDanger=cell=>cell==1?10:0, Walkable=cell=>cell!=3 };
            var approach = MonsterTactics.Reposition(obstructed,distantActor,new[]{hit});
            Check(approach.SequenceEqual(new[]{0,1}),
                  "melee approach crosses unavoidable danger when no immediate attack is in reach");
            var tackled = dangerous with { TackleAt = (_,cell,_,_) => cell == 0 ? new Tackle.Loss(1,1) : Tackle.Loss.None };
            var loss = MonsterTactics.Routes(tackled,Actor(3))[2];
            Check(loss.ActionPoints == 5 && loss.MovementPoints == 0 && loss.Path.SequenceEqual(new[]{0,1,2}),
                  "hazard preference preserves native tackle AP and MP deductions");
        }
        // Equal XY at different heights remain separate native cells.
        using (MapGeometry.BeginScope(new GeometryContext(
            new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(1,0,2),new CellXYZ(7,0,2)},
            new[]{(0,1),(1,2)})))
        {
            var actor = Actor(2);
            var board = new MonsterTactics.Board { Fighters=new[]{actor},MovementDanger=cell=>cell==2?3:0 };
            var routes = MonsterTactics.Routes(board,actor);
            Check(routes[2].Path.SequenceEqual(new[]{0,1,2}) && !routes.ContainsKey(3),
                  "directed XYZ height edges remain authoritative under danger costs");
            var network = new PortalNetwork();
            network.SetNativeRoute(1,3);
            board = board with { Portals = () => network };
            var portal = MonsterTactics.Routes(board,actor)[3];
            Check(portal.Path.SequenceEqual(new[]{0,1,3}) && portal.MovementPoints == 1,
                  "explicit native portal keeps its original one-step MP payment");
        }
        return checks + HostCases();
    }
    private static int HostCases()
    {
        var cells = new[] { new[]{0,0,0},new[]{1,0,0},new[]{2,0,0},
            new[]{0,1,0},new[]{1,1,0},new[]{2,1,0},new[]{3,0,0} };
        System.Text.Json.JsonElement Request(object[]? dangers, string identity)
        {
            var board = new Dictionary<string,object> {
                ["cells"]=cells.Select((xyz,id)=>new{id,xyz}).ToArray(),
                ["edges"]=new[]{new[]{0,1},new[]{1,2},new[]{0,3},new[]{3,4},new[]{4,5},new[]{5,2}},
                ["actors"]=new[]{new{id=1L,team=0,cell=0,hp=100,maxHp=100,ap=3,mp=4},
                    new{id=2L,team=1,cell=6,hp=100,maxHp=100,ap=3,mp=0}},
                ["lineOfSight"]=cells.SelectMany((_,from)=>cells.Select((_,to)=>new object[]{from,to,true})).ToArray(),
            };
            if(dangers!=null)board["movementDanger"]=dangers;
            return System.Text.Json.JsonSerializer.SerializeToElement(new {
                protocol=1,requestId=identity,source=new{actorId=1L,fightInstanceId=identity,turnId=1,catalogRevision="hazard-fixture-v1"},board,
                spells=new[]{new{id=902,grade=1,cost=3,minRange=1,maxRange=1,damage=20,
                    rows=new[]{new{kind="damage",amount=20,target="enemy",fixedCells=new[]{new[]{0,0}}}}}},
                native=new{usage=Array.Empty<object>()},limits=new{budgetMs=1000},excludedActions=Array.Empty<string>() });
        }
        System.Text.Json.JsonElement Action(System.Text.Json.JsonElement request)
            => System.Text.Json.JsonSerializer.SerializeToElement(Wakfu.Jondo.Planner.Decide(request)).GetProperty("action");
        var dangerous=Request(new object[]{new{cell=1,cost=3}},"hazard-host-safe");
        var original=dangerous.GetRawText();
        var safe=Action(dangerous);
        if(safe.GetProperty("type").GetString()!="move" ||
           !safe.GetProperty("path")[0].EnumerateArray().Select(v=>v.GetInt32()).SequenceEqual(new[]{0,1,0}) ||
           dangerous.GetRawText()!=original)
            throw new Exception("Host must propagate danger and choose the safe detour without mutating input: "+safe);
        Console.WriteLine("PASS: real Host parses movement danger and chooses the safe detour without source mutation");
        var zero=Action(Request(new object[]{new{cell=1,cost=0}},"hazard-host-zero"));
        var absent=Action(Request(null,"hazard-host-absent"));
        if(zero.GetRawText()!=absent.GetRawText())throw new Exception("Explicit zero danger changed legacy Host behavior");
        Console.WriteLine("PASS: absent and explicit zero danger preserve the same Host action");
        foreach(var bad in new object[]{new{cell=1,cost=-1},new{cell=99,cost=3}})
        {
            bool rejected=false;
            try { Action(Request(new[]{bad},"hazard-host-invalid")); }
            catch(ArgumentException){ rejected=true; }
            if(!rejected)throw new Exception("Host accepted invalid movement danger");
        }
        Console.WriteLine("PASS: real Host rejects negative danger and out-of-board danger cells");
        System.Text.Json.JsonElement Decide(object[] hazards) =>
            System.Text.Json.JsonSerializer.SerializeToElement(Wakfu.Jondo.Planner.Decide(Request(hazards,"hazard-reuse")));
        Decide(new object[]{new{cell=1,cost=3},new{cell=3,cost=1}});
        var reordered=Decide(new object[]{new{cell=3,cost=1},new{cell=1,cost=3},new{cell=4,cost=0}});
        if(!reordered.GetProperty("planReused").GetBoolean())
            throw new Exception("Equivalent reordered sparse danger field invalidated a certified continuation");
        Console.WriteLine("PASS: equivalent reordered danger and zero entries retain fresh plan revalidation");
        var changed=Decide(new object[]{new{cell=3,cost=1},new{cell=1,cost=4}});
        if(changed.GetProperty("planReused").GetBoolean())
            throw new Exception("Changed movement danger reused an old cast-origin plan");
        Console.WriteLine("PASS: changed movement danger invalidates and replans the turn continuation");
        return 5;
    }
    private static Fighter Actor(int mp,int cell=0) => new()
    { Id=1,TeamId=0,CellId=cell,CurrentHP=100,MaxHP=100,CurrentAP=6,MaxAP=6,
      CurrentMP=mp,MaxMP=mp,Level=10,IsMonster=true };
}
