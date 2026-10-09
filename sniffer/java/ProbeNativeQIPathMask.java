/** Native QI.Z path-option oracle including W aliases outside the rectangle. */
public class ProbeNativeQIPathMask {
    static class Grid extends QI {
        Grid() {
            bpZ = 10; bqa = 20; bqd = 2; bqe = 2;
            biD = new short[4]; biE = 4;
        }
    }

    public static void main(String[] args) {
        Grid grid = new Grid();
        for (int raw = 0; raw < 65536; raw++) {
            grid.biD[0] = (short) raw;
            boolean expected = (((short) raw) & 768) != 0;
            if (grid.Z(10, 20) != expected || grid.Z(12, 19) != expected) {
                throw new AssertionError("mask/index alias " + raw);
            }
            if (grid.Z(9, 20) || grid.Z(10, 22)) {
                throw new AssertionError("invalid index " + raw);
            }
        }
        grid.biD[0] = 256;
        if (!grid.Z(10, Integer.MIN_VALUE + 20)) {
            throw new AssertionError("signed-int W overflow alias");
        }
        System.out.println("PASS native QI.Z: 65536 masks, W aliases, index bounds, int32 overflow");
    }
}
