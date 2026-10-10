import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.TreeMap;

/** Offline native world-entity reader; validates complete PC refresh snapshots. */
public final class ProbeWorldPublicCharacteristics {
    public static void main(String[] args) throws Exception {
        ByteBuffer bytes = ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
        eHf format = eHf.values()[Byte.toUnsignedInt(bytes.get())];
        eHk entity = new eHk();
        var sectionReader = eHd.class.getDeclaredMethod("a", eHe.class);
        sectionReader.setAccessible(true);
        Map<Integer, Integer> currents = new TreeMap<>();
        for (eHe section : format.fuK()) {
            Object reader = sectionReader.invoke(entity, section);
            boolean success = (Boolean) reader.getClass().getMethod("aG", ByteBuffer.class)
                .invoke(reader, bytes);
            if (!success) throw new AssertionError("Native section rejected: " + section);
            if (reader instanceof pl publicStats) {
                for (tB row : publicStats.SS.abi) {
                    int identity = Byte.toUnsignedInt(row.Sj);
                    if (currents.put(identity, row.abj) != null) {
                        throw new AssertionError("Duplicate characteristic: " + identity);
                    }
                }
            }
        }
        if (bytes.hasRemaining()) throw new AssertionError("Trailing native entity bytes");
        if (currents.isEmpty()) throw new AssertionError("Missing public characteristics");
        for (int index = 1; index < args.length; index++) {
            String[] expectation = args[index].split("=", 2);
            int identity = Integer.parseInt(expectation[0]);
            int expected = Integer.parseInt(expectation[1]);
            if (!Integer.valueOf(expected).equals(currents.get(identity))) {
                throw new AssertionError("PC " + identity + " expected " + expected
                    + " got " + currents.get(identity));
            }
        }
        System.out.println("PASS native format=" + format + " PC count=" + currents.size()
            + " complete=true expected=" + (args.length - 1));
    }
}
