import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import com.google.gson.GsonBuilder;

/** Complete aNw source export; no spell catalog or runtime reconstruction. */
public class ExportNativeExecutionCounts {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Output path required");
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
                + "/%d.jar!/%d.bin");
        List<Integer> ids = new ArrayList<>();
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw row) { ids.add(row.aZE()); }
        });
        Map<String, Object> effects = new TreeMap<>();
        for (int id : ids) {
            eVn effect = bcA.dcX().AH(id);
            if (effect == null) throw new IllegalStateException("Missing native effect " + id);
            Object previous = effects.put(Integer.toString(id), Map.of(
                    "effect_class", effect.awM(),
                    "event_execution_count", (int) effect.aZS(),
                    "event_execution_count_per_level", effect.cyc()));
            if (previous != null) throw new IllegalStateException("Duplicate effect " + id);
        }
        Map<String, Object> document = Map.of(
                "schema", "native-execution-counts-v1",
                "source", "bcA.AH(aNw): eVn.aZS()/cyc(); eZR.bbj",
                "complete", true, "count", effects.size(), "effects", effects);
        Files.writeString(Path.of(args[0]), new GsonBuilder().create().toJson(document));
        System.out.println("exported " + effects.size());
    }
}
