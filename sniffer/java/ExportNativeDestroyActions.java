import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Read-only original breed action census; no game session or client modification. */
public class ExportNativeDestroyActions {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Object> rows = new ArrayList<>();
        Map<Integer,Integer> counts = new TreeMap<>();
        int[] breeds = {0};
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb breed) {
                breeds[0]++;
                for (aMg action : breed.csj()) {
                    counts.merge((int)action.aGJ(), 1, Integer::sum);
                    if (action.aGJ() != 3) continue;
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("reference_id",breed.d()); row.put("family_id",breed.cqM());
                    row.put("min_level",breed.cqN()); row.put("max_level",breed.cqO());
                    row.put("action_id",action.d()); row.put("action_type",action.aGJ());
                    row.put("criteria",action.clT()); row.put("duration",action.getDuration());
                    row.put("native_cbH",action.cbH()); row.put("native_clx",action.clx());
                    row.put("native_csI",action.csI()); row.put("native_csJ",action.csJ());
                    row.put("native_csK",action.csK()); rows.add(row);
                }
            }
        });
        Map<String,Object> output = Map.of("authority","Original installed aMb.csj/aMg; exhaustive breed table, positive type3 only",
            "breed_count",breeds[0],"world_action_type_counts",counts,"actions",rows);
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(output));
        System.out.println("breeds="+breeds[0]+" type3_actions="+rows.size()+" action_types="+counts);
    }
}
