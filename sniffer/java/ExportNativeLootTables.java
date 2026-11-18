import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Offline fFc/fFe loot definitions; does not draw or execute rewards. */
public class ExportNativeLootTables {
    static Object raw(Object value) throws Exception {
        if (value == null || value instanceof Number || value instanceof String || value instanceof Boolean) return value;
        if (value.getClass().isArray()) {
            List<Object> rows = new ArrayList<>();
            for (int i = 0; i < Array.getLength(value); i++) rows.add(raw(Array.get(value, i)));
            return rows;
        }
        Map<String,Object> row = new TreeMap<>();
        row.put("native_class", value.getClass().getName());
        for (Method method : value.getClass().getDeclaredMethods())
            if (Modifier.isPublic(method.getModifiers()) && method.getParameterCount() == 0
                    && method.getReturnType() != Void.TYPE && !method.getName().equals("bGI"))
                row.put(method.getName(), raw(method.invoke(value)));
        return row;
    }
    public static void main(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("OUTPUT TABLE_ID...");
        boolean all = args.length == 2 && args[1].equals("--all");
        Set<Integer> requested = new TreeSet<>();
        if (!all) for (int i = 1; i < args.length; i++) requested.add(Integer.parseInt(args[i]));
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Object> rows = new ArrayList<>();
        fFc prototype = new fFc();
        apw.bGL().a(prototype, new apB<fFc>() { public void load(fFc value) {
            if (all || requested.contains(value.d())) try { rows.add(raw(value)); }
            catch (Exception error) { throw new RuntimeException(error); }
        }});
        if (!all && rows.size() != requested.size()) throw new IllegalStateException("Requested table absent or duplicated");
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(
            Map.of("schema", "native-loot-tables-v1", "binary_table", prototype.bGI(), "tables", rows)));
        System.out.println("Exported typed loot tables: " + rows.size());
    }
}
