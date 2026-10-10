import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Export native rift definitions offline without game or database writes. */
public class ExportInfiniteWaveEvidence {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Map<String,Object>> rows = new ArrayList<>();
        aLF prototype = new aLF();
        apw.bGL().a(prototype, new apB<aLF>() {
            public void load(aLF value) {
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("id", value.d());
                row.put("raw_cpb", value.cpb());
                row.put("raw_cpc", value.cpc());
                row.put("raw_rI", value.rI());
                row.put("first_map_id", value.cpf());
                row.put("raw_type", value.cnn());
                row.put("species_refs", Arrays.stream(value.cpd()).mapToInt(aLI::cpi).toArray());
                List<Map<String,Object>> locations = new ArrayList<>();
                for (aLH location : value.cpe()) {
                    Map<String,Object> entry = new LinkedHashMap<>();
                    entry.put("map_id", location.arM());
                    entry.put("raw_type", location.cnn());
                    locations.add(entry);
                }
                row.put("locations", locations);
                rows.add(row);
            }
        });
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("native_record_class", "aLF");
        result.put("binary_table_id", prototype.bGI());
        result.put("records", rows);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Exported " + rows.size() + " native infinite-wave records");
    }
}
