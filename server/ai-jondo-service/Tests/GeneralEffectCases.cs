using System.Text.Json;
using Jondo.Unity.Server.Managers;
using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;
using Wakfu.Jondo;

internal static class GeneralEffectCases
{
    public static int Run()
    {
        int checks=0;
        void Check(bool value,string name)
        {checks++;if(!value)throw new Exception("General native effects: "+name);}
        Fighter Actor(long id,int team,int cell,int hp=100,int maximum=100)=>new(){Id=id,TeamId=team,
            CellId=cell,CurrentHP=hp,MaxHP=maximum,CurrentAP=6,MaxAP=6,CurrentMP=0,MaxMP=0,
            NativeHpMinimum=0,NativeHpFrozen=false,NativeHpRawMode="bounded",NativeUndead=false,NativeIsCarried=false,
            NativeHealingResistanceEnabled=false,NativeHealingResistanceMinimum=0,
            NativeHealingResistanceMaximum=1000,NativeHealingResistanceFrozen=false,
            NativeVirtualHpFrozen=false,NativeStats=new Dictionary<int,int>{{87,0},{32,0}},IsMonster=true,
            NativeArmorAuthority=new NativePoolAuthority(0,int.MaxValue,false),
            NativeBarrierAuthority=new NativePoolAuthority(0,int.MaxValue,false),
            NativeVirtualHpAuthority=new NativePoolAuthority(0,0,false)};
        using var golden=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "Fixtures","NativePercentGoldens.json")));
        var data=golden.RootElement;
        foreach(var sample in data.GetProperty("percentCases").EnumerateArray())
        {
            var hp=sample.GetProperty("hpContext");
            var source=Actor(1,0,0,hp.GetProperty("source_hp").GetInt32(),hp.GetProperty("source_max_hp").GetInt32());
            var target=Actor(2,1,1,hp.GetProperty("target_hp").GetInt32(),hp.GetProperty("target_max_hp").GetInt32());
            var parameters=sample.GetProperty("parameters");bool rejected=false;NativeAmountForecast? amount=null;
            try{amount=NativeEffectAmounts.Base(parameters[4].GetInt32(),parameters[0].GetInt32(),source,target,
                sample.GetProperty("allowSignedBase").GetBoolean());}catch(ArgumentException){rejected=true;}
            bool expectsError=sample.TryGetProperty("error",out _);
            Check(expectsError?rejected:!rejected&&amount!.Outcomes.Any(x=>x.Amount==sample.GetProperty("result").GetProperty("base").GetInt32()),
                "unchanged World HP-base scalar oracle: "+sample.GetProperty("id"));
            if(!expectsError)Check(Math.Abs(amount!.Outcomes.Sum(x=>x.Probability)-1)<1e-10,
                "native HP rounding distribution remains normalized");
        }
        foreach(var sample in data.GetProperty("nativePAFloorCases").EnumerateArray())
        {
            var target=Actor(2,1,1);target.NativeHpMinimum=sample.GetProperty("targetNativeMinimum").GetInt32();
            target.NativeHpFrozen=sample.GetProperty("targetNativeFrozen").GetBoolean();
            var result=NativeHpForecast.Apply(target,sample.GetProperty("base").GetProperty("base").GetInt32(),true);
            Check(result.Current==sample.GetProperty("consumption").GetProperty("current").GetInt32(),
                "unchanged World PA floor/frozen oracle: "+sample.GetProperty("id"));
        }
        foreach(var sample in data.GetProperty("lightHealingCases").EnumerateArray())
        {
            Dictionary<int,int> Stats(JsonElement value)=>value.EnumerateObject().ToDictionary(p=>int.Parse(p.Name),p=>p.Value.GetInt32());
            var result=NativeHealingCalculator.Amount(sample.GetProperty("base").GetInt32(),sample.GetProperty("nativeElement").GetInt32(),
                Stats(sample.GetProperty("sourceStats")),Stats(sample.GetProperty("targetStats")),
                sample.GetProperty("coefficientMask").GetInt32(),true,false,true,false,false);
            Check(result.Outcomes.Any(x=>x.Amount==sample.GetProperty("result").GetInt32()),
                "unchanged World Light healing oracle: "+sample.GetProperty("id"));
        }
        using(var resistance=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "Fixtures","NativeHealingResistanceGoldens.json"))))
        {
            int compared=0,nonRepresentable=0;
            foreach(var sample in resistance.RootElement.GetProperty("cases").EnumerateArray())
            {
                var input=sample.GetProperty("inputs");
                string[] integerKeys={"actual_heal","target_max_hp","current","minimum","maximum"};
                if(integerKeys.Any(key=>input.GetProperty(key).ValueKind!=JsonValueKind.Number
                        ||!input.GetProperty(key).TryGetInt32(out _))
                    ||input.GetProperty("enabled").ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                    ||input.GetProperty("frozen").ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                {nonRepresentable++;continue;}
                bool rejected=false;int answer=0;
                try{answer=NativeHealingCalculator.ResistanceAfter(input.GetProperty("actual_heal").GetInt32(),
                    input.GetProperty("target_max_hp").GetInt32(),input.GetProperty("current").GetInt32(),
                    input.GetProperty("enabled").GetBoolean(),input.GetProperty("frozen").GetBoolean(),
                    input.GetProperty("minimum").GetInt32(),input.GetProperty("maximum").GetInt32());}
                catch(ArgumentException){rejected=true;}
                bool expectedError=sample.TryGetProperty("expectedError",out _);
                Check(expectedError?rejected:!rejected&&answer==sample.GetProperty("expected").GetInt32(),
                    "original World signed healing/resistance oracle: "+sample.GetProperty("id"));
                compared++;
            }
            Check(compared+nonRepresentable==resistance.RootElement.GetProperty("caseCount").GetInt32(),
                "healing resistance oracle coverage is explicit");
            Console.WriteLine($"Healing resistance oracle: {compared} typed cases checked; {nonRepresentable} Python-only malformed type cases outside C# signature");
        }

        var cells=new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(2,0,0)};
        using var geometry=MapGeometry.BeginScope(new GeometryContext(cells,new[]{(0,1),(1,0),(1,2),(2,1)}));
        MonsterTactics.Board Board(Fighter[] actors)=>new(){Fighters=actors,Sees=(_,_)=>true,
            Reach=(row,caster,from,aim)=>Planner.NativeReach(actors,row,caster,from,aim)};
        SpellEffect Row(string kind,int basis,int value,string target,int? healing=null,int mask=0)
        {
            var row=SemanticRows.Create(kind,value,target,nativeCoefficientMask:mask);
            NativeEffectAmounts.Bind(row,basis,value,healing);return row;
        }
        MonsterTactics.Spell Spell(int id,SpellEffect row,int value=50)=>new(){Id=id,Grade=1,Cost=3,
            MinRange=0,MaxRange=3,PerTurn=2,Damage=NativeEffectAmounts.IsDamage(row)?value:0,
            Heal=NativeEffectAmounts.IsHealing(row)?value:0,Rows=new[]{row}};
        MonsterTactics.Action Step(Fighter source,Fighter target,MonsterTactics.Spell spell,int ap)
            =>new(new[]{source.CellId},spell,target,target.CellId,1,ActionPoints:ap,MovementPoints:0);

        var caster=Actor(1,0,0);var enemy=Actor(2,1,1);var board=Board(new[]{caster,enemy});
        var targetPercent=Spell(9101,Row("damage",5,50,"enemy"));
        var plan=MonsterTactics.PlanTurn(board,caster,new[]{targetPercent},budgetMs:1000);
        Check(plan.Count==2,"paid target-current-percent damage remains repeatable with native resources");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,plan))
            Check(enemy.CurrentHP==25&&caster.CurrentAP==0,"two live 50% target-HP casts deal50 then25");
        Check(enemy.CurrentHP==100&&caster.CurrentAP==6,"percent plan restores source HP/resources");

        caster.CurrentHP=20;
        var selfHeal=Spell(9102,Row("heal",0,50,"self",1));
        var sourcePercent=Spell(9103,Row("damage",2,100,"enemy"),100);
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,caster,selfHeal,6),Step(caster,enemy,sourcePercent,3)}))
            Check(caster.CurrentHP==70&&enemy.CurrentHP==30,"source-HP damage reads actual preceding heal:20+50 then70damage");
        Check(caster.CurrentHP==20&&enemy.CurrentHP==100,"mixed native healing/damage replay undoes all HP");

        caster.CurrentHP=100;var ally=Actor(3,0,1,20);enemy.CellId=2;board=Board(new[]{caster,ally,enemy});
        var missingHeal=Spell(9104,Row("heal",6,50,"ally",1));
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,ally,missingHeal,6),Step(caster,ally,missingHeal,3)}))
            Check(ally.CurrentHP==80,"missing-HP healing recomputes20→60→80 after each cast");
        Check(ally.CurrentHP==20&&caster.CurrentAP==6,"missing-HP forecast leaves original actors unchanged");

        ally=Actor(3,0,1,100,1000);ally.NativeHealingResistanceEnabled=true;board=Board(new[]{caster,ally,enemy});
        var flatHeal=Spell(9105,Row("heal",0,100,"ally",1,mask:2),100);
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,ally,flatHeal,6),Step(caster,ally,flatHeal,3)}))
            Check(ally.CurrentHP==298&&ally.NativeForecastHealResistance==39,
                "two native heals apply100 then98 and advance healing resistance0→20→39");
        Check(ally.CurrentHP==100&&ally.NativeForecastHealResistance==null&&ally.NativeStats![32]==0,
            "repeat-heal resistance and HP are private and fully restored");

        enemy=Actor(2,1,1,2,100);board=Board(new[]{caster,enemy});caster.CurrentAP=3;
        var rounded=Spell(9106,Row("damage",5,75,"enemy"),75);
        var forecast=NativeEffectAmounts.Estimate(rounded.Rows[0],caster,enemy)!;
        Check(Math.Abs(forecast.ProbabilityAtLeast(2)-.5)<1e-10,"75% of2HP has half kill probability, not guaranteed ceil2");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,enemy,rounded,3)}))
            Check(enemy.CurrentHP==1,"fractional native amount replay retains the conservative living branch");
        var certain=Spell(9107,Row("damage",0,2,"enemy"),2);
        plan=MonsterTactics.PlanTurn(board,caster,new[]{rounded,certain},budgetMs:1000);
        Check(plan.Count==1&&plan[0].Spell.Id==9107,"actual planner prefers certain native kill to half-chance rounding");

        enemy.CurrentHP=100;enemy.NativeHpMinimum=1;var full=Spell(9108,Row("damage",5,100,"enemy"),100);
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,enemy,full,3)}))
            Check(enemy.CurrentHP==1,"native HP floor remains alive under100% current-HP damage");
        enemy.NativeHpFrozen=true;
        Check(MonsterTactics.PlanTurn(board,caster,new[]{full},budgetMs:1000).Count==0,"frozen native HP grants no fabricated damage/kill value");
        enemy.NativeHpFrozen=false;enemy.NativeHpMinimum=0;enemy.CurrentHP=5;enemy.MaxHP=5;
        enemy.NativeHpRawMode="copied";enemy.NativeHpRawCurrent=10;
        var shift=NativeHpForecast.Apply(enemy,5,true);
        Check(shift.Current==5&&shift.Raw==5,"copied raw10/effective5 consumes hidden raw HP without inventing visible damage");
        Check(enemy.NativeHpRawCurrent==10&&enemy.CurrentHP==5,"raw HP arithmetic does not mutate the native snapshot");
        caster.CurrentAP=6;
        var rawHit=Spell(9109,Row("damage",0,5,"enemy"),5);
        plan=MonsterTactics.PlanTurn(board,caster,new[]{rawHit},budgetMs:1000);
        Check(plan.Count==2,"planner retains necessary zero-visible-damage raw-HP preparation before actual kill");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,plan))
            Check(enemy.CurrentHP==0&&enemy.NativeHpRawCurrent==0,
                "two real PA forecasts consume raw10→5→0 and only second cast kills effective5");
        Check(enemy.CurrentHP==5&&enemy.NativeHpRawCurrent==10&&caster.CurrentAP==6,
            "raw-HP preparation forecast restores original source and hidden raw state");
        enemy=Actor(2,1,1,20);enemy.NativeStats=new Dictionary<int,int>{{87,50},{32,0}};
        board=Board(new[]{caster,enemy});var blocked=Row("damage",5,100,"enemy");
        forecast=NativeEffectAmounts.Estimate(blocked,caster,enemy)!;
        Check(Math.Abs(forecast.Mean-18)<1e-10&&Math.Abs(forecast.ProbabilityAtLeast(20)-.5)<1e-10,
            "native50% block gives16/20 damage and half kill odds, not a guaranteed kill");
        var unblocked=SemanticRows.Create("damage",20,"enemy",nativeCoefficientMask:0,nativeDamageFlags:new[]{2});
        NativeEffectAmounts.Bind(unblocked,0,20);
        Check(NativeEffectAmounts.Estimate(unblocked,caster,enemy)!.ProbabilityAtLeast(20)==1,
            "original flag2 bypasses block without sampling authoritative RNG");
        enemy.NativeStats=new Dictionary<int,int>{{32,0}};
        Check(NativeEffectAmounts.Estimate(blocked,caster,enemy)==null,
            "absent native block characteristic stays unknown, not invented zero");
        enemy=Actor(2,1,1,5);board=Board(new[]{caster,enemy});
        var chanceRow=SemanticRows.Create("damage",5,"enemy",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(chanceRow,0,5,probability:.5);
        var chance=NativeEffectAmounts.Estimate(chanceRow,caster,enemy)!;
        Check(chance.Minimum==0&&Math.Abs(chance.Mean-2.5)<1e-10&&chance.ProbabilityAtLeast(5)==.5,
            "native spell probability retains a real miss branch and weighted damage/kill odds");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,enemy,Spell(9111,chanceRow,5),6)}))
            Check(enemy.CurrentHP==5&&caster.CurrentAP==3,"uncertain damage replay does not fabricate guaranteed minimum1 on a miss");
        var uncertain=SemanticRows.Create("damage",5,"enemy",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(uncertain,0,5,eligibilityKnown:false);
        Check(NativeEffectAmounts.Estimate(uncertain,caster,enemy)==null,"unproven native eligibility is not forecast as an unconditional hit");
        var guarded=SemanticRows.Create("heal",20,"ally",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(guarded,0,20,1,eligibilityKnown:false,targetNotCarried:true);
        Check(NativeEffectAmounts.Estimate(guarded,caster,enemy)!=null,"exact known not-carried fact discharges that native healing guard");
        enemy.NativeIsCarried=true;
        Check(NativeEffectAmounts.Estimate(guarded,caster,enemy)==null,"actually carried target fails the proven healing guard");
        enemy.NativeIsCarried=null;
        Check(NativeEffectAmounts.Estimate(guarded,caster,enemy)==null,"missing carrying authority remains unknown");
        enemy.NativeIsCarried=false;
        var rebound=SemanticRows.Create("damage",5,"enemy",nativeCoefficientMask:0);
        NativeEffectAmounts.Bind(rebound,0,5,sourceBindingKnown:false);
        Check(NativeEffectAmounts.Estimate(rebound,caster,enemy)==null,"unknown effective caster cannot lend fabricated damage/barrier stats");
        var targetOnly=SemanticRows.Create("heal",30,"ally",nativeCoefficientMask:2);
        NativeEffectAmounts.Bind(targetOnly,4,30,1,sourceBindingKnown:false);
        Check(NativeEffectAmounts.Estimate(targetOnly,caster,enemy)==null,
            "unknown effective caster also invalidates typed healing recipient authority");
        enemy=Actor(2,1,1,5,5);enemy.NativeStats=new Dictionary<int,int>{{87,0},{32,0},{97,5}};
        enemy.NativeArmorAuthority=new NativePoolAuthority(0,5,false);board=Board(new[]{caster,enemy});
        var armorHit=Spell(9110,Row("damage",0,5,"enemy"),5);
        plan=MonsterTactics.PlanTurn(board,caster,new[]{armorHit},budgetMs:1000);
        Check(plan.Count==2,"known unfrozen armor retains the necessary armor-breaking prefix before kill");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,plan))
            Check(enemy.CurrentHP==0&&enemy.NativeForecastArmor==0,"known armor depletes5→0 before second native hit kills");
        Check(enemy.CurrentHP==5&&enemy.NativeStats[97]==5&&enemy.NativeForecastArmor==null,
            "armor preparation replay restores HP, immutable source stats and private pool");
        enemy.NativeArmorAuthority=null;
        Check(MonsterTactics.PlanTurn(board,caster,new[]{armorHit},budgetMs:1000).Count==0,
            "unknown armor mutability does not invent future depletion and kill");
        enemy.NativeArmorAuthority=new NativePoolAuthority(0,5,true);
        plan=MonsterTactics.PlanTurn(board,caster,new[]{armorHit},budgetMs:1000);
        Check(plan.Count==1,"source-proven frozen armor consumes zero native PA and cannot absorb the hit");
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,plan))
            Check(enemy.CurrentHP==0&&NativeHpForecast.Armor(enemy)==5,
                "frozen armor remains5 while the original unabsorbed damage kills HP5");
        enemy=Actor(2,1,1);enemy.NativeHpRawMode="copied";enemy.NativeHpRawCurrent=100;
        caster.CurrentAP=6;board=Board(new[]{caster,enemy});
        var legacyHit=Spell(9112,SemanticRows.Create("damage",20,"enemy",nativeCoefficientMask:0),20);
        var followingPercent=Spell(9113,Row("damage",5,50,"enemy"));
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,enemy,legacyHit,6),Step(caster,enemy,followingPercent,3)}))
            Check(enemy.CurrentHP==40&&enemy.NativeHpRawCurrent==40,
                "legacy flat hit updates copied rawHP before typed current-percent damage:100→80→40");
        Check(enemy.CurrentHP==100&&enemy.NativeHpRawCurrent==100,"mixed legacy/native damage restores effective and rawHP");
        enemy.NativeHpRawMode="bounded";enemy.NativeHpRawCurrent=null;enemy.NativeHpMinimum=1;caster.CurrentAP=3;
        var legacyFinisher=Spell(9114,SemanticRows.Create("damage",100,"enemy",nativeCoefficientMask:0),100);
        using(var replay=MonsterTactics.Simulation.Replay(board,caster,new[]{Step(caster,enemy,legacyFinisher,3)}))
            Check(enemy.CurrentHP==1,"legacy flat damage honors explicit native HP floor before future typed casts");
        enemy.NativeHpFrozen=true;
        Check(MonsterTactics.PlanTurn(board,caster,new[]{legacyFinisher},budgetMs:1000).Count==0,
            "legacy damage does not receive a fake kill bonus against explicitly frozen native HP");

        using(var sdk=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
            "Fixtures","NativeAmountSdkGoldens.json"))))
        {
            var oldAssembly=System.Reflection.Assembly.LoadFrom(Path.Combine(AppContext.BaseDirectory,
                "Fixtures","OldConsumer89179.dll"));
            var oldDecide=oldAssembly.GetType("Wakfu.Jondo.Planner")!.GetMethod("Decide",
                System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
            object JsonActor(long id,int team,int cell,int hp)=>new{id,team,cell,hp,maxHp=100,ap=id==1?3:0,mp=0,
                stats=new Dictionary<string,int>{{"87",0},{"32",0},{"21",500},{"97",0},{"100",0},{"92",0}},physicalRadius=0,direction=1,
                nativeHp=new{version=1,minimum=0,frozen=false,rawCurrentMode="bounded",rawCurrent=(int?)null},
                nativeUndead=false,nativeIsCarried=false,nativeHealingResistanceEnabled=false,nativeVirtualHpFrozen=false,virtualHpMax=0,
                nativeHealingResistance=new{enabled=false,minimum=0,maximum=1000,frozen=false},
                nativeArmor=new{version=1,minimum=0,maximum=int.MaxValue,frozen=false},
                nativeBarrier=new{version=1,minimum=0,maximum=int.MaxValue,frozen=false},
                nativeVirtualHp=new{version=1,minimum=0,maximum=0,frozen=false}};
            foreach(var record in sdk.RootElement.GetProperty("effects").EnumerateObject())
            {
                var request=JsonSerializer.SerializeToElement(new{protocol=1,requestId="native-amount-"+record.Name,
                    source=new{actorId=1L,fightInstanceId="native-amount-"+record.Name,turnId=1,catalogRevision="0793-actual-SDK-rows"},
                    board=new{cells=cells.Select((p,id)=>new{id,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
                        edges=new[]{new[]{0,1},new[]{1,0},new[]{1,2},new[]{2,1}},
                        actors=new[]{JsonActor(1,0,0,100),JsonActor(2,0,1,10),JsonActor(3,1,2,100)}},
                    spells=new[]{new{id=int.Parse(record.Name),grade=1,cost=3,minRange=1,maxRange=3,
                        rows=record.Value.GetProperty("semantic").Clone()}},
                    native=new{usage=Array.Empty<object>()},limits=new{budgetMs=500}});
                string original=request.GetRawText();var response=JsonSerializer.SerializeToElement(Planner.Decide(request));
                var action=response.GetProperty("action");
                Check(action.GetProperty("type").GetString()=="cast"&&action.GetProperty("targetId").GetInt64()==2,
                    "actual Host selects wounded ally from real SDK zero-scalar native heal rows: "+record.Name);
                Check(request.GetRawText()==original,"Host preserves actual SDK native amount DTO: "+record.Name);
                var oldResponse=JsonSerializer.SerializeToElement(oldDecide.Invoke(null,new object?[]{request,null}));
                Check(oldResponse.GetProperty("action").GetProperty("type").GetString()!="cast",
                    "actual frozen89179 binary cannot fabricate health from closed typed geometry: "+record.Name);
            }
            using var witnessed=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,
                "Fixtures","Native1533ObservedCase.json")));
            var originalCase=witnessed.RootElement;
            var owned=sdk.RootElement.GetProperty("bookProjections").GetProperty("1533");
            var serialized=owned.GetProperty("semantic").EnumerateArray().Single(r=>
                r.GetProperty("kind").GetString()=="heal"&&r.GetProperty("target").GetString()=="ally");
            var descriptor=NativeEffectAmounts.ReadDescriptor(serialized)!;
            var nativeGeometry=NativeEffectAmounts.Geometry(serialized);
            var nativeOffsets=nativeGeometry.GetProperty("fixedCells").EnumerateArray()
                .Select(p=>(p[0].GetInt32(),p[1].GetInt32())).ToArray();
            var realHeal=SemanticRows.WithOffsets(SemanticRows.Create("heal",0,"ally",
                nativeCoefficientMask:serialized.GetProperty("nativeCoefficientMask").GetInt32(),
                nativeDamageFlags:serialized.GetProperty("nativeDamageFlags").EnumerateArray().Select(p=>p.GetInt32()).ToArray()),nativeOffsets);
            SemanticRows.WithNativeAreaPolicy(realHeal,nativeGeometry.GetProperty("nativeAreaCenterOnCaster").GetBoolean(),
                nativeGeometry.GetProperty("nativeAreaUseTargetRadius").GetBoolean());
            NativeAreaPolicy.Bind(realHeal,nativeGeometry.GetProperty("nativeInArea").GetBoolean());
            NativeEffectAmounts.Bind(realHeal,descriptor.Kind,descriptor.Value,descriptor.HealingElement,
                descriptor.Probability,descriptor.EligibilityKnown,descriptor.SourceBindingKnown,descriptor.TargetNotCarried);
            Check(descriptor.SourceBindingKnown&&descriptor.TargetNotCarried&&!descriptor.EligibilityKnown,
                "actual owned1533 retains proven source plus conditional not-carried guard");
            var realCells=new[]{new CellXYZ(0,0,0),new CellXYZ(1,0,0),new CellXYZ(10,0,0)};
            using var realScope=MapGeometry.BeginScope(new GeometryContext(realCells,new[]{(0,1),(1,0)}));
            // HP, stats and the witnessed healing sequence are real receipts.
            // PA bounds/raw mode/carrying/pool authority are controlled advisory
            // premises here: the older receipt did not capture these new fields.
            // This replay is not a new native World integration qualification.
            var healer=Actor(1,0,0,originalCase.GetProperty("source").GetProperty("hp").GetInt32(),
                originalCase.GetProperty("source").GetProperty("maxHp").GetInt32());
            var patient=Actor(2,0,1,originalCase.GetProperty("target").GetProperty("hp").GetInt32(),
                originalCase.GetProperty("target").GetProperty("maxHp").GetInt32());
            healer.NativeStats=JsonSerializer.Deserialize<Dictionary<int,int>>(originalCase.GetProperty("source").GetProperty("stats"))!;
            patient.NativeStats=JsonSerializer.Deserialize<Dictionary<int,int>>(originalCase.GetProperty("target").GetProperty("stats"))!;
            healer.CurrentAP=healer.MaxAP=4;healer.Level=patient.Level=83;
            var distant=Actor(3,1,2,2050,2050);
            var realBoard=Board(new[]{healer,patient,distant});
            var realSpell=new MonsterTactics.Spell{Id=1533,Grade=83,Cost=2,MinRange=1,MaxRange=6,
                PerTarget=3,Heal=14,Rows=new[]{realHeal}};
            var observed=originalCase.GetProperty("observedHeals").EnumerateArray().ToArray();
            using(var replay=MonsterTactics.Simulation.Replay(realBoard,healer,new[]{Step(healer,patient,realSpell,4)}))
                Check(patient.CurrentHP==observed[0].GetProperty("after").GetInt32(),
                    "actual1533 native14/water346 witnessed first lower branch heals1394→1456(+62)");
            var realPlan=MonsterTactics.PlanTurn(realBoard,healer,new[]{realSpell},budgetMs:1000);
            Check(realPlan.Count==2,"actual1533 keeps the final11HP heal instead of legacy10%remaining cutoff");
            using(var replay=MonsterTactics.Simulation.Replay(realBoard,healer,realPlan))
                Check(patient.CurrentHP==observed[1].GetProperty("after").GetInt32()&&healer.CurrentAP==0,
                    "actual1533 second native heal restores1456→1467(+11) within4AP");
            Check(patient.CurrentHP==1394&&healer.CurrentAP==4&&patient.NativeStats[32]==0,
                "actual1533 replay restores captured original HP, AP and resistance");
            patient.NativeIsCarried=true;
            Check(MonsterTactics.PlanTurn(realBoard,healer,new[]{realSpell},budgetMs:1000).Count==0,
                "actual owned1533 rejects carried recipient without bypassing its native guard");
            patient.NativeIsCarried=null;
            Check(MonsterTactics.PlanTurn(realBoard,healer,new[]{realSpell},budgetMs:1000).Count==0,
                "actual owned1533 does not invent absent carrying authority");
            System.Text.Json.Nodes.JsonObject ActorNode(long id,int team,int cell,JsonElement facts,int ap)
            {
                var node=JsonSerializer.SerializeToNode(JsonActor(id,team,cell,facts.GetProperty("hp").GetInt32()))!.AsObject();
                node["maxHp"]=facts.GetProperty("maxHp").GetInt32();node["ap"]=ap;node["maxAp"]=8;
                node["level"]=83;node["monsterRef"]=5022;node["wp"]=4;
                var stats=System.Text.Json.Nodes.JsonNode.Parse(facts.GetProperty("stats").GetRawText())!.AsObject();
                // A valid remaining-resource window isolates two heals; mastery,
                // HP and resistances remain the captured native values.
                stats["2"]=ap;stats["3"]=0;node["stats"]=stats;return node;
            }
            var fullSource=ActorNode(1,0,0,originalCase.GetProperty("source"),4);
            var fullTarget=ActorNode(2,0,1,originalCase.GetProperty("target"),0);
            var fullSpell=System.Text.Json.Nodes.JsonNode.Parse(originalCase.GetProperty("spell").GetRawText())!.AsObject();
            fullSpell["rows"]=System.Text.Json.Nodes.JsonNode.Parse(owned.GetProperty("semantic").GetRawText());
            fullSpell["nativeSupport"]=System.Text.Json.Nodes.JsonNode.Parse(owned.GetProperty("support").GetRawText());
            foreach(bool? carried in new bool?[]{false,true,null})
            {
                if(carried.HasValue)fullTarget["nativeIsCarried"]=carried.Value;
                else fullTarget.Remove("nativeIsCarried");
                var request=JsonSerializer.SerializeToElement(new{protocol=1,requestId="owned1533-"+carried,
                    source=new{actorId=1L,fightInstanceId="owned1533-"+carried,turnId=1,catalogRevision="0793-actual-owned1533"},
                    board=new{cells=realCells.Select((p,id)=>new{id,xyz=new[]{p.X,p.Y,p.Z}}).ToArray(),
                        edges=new[]{new[]{0,1},new[]{1,0}},actors=new object[]{fullSource,fullTarget,JsonActor(3,1,2,100)},
                        lineOfSight=Enumerable.Range(0,3).SelectMany(a=>Enumerable.Range(0,3).Select(b=>new object[]{a,b,true})).ToArray()},
                    spells=new[]{fullSpell},native=new{usage=Array.Empty<object>()},limits=new{budgetMs=500}});
                var response=JsonSerializer.SerializeToElement(Planner.Decide(request));var action=response.GetProperty("action");
                Check(carried==false?action.GetProperty("type").GetString()=="cast"&&action.GetProperty("targetId").GetInt64()==2
                    :action.GetProperty("type").GetString()!="cast",
                    "actual Host whole owned1533 mixed book respects exact carrying guard: "+carried);
                if(carried==false)
                {
                    var oldResponse=JsonSerializer.SerializeToElement(oldDecide.Invoke(null,new object?[]{request,null}));
                    Check(oldResponse.GetProperty("action").GetProperty("type").GetString()!="cast",
                        "actual frozen89179 cannot fabricate mixed-book healing while its valid damage target is out of range");
                }
            }
        }
        Console.WriteLine($"PASS: {checks} staged native amount/healing/HP checks");
        return checks;
    }
}
