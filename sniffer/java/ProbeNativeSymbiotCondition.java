import java.lang.reflect.Proxy;
import java.util.ArrayList;
/** Original eOU direct-eHg selector and dTC matrix, without a fight/service. */
public final class ProbeNativeSymbiotCondition {
    static eHg actor(boolean value) {
        return (eHg) Proxy.newProxyInstance(eHg.class.getClassLoader(), new Class[]{eHg.class},
            (proxy, method, args) -> {
                if (method.getName().equals("dTC")) return value;
                throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) {
        int count = 0;
        for (boolean caster : new boolean[]{false,true})
            for (boolean target : new boolean[]{false,true})
                for (String selector : new String[]{"target","TARGET","caster","eventtarget",""}) {
                    var parameters = new ArrayList<alS>();
                    parameters.add(new amc(selector));
                    var predicate = new eOU(parameters);
                    boolean actual = predicate.a(actor(caster),actor(target),null,null)==0;
                    boolean expected = selector.equalsIgnoreCase("target") ? target : caster;
                    if (actual != expected) throw new AssertionError(selector);
                    count++;
                }
        var parameters = new ArrayList<alS>();
        parameters.add(new amc("target"));
        if (new eOU(parameters).a(actor(true),null,null,null)!=-1)
            throw new AssertionError("null target");
        System.out.println("PASS " + count + " eOU selector/dTC cases and null target");
    }
}
