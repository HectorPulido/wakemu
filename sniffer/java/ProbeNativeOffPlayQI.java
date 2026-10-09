import java.lang.reflect.Field;

/** Real fdt status and QI operations; actor properties/cleanup side effects isolated. */
public final class ProbeNativeOffPlayQI {
    static class Actor extends ProbeNativeFightersBreedRange.A {
        long identity;
        byte obstacle;
        ProbeNativeFightersBreedRange.F fight;
        public long Sn() { return identity; }
        public byte bcN() { return obstacle; }
        public void M(byte value) { obstacle = value; }
        public fcb dpt() { return fight; }
        public boolean dnS() { return false; } // Explicit ordinary visibility domain.
        public boolean dnz() { return true; } // Actual active-fight association.
    }

    public static void main(String[] args) throws Exception {
        Actor actor = (Actor) ProbeNativeFightersBreedRange.U.allocateInstance(Actor.class);
        actor.identity = 7; actor.obstacle = 0; actor.x = 1; actor.y = 1;
        actor.fight = (ProbeNativeFightersBreedRange.F)
            ProbeNativeFightersBreedRange.U.allocateInstance(ProbeNativeFightersBreedRange.F.class);
        fdt<big> statuses = new fdt<>();
        Field registry = fcb.class.getDeclaredField("rRN");
        registry.setAccessible(true); registry.set(actor.fight, statuses);
        statuses.a(actor, (byte) 0, false, actor);
        ProbeNativeQIRegistry.Grid qi = new ProbeNativeQIRegistry.Grid();
        qi.i(actor);
        System.out.println("Fresh baF=" + actor.baF() + " baG=" + actor.baG()
            + " bcP=" + actor.bcP() + " bcQ=" + actor.bcQ());
        if (!actor.baF() || actor.baG() || !actor.bcP() || !actor.bcQ())
            throw new AssertionError("Fresh native fighter contract");
        if (!statuses.bv(actor) || actor.baF() || !actor.baG() || actor.baK())
            throw new AssertionError("Actual native OFF_PLAY transition");
        if (qi.O((byte) 0) != actor || !qi.U(1, 1).contains((byte) 0)
            || actor.bcN() != 0 || !actor.bcP() || !actor.bcQ())
            throw new AssertionError("OFF_PLAY altered QK registration/flags");
        qi.g(actor);
        if (actor.bcN() != -1 || qi.O((byte) 0) != null || !qi.U(1, 1).isEmpty())
            throw new AssertionError("Actual QI.g removal contract");
        System.out.println("PASS real fdt OFF_PLAY; QI slot/index/bcP/bcQ unchanged; explicit QI.g resets byte");
        System.out.println("Scope: status/QI primitives; full fcb.aC cleanup order is bytecode evidence");
    }
}
