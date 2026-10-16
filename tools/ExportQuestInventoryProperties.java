import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import com.google.gson.GsonBuilder;

/** Read-only native QUEST classification; never modifies the installed client. */
public final class ExportQuestInventoryProperties {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<Integer, List<Integer>> properties = new TreeMap<>();
        Map<Integer, Integer> maximums = new TreeMap<>();
        apw.bGL().a(new aLO(), new apB<aLO>() {
            public void load(aLO row) {
                for (int property : row.cpO()) {
                    if (property == 2 || property == 21) {
                        properties.computeIfAbsent(property, ignored -> new ArrayList<>()).add(row.d());
                        maximums.put(row.d(), (int) new bIJ().f(row).bfi());
                    }
                }
            }
        });
        List<Integer> personal = new ArrayList<>(properties.get(2));
        personal.removeAll(properties.get(21));
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("source", "Installed aLO.cpO native property IDs; foc.QUEST=2, foc.ACCOUNT_QUEST=21. Account properties take precedence.");
        output.put("client_sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of("client/lib/wakfu-client.jar")))));
        output.put("quest_property_references", properties.get(2));
        output.put("account_quest_property_references", properties.get(21));
        output.put("personal_references", personal);
        maximums.keySet().retainAll(personal);
        output.put("maximum_quantities", maximums);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(output) + "\n");
    }
}
