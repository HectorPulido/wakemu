import java.lang.reflect.*;
/** Original eYH.C parameter gate; no fight, service or catalog initialization. */
public class ProbeNativeAIControlValue {
    public static void main(String[] args) throws Exception {
        Field definition = Qe.class.getDeclaredField("bfp");
        definition.setAccessible(true);
        Field amount = Qe.class.getDeclaredField("aSg");
        amount.setAccessible(true);
        for (int parameter : new int[]{Integer.MIN_VALUE, -1, 0, 1, Integer.MAX_VALUE}) {
            eYH runner = new eYH();
            definition.set(runner, Proxy.newProxyInstance(eVn.class.getClassLoader(),
                new Class[]{eVn.class}, (p, method, a) -> {
                    if (method.getName().equals("a") && a.length == 3) return parameter;
                    throw new AssertionError(method);
                }));
            runner.C(null);
            if (amount.getInt(runner) != (parameter > 0 ? 1 : 0))
                throw new AssertionError(parameter);
        }
        System.out.println("PASS original eYH.C five signed-int parameter cases");
    }
}
