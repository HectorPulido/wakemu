import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.HexFormat;

/** Offline original eYJ additional codec, clone identity and owner flags. */
public final class ProbeNativeTargetAura {
    public static void main(String[] args) throws Exception {
        Field identity = eYJ.class.getDeclaredField("rGF");
        identity.setAccessible(true);
        Method codec = eYJ.class.getDeclaredMethod("b", iP.class);
        codec.setAccessible(true);
        for (long uid : new long[]{1L, 56L, 2147483648L}) {
            eYJ runner = new eYJ();
            identity.setLong(runner, uid);
            iP builder = iN.QQ();
            codec.invoke(runner, builder);
            byte[] actual = builder.QA().toByteArray();
            byte[] expected = ij.MR().af(uid).MX().toByteArray();
            if (!java.util.Arrays.equals(actual, expected)) {
                throw new AssertionError("eYJ additional data differ from original ij21");
            }
            eYJ clone = runner.fQv();
            if (identity.getLong(clone) != uid || !runner.bbA() || !runner.bbB() || runner.bbz()) {
                throw new AssertionError("eYJ clone/owner contract differs");
            }
            System.out.println("codec " + uid + " " + HexFormat.of().formatHex(actual));
        }
        System.out.println("PASS original eYJ additional data and clone identities");
    }
}
