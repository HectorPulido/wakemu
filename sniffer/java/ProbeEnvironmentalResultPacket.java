import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Objects;

/** Compare server result vectors with the installed, unmodified cAL decoder. */
public final class ProbeEnvironmentalResultPacket {
    public static void main(String[] args) throws Exception {
        int count = 0;
        for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
            String[] row = line.split("\t", -1);
            if (row.length != 7) throw new AssertionError("Invalid vector");
            cAL decoded = new cAL();
            if (!decoded.dp(HexFormat.of().parseHex(row[6])))
                throw new AssertionError("Original decoder refused vector");
            String name = row[2].isEmpty() ? null : new String(
                Base64.getDecoder().decode(row[2]), StandardCharsets.UTF_8);
            if (decoded.d() != 13263 || decoded.aHq() != Integer.parseInt(row[0])
                    || decoded.eNG() != Integer.parseInt(row[1])
                    || !Objects.equals(decoded.dmr(), name)
                    || decoded.dms() != Integer.parseInt(row[3])
                    || decoded.cpk() != Short.parseShort(row[4])
                    || decoded.eNF() != Integer.parseInt(row[5]))
                throw new AssertionError("Original decoder field mismatch at " + count);
            count++;
        }
        if (count == 0) throw new AssertionError("No vectors");
        System.out.println("PASS " + count + " original cAL result vectors");
    }
}
