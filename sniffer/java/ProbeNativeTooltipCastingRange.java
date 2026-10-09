import java.lang.reflect.Field;

/** Original bPO.elJ tooltip versus fcj target-mask range; no catalogs/client. */
public class ProbeNativeTooltipCastingRange {
    static class Actor extends bjo {
        int bonus;
        public int c(PC stat) { if (stat == ffw.sgK) return bonus; throw new AssertionError(stat); }
        public PN<eVn> fqE() { return null; }
        public Qf bax() { return null; }
    }
    static class Spell extends bPK {
        int minimum, maximum;
        boolean modifiable;
        Spell() { super(null); }
        public int i(fyG spell, eGj actor, Object target, Object fight) { return maximum; }
        public int j(fyG spell, eGj actor, Object target, Object fight) { return minimum; }
        public boolean d(fyG spell, Object actor, Object target, Object fight) { return modifiable; }
    }
    public static void main(String[] args) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe"); field.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) field.get(null);
        Actor actor = (Actor) unsafe.allocateInstance(Actor.class);
        Spell definition = (Spell) unsafe.allocateInstance(Spell.class);
        bPO instance = (bPO) unsafe.allocateInstance(bPO.class);
        Field source = fyG.class.getDeclaredField("tww"); source.setAccessible(true); source.set(instance, definition);
        Field owner = bPO.class.getDeclaredField("kLZ"); owner.setAccessible(true); owner.set(instance, actor);
        int[][] cases = {
            {2, 6, 1, 2, 0, 0, 8, 8},
            {2, 6, 1, 2, 1, 0, 8, 9},
            {2, 6, 1, 2, 0, 1, 8, 1},
            {0, 0, 1, 2, 0, 0, 2, 0},
            {2, 1, 0, 2, 0, 0, 2, 1}
        };
        for (int[] row : cases) {
            definition.minimum = row[0]; definition.maximum = row[1];
            definition.modifiable = row[2] != 0; actor.bonus = row[3];
            int tooltip = instance.elJ();
            int mask = ProbeNativeCastingRange.nativeRange(row[0], row[1], row[2] != 0,
                                                           row[3], row[4] != 0, row[5] != 0);
            if (tooltip != row[6] || mask != row[7]) throw new AssertionError(tooltip + "," + mask);
            System.out.println("tooltip=" + tooltip + ", target-mask=" + mask);
        }
        System.out.println("PASS original tooltip/target-mask contracts: 5 cases");
    }
}
