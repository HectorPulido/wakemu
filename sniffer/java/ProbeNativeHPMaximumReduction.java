import java.lang.reflect.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Actual eWO HP setters and Qe event flags; no game services required. */
public class ProbeNativeHPMaximumReduction {
    static void set(Object o,Class<?> c,String n,Object v)throws Exception {
        Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);
    }
    public static void main(String[] args)throws Exception {
        if (!(eVi.fLJ().pS(21) instanceof eWO)) throw new AssertionError("registry");
        List<Object> rows=new ArrayList<>();
        for(int[] test:new int[][]{{60,25,2,1,1},{60,150,0,1,1},{60,150,2,1,1},{60,25,2,0,1},{60,25,2,1,0},{60,-25,2,1,1},{1,99,0,1,1}}) {
            int initial=test[0], amount=test[1], mode=test[2];
            fff hp=new fff(ffw.sgC,0,1000);hp.or(100);hp.on(initial);
            Map<PC,fff> stats=new HashMap<>();stats.put(ffw.sgC,hp);
            eWO runner=new eWO(ffw.sgC);
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
                (p,m,a)->switch(m.getName()) {case "aZD"->(byte)mode;default->throw new UnsupportedOperationException(m.getName());});
            set(runner,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));
            set(runner,Qe.class,"bfp",definition);set(runner,Qe.class,"aSg",amount);
            set(runner,Qe.class,"bfD",true);set(runner,eZR.class,"rEj",true);set(runner,eWO.class,"rCs",test[3]==1);set(runner,eWO.class,"rCr",test[4]==1);
            Method apply=eWO.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,true);
            Map<String,Object> row=new LinkedHashMap<>();row.put("input",test);row.put("applied",runner.getValue());
            row.put("after",List.of(hp.aYS(),hp.aYU(),hp.aYW(),hp.aYT()));row.put("events",runner.bbw().toString());
            runner.bbR();row.put("removed",List.of(hp.aYS(),hp.aYU(),hp.aYW(),hp.aYT()));rows.add(row);
        }
        System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(rows));
        System.exit(0);
    }
}
