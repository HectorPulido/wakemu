/** Installed eWD AdditionalDatas flag17, including explicit false presence. */
public final class ProbeNativeControllerAdditional {
    public static void main(String[] args) {
        for (boolean value : new boolean[]{false, true}) {
            byte[] bytes = ij.MR().r(value).MY().toByteArray();
            if (bytes.length != 3 || bytes[0] != (byte) 0x88 || bytes[1] != 1
                    || bytes[2] != (value ? 1 : 0)) {
                throw new AssertionError("Native eWD additional boolean changed");
            }
        }
        System.out.println("PASS installed eWD field17 explicit false/true");
    }
}
