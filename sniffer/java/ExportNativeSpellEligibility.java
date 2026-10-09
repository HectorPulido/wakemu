import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.lang.reflect.*;
import java.util.zip.*;
import com.google.gson.Gson;

/** Original scalar casting flags; independent of level, including level0. */
public class ExportNativeSpellEligibility {
    static Map<String, Object> flags(fyP table) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("line_of_sight_cwL", table.cwL());
        value.put("linear_cwM", table.cwM());
        value.put("path_option_cwN", table.cwN());
        value.put("diagonal_cwT", table.cwT());
        value.put("mandatory_empty_cwU", table.cwU());
        value.put("linear_path_cwV", table.cwV());
        value.put("allow_self_cwE", table.cwE());
        value.put("range_modifiable", table.guk());
        return value;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() { public void load(aKX raw) {} });
        apw.bGL().a(new aNw(), new apB<aNw>() { public void load(aNw raw) {} });
        Field base = fyF.class.getDeclaredField("twf"); base.setAccessible(true);
        Method conditional = bPS.class.getDeclaredMethod("a", aNs.class); conditional.setAccessible(true);
        Gson gson = new Gson(); int[] count = {0};
        try (Writer out = new BufferedWriter(new OutputStreamWriter(Files.newOutputStream(Path.of(args[0])), java.nio.charset.StandardCharsets.UTF_8))) {
            out.write("{\"source\":\"Original fyP flags + fyF/fcO/fcj/ePI consumer contracts; scalar flags apply at every level including0\",\"spells\":{");
            apw.bGL().a(new aNr(), new apB<aNr>() {
                public void load(aNr raw) { try {
                    bPK spell = bPS.elL().IP(raw.d());
                    Map<String, Object> record = new LinkedHashMap<>();
                    record.put("baseline", flags((fyP) base.get(spell)));
                    record.put("forbid_QI_P", spell.gjl());
                    record.put("cast_criterion_raw", raw.cwd());
                    record.put("cast_criterion_native_present", spell.gtP() != null);
                    List<Object> rules = new ArrayList<>();
                    for (var entry : raw.cwI().entrySet()) {
                        Map<String, Object> rule = new LinkedHashMap<>();
                        rule.put("criteria", entry.getKey());
                        rule.put("flags", flags((fyP) conditional.invoke(null, entry.getValue())));
                        rules.add(rule);
                    }
                    record.put("conditional", rules);
                    if (count[0]++ > 0) out.write(",");
                    out.write(gson.toJson(Integer.toString(raw.d())) + ":" + gson.toJson(record));
                } catch (Exception error) { throw new RuntimeException("spell " + raw.d(), error); } }
            });
            out.write("}}\n");
        }
        System.out.println("Exported original eligibility flags for " + count[0] + " spells");
    }
}
