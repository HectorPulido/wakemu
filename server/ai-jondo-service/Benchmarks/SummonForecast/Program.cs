using System.Diagnostics;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

// Synthetic core-only workload: callbacks are controlled fixtures, not native
// evidence. This does not measure Host integration, World or callback I/O.
Console.WriteLine("Synthetic SummonsNextTurn benchmark; callback answers are fixtures, not native evidence.");
using var geometry=MapGeometry.BeginScope(new GeometryContext(
    Enumerable.Range(0,64).Select(x=>new CellXYZ(x,0,0)).ToArray(),
    Enumerable.Range(0,63).SelectMany(x=>new[]{(x,x+1),(x+1,x)})));
foreach (var (name,summonCount,enemyCount,spellCount,originCount,evidence) in new[] {
    ("unwired", 4,4,4,4,false), ("small",1,1,2,1,true), ("fanout",4,4,4,4,true)
})
{
    var owner=new Fighter{Id=1,TeamId=0,CellId=0,CurrentHP=100,MaxHP=100};
    var summons=Enumerable.Range(0,summonCount).Select(i=>new Fighter{
        Id=2+i,TeamId=0,CellId=2+i,CurrentHP=100,MaxHP=100,
        Invocador=owner.Id,CurrentAP=6,MaxAP=6,CurrentMP=3,MaxMP=3}).ToArray();
    var enemies=Enumerable.Range(0,enemyCount).Select(i=>new Fighter{
        Id=100+i,TeamId=1,CellId=20+i,CurrentHP=100,MaxHP=100}).ToArray();
    var spells=Enumerable.Range(0,spellCount).Select(i=>new MonsterTactics.Spell{
        Id=1000+i,Grade=1,Cost=3,MinRange=1,MaxRange=63,Damage=20,
        NeedsLineOfSight=true}).ToList();
    var origins=Enumerable.Range(8,originCount).ToArray();
    long criterion=0,sight=0,damage=0;
    var board=new MonsterTactics.Board{
        Fighters=new[]{owner}.Concat(summons).Concat(enemies).ToArray(),
        SpellsOf=_=>spells,
        SummonReachableOrigins=_=>origins,
        SummonCastCriterion=evidence?(_,_,_,_)=>{criterion++;return true;}:null,
        SummonSightEvidence=(_,_,_)=>{sight++;return true;},
        SummonDamageEvidence=(_,_,_,_)=>{damage++;return true;},
    };
    using var sim=MonsterTactics.Simulation.Replay(board,owner,Array.Empty<MonsterTactics.Action>());
    for(int i=0;i<100;i++)MonsterTactics.SummonsNextTurn(sim,owner);
    criterion=sight=damage=0;
    const int samples=31,iterations=100;
    var times=new double[samples]; double checksum=0;
    for(int sample=0;sample<samples;sample++)
    {
        long start=Stopwatch.GetTimestamp();
        for(int i=0;i<iterations;i++)checksum+=MonsterTactics.SummonsNextTurn(sim,owner);
        times[sample]=Stopwatch.GetElapsedTime(start).TotalMicroseconds/iterations;
    }
    Array.Sort(times);
    double calls=samples*iterations;
    Console.WriteLine($"{name}: p50={times[samples/2]:F2} us p95={times[(int)(samples*.95)]:F2} us; " +
        $"criterion/sight/damage={criterion/calls:F0}/{sight/calls:F0}/{damage/calls:F0} per evaluation; checksum={checksum:F0}");
}
