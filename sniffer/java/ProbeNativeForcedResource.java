import java.lang.reflect.*;
import java.util.*;

/** Execute real eYO setters against real fff bounds, without a live client. */
public class ProbeNativeForcedResource {
    static void set(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        field.set(object, value);
    }
    static void check(int amount, boolean setMaximum, int expectedCurrent, int expectedMaximum) throws Exception {
        fff resource = new fff(ffw.sgF, 0, 6);
        resource.or(6);
        resource.on(2);
        Map<PC, fff> stats = new HashMap<>();
        stats.put(ffw.sgF, resource);
        eYO effect = new eYO(ffw.sgF);
        set(effect, Qe.class, "bfs", ProbeCombatArithmetic.actor(stats, 1));
        set(effect, Qe.class, "aSg", amount);
        set(effect, Qe.class, "bfD", true);
        set(effect, eYO.class, "rGN", setMaximum);
        Method apply = eYO.class.getDeclaredMethod("c", Qe.class, boolean.class);
        apply.setAccessible(true);
        apply.invoke(effect, null, true);
        if (resource.aYS() != expectedCurrent || resource.aYU() != expectedMaximum)
            throw new AssertionError("Forced resource " + resource.aYS() + "/" + resource.aYU());
        effect.bbR();
        if (resource.aYS() != expectedCurrent || resource.aYU() != expectedMaximum)
            throw new AssertionError("Removing setter unexpectedly reverted resource");
    }
    public static void main(String[] args) throws Exception {
        check(4, false, 4, 6);
        check(9, false, 6, 6);
        check(-3, false, 0, 6);
        check(9, true, 6, 6);
        check(0, true, 0, 0);
        System.out.println("Native eYO: current and optional maximum setters clamp; removal does not undo assignment.");
    }
}
