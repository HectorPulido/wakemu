import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
/** Offline registry, null400 and characteristic current gain/loss evidence. */
public class ProbeStatEffects {
    static void assign(Object object,Class<?> owner,String name,Object value)throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    static eVn definition(int id,int... params) {
        return (eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
            (proxy,method,args)->switch(method.getName()) {
                case "aZE"->id;
                case "fKJ"->params.length;
                case "a"->{if(args.length==3 && ((short)args[1])!=0)throw new AssertionError("null400 level must0");yield params[(int)args[0]];}
                default->throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[]args)throws Exception {
        Object runner=eVi.fLJ().pS(400);
        if(!(runner instanceof eXE))throw new AssertionError("400 must null eXE");
        eXE nil=new eXE();nil.lV(400);nil.dg(2345);nil.dj(1234);
        assign(nil,Qe.class,"bfp",definition(150327,7));
        nil.C(null);
        if(nil.cYh()!=7 || nil.getValue()!=0)throw new AssertionError("null status/value");
        assign(nil,Qe.class,"bfr",ProbeCombatArithmetic.actor(new HashMap<>(),0));
        assign(nil,Qe.class,"bfs",ProbeCombatArithmetic.actor(new HashMap<>(),1));
        Method noop=eXE.class.getDeclaredMethod("c",Qe.class,boolean.class);noop.setAccessible(true);noop.invoke(nil,null,true);
        Files.write(Path.of(args[0]),nil.bca().toByteArray());
        System.out.println("400=eXE null stats; param0@level0 status7; value0 proto="+HexFormat.of().formatHex(nil.bca().toByteArray()));
        for(eWW change:new eWW[]{new eWQ(ffw.sgQ),new eWR(ffw.sgQ)}) {
            Map<PC,fff> stats=new HashMap<>();ProbeCombatArithmetic.put(stats,ffw.sgQ,80);
            assign(change,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));
            assign(change,Qe.class,"aSg",30);assign(change,eWW.class,"rCB",30);
            Method apply=change.getClass().getDeclaredMethod("d",PA.class);apply.setAccessible(true);apply.invoke(change,stats.get(ffw.sgQ));
            int expected=change instanceof eWQ?110:50;
            if(stats.get(ffw.sgQ).aYS()!=expected || change.getValue()!=30)throw new AssertionError("native current characteristic application");
            Method remove=change.getClass().getDeclaredMethod("fNM");remove.setAccessible(true);remove.invoke(change);
            if(stats.get(ffw.sgQ).aYS()!=80)throw new AssertionError("native current characteristic removal");
            change.lV(change instanceof eWQ?30:40);change.dg(2345);change.dj(1234);
            assign(change,Qe.class,"bfp",definition(150327));assign(change,Qe.class,"bfr",ProbeCombatArithmetic.actor(new HashMap<>(),0));
            System.out.println(change.getClass().getSimpleName()+" stat20 current80->"+expected+"->80 additional="+HexFormat.of().formatHex(change.bca().QA().toByteArray()));
        }
        for(eWW change:new eWW[]{new eWQ(ffw.sgQ),new eWR(ffw.sgQ)}) {
            Map<PC,fff> stats=new HashMap<>();fff value=new fff(ffw.sgQ,0,100);value.or(100);
            int before=change instanceof eWQ?80:10;value.on(before);stats.put(ffw.sgQ,value);
            assign(change,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));assign(change,Qe.class,"aSg",30);
            Method apply=change.getClass().getDeclaredMethod("d",PA.class);apply.setAccessible(true);apply.invoke(change,value);
            if(change.getValue()!=(change instanceof eWQ?20:10))throw new AssertionError("actual clamped delta");
            Method remove=change.getClass().getDeclaredMethod("fNM");remove.setAccessible(true);remove.invoke(change);
            if(value.aYS()!=before)throw new AssertionError("remove must reverse actual delta");
            System.out.println("clamped "+change.getClass().getSimpleName()+" request30 actual"+change.getValue()+" restores"+before);
        }
        if(args.length>1) {
            cvY packet=new cvY();if(!packet.dp(Files.readAllBytes(Path.of(args[1]))) || packet.eII()!=120)throw new AssertionError("application13497");
            eWQ received=new eWQ();received.lV(120);received.ds(packet.eIJ());
            if(received.LV()!=2345 || received.getValue()!=30 || received.Mt()!=30 || received.fNI()!=ffw.sgQ)
                throw new AssertionError("native stat application identity/additional");
            System.out.println("Python13497 -> native eWQ120 stat20 UID2345 actual30 request30");
        }
        for(Field field:eVi.class.getDeclaredFields())if(field.getType()==eVj.class) {
            field.setAccessible(true);eVj entry=(eVj)field.get(null);Object r=entry.bkv();
            if(r instanceof eWW stat && r.getClass()!=eWR.class && r.getClass()!=eWQ.class)continue;
            if(r instanceof eWW stat)System.out.println("registry "+entry.d()+" "+r.getClass().getSimpleName()+" stat="+(stat.fNI()==null?-1:(stat.fNI().aKg()&255)));
        }
    }
}
