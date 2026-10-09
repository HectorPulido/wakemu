import java.nio.file.*;
import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;

/** Original class-only aKf -> aZL -> bhe model selection, all byte operands. */
public final class ExportNativeClassCopyAppearance {
    static String sha(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        JsonObject source = JsonParser.parseString(Files.readString(
            Path.of("server/protocol/breed-innate-definitions.json"))).getAsJsonObject();
        Set<Integer> seeds = new TreeSet<>();
        for (JsonElement row : source.getAsJsonArray("breeds"))
            seeds.add(row.getAsJsonObject().get("breed").getAsInt());
        aZL loader = new aZL();
        Method load = aZL.class.getDeclaredMethod("a", aKf.class);
        load.setAccessible(true);
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Set<Integer> loaded = new TreeSet<>();
        apw.bGL().a(new aKf(), new apB<aKf>() {
            public void load(aKf definition) {
                if (!seeds.contains(definition.d())) return;
                try { load.invoke(loader, definition); loaded.add(definition.d()); }
                catch (Exception error) { throw new RuntimeException(error); }
            }
        });
        if (!loaded.equals(seeds)) throw new AssertionError("Missing actual class graphics definitions " + loaded);
        Map<String,Object> breeds = new TreeMap<>();
        for (int breed : seeds) {
            Map<String,Object> sexes = new TreeMap<>();
            for (byte sex = 0; sex < 2; sex++) {
                List<Integer> models = new ArrayList<>();
                for (int cloth = -128; cloth <= 127; cloth++)
                    models.add((int) bhe.dkj().b((short) breed, sex, (short) cloth));
                sexes.put(Byte.toString(sex), models);
            }
            breeds.put(Integer.toString(breed), sexes);
        }
        int bucket = new aKf().bGI();
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("schema", 1);
        result.put("source", "Original aKf -> aZL.a(aKf) -> bhe.b(breed,sex,cloth); plain ordinary pGT override absent policy");
        result.put("jar_sha256", sha(Path.of("client/lib/wakfu-client.jar")));
        result.put("bdata_bucket", bucket);
        result.put("bdata_sha256", sha(Path.of("client/contents/bdata/" + bucket + ".jar")));
        result.put("class_seed_sha256", sha(Path.of("server/protocol/breed-innate-definitions.json")));
        result.put("cloth_offset", -128);
        result.put("breeds", breeds);
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Exported " + seeds.size() + " class models, 9216 native selections");
    }
}
