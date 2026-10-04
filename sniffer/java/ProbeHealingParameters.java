import java.util.*;
import java.lang.reflect.*;
/** Offline native eXs/fat parameter and consumption proof. */
public class ProbeHealingParameters {
    static void set(Object obj,String name,Object value)throws Exception {
        Field f=Qe.class.getDeclaredField(name);f.setAccessible(true);f.set(obj,value);
    }
    public static void main(String[] args)throws Exception {
        for(int[] p:new int[][]{{80},{80,0},{10,3,1},{10,3,2},{10,3,3},{10,3,4},{10,3,5},{10,3,6},{80,3,99}}){
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
                (proxy,m,a)->switch(m.getName()){case "fKJ"->p.length;case "a"->p[(int)a[0]];default->throw new UnsupportedOperationException(m.getName());});
            eXs runner=new eXs(eVg.rpe,far.rJU);
            set(runner,"bfp",definition);
            set(runner,"bfr",ProbeCombatArithmetic.actor(ProbeCombatArithmetic.stats(ffw.sgC,300),0));
            set(runner,"bfs",ProbeCombatArithmetic.actor(ProbeCombatArithmetic.stats(ffw.sgC,600),1));
            Method evaluate=eXs.class.getDeclaredMethod("fOA");evaluate.setAccessible(true);evaluate.invoke(runner);
            int mode=p.length==3?p[2]:0;
            int expected=switch(mode){case 1,4->100000;case 2->30;case 3->99970;case 5->60;case 6->99940;default->80;};
            if(runner.getValue()!=expected)throw new AssertionError("eXs parameters");
            System.out.println(Arrays.toString(p)+" -> "+runner.getValue());
        }
        Map<PC,fff> target=new HashMap<>();
        fff hp=new fff(ffw.sgC,0,100);hp.or(100);hp.on(90);target.put(ffw.sgC,hp);
        fff virtual=new fff(ffw.shL,0,20);virtual.or(20);virtual.on(5);target.put(ffw.shL,virtual);
        eXs runner=new eXs(eVg.rpe,far.rJU);set(runner,"bfs",ProbeCombatArithmetic.actor(target,1));set(runner,"aSg",30);
        Method consume=eXs.class.getDeclaredMethod("fOz");consume.setAccessible(true);consume.invoke(runner);
        if(runner.getValue()!=25 || hp.aYS()!=100 || virtual.aYS()!=20)throw new AssertionError("eXs consumption");
        System.out.println("30 computed -> HP10 + virtual15; aSg25 (PO receives same field)");
        Map<PC,fff> source=new HashMap<>();ProbeCombatArithmetic.put(source,ffw.shV,25);ProbeCombatArithmetic.put(source,ffw.shW,25);
        eVn flags=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(proxy,m,a)->m.getName().equals("a") && (a[0]==eVl.rwT || a[0]==eVl.rwU));
        fat f=new fat(ProbeCombatArithmetic.actor(source,0),ProbeCombatArithmetic.actor(new HashMap<>(),1),eVg.rpe,flags);
        f.setValue(80);f.Tf(3);f.Tg(25);f.fSy();
        if(f.getValue()!=150)throw new AssertionError("both range/additional final "+f.getValue());
        System.out.println("both range masteries25 + additional final25:80 ->150");
    }
}
