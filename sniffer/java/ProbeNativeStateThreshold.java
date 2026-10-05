import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Native eMF forwards the state id and minimum level through eHg.w. */
public class ProbeNativeStateThreshold {
    static eHg actor(int minimumExpected) {
        return (eHg) Proxy.newProxyInstance(eHg.class.getClassLoader(), new Class<?>[]{eHg.class},
            (proxy, method, values) -> {
                if (method.getName().equals("w")) {
                    if ((long) values[0] != 390 || (long) values[1] != minimumExpected)
                        throw new AssertionError("Wrong native state id or minimum level");
                    return true;
                }
                throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) {
        ArrayList<alS> parameters = new ArrayList<>();
        parameters.add(new alw(390));
        if (new eMF(parameters).a(actor(0), null, null, null) != 0)
            throw new AssertionError("Default threshold");
        parameters.add(new alw(5));
        parameters.add(new amc("target"));
        if (new eMF(parameters).a(actor(0), actor(5), null, null) != 0)
            throw new AssertionError("Explicit target threshold");
        System.out.println("Native eMF: minimum zero by default; explicit minimum and target verified.");
    }
}
