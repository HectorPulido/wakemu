import java.lang.reflect.Field;
import java.lang.reflect.Proxy;

/** Executes original eZR.bbj, including Java float and f2i instructions. */
public class ProbeNativeExecutionCounts {
    static class Runner extends eYg {
        short level;
        public short fRR() { return level; }
        int budget() { bbj(); return bfB; }
    }
    public static void main(String[] args) throws Exception {
        Field definition = Qe.class.getDeclaredField("bfp");
        definition.setAccessible(true);
        int cases = 0;
        for (short base : new short[]{-32768, -1, 0, 1, 32767}) {
            for (float slope : new float[]{-3.25f, 0f, .1f, 1f, 100000f,
                    Float.POSITIVE_INFINITY, Float.NaN}) {
                for (short level : new short[]{-32768, -1, 0, 1, 10, 32767}) {
                    Runner runner = new Runner();
                    runner.level = level;
                    definition.set(runner, Proxy.newProxyInstance(eVn.class.getClassLoader(),
                            new Class[]{eVn.class}, (p, method, values) -> {
                                if (method.getName().equals("aZS")) return base;
                                if (method.getName().equals("cyc")) return slope;
                                throw new UnsupportedOperationException(method.getName());
                            }));
                    int actual = runner.budget();
                    int expected = base < 0 ? -1 : (int)((float)base + (float)level * slope);
                    if (actual != expected) throw new AssertionError("Native budget mismatch");
                    cases++;
                }
            }
        }
        System.out.println("Native eZR.bbj " + cases + " cases PASS");
    }
}
