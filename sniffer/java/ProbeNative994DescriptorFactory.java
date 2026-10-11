import java.lang.reflect.Method;

/** Verify the eHK template's inherited factory creates actual eHI subtype1. */
public class ProbeNative994DescriptorFactory {
    static class Target extends ProbeNativeLevelGroup.Actor {
        final ffh pool = new ffh();
        public eGH dsG() { return null; } // Explicit nonclass breed branch.
        public ffh frZ() { return pool; }
        public int c(PC stat) { return pool.c(stat); }
        public int bwX() { return 42; }
        public String getName() { return "Actual target probe"; }
    }
    public static void main(String[] args) throws Exception {
        Target target = new Target();
        target.level = 50;
        eHI actual = new eHK().b((short)2798, "target", 1, (short)50, target, 100, null);
        if(actual.getClass() != eHI.class) throw new AssertionError("Factory class");
        Method subtype = eHI.class.getDeclaredMethod("fxb");
        subtype.setAccessible(true);
        if(((Byte)subtype.invoke(actual)) != 1) throw new AssertionError("Actual subtype");
        System.out.println("PASS eHK inherited b(target) returns actual eHI subtype1; nonclass curves skipped");
    }
}
