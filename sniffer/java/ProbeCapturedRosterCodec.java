import java.nio.ByteBuffer;
import java.lang.reflect.*;
/** Parse/serialize yS/yT/tr with original native code, without combat initialization. */
public final class ProbeCapturedRosterCodec {
    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) result.append(String.format("%02x", value & 255));
        return result.toString();
    }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        Class<?> rosterType = Class.forName("yS"), entryType = Class.forName("yT");
        for (int selected : new int[] {-128, -1, 0, 9, 127}) {
            Object roster = rosterType.getConstructor().newInstance();
            rosterType.getField("amS").setByte(roster, (byte) selected);
            for (int slot : new int[] {-1, 0, 9, 10}) {
                Object entry = entryType.getConstructor().newInstance();
                Object row = entryType.getField("amT").get(entry);
                row.getClass().getField("Sj").setByte(row, (byte) slot);
                row.getClass().getField("aaN").setShort(row, (short) -32768);
                row.getClass().getField("aaO").setShort(row, (short) -2);
                row.getClass().getField("VY").set(row, "é");
                ((java.util.List<Object>) rosterType.getField("amR").get(roster)).add(entry);
            }
            ByteBuffer buffer = ByteBuffer.allocate(10000);
            if (!((Boolean) rosterType.getMethod("aF", ByteBuffer.class).invoke(roster, buffer)))
                throw new IllegalStateException("Native serialize refused");
            byte[] bytes = new byte[buffer.position()]; buffer.flip(); buffer.get(bytes);
            Object decoded = rosterType.getConstructor().newInstance();
            if (!((Boolean) rosterType.getMethod("aG", ByteBuffer.class).invoke(decoded, ByteBuffer.wrap(bytes))))
                throw new IllegalStateException("Native parse refused");
            ByteBuffer second = ByteBuffer.allocate(10000);
            rosterType.getMethod("aF", ByteBuffer.class).invoke(decoded, second);
            byte[] again = new byte[second.position()]; second.flip(); second.get(again);
            if (!java.util.Arrays.equals(bytes, again)) throw new IllegalStateException("Native roundtrip differs");
            System.out.println(selected + " " + hex(bytes));
        }
    }
}
