import java.util.Arrays;
import java.util.Collections;

/** Offline reader check for the cva/12044 layout using the installed client JAR. */
public final class VerifySpectatorBootstrap {
    private static final String FIXTURE =
        "000001c801000000000000007b00000000000000ea000000000000015900" +
        "000008746f706f6c6f677900000000000000000001000000000000000200" +
        "01000000000000000a000102000573746174730007656666656374730000" +
        "0000000000020000002b0000000302000000000000001400000009000000" +
        "00000000000a0000000701010000000400010000000500";

    private static byte[] unhex(String input) {
        byte[] result = new byte[input.length() / 2];
        for (int i = 0; i < result.length; i++) {
            result[i] = (byte) Integer.parseInt(input.substring(i * 2, i * 2 + 2), 16);
        }
        return result;
    }

    public static void main(String[] args) {
        cva message = new cva();
        if (!message.dp(unhex(FIXTURE))) {
            throw new AssertionError("cva rejected the spectator bootstrap fixture");
        }
        if (message.bhe() != 456 || message.eHb() != 1 || message.eHc() != 234L
            || message.eHd() != 345L || message.eHs() != 1L || message.eHt() != 2L
            || message.eHa() != 1 || message.Mj(0) != 10L
            || message.eHn() != 2) {
            throw new AssertionError("cva inherited or spectator fields were misread");
        }
        if (!Arrays.equals(message.eHr(), "topology".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            || !Arrays.equals(message.Mn(0), "stats".getBytes(java.nio.charset.StandardCharsets.UTF_8))
            || !Arrays.equals(message.Mo(0), "effects".getBytes(java.nio.charset.StandardCharsets.UTF_8))) {
            throw new AssertionError("cva nested snapshot data was misread");
        }
        feN timeline = new feN();
        timeline.dT(message.eHo());
        if (timeline.dNH() != 3 || timeline.rJ(10L) != 7 || !timeline.rK(10L)
            || timeline.rJ(20L) != 9 || timeline.rK(20L)
            || !timeline.fYZ().containsKey(4) || !timeline.fZb().containsKey(5)) {
            throw new AssertionError("native feN current timeline state was misread");
        }
        feN nativeState = new feN();
        nativeState.Ag(3);
        nativeState.ac(10L, 7);
        nativeState.ac(20L, 9);
        nativeState.rP(20L);
        nativeState.e(4, Collections.emptyList());
        nativeState.fZb().put(5, Collections.emptyList());
        if (!Arrays.equals(nativeState.TM(0), message.eHo())) {
            throw new AssertionError("Python timeline bytes differ from native feI encoder: "
                + java.util.HexFormat.of().formatHex(nativeState.TM(0)) + " != "
                + java.util.HexFormat.of().formatHex(message.eHo()));
        }
        System.out.println("native cva/12044 and feN reader accepted 143-byte current-state fixture");
    }
}
