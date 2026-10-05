import java.lang.reflect.*;

/** eXc28 mutates HP/KO clock, independently of ordinary damage arithmetic. */
public class ProbeNativeKill28 {
    public static void main(String[] args) throws Exception {
        Field target = Qe.class.getDeclaredField("bfs");
        target.setAccessible(true);
        Field bypass = eXc.class.getDeclaredField("rCL");
        bypass.setAccessible(true);
        Method apply = eXc.class.getDeclaredMethod("c", Qe.class, boolean.class);
        apply.setAccessible(true);
        for (boolean ignoreKo : new boolean[]{false,true}) {
            fff hp = new fff(ffw.sgC,5,100); hp.or(100); hp.on(80);
            fff clock = new fff(ffw.sgM,0,10); clock.or(10); clock.on(3);
            int[] propertyCalls = {0};
            PV actor = (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),
                new Class<?>[]{PV.class},(proxy,method,values)->{
                    if(method.getName().equals("a"))
                        return values[0]==ffw.sgC || values[0]==ffw.sgM;
                    if(method.getName().equals("b"))
                        return values[0]==ffw.sgC ? hp : clock;
                    if(method.getName().equals("f")) {
                        if(values[0]!=ffe.seI)throw new AssertionError("Wrong property");
                        propertyCalls[0]++;return null;
                    }
                    throw new UnsupportedOperationException(method.toString());
                });
            eXc runner = new eXc(); target.set(runner,actor); bypass.setBoolean(runner,ignoreKo);
            apply.invoke(runner,null,false);
            if(hp.aYT()!=5 || clock.aYT()!=0 || propertyCalls[0]!=(ignoreKo?1:0))
                throw new AssertionError("Kill contract mismatch");
        }
        eXc absent = new eXc(); apply.invoke(absent,null,false);
        if(!absent.fNj())throw new AssertionError("Null target must suppress notification");
        System.out.println("PASS eXc HP->minimum, KOclock->0, optional DONT_TRIGGER_KO, null suppression");
    }
}
