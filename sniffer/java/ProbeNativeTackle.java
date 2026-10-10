import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Collections;

/** Original fef arithmetic with actual fcP interface and empty BACK locator list. */
public final class ProbeNativeTackle {
    public static void main(String[] args) throws Exception {
        Class<?> calculator = Class.forName("fef");
        Class<?> fighter = Class.forName("fcP");
        Class<?> cell = Class.forName("aBn");
        Method bind = calculator.getMethod("a", fighter);
        Method total = calculator.getDeclaredMethod("a", int.class, int.class, java.util.List.class, cell);
        total.setAccessible(true);
        System.out.println("[");
        boolean first = true;
        for (int level : new int[]{1, 60, 200}) {
            final short currentLevel = (short) level;
            Object actor = Proxy.newProxyInstance(fighter.getClassLoader(), new Class<?>[]{fighter},
                (proxy, method, params) -> {
                    if (method.getName().equals("cmZ")) return currentLevel;
                    throw new AssertionError("Unexpected native fighter lookup: " + method);
                });
            Object engine = calculator.getConstructor().newInstance();
            bind.invoke(engine, actor);
            for (int lock : new int[]{0, 1, 60, 100, 499, 1000}) {
                for (int dodge : new int[]{0, 1, 60, 100, 499, 1000}) {
                    int loss = (Integer) total.invoke(engine, lock, dodge, Collections.emptyList(), null);
                    int mp = (loss + 1) / 2;
                    if (!first) System.out.println(",");
                    first = false;
                    System.out.print("{\"level\":" + level + ",\"lock\":" + lock + ",\"dodge\":" + dodge
                        + ",\"ap\":" + (loss - mp) + ",\"mp\":" + mp + "}");
                }
            }
        }
        System.out.println("\n]");
    }
}
