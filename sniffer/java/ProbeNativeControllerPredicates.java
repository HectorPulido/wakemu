import java.lang.reflect.Proxy;
import java.util.ArrayList;
/** Offline actual eIC/eOx null, identity and dTD matrix; no fight/service. */
public final class ProbeNativeControllerPredicates {
    static eHg actor(long identity, long controller) {
        return (eHg) Proxy.newProxyInstance(eHg.class.getClassLoader(), new Class[]{eHg.class},
            (proxy, method, args) -> switch(method.getName()) {
                case "Sn" -> identity;
                case "dTD" -> controller;
                case "toString" -> "OwnedProbeActor";
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) {
        var same = new eIC(new ArrayList<alS>());
        var original = new eOx(new ArrayList<alS>());
        int count = 0;
        for (long casterController : new long[]{0,1,2,Long.MIN_VALUE})
            for (long targetIdentity : new long[]{0,1,2,Long.MIN_VALUE})
                for (long targetController : new long[]{0,1,2,Long.MIN_VALUE}) {
                    eHg caster = actor(99, casterController);
                    eHg target = actor(targetIdentity, targetController);
                    if ((same.a(caster,target,null,null)==0) != (casterController==targetController))
                        throw new AssertionError("eIC");
                    if ((original.a(caster,target,null,null)==0) != (casterController==targetIdentity))
                        throw new AssertionError("eOx");
                    count++;
                }
        for (Object target : new Object[]{null,new Object()}) {
            if (same.a(actor(1,1),target,null,null)!=-1 || original.a(actor(1,1),target,null,null)!=-1)
                throw new AssertionError("null/non-eHg");
        }
        try { same.a(null,actor(1,1),null,null); throw new AssertionError("caster"); }
        catch (alA expected) {}
        if (new ePJ(new ArrayList<alS>()).a(actor(1,1),actor(2,2),null,null)!=-1)
            throw new AssertionError("ePJ null runner");
        System.out.println("PASS "+count+" controller combinations, null/non-eHg/caster and ePJ null runner");
    }
}
