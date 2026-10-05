import java.util.ArrayList;
import java.time.LocalDateTime;
import java.time.ZoneOffset;

/** Original eJL argument order, UTC milliseconds, and long-to-int narrowing. */
public final class ProbeNativeDateCriteria {
    static long date(long... values) {
        ArrayList<alS> args = new ArrayList<>();
        for (long value : values) args.add(new alw(value));
        return new eJL(args).d(null, null, null, null);
    }
    public static void main(String[] args) {
        for (int[] values : new int[][] {{6,1,2026,9,59,59}, {7,7,2026,10,0,0},
                {8,9,2026,10,0,0}, {29,2,2024,0,0,0}}) {
            long expected = LocalDateTime.of(values[2], values[1], values[0],
                values[3], values[4], values[5]).toInstant(ZoneOffset.UTC).toEpochMilli();
            long actual = date(values[0], values[1], values[2], values[3], values[4], values[5]);
            if (actual != expected) throw new AssertionError(actual + " != " + expected);
            System.out.println("PASS UTC " + actual);
        }
        if (date(4294967302L,1,2026,9,59,59) != date(6,1,2026,9,59,59))
            throw new AssertionError("Native long-to-int narrowing differs");
        System.out.println("PASS native narrowing");
    }
}
