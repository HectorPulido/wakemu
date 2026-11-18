import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Offline typed aLl/aLo/aLn/aLm export. Does not execute game actions. */
public class ExportNativeGenericDescriptors {
    static String sha(Path file) throws Exception {
        var digest = java.security.MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(file)) {
            byte[] buffer = new byte[65536];
            int size;
            while ((size = input.read(buffer)) >= 0) digest.update(buffer, 0, size);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("OUTPUT DESCRIPTOR_ID...");
        boolean all = args.length == 2 && args[1].equals("--all");
        Set<Integer> requested = new TreeSet<>();
        if (!all) for (int i = 1; i < args.length; i++) requested.add(Integer.parseInt(args[i]));
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Map<String,Object>> descriptors = new ArrayList<>();
        aLl prototype = new aLl();
        apw.bGL().a(prototype, new apB<aLl>() {
            public void load(aLl value) {
                if (!all && !requested.contains(value.d())) return;
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("native_class", "aLl"); row.put("descriptor_id", value.d());
                List<Map<String,Object>> groups = new ArrayList<>();
                int index = 0;
                for (aLo group : value.cnY()) {
                    Map<String,Object> g = new LinkedHashMap<>();
                    g.put("native_class", "aLo"); g.put("id", group.d());
                    g.put("clx", group.clx()); g.put("cod", group.cod());
                    g.put("coe", group.coe()); g.put("cof", group.cof());
                    g.put("cnd", group.cnd()); g.put("cog", group.cog());
                    List<Map<String,Object>> actions = new ArrayList<>();
                    for (aLn action : group.coh()) {
                        Map<String,Object> a = new LinkedHashMap<>();
                        a.put("native_class", "aLn"); a.put("wire_action", index++);
                        a.put("native_id", action.d()); a.put("criterion", action.clT());
                        a.put("raw_cob", action.cob());
                        List<Map<String,Object>> effects = new ArrayList<>();
                        for (aLm effect : action.coc()) {
                            Map<String,Object> e = new LinkedHashMap<>();
                            e.put("native_class", "aLm"); e.put("action_reference", effect.awM());
                            e.put("effect_type", effect.cnZ()); e.put("criterion", effect.clT());
                            e.put("parameters", effect.coa()); effects.add(e);
                        }
                        a.put("effects", effects); actions.add(a);
                    }
                    g.put("actions", actions); groups.add(g);
                }
                row.put("groups", groups); descriptors.add(row);
            }
        });
        if (!all && descriptors.size() != requested.size()) throw new IllegalStateException("Requested descriptor absent or duplicated");
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("schema", "native-generic-descriptors-v1");
        result.put("binary_table", prototype.bGI()); result.put("descriptors", descriptors);
        result.put("source_sha256", Map.of("client/lib/wakfu-client.jar", sha(Path.of("client/lib/wakfu-client.jar")),
            "client/contents/bdata/" + prototype.bGI() + ".jar", sha(Path.of("client/contents/bdata/" + prototype.bGI() + ".jar"))));
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Exported typed descriptors: " + descriptors.size());
    }
}
