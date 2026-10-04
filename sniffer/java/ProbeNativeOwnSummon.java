import java.lang.reflect.*;
import java.util.ArrayList;

public class ProbeNativeOwnSummon {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        Actor root;
        boolean summon;
        public eGH dsG() {
            return (eGH) Proxy.newProxyInstance(eGH.class.getClassLoader(),new Class<?>[]{eGH.class},
                (proxy,method,args) -> { if (method.getName().equals("aXA")) return (short)42;
                    throw new UnsupportedOperationException(method.getName()); });
        }
        public eGj fqK() { return root; }
        public boolean dTE() { return summon; }
    }
    static eOG criterion(String selector) {
        ArrayList<alS> parameters = new ArrayList<>();
        if (selector != null) parameters.add(new amc(selector));
        return new eOG(parameters);
    }
    public static void main(String[] args) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) field.get(null);
        Actor caster = (Actor) unsafe.allocateInstance(Actor.class);
        Actor target = (Actor) unsafe.allocateInstance(Actor.class);
        Actor foreign = (Actor) unsafe.allocateInstance(Actor.class);
        caster.root=caster; target.root=caster; target.summon=true; foreign.root=foreign;
        if (criterion(null).a(caster,target,null,null)!=0) throw new AssertionError("owned summon");
        for (int breed : new int[]{42,65578,41}) {
            ArrayList<alS> parameters=new ArrayList<>();parameters.add(new alw(breed));
            int expected=breed==41?-1:0;
            if (new eOG(parameters).a(caster,target,null,null)!=expected) throw new AssertionError("breed narrowing");
        }
        target.summon=false;
        if (criterion(null).a(caster,target,null,null)!=-1) throw new AssertionError("ordinary actor");
        target.summon=true; target.root=foreign;
        if (criterion(null).a(caster,target,null,null)!=-1) throw new AssertionError("foreign summon");
        if (criterion(null).a(caster,null,null,null)!=-1) throw new AssertionError("null target");
        caster.summon=true;
        if (criterion("caster").a(caster,target,null,null)!=0) throw new AssertionError("caster selector");
        System.out.println("eOG own/foreign/ordinary/null/caster selector PASS");
    }
}
