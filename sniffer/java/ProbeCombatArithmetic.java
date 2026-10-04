import java.util.*;
import java.lang.reflect.*;
/** Native common fau/fat arithmetic and eXt characteristic absorption proof. */
public class ProbeCombatArithmetic {
    static PV actor(Map<PC,fff> stats, int x) {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},
            (proxy,method,args)->switch(method.getName()) {
                case "a" -> stats.containsKey(args[0]);
                case "b" -> stats.get(args[0]);
                case "c" -> stats.containsKey(args[0]) ? stats.get(args[0]).aYS() : 0;
                case "bcz" -> x;
                case "bcA" -> 0;
                case "bcB" -> (short)0;
                case "bcL", "bcK" -> (byte)0;
                case "Sn" -> x==0?22L:-33L;
                case "bcy" -> aAS.dyA;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    static Map<PC,fff> stats(PC stat,int amount) {
        Map<PC,fff> values=new HashMap<>(); put(values,(ffw)stat,amount); return values;
    }
    static void put(Map<PC,fff> values,ffw stat,int amount) {
        fff value=new fff(stat,0,1000000);value.or(1000000);value.on(amount);values.put(stat,value);
    }
    static void healing(int base,Map<PC,fff> source,Map<PC,fff> target,int expected) {
        fat formula=new fat(actor(source,0),actor(target,1),eVg.rpe,null);
        formula.setValue(base);formula.Tf(3);formula.mq(false);formula.fSy();
        if(formula.getValue()!=expected)throw new AssertionError("native heal:"+formula.getValue()+" expected"+expected);
        System.out.println("heal "+base+" -> "+formula.getValue());
    }
    public static void main(String[] args)throws Exception {
        for(Set<eVl> flags:List.of(Set.<eVl>of(),Set.of(eVl.rwT,eVl.rwU),Set.of(eVl.rxe))) {
            eVn effect=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
                (proxy,method,arguments)->switch(method.getName()) {
                    case "a" -> flags.contains(arguments[0]);
                    default -> throw new UnsupportedOperationException(method.getName());
                });
            boolean melee=eYE.b(actor(new HashMap<>(),0),actor(new HashMap<>(),1),effect);
            boolean ranged=eYE.a(actor(new HashMap<>(),0),actor(new HashMap<>(),1),effect);
            if(!melee || ranged!=flags.contains(eVl.rwU))throw new AssertionError("native range flags");
            eXt x=new eXt(eVg.rpe,far.rJU);
            Field definition=Qe.class.getDeclaredField("bfp");definition.setAccessible(true);definition.set(x,effect);
            Method indirect=eXt.class.getDeclaredMethod("fOG");indirect.setAccessible(true);
            if((boolean)indirect.invoke(x)==flags.contains(eVl.rxe))throw new AssertionError("native forced direct flag");
            System.out.println("native range/direct flags "+flags+" melee="+melee+" ranged="+ranged);
        }
        for(int mask=0;mask<4;mask++) {
            Map<PC,fff> s=new HashMap<>(),t=new HashMap<>();
            put(s,ffw.sgQ,100);put(s,ffw.shi,100);
            put(t,ffw.shj,50);
            fau f=new fau(actor(s,0),actor(t,1),eVg.rpe,null);
            f.setValue(200);f.Tf(mask);f.mq(false);f.mw(false);f.fSy();
            int expected=new int[]{200,800,100,600}[mask];
            if(f.getValue()!=expected)throw new AssertionError("fau mask"+mask+":"+f.getValue());
            System.out.println("native coefficient mask"+mask+" -> "+expected);
        }
        for(int[] parameters:new int[][]{{80},{80,0},{80,2,0},{10,3,1},{10,3,2},{10,3,3},{10,3,4},{10,3,5},{10,3,6},{80,3,99}}) {
            eVn effect=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
                (proxy,method,arguments)->switch(method.getName()) {
                    case "fKJ" -> parameters.length;
                    case "a" -> parameters[(int)arguments[0]];
                    default -> throw new UnsupportedOperationException(method.getName());
                });
            eXt x=new eXt(eVg.rpe,far.rJU);
            Field definition=Qe.class.getDeclaredField("bfp");definition.setAccessible(true);definition.set(x,effect);
            Map<PC,fff>s=new HashMap<>(),t=new HashMap<>();
            put(s,ffw.sgC,300);put(t,ffw.sgC,600);
            Field source=Qe.class.getDeclaredField("bfr"),target=Qe.class.getDeclaredField("bfs");
            source.setAccessible(true);target.setAccessible(true);
            source.set(x,actor(s,0));target.set(x,actor(t,1));
            Method evaluate=eXt.class.getDeclaredMethod("fOA");evaluate.setAccessible(true);evaluate.invoke(x);
            int kind=parameters.length==3?parameters[2]:0;
            int expected=switch(kind){case 1,4->100000;case 2->30;case 3->99970;case 5->60;case 6->99940;default->80;};
            if(x.getValue()!=expected || x.rDu!=(parameters.length>1?parameters[1]:3))
                throw new AssertionError("native eXt parameter contract");
            System.out.println("native eXt params"+Arrays.toString(parameters)+" -> value"+x.getValue()+" mask"+x.rDu+" kind"+x.rDt);
        }
        for(ffw stat:new ffw[]{ffw.sgQ,ffw.sgP,ffw.shl,ffw.shU,ffw.shX,ffw.shY,ffw.shV,ffw.shW,ffw.shZ,ffw.sha,ffw.sig,ffw.shS,ffw.shQ,ffw.shL})
            System.out.println(stat.toString()+" id="+(stat.aKg()&255));
        healing(80,stats(ffw.sgP,25),new HashMap<>(),100);
        healing(80,stats(ffw.sgQ,25),new HashMap<>(),100);
        healing(80,stats(ffw.sig,25),new HashMap<>(),100);
        healing(100,new HashMap<>(),stats(ffw.sha,100),90);
        Map<PC,fff> source=new HashMap<>(),target=new HashMap<>();
        put(source,ffw.shS,15);put(target,ffw.shQ,20);put(target,ffw.shL,30);put(target,ffw.sgC,100);
        eXt damage=new eXt();
        Method consume=eXt.class.getDeclaredMethod("a",int.class,PV.class,PV.class);consume.setAccessible(true);
        consume.invoke(damage,101,actor(source,0),actor(target,1));
        int hp=target.get(ffw.sgC).aYS();
        if(hp!=64 || source.get(ffw.shS).aYS()!=0 || target.get(ffw.shQ).aYS()!=0 || target.get(ffw.shL).aYS()!=0)
            throw new AssertionError("native source barrier / target armor / virtual HP order");
        System.out.println("damage101 -> source barrier15 + target armor20 + virtualHP30 + HP36; target HP64");
    }
}
