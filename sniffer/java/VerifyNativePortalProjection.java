import java.nio.ByteBuffer;

/** Checks whether a state/action overlay can change a native raw object's type. */
public final class VerifyNativePortalProjection {
    public static void main(String[] args) {
        bEG ranch = bEE.cb((short) 85).bej().bau();
        bEG zaap = bEE.cb((short) 70).bej().bau();
        Class<?> original = ranch.getClass();
        // Native field 2: enabled state plus one advertised action (76).
        ByteBuffer overlay = ByteBuffer.allocate(20);
        overlay.put((byte) 1).put((byte) 2).putInt(6).put((byte) 2);
        overlay.putShort((short) 1);
        overlay.put(new byte[] {1, 1, 0, 0, 0}).put((byte) 0);
        overlay.putInt(1).put((byte) 76);
        ranch.as(overlay.array());
        if (ranch.getClass() != original || ranch instanceof bEu) {
            throw new AssertionError("Unexpected type replacement");
        }
        if (!(zaap instanceof bCu) || !(zaap instanceof bEu)) {
            throw new AssertionError("Native type 70 differs");
        }
        System.out.println("raw85=" + original.getName() + "; raw70=" + zaap.getClass().getName());
        System.out.println("PASS: state/action overlay preserves raw85 class; no native ZAAP projection");
    }
}
