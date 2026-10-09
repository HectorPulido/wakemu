import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/** Original eZU envelope primitive; no catalog or running-effect replay. */
public final class ProbeNativeRemoteEffects {
    public static void main(String[] args) throws Exception {
        eZU serializer = new eZU(new eZV(null));
        Method method = eZU.class.getDeclaredMethod("a", boolean.class, Map.class, Map.class);
        method.setAccessible(true);
        int checked = 0;
        for (int length : new int[]{0, 1, 255, 32767}) {
            eWn grant = new eWn();
            byte[] payload = new byte[length];
            Arrays.fill(payload, (byte) 0x5a);
            Map<Qe, byte[]> ordinary = new LinkedHashMap<>();
            ordinary.put(grant, payload);
            byte[] actual = (byte[]) method.invoke(serializer, false, ordinary, new LinkedHashMap<Qe, byte[]>());
            byte[] expected = ByteBuffer.allocate(12 + length).putShort((short)1)
                .putInt(grant.d()).putShort((short)length).put(payload).putInt(0).array();
            if (!Arrays.equals(actual, expected)) throw new AssertionError("length=" + length);
            checked++;
        }
        Map<Qe, byte[]> oversized = new LinkedHashMap<>();
        oversized.put(new eWn(), new byte[25000]);
        oversized.put(new eWn(), new byte[25000]);
        byte[] fallback = (byte[])method.invoke(serializer, false, oversized, new LinkedHashMap<Qe, byte[]>());
        if (!Arrays.equals(fallback, new byte[2])) throw new AssertionError("oversize fallback");
        checked++;
        System.out.println("PASS " + checked + " original eZU envelope checks; inclusion/replay not exercised");
    }
}
