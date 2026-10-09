import java.lang.reflect.Proxy;
import java.util.Arrays;

/** Actual Tc/SQ current-cycle insertion; eWl's raw gate is source-transcribed. */
public final class ProbeNativeAdditionalTurn {
    public static void main(String[] args) throws Exception {
        fce context = (fce) Proxy.newProxyInstance(fce.class.getClassLoader(),
            new Class[]{fce.class}, (p, m, a) -> {
                if (m.getName().equals("d")) return 12;
                throw new UnsupportedOperationException(m.getName());
            });
        int[] modes = {-1, 0, 1, 2, 99};
        int[] offsets = {Integer.MIN_VALUE, -5, -1, 0, 1, 2, 3, 4, Integer.MAX_VALUE};
        StringBuilder rows = new StringBuilder("[");
        int count = 0;
        for (int mode : modes) for (int offset : offsets) {
            Tc timeline = new Tc(new feq(context, null));
            timeline.biq().add(new long[]{7, -7, 8});
            timeline.bir().add(new long[]{7, -7, 8});
            timeline.bsx = 1;
            SQ options = new SQ();
            options.a(SR.pv(mode));
            options.pt(offset);
            options.ej(7);
            int base = mode == 0 ? 1 : 0; // First caster7 occurs at native index0.
            int raw = base + offset;
            int slot = timeline.a(options); // Original native floorMod/anchor implementation.
            if (raw > 1) timeline.p(7, slot); // Source eWl.c gate, then original Tc.p gate.
            if (count++ != 0) rows.append(',');
            rows.append("{\"mode\":").append(mode).append(",\"offset\":").append(offset)
                .append(",\"order\":").append(Arrays.toString(timeline.biq().toArray()))
                .append(",\"cursor\":").append(timeline.bik()).append('}');
        }
        System.out.println(rows.append(']'));
        System.err.println("Actual Tc/SQ additional-turn observations: " + count);
    }
}
