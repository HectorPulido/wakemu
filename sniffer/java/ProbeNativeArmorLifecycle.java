import java.lang.reflect.*;
import java.util.*;

/** Original eWx cloning, transient faq accumulator and inherited producer0. */
public class ProbeNativeArmorLifecycle {
    static void set(Object value, Class<?> owner, String name, Object field) throws Exception {
        Field member = owner.getDeclaredField(name);
        member.setAccessible(true);
        member.set(value, field);
    }
    public static void main(String[] arguments) throws Exception {
        for (int mode = 0; mode < 4; mode++) {
            final int selected = mode;
            eVn definition = (eVn) Proxy.newProxyInstance(eVn.class.getClassLoader(),
                new Class<?>[] {eVn.class}, (proxy, method, args) -> switch (method.getName()) {
                    case "fKJ" -> 2;
                    case "aZE" -> 123456;
                    case "a" -> new int[] {100, selected}[(int) args[0]];
                    case "aZO" -> new BitSet();
                    default -> throw new UnsupportedOperationException(method.getName());
                });
            Map<PC, fff> source = new HashMap<>(), target = new HashMap<>();
            ProbeCombatArithmetic.put(source, ffw.sim, 0);
            ProbeCombatArithmetic.put(target, ffw.sin, 0);
            ProbeCombatArithmetic.put(target, ffw.shQ, 0);
            eWx runner = new eWx();
            set(runner, Qe.class, "bfp", definition);
            set(runner, Qe.class, "bfr", ProbeNativeArmor.actor(source, 0));
            set(runner, Qe.class, "bfs", ProbeNativeArmor.actor(target, 1));
            runner.lV(1013);
            if (!runner.bbw().get(0)) throw new AssertionError("generic producer0");
            runner.SX(25);
            runner.C(null);
            int expected = mode == 0 ? 100 : 125;
            if (runner.getValue() != expected) throw new AssertionError("modifier mode " + mode);
            eWx cloned = runner.fNk();
            Field modifier = eWx.class.getDeclaredField("rBA");
            modifier.setAccessible(true);
            if (modifier.getInt(cloned) != 0) throw new AssertionError("clone retained transient modifier");
            if (!cloned.bbw().get(0)) throw new AssertionError("clone producer0");
        }
        System.out.println("PASS eWx transient modifier modes, clone reset, generic producer0");
    }
}
