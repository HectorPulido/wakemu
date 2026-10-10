import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;

/** Offline presentation metadata audit; does not execute game effects. */
public class ExportRelicAuraEffects {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final Set<Integer> EXTRA = Set.of(20720,24110,28417,31361,32351,33395,29764,29789,31388,32355,33396);
    private static List<Object> presentation(Iterator<OY> iterator) {
        List<Object> rows = new ArrayList<>();
        iterator.forEachRemaining(value -> {
            Map<String,Object> row = new LinkedHashMap<>();
            row.put("native_class", value.getClass().getName());
            row.put("kind", value.aYb().toString());
            row.put("native_fields", JSON.toJsonTree(value));
            if (value instanceof Pt particle) {
                row.put("particle_reference", particle.aYG());
                row.put("orientation", particle.aYI().toString());
                row.put("flag_aYH", particle.aYH());
            }
            rows.add(row);
        });
        return rows;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        Map<Integer,JsonElement> definitions = new HashMap<>();
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw raw) { definitions.put(raw.aZE(), JSON.toJsonTree(raw)); }
        });
        List<Object> rows = new ArrayList<>();
        apw.bGL().a(new aLO(), new apB<aLO>() {
            public void load(aLO raw) {
                bJp item = new bIJ().f(raw);
                item.gjg().forEachRemaining(effect -> {
                    if (!effect.a(eVl.rxf) && !EXTRA.contains(item.d())) return;
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("reference", item.d());
                    row.put("item_level", item.cmZ());
                    row.put("effect_id", effect.aZE());
                    row.put("generic", effect.awM());
                    row.put("runner", eVi.fLJ().pS(effect.awM()).getClass().getName());
                    row.put("is_relic_aura_flag_35", effect.a(eVl.rxf));
                    row.put("parameters", effect.fKI());
                    row.put("criteria_native_class", effect.fKT()==null?null:effect.fKT().getClass().getName());
                    row.put("effect_native_fields", definitions.get(effect.aZE()));
                    row.put("presentation_fKV", presentation(effect.fKV()));
                    row.put("presentation_fKW", presentation(effect.fKW()));
                    row.put("presentation_fKY", effect.fKY()==null?List.of():presentation(effect.fKY().iterator()));
                    rows.add(row);
                });
            }
        });
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of("client/lib/wakfu-client.jar"))));
        Path destination = Path.of(args.length==0?".runtime/local/relic-aura-equipment-roots.json":args[0]);
        Files.writeString(destination, JSON.toJson(Map.of("source", "Installed aLO/bIJ/eVn and aNw; presentation OY/Pt, not gameplay triggers", "client_jar_sha256",hash,"effects",rows)));
        System.out.println("Exported " + rows.size() + " native equipment/presentation rows to " + destination);
    }
}
