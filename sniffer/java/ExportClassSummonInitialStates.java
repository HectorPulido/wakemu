import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import com.google.gson.*;

/** Export only class-reachable fresh descriptor initial-state triples. */
public class ExportClassSummonInitialStates {
    public static void main(String[] args) throws Exception {
        JsonObject books = JsonParser.parseString(Files.readString(
            Path.of("server/protocol/native-class-summon-abilities.json")))
            .getAsJsonObject().getAsJsonObject("profiles");
        Set<String> wanted = books.keySet();
        Map<String, Object> profiles = new TreeMap<>();
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
            + "/%d.jar!/%d.bin");
        Method convert = bbo.class.getDeclaredMethod("a", aMb.class, short.class);
        convert.setAccessible(true);
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb row) {
                if (!wanted.contains(Integer.toString(row.d()))) return;
                try {
                    blj breed = (blj) convert.invoke(null, row, (short) row.d());
                    profiles.put(Integer.toString(row.d()), Map.of(
                        "initial_state_triples", breed.cle(),
                        "fight_properties", breed.fsp()));
                } catch (Exception failure) {
                    throw new RuntimeException(failure);
                }
            }
        });
        if (profiles.size() != wanted.size())
            throw new IllegalStateException("Missing class summon profile");
        Files.writeString(Path.of(args[0]), new Gson().toJson(Map.of(
            "source", "big.a(eGH) via fresh bje.aQc; eGH.cle triples",
            "profiles", profiles)) + "\n");
        System.out.println("Exported " + profiles.size() + " class profiles");
    }
}
