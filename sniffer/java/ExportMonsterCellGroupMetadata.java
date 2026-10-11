import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;

/** Exact eYk dependency metadata using the same getters as the class graph. */
public class ExportMonsterCellGroupMetadata {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<String,Object> rows = new TreeMap<>();
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(line);
            eVn effect = bcA.dcX().AH(reference);
            if (effect == null || effect.awM() != 349 || effect.aZP() == null)
                throw new IllegalStateException("Missing original eYk definition " + reference);
            if (rows.put(line, Map.of("criterion_present", effect.fKT() != null,
                    "area_class", effect.aZP().getClass().getName(),
                    "raw_parameters", effect.fKI())) != null)
                throw new IllegalStateException("Duplicate original eYk definition");
        }
        Files.writeString(Path.of(args[1]), new Gson().toJson(rows) + "\n");
        System.out.println("Exported original cell-group dependencies: " + rows.size());
    }
}
