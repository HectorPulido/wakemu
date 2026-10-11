import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

/** Export actual fpR predicates and their native item rarity authority. */
public final class ExportNativeSublimationTargets {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Map<String,Object>> rows = new ArrayList<>();
        apw.bGL().a(new aLO(), new apB<aLO>() {
            public void load(aLO raw) {
                bJp definition = new bIJ().f(raw);
                fnR item = fnR.a(1L, definition);
                boolean epic = fpR.sRB.ax(item), relic = fpR.sRC.ax(item);
                if (epic && relic) throw new AssertionError("Overlapping native special predicates");
                if (!epic && !relic) return;
                fof rarity = item.dAX();
                if ((epic && (rarity != fof.sJk || rarity.aKg() != 7))
                    || (relic && (rarity != fof.sJi || rarity.aKg() != 5)))
                    throw new AssertionError("Unexpected native target rarity");
                rows.add(Map.of("reference", definition.d(), "item_level", (int) definition.cmZ(),
                    "pattern_type", epic ? "EPIC" : "RELIC", "rarity_code", (int) rarity.aKg(),
                    "rarity_enum", rarity.name()));
            }
        });
        rows.sort(Comparator.comparingInt(row -> (int) row.get("reference")));
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
            .digest(Files.readAllBytes(Path.of("client/lib/wakfu-client.jar"))));
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(
            Map.of("client_jar_sha256", hash, "source", "fpR.EPIC/RELIC.ax(fnR) -> fnR.dAX/fof.aKg",
                "count", rows.size(), "targets", rows)) + "\n");
        System.out.println("Exported " + rows.size() + " native special targets; jar=" + hash);
    }
}
