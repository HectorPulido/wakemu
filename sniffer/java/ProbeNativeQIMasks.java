import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Exhaustive real-client QI mask oracle, with no binary catalogs loaded. */
public class ProbeNativeQIMasks {
    static class Grid extends QI {
        Grid(int x, int y, int width, int height, short[] masks) {
            bpZ = x; bqa = y; bqd = width; bqe = height; biD = masks;
        }
    }

    static byte flags(QI grid, int x, int y) {
        return (byte) ((grid.P(x, y) ? 1 : 0) | (grid.Q(x, y) ? 2 : 0)
                      | (grid.R(x, y) ? 4 : 0) | (grid.aK(x, y) ? 8 : 0));
    }

    public static void main(String[] args) throws Exception {
        byte[] table = new byte[65536];
        short[] masks = new short[1];
        Grid grid = new Grid(10, 20, 1, 1, masks);
        for (int raw = 0; raw < 65536; raw++) {
            masks[0] = (short) raw;
            table[raw] = flags(grid, 10, 20);
            if (flags(grid, 9, 20) != 0 || flags(grid, 11, 20) != 0
                || flags(grid, 10, 19) != 0 || flags(grid, 10, 21) != 0) {
                throw new AssertionError("out-of-bounds mask " + raw);
            }
        }
        Grid wrapped = new Grid(Integer.MAX_VALUE, 0, 1, 1, new short[]{128});
        if (flags(wrapped, Integer.MAX_VALUE, 0) != 0) {
            throw new AssertionError("native upper-bound signed-int overflow");
        }
        Grid minimum = new Grid(Integer.MIN_VALUE, 0, 1, 1, new short[]{128});
        if (flags(minimum, Integer.MIN_VALUE, 0) != 13
            || flags(minimum, Integer.MIN_VALUE + 1, 0) != 0) {
            throw new AssertionError("native minimum signed-int bounds");
        }
        Files.write(Path.of(args[0]), table);
        System.out.println("PASS 65536 signed-short masks; P/Q/R/aK; OOB; signed-int bounds");
        System.out.println("sha256=" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(table)));
    }
}
