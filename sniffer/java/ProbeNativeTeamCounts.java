import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;
import gnu.trove.map.hash.TLongObjectHashMap;

/** Original eJo/eKz/eKK and actual fdt/fdy filters, without runtime catalogs. */
public final class ProbeNativeTeamCounts {
    static final class A extends ProbeNativeFightersBreedRange.A {
        byte type, team;
        long id;
        public long Sn() { return id; }
        public byte aGJ() { return type; }
        public byte bcM() { return team; }
        public boolean buX() { return false; }
    }
    static void field(Object value, Class<?> owner, String name, Object data) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        field.set(value, data);
    }
    static void check(long actual, long expected) {
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
    public static void main(String[] arguments) throws Exception {
        ProbeNativeFightersBreedRange.F fight = (ProbeNativeFightersBreedRange.F)
            ProbeNativeFightersBreedRange.U.allocateInstance(ProbeNativeFightersBreedRange.F.class);
        fdt<big> population = new fdt<>();
        TLongObjectHashMap<big> actors = new TLongObjectHashMap<>();
        TLongObjectHashMap<fdy> statuses = new TLongObjectHashMap<>();
        A caster = null;
        for (int type = 0; type < 6; type++) {
            A actor = (A) ProbeNativeFightersBreedRange.U.allocateInstance(A.class);
            actor.type = (byte) type; actor.team = (byte) (type % 2);
            actor.id = type + 1; actor.breed = (short) 5347;
            actors.put(actor.id, actor);
            statuses.put(actor.id, new fdy(actor.team, false, false, actor.id));
            if (type == 0) caster = actor;
        }
        field(population, fdt.class, "saq", actors);
        field(population, fdt.class, "sap", statuses);
        field(fight, fcb.class, "rRN", population);
        check(fight.e((short) -1, (byte) -1), 2);
        check(fight.e((short) 5347, (byte) 0), 1);
        check(fight.e((short) 5525, (byte) -1), 0);
        check(new eKK(new ArrayList<alS>(List.of(new alw(256), new alw(65536 + 5347))))
            .d(caster, null, null, fight), 1);
        check(new eJo(new ArrayList<alS>()).d(caster, null, null, fight), 3);
        check(new eKz(new ArrayList<alS>(List.of(new alw(-1))))
            .d(caster, null, null, fight), 1);
        System.out.println("PASS: 6 original native team-count checks");
    }
}
