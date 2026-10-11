import java.lang.reflect.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Original eVi991/eWN PC14, cap, Qe event flags and fff raw-current lifecycle. */
public class ProbeNativeKOMaximum {
    static void set(Object o,Class<?> c,String n,Object v)throws Exception {
        Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);
    }
    public static void main(String[]args)throws Exception {
        Object prototype=eVi.fLJ().pS(991);
        if (!(prototype instanceof eWN original))throw new AssertionError("not eWN");
        PC stat=original.fNI();original.bbx();
        if ((stat.aKg()&255)!=14)throw new AssertionError("not PC14");
        Map<String,Object> output=new LinkedHashMap<>();
        output.put("effect_class",991);output.put("runner",original.getClass().getName());
        output.put("fixed_stat_id",stat.aKg()&255);output.put("cap",stat.aZt());
        output.put("events",original.bbw().stream().boxed().toList());
        output.put("bbA",original.bbA());output.put("bbB",original.bbB());
        List<Object> rows=new ArrayList<>();
        for(int[]test:new int[][]{{3,3,0,2,1,1,0},{3,3,0,10,1,1,0},{4,3,50,2,1,1,0},{3,3,0,2,0,1,0},{3,3,0,2,1,0,0},{3,5,0,2,1,1,1},{3,3,0,-2,1,1,0}}) {
            fff pa=new fff((ffw)stat,0,Integer.MAX_VALUE);pa.or(test[0]);pa.om(test[2]);
            pa.on(Math.min(test[0],test[1]));
            // Original copy authority permits hidden frozen raw current.
            if(test[6]==1) {set(pa,fff.class,"bqD",test[1]);set(pa,fff.class,"sfT",true);}
            Map<PC,fff> stats=new HashMap<>();stats.put(stat,pa);
            eWN runner=new eWN(stat);set(runner,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));
            set(runner,Qe.class,"aSg",test[3]);set(runner,eWN.class,"rCl",test[4]==1);
            set(runner,eWN.class,"rCm",test[5]==1);set(runner,eZR.class,"rEj",true);
            Method apply=eWN.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,true);
            Map<String,Object> row=new LinkedHashMap<>();row.put("input",test);row.put("applied",runner.getValue());
            row.put("after",List.of(pa.aYS(),pa.aYU(),pa.aYV(),pa.aYT()));
            runner.bbR();row.put("removed",List.of(pa.aYS(),pa.aYU(),pa.aYV(),pa.aYT()));rows.add(row);
        }
        output.put("rows",rows);System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(output));System.exit(0);
    }
}
