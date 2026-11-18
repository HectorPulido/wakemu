import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Offline dungeon identities/species; never starts or mutates a game client. */
public class ExportNativeDungeonDefinitions {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("schema_version", 1);
        result.put("native_table_id", new aKU().bGI());
        result.put("definitions", ExportNativeQuestDefinitions.table(new aKU()));
        Map<String,String> hashes = new TreeMap<>();
        for (String path : List.of("client/lib/wakfu-client.jar", "client/contents/bdata/" + new aKU().bGI() + ".jar")) {
            hashes.put(path, ExportNativeQuestDefinitions.sha(Path.of(path)));
        }
        result.put("source_sha256", hashes);
        Files.writeString(Path.of(args[0]), new GsonBuilder().serializeNulls().create().toJson(result));
        System.out.println("dungeons=" + ((List<?>)result.get("definitions")).size());
    }
}
