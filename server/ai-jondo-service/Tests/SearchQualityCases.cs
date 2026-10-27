using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

internal static class SearchQualityCases
{
    public static int Run()
    {
        int checks=0;
        void Check(bool value,string name)
        { if(!value)throw new Exception("FAIL: "+name);checks++;Console.WriteLine("PASS: "+name); }
        Fighter F(long id,int team,int cell,int hp=100,int ap=6,int mp=0)=>new(){Id=id,
            TeamId=team,CellId=cell,CurrentHP=hp,MaxHP=100,CurrentAP=ap,MaxAP=6,
            CurrentMP=mp,MaxMP=mp,Level=10,IsMonster=true};
        var line=Enumerable.Range(0,5).Select(x=>new CellXYZ(x,0,0)).ToArray();
        var lineEdges=Enumerable.Range(0,4).SelectMany(x=>new[]{(x,x+1),(x+1,x)}).ToArray();
        using(MapGeometry.BeginScope(new GeometryContext(line,lineEdges)))
        {
            foreach(var (cost,perTurn,perTarget,expected) in new[]{(0,0,0,1),(0,3,3,3),(2,0,0,3),(2,0,1,1)})
            {
                var caster=F(1,0,0,100,cost==0?0:6);
                var ally=F(3,0,1,10);var enemy=F(2,1,4);
                var fighters=new[]{caster,ally,enemy};
                var board=new MonsterTactics.Board{Fighters=fighters,
                    Reach=(r,c,f,a)=>Wakfu.Jondo.Planner.NativeReach(fighters,r,c,f,a)};
                var heal=new MonsterTactics.Spell{Id=80,Grade=1,Cost=cost,MinRange=1,MaxRange=3,
                    Heal=40,PerTurn=perTurn,PerTarget=perTarget,
                    Rows=new[]{SemanticRows.Create("heal",40,"ally")}};
                var plan=MonsterTactics.PlanTurn(board,caster,new[]{heal},budgetMs:200);
                Check(plan.Count==expected,$"useful healing repeats within native cost/limits {cost}/{perTurn}/{perTarget}");
                using(var simulation=MonsterTactics.Simulation.Replay(board,caster,plan))
                    Check(ally.CurrentHP==(expected==1?50:100),"healing forecast caps actual missing HP");
                Check(ally.CurrentHP==10&&caster.CurrentAP==(cost==0?0:6)
                    &&caster.LanzadosEsteTurno.Count==0&&caster.LanzadosPorObjetivo.Count==0,
                    "heal planning and replay restore HP/AP/usage source");
            }
            foreach(int perTarget in new[]{0,1})
            {
                var self=F(1,0,0,10);var enemy=F(2,1,4);
                var board=new MonsterTactics.Board{Fighters=new[]{self,enemy}};
                var heal=new MonsterTactics.Spell{Id=81,Grade=1,Cost=2,MinRange=0,MaxRange=0,
                    Heal=40,PerTarget=perTarget,Rows=new[]{SemanticRows.Create("heal",40,"self")}};
                var plan=MonsterTactics.PlanTurn(board,self,new[]{heal},budgetMs:200);
                Check(plan.Count==(perTarget==1?1:3),"self healing consumes the same per-target quota");
                self.CurrentHP=100;
                Check(MonsterTactics.PlanTurn(board,self,new[]{heal},budgetMs:200).Count==0,
                    "full-health self does not waste healing actions");
            }
            var buffer=F(1,0,0,100,0);var foe=F(2,1,4);
            var buff=new MonsterTactics.Spell{Id=82,Grade=1,Cost=0,MinRange=0,MaxRange=0,
                Buff=1,Rows=new[]{SemanticRows.Create("gain_ap",1,"self")}};
            var freePlan=MonsterTactics.PlanTurn(new MonsterTactics.Board{Fighters=new[]{buffer,foe}},buffer,new[]{buff},budgetMs:200);
            Check(freePlan.Count==1,"beneficial free unbounded setup is considered once, not looped");
            Check(buffer.CurrentAP==0&&buffer.LanzadosEsteTurno.Count==0,"free setup planning preserves source resources");
            var impossible=new MonsterTactics.Spell{Id=83,Grade=1,Cost=0,MinRange=0,MaxRange=0,
                Buff=1,NeedsFreeCell=true,Rows=buff.Rows};
            Check(MonsterTactics.PlanTurn(new MonsterTactics.Board{Fighters=new[]{buffer,foe}},buffer,
                new[]{impossible},budgetMs:200).Count==0,
                "self-only free-cell contradiction cannot masquerade as a legal free buff");
            var timed=F(11,0,0,100,6);var target=F(12,1,1);
            bool keep=true;int reached=0;
            var timedBoard=new MonsterTactics.Board{Fighters=new[]{timed,target},Reach=(r,c,f,a)=>
            {reached++;keep=false;return new[]{target};}};
            var timedHit=new MonsterTactics.Spell{Id=84,Grade=1,Cost=3,MinRange=1,MaxRange=1,
                Damage=20,Rows=new[]{SemanticRows.Create("damage",20,"enemy")}};
            var prefix=MonsterTactics.PlanTurn(timedBoard,timed,new[]{timedHit},budgetMs:1000,
                continueSearch:()=>keep);
            Check(reached>0&&prefix.Count==1,"soft deadline retains the first fully evaluated useful cast");
            Check(timed.CurrentAP==6&&timed.CurrentMP==0&&timed.CellId==0&&target.CurrentHP==100
                &&timed.LanzadosEsteTurno.Count==0&&timed.LanzadosPorObjetivo.Count==0,
                "deadline prefix preserves all source resources, damage and usage");
            reached=0;
            Check(MonsterTactics.PlanTurn(timedBoard,timed,new[]{timedHit},budgetMs:1000,
                continueSearch:()=>false).Count==0&&reached==0,
                "already expired search does not evaluate or fabricate an action");
        }
        var cells=new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(2,0,0),new CellXYZ(3,0,0),
            new CellXYZ(0,1,0),new CellXYZ(1,1,0),new CellXYZ(2,1,0),new CellXYZ(3,1,0)};
        var edges=new[]{(0,1),(1,0),(1,2),(2,1),(0,4),(4,0),(4,5),(5,4),(5,6),(6,5),(6,7),(7,6)};
        using(MapGeometry.BeginScope(new GeometryContext(cells,edges)))
        {
            var caster=F(1,0,0,100,6,4);var enemy=F(2,1,3);
            var board=new MonsterTactics.Board{Fighters=new[]{caster,enemy},
                TackleAt=(_,cell,_,_)=>cell==1?new Tackle.Loss(3,0):Tackle.Loss.None};
            var hit=new MonsterTactics.Spell{Id=90,Grade=1,Cost=3,MinRange=1,MaxRange=1,
                Damage=20,Rows=new[]{SemanticRows.Create("damage",20,"enemy")}};
            var plan=MonsterTactics.PlanTurn(board,caster,new[]{hit},budgetMs:300);
            Check(plan.Count==2&&plan.All(a=>a.From==7),"longer AP-preserving origin enables the complete two-hit turn");
            using(var simulation=MonsterTactics.Simulation.Replay(board,caster,plan))
                Check(enemy.CurrentHP==60&&caster.CurrentAP==0,"selected resource-preserving origin replays legal two-hit outcome");
            Check(enemy.CurrentHP==100&&caster.CurrentAP==6&&caster.CurrentMP==4&&caster.CellId==0,
                "origin search does not leak movement, damage or resource state");
            var receipts=Enumerable.Range(0,20).Select(i=>new MonsterTactics.Action(new[]{0},hit,enemy,3,
                100-i,100-i,i,20-i){MovementDanger=i}).ToArray();
            var frontier=MonsterTactics.OriginFrontier(receipts);
            Check(frontier.Count<=4&&frontier.Contains(receipts[19])&&frontier.Contains(receipts[0]),
                "resource-origin frontier stays bounded and preserves AP/MP extremes");
        }
        var tCells=new[]{new CellXYZ(0,0,0),new CellXYZ(0,1,0),new CellXYZ(-1,0,0),new CellXYZ(1,0,0),new CellXYZ(2,0,0)};
        var tEdges=new[]{(1,0),(0,1),(2,0),(0,2),(0,3),(3,0),(3,4),(4,3)};
        using(MapGeometry.BeginScope(new GeometryContext(tCells,tEdges)))
        {
            var caster=F(1,0,1,100,0,1);var ally=F(3,0,2,100,3,3);var enemy=F(2,1,4);
            var board=new MonsterTactics.Board{Fighters=new[]{caster,ally,enemy}};
            var hit=new MonsterTactics.Spell{Id=91,Grade=1,Cost=3,MinRange=1,MaxRange=1,
                Damage=20,Rows=new[]{SemanticRows.Create("damage",20,"enemy")}};
            var selected=MonsterTactics.Reposition(board,caster,new[]{hit});
            caster.CellId=selected.Last();
            Check(MonsterTactics.Routes(board,ally).ContainsKey(3),"idle actor avoids taking an ally's only attack corridor");
            caster.CellId=0;
            var opened=MonsterTactics.Reposition(board,caster,new[]{hit});
            caster.CellId=opened.Last();
            Check(opened.Count>1&&MonsterTactics.Routes(board,ally).ContainsKey(3),
                "idle actor leaves an already blocked junction to open the allied route; path="+string.Join(",",opened)+" reachable="+string.Join(",",MonsterTactics.Routes(board,ally).Keys));
            caster.CellId=0;ally.CurrentMP=0;
            var futureOpened=MonsterTactics.Reposition(board,caster,new[]{hit});
            caster.CellId=futureOpened.Last();ally.CurrentMP=ally.MaxMP;
            Check(futureOpened.Count>1&&MonsterTactics.Routes(board,ally).ContainsKey(3),
                "spent ally movement still preserves its next-turn corridor using actual maximum MP");
            caster.CellId=1;caster.CurrentAP=3;enemy.CurrentHP=1;
            var winning=new MonsterTactics.Spell{Id=92,Grade=1,Cost=3,MinRange=1,MaxRange=2,
                Damage=20,Rows=hit.Rows};
            var plan=MonsterTactics.PlanTurn(board,caster,new[]{winning},budgetMs:200);
            Check(plan.Count>0&&plan[0].From==0,"allied corridor cost never bans a currently winning legal cast");
            using(var simulation=MonsterTactics.Simulation.Replay(board,caster,plan))
                Check(enemy.CurrentHP==0,"winning-cast exception produces the actual terminal damage forecast");
        }
        return checks;
    }
}
