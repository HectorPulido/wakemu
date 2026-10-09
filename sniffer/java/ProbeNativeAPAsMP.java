import java.lang.reflect.*;
import java.util.*;

/** Original eWq/eWr and expandable/frozen PA setters, offline. */
public class ProbeNativeAPAsMP {
    static void set(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    static void check(fff value,int raw,int current,int maximum) {
        if(value.aYT()!=raw || value.aYS()!=current || value.aYU()!=maximum)
            throw new AssertionError(value.aYT()+"/"+value.aYS()+"/"+value.aYU());
    }
    public static void main(String[]args)throws Exception {
        fff ap=new fff(ffw.sgD,ffw.sgD.aZo(),ffw.sgD.aZp());ap.or(6);ap.on(6);
        fff mp=new fff(ffw.sgE,ffw.sgE.aZo(),ffw.sgE.aZp());mp.or(3);mp.on(3);
        eWq effect=new eWq();
        PV delegate=ProbeCombatArithmetic.actor(Map.of(ffw.sgD,ap,ffw.sgE,mp),7);
        PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},
            (proxy,method,arguments)->switch(method.getName()) {
                case "f", "h" -> null;
                default -> method.invoke(delegate,arguments);
            });
        set(effect,Qe.class,"bfs",target);
        effect.C(null);
        Method apply=eWq.class.getDeclaredMethod("c",Qe.class,boolean.class);
        apply.setAccessible(true);apply.invoke(effect,null,true);
        check(mp,9,9,9);
        ap.on(8);check(ap,6,6,6);check(mp,9,9,9);
        ap.or(8);check(mp,9,9,11);
        ap.oo(2);check(mp,7,7,11);
        effect.bbR();check(mp,3,3,3);
        mp.on(7);check(mp,3,3,3);
        mp.or(5);check(mp,3,3,5);
        mp.oo(1);check(mp,2,2,5);
        mp.or(8);check(mp,2,2,8);
        set(mp,fff.class,"sfT",true);
        mp.on(1);check(mp,2,2,8);
        mp.or(2);check(mp,2,2,2);
        mp.or(8);check(mp,2,2,8);
        System.out.println("PASS original eWq/eWr raw/effective/maximum and frozen/expandable PA");
    }
}
