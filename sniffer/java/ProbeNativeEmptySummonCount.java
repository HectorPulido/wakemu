import java.util.*;

/** Actual GF/dTB on a source-complete empty native owned collection. */
public class ProbeNativeEmptySummonCount {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        public Collection<? extends eGj> dnC() { return Collections.emptyList(); }
    }
    public static void main(String[] args) {
        Actor actor = new Actor();
        int[] filters = {Integer.MIN_VALUE, -1, 0, 3798, 32767, Integer.MAX_VALUE};
        for (int filter : filters)
            if (actor.GF(filter) != 0) throw new AssertionError(filter);
        if (actor.dTB() != 0) throw new AssertionError("Unfiltered count");
        System.out.println("7 native empty summon count assertions PASS");
    }
}
