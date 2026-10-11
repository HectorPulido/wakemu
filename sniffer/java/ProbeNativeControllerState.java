/** Differential oracle for the installed fdy original/current controller state. */
public final class ProbeNativeControllerState {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        var constructor = fdy.class.getDeclaredConstructor(byte.class, boolean.class,
            boolean.class, long.class);
        constructor.setAccessible(true);
        fdy row = constructor.newInstance((byte) 0, false, false, 7L);
        check(row.dTD() == 7L && row.fXZ().longValue() == 7L, "fresh controllers");
        check(row.fXW() == 0 && row.bcM() == 0, "fresh teams");
        row.a(Long.valueOf(-7L), (byte) 4);
        check(row.dTD() == 7L && row.fXZ().longValue() == -7L, "transfer controllers");
        check(row.fXW() == 0 && row.bcM() == 4, "transfer teams");
        row.au((byte) 5);
        check(row.fXW() == 0 && row.bcM() == 5, "affiliation leaves original");
        row.a(null, (byte) -1);
        check(row.fXZ() == null && row.bcM() == -1, "clear nullable relation");
        row.a(Long.valueOf(row.dTD()), row.fXW());
        check(row.fXZ().longValue() == 7L && row.bcM() == 0, "restore originals");
        System.out.println("PASS installed fdy constructor/transfer/affiliation/clear/restore");
    }
}
