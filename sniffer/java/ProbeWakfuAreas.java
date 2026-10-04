import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** Offline native geometry evidence; no game server or client connection. */
public class ProbeWakfuAreas {
    public static void main(String[] args) {
        anc[] areas = {anD.bEz(), anA.bEy(), new anu(), new anw(), new anH()};
        int[][] params = {{}, {}, {2}, {2}, {1, 2}};
        int[] expectedSizes = {1, 0, 13, 9, 12};
        for (int i = 0; i < areas.length; i++) {
            anc area = areas[i];
            area.p(params[i]);
            Set<String> unique = new HashSet<>();
            System.out.print(area.bEm() + ":");
            for (int[] offset : area.bEl()) {
                unique.add(Arrays.toString(offset));
                System.out.print(Arrays.toString(offset));
            }
            System.out.println();
            if (unique.size() != expectedSizes[i]) {
                throw new AssertionError(area.bEm() + " unexpected native area size");
            }
        }
        // Native amX membership consumes XY only, despite receiving three Z values.
        if (!areas[0].a(5, 7, (short) 0, 0, 0, (short) 0,
                        aAS.dyA, 5, 7, (short) 99)) {
            throw new AssertionError("Point XY membership unexpectedly depends on Z");
        }
        System.out.println("Native area sizes and XY height behavior verified");
    }
}
