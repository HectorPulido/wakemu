import java.lang.reflect.Field;

/** Headless checks of the installed result component; no client files are edited. */
public final class ProbeEnvironmentalResultSelection {
    public static void main(String[] args) throws Exception {
        bhE component = new bhE();
        bhR[] rewards = new bhR[3];
        for (int i = 0; i < rewards.length; i++) {
            bhS source = new bhS(100 + i, 11423 + i, (short)(2 + i),
                                 500 + i, 7 + i, false, (byte)i);
            rewards[i] = new bhR(source);
            if (source.aAi() != 11423 + i || source.bfh() != 2 + i
                    || source.agO() != 500 + i || source.aHk() != 7 + i)
                throw new AssertionError("Original reward display fields differ");
        }
        Field population = bhE.class.getDeclaredField("idj");
        population.setAccessible(true);
        population.set(component, rewards);
        int[] indices = {-1, 0, 1, 2, 3, 230};
        for (int index : indices) {
            component.CK(index);
            bhR expected = index >= 0 && index < rewards.length ? rewards[index] : null;
            if (component.dmq() != expected)
                throw new AssertionError("Original result selection is not a reward-list index");
        }
        short[] rawRanks = {-3, -2, -1, 0, 32766, 32767};
        short[] displayed = {-2, -1, 0, 1, 32767, -32768};
        for (int i = 0; i < rawRanks.length; i++) {
            // Exact cio13263 instructions: rank + 1, i2s, bhE.bw.
            component.bw((short)(rawRanks[i] + 1));
            if (component.dmp() != displayed[i])
                throw new AssertionError("Original signed-short rank storage differs");
        }
        System.out.println("PASS original bhE: 6 reward-index vectors, 6 rank-storage vectors, 3 reward-display descriptors");
    }
}
