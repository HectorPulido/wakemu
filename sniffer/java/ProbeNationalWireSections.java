import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HexFormat;

/** Check server citizenship and PvP-rank sections with original serializers. */
public final class ProbeNationalWireSections {
    public static void main(String[] args) throws Exception {
        int count = 0;
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            String[] row = line.split("\t", -1);
            if (row.length != 4) throw new AssertionError("Invalid vector");
            byte[] ranks = HexFormat.of().parseHex(row[0]);
            byte[] scores = HexFormat.of().parseHex(row[1]);
            rk rank = new rk();
            ByteBuffer rankInput = ByteBuffer.wrap(ranks);
            if (!rank.aG(rankInput) || rankInput.hasRemaining()
                    || rank.Wt != Integer.parseInt(row[2]) || rank.WO != 0
                    || rank.WH != 0 || rank.WI != 0 || rank.WJ != 0 || rank.WP)
                throw new AssertionError("Original rk mismatch");
            ByteBuffer rankOutput = ByteBuffer.allocate(rank.DN());
            if (!rank.aF(rankOutput) || !Arrays.equals(rankOutput.array(), ranks))
                throw new AssertionError("Original rk serialization mismatch");
            qT points = new qT();
            ByteBuffer scoreInput = ByteBuffer.wrap(scores);
            if (!points.aG(scoreInput) || scoreInput.hasRemaining() || !points.Wc.isEmpty())
                throw new AssertionError("Original qT mismatch");
            String[] expected = row[3].isEmpty() ? new String[0] : row[3].split(",");
            if (points.Wb.size() != expected.length) throw new AssertionError("Population mismatch");
            for (int index = 0; index < expected.length; index++) {
                String[] pair = expected[index].split(":");
                qW score = points.Wb.get(index);
                if (score.Wi != Integer.parseInt(pair[0]) || score.Wj != Integer.parseInt(pair[1]))
                    throw new AssertionError("Signed native citizenship mismatch");
            }
            ByteBuffer scoreOutput = ByteBuffer.allocate(points.DN());
            if (!points.aF(scoreOutput) || !Arrays.equals(scoreOutput.array(), scores))
                throw new AssertionError("Original qT serialization mismatch");
            count++;
        }
        if (count == 0) throw new AssertionError("No vectors");
        System.out.println("PASS " + count + " original rk/qT/qW roundtrip vectors");
    }
}
