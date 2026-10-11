import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Read-only exhaustive native conversational action fields; no inferred roots. */
public class ExportNpcActionContracts {
    public static void main(String[] args) throws Exception {
        Path data = Path.of("client/contents/bdata").toAbsolutePath();
        apw.bGL().dd("jar:file:" + data + "/%d.jar!/%d.bin");
        List<Object> rows = new ArrayList<>();
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb breed) {
                for (aMg action : breed.csj()) {
                    if (action.aGJ() != 4) continue;
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("reference_id", breed.d());
                    row.put("action_id", action.d());
                    row.put("criteria", action.clT());
                    row.put("native_cbH", action.cbH());
                    row.put("native_clx", action.clx());
                    row.put("duration", action.getDuration());
                    row.put("native_csI", action.csI());
                    row.put("native_csJ", action.csJ());
                    row.put("native_csK", action.csK());
                    rows.add(row);
                }
            }
        });
        Map<Integer, Boolean> available = new TreeMap<>();
        for (int table : new int[]{42,43,44,45,46,62,63})
            available.put(table, Files.isRegularFile(data.resolve(table + ".jar")));
        Map<String, Object> output = Map.of("schema", "native-npc-action-contracts-v1",
            "actions", rows, "related_table_archives_present", available);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(output));
        System.out.println("actions=" + rows.size() + " tables=" + available);
    }
}
