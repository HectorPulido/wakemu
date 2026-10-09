import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.HexFormat;

/** Bounded native eXf nested-state codec proof without effect catalogs/services. */
public final class ProbeNativeTurnSuppression {
    public static void main(String[] args) throws Exception {
        Class<?> runnerClass = Class.forName("eXf");
        Field start = runnerClass.getDeclaredField("rCS");
        Field end = runnerClass.getDeclaredField("rCT");
        start.setAccessible(true);
        end.setAccessible(true);
        Method encode = runnerClass.getDeclaredMethod("b", Class.forName("iP"));
        Method restore = runnerClass.getDeclaredMethod("f", Class.forName("iN"));
        encode.setAccessible(true);
        restore.setAccessible(true);
        int assertions = 0;
        for (boolean first : new boolean[]{false, true}) {
            for (boolean last : new boolean[]{false, true}) {
                Object runner = runnerClass.getConstructor().newInstance();
                if (!start.getBoolean(runner) || !end.getBoolean(runner)) {
                    throw new AssertionError("Native constructor flags");
                }
                start.setBoolean(runner, first);
                end.setBoolean(runner, last);
                iP builder = iN.QQ();
                encode.invoke(runner, builder);
                iN message = builder.QX();
                byte[] actual = message.toByteArray();
                String expected = "42068801" + (first ? "01" : "00")
                    + "9001" + (last ? "01" : "00");
                if (!HexFormat.of().formatHex(actual).equals(expected)) {
                    throw new AssertionError(HexFormat.of().formatHex(actual) + " != " + expected);
                }
                Object restored = runnerClass.getConstructor().newInstance();
                restore.invoke(restored, message);
                if (start.getBoolean(restored) != first || end.getBoolean(restored) != last) {
                    throw new AssertionError("Native restore flags");
                }
                assertions += 3;
            }
        }
        System.out.println("Native eXf constructor/wire/restore: " + assertions + " assertions PASS");
    }
}
