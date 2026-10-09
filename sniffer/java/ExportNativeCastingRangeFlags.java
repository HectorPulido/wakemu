import com.google.gson.Gson;
import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
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


/** Offline bulk range flags from installed aNr tables; no client/network use. */
public final class ExportNativeCastingRangeFlags {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Usage: ExportNativeCastingRangeFlags output.json");
        }
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() {
            public void load(aKX raw) {}
        });
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw raw) {}
        });
        Field baseline = fyF.class.getDeclaredField("twf");
        baseline.setAccessible(true);
        Method select = bPS.class.getDeclaredMethod("a", aNs.class);
        select.setAccessible(true);
        Gson gson = new Gson();
        int[] counts = {0, 0};
        try (Writer output = new BufferedWriter(new OutputStreamWriter(
                Files.newOutputStream(Path.of(args[0])),
                StandardCharsets.UTF_8))) {
            output.write("{\"source\":\"Installed aNr/fyP.guk baseline and conditional range flags, offline\",\"spells\":{");
            apw.bGL().a(new aNr(), new apB<aNr>() {
                public void load(aNr raw) {
                    try {
                        bPK spell = bPS.elL().IP(raw.d());
                        fyP table = (fyP) baseline.get(spell);
                        Map<String, Object> record = new LinkedHashMap<>();
                        record.put("range_modifiable", table.guk());
                        List<Object> conditional = new ArrayList<>();
                        for (var entry : raw.cwI().entrySet()) {
                            fyP alternate = (fyP) select.invoke(null, entry.getValue());
                            conditional.add(Map.of("criteria", entry.getKey(),
                                    "range_modifiable", alternate.guk()));
                        }
                        record.put("conditional", conditional);
                        if (counts[0]++ > 0) {
                            output.write(",");
                        }
                        counts[1] += conditional.isEmpty() ? 0 : 1;
                        output.write(gson.toJson(Integer.toString(raw.d())) + ":" + gson.toJson(record));
                    } catch (Exception error) {
                        throw new IllegalStateException("Cannot export native spell " + raw.d(), error);
                    }
                }
            });
            output.write("}}\n");
        }
        System.out.println("Exported " + counts[0] + " spells, " + counts[1] + " with conditional flags");
    }
}
