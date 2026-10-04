import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;

/** Offline raw evidence only: these fields do not establish innate assignment. */
public class ExportClassStateEvidence {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Map<String,Object>> rows = new ArrayList<>();
        apw.bGL().a(new aNv(), new apB<aNv>() {
            public void load(aNv state) {
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("id",state.d());
                for (var field : aNv.class.getDeclaredFields()) {
                    try { field.setAccessible(true); row.put(field.getName(),field.get(state)); }
                    catch (ReflectiveOperationException error) { throw new IllegalStateException(error); }
                }
                rows.add(row);
            }
        });
        Files.writeString(Path.of(args[0]),new Gson().toJson(rows));
        System.out.println("Exported " + rows.size() + " raw state records; assignment remains unproven");
    }
}
