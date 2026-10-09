import java.util.ArrayList;
import java.util.List;

/** Verify original ePs long-to-int conversion separately from roster counting. */
public class ProbeNativeSummonCountFilter {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        public int GF(int breed) { return breed; }
    }

    static class Criterion extends ePs {
        Criterion(long breed) {
            super(new ArrayList<alS>(List.of(new amc("caster"), new alw(breed))));
        }
        int filter(Actor actor) { return super.b(actor); }
    }

    public static void main(String[] args) {
        Actor actor = new Actor();
        long[] filters = {-1L, -2L, 3798L, 4294967295L, -4294967297L,
                          4294971094L, -4294963498L, Long.MAX_VALUE};
        for (long filter : filters) {
            int actual = new Criterion(filter).filter(actor);
            if (actual != (int) filter) throw new AssertionError(filter + ":" + actual);
        }
        if (eGE.pIq.aXA() != -1) throw new AssertionError("Native NONE wildcard");
        System.out.println("9 native summon-filter assertions PASS");
    }
}
