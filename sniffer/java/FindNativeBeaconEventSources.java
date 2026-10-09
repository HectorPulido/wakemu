import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Inventory actual published aZO bits, separately from subscription masks. */
public class FindNativeBeaconEventSources {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<Integer, List<Map<String, Object>>> sources = new TreeMap<>();
        for (int id : new int[]{1024, 1025, 1028}) sources.put(id, new ArrayList<>());
        int[] checked = {0};
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw raw) {
                checked[0]++;
                eVn effect = bcA.dcX().AH(raw.aZE());
                if (effect == null) throw new IllegalStateException("Missing native definition " + raw.aZE());
                BitSet emitted = effect.aZO();
                if (emitted == null) return;
                for (var entry : sources.entrySet()) {
                    if (emitted.get(entry.getKey())) entry.getValue().add(Map.of(
                        "reference", effect.aZE(), "effect_class", effect.awM(),
                        "emitted_events", emitted.stream().toArray()));
                }
            }
        });
        Map<String, Object> result = new TreeMap<>();
        result.put("source", "Installed aNw -> bcA.AH -> eVn.aZO. Subscription masks and unrelated numeric namespaces excluded.");
        result.put("definitions_checked", checked[0]);
        result.put("events", sources);
        result.put("limitation", "Absence of aZO producers does not prove an external server lifecycle event unavailable.");
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Definitions=" + checked[0]);
        for (var entry : sources.entrySet()) System.out.println(entry.getKey() + " producers=" + entry.getValue().size());
    }
}
