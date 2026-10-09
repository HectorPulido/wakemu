import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Offline eXD.fOQ control flow for proven empty physical carry relations. */
public class ProbeNativeDisplacementUncarryFlag {
    public static void main(String[] args) throws Exception {
        if (eVl.rxh.fLK() != 37 || !eVl.rxh.name().equals("DO_NOT_UNCARRY")) {
            throw new AssertionError("Unexpected native carry flag");
        }
        for (boolean flag : new boolean[]{false, true}) {
            final int[] reads = {0, 0};
            PV actor = (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),
                new Class<?>[]{PV.class, fax.class, eHG.class}, (proxy, method, values) -> {
                    if (method.getName().equals("frA")) {
                        reads[0]++;
                        return false;
                    }
                    throw new AssertionError("Unexpected actor read " + method);
                });
            eVn definition = (eVn) Proxy.newProxyInstance(eVn.class.getClassLoader(),
                new Class<?>[]{eVn.class}, (proxy, method, values) -> {
                    if (method.getName().equals("a") && values[0] instanceof eVl) {
                        reads[1]++;
                        return flag;
                    }
                    throw new AssertionError("Unexpected definition read " + method);
                });
            eXq runner = new eXq();
            for (Object[] pair : new Object[][]{{"bfr", actor}, {"bfp", definition}}) {
                Field field = Qe.class.getDeclaredField((String)pair[0]);
                field.setAccessible(true);
                field.set(runner, pair[1]);
            }
            Method uncarry = eXD.class.getDeclaredMethod("fOQ");
            uncarry.setAccessible(true);
            uncarry.invoke(runner);
            if (reads[0] != 1 || reads[1] != 0) {
                throw new AssertionError("Empty carry must return before flag lookup");
            }
        }
        System.out.println("PASS native flag37: proven frA=false skips uncarry before flag lookup");
    }
}
