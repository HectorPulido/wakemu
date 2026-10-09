import java.lang.reflect.*;
import java.util.*;

/** Real eZG.c / PB counter arithmetic / fff setters, no running services. */
public final class ProbeNativeProtectedKill {
    static void field(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    static class Counts extends PB<ffe> {
        public boolean a(wU raw) { throw new UnsupportedOperationException(); }
        public boolean b(wU raw) { throw new UnsupportedOperationException(); }
    }
    public static void main(String[] args) throws Exception {
        Method apply=eZG.class.getDeclaredMethod("c",Qe.class,boolean.class);
        apply.setAccessible(true);
        int cases=0;
        for(int count=-128;count<=127;count++) for(boolean frozen:new boolean[]{false,true}) {
            Counts counts=new Counts();counts.a(ffe.sdP,(byte)count);counts.a(ffe.sdJ,(byte)count);
            fff hp=new fff(ffw.sgC,0,100), clock=new fff(ffw.sgM,0,10);
            field(hp,fff.class,"bqG",100);field(clock,fff.class,"bqG",10);
            hp.on(40);clock.on(3);
            field(hp,fff.class,"sfT",frozen);
            List<Integer> calls=new ArrayList<>();
            PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)-> {
                if(m.getName().equals("f")) {
                    ffe property=(ffe)a[0];calls.add((int)property.aKg());counts.c(property);return null;
                }
                if(m.getName().equals("b")) return a[0]==ffw.sgC?hp:clock;
                throw new AssertionError("Unexpected PV access "+m);
            });
            eZG runner=new eZG();field(runner,Qe.class,"bfs",target);
            runner.C(null);apply.invoke(runner,null,false);
            int expected=(byte)(count+1);
            if(counts.b(ffe.sdP)!=expected || counts.b(ffe.sdJ)!=expected
                    || !calls.equals(List.of(19,12)) || hp.aYS()!=(frozen?40:0)
                    || clock.aYW()!=0 || clock.aYS()!=0 || runner.getValue()!=0)
                throw new AssertionError("Native eZG mismatch "+count+" "+frozen
                    +" counters="+counts.b(ffe.sdP)+","+counts.b(ffe.sdJ)
                    +" calls="+calls+" hp="+hp.aYS()+" clock="+clock.aYW()+","+clock.aYS()
                    +" value="+runner.getValue());
            cases++;
        }
        System.out.println("PASS "+cases+" eZG counter wrap, property order, HP min/frozen, KO max0, value0");
    }
}
