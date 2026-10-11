import java.io.BufferedWriter;
import java.io.Writer;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import com.google.gson.Gson;

/** Full fyP.guh cost maps, including signed Huppermage resource111. Offline. */
public final class ExportNativeSpellResourceCosts {
    private static Map<String, Object> table(fyP value, int maximum) {
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, Object> resources = new TreeMap<>();
        for (Map.Entry<ffw, fyI> entry : value.guh().entrySet()) {
            List<Integer> levels = new ArrayList<>();
            for (int level = 0; level <= maximum; level++) {
                levels.add(entry.getValue().Qi(level));
            }
            resources.put(Integer.toString(Byte.toUnsignedInt(entry.getKey().aKg())), levels);
        }
        result.put("resources", resources);
        return result;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("Usage: ExportNativeSpellResourceCosts CLIENT_DIRECTORY OUTPUT_JSON");
        }
        apw.bGL().dd("jar:file:" + Path.of(args[0]).resolve("contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Field base = fyF.class.getDeclaredField("twf");
        base.setAccessible(true);
        Method conditional = bPS.class.getDeclaredMethod("a", aNs.class);
        conditional.setAccessible(true);
        Gson gson = new Gson();
        int[] count = {0};
        try (Writer output = new BufferedWriter(Files.newBufferedWriter(Path.of(args[1]), StandardCharsets.UTF_8))) {
            output.write("{\"schema\":\"native-spell-resource-costs-v1\",\"source\":\"Original fyF.g iterates fyP.guh; fyI.Qi(level0..maximum); sid111 uses signed fyQ.h, other PCs use nonnegative fyQ.g\",\"spells\":{");
            apw.bGL().a(new aNr(), new apB<aNr>() {
                public void load(aNr raw) {
                    try {
                        bPK spell = new bPK(bPS.d(raw));
                        int maximum = spell.Fq();
                        Map<String, Object> record = new LinkedHashMap<>();
                        record.put("maximum_level", maximum);
                        record.put("baseline", table((fyP) base.get(spell), maximum));
                        List<Object> rules = new ArrayList<>();
                        for (var entry : raw.cwI().entrySet()) {
                            Map<String, Object> rule = table((fyP) conditional.invoke(null, entry.getValue()), maximum);
                            rule.put("criteria", entry.getKey());
                            rules.add(rule);
                        }
                        record.put("conditional", rules);
                        if (count[0]++ > 0) output.write(",");
                        output.write(gson.toJson(Integer.toString(raw.d())));
                        output.write(":");
                        output.write(gson.toJson(record));
                    } catch (Exception error) {
                        throw new RuntimeException("Native resource-cost spell " + raw.d(), error);
                    }
                }
            });
            output.write("}}\n");
        }
        System.out.println("Exported " + count[0] + " complete native spell resource-cost maps");
    }
}
