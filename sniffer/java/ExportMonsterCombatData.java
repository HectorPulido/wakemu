import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Complete aMb rows and fresh native combat descriptors, offline only. */
public class ExportMonsterCombatData {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
            + "/%d.jar!/%d.bin");
        Method convert = bbo.class.getDeclaredMethod("a", aMb.class, short.class);
        convert.setAccessible(true);
        List<Map<String, Object>> monsters = new ArrayList<>();
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb row) {
                try {
                    blj descriptor = (blj) convert.invoke(null, row, (short) row.d());
                    Map<String, Object> record = new LinkedHashMap<>();
                    record.put("ref", row.d());
                    record.put("family_id", row.cqM());
                    record.put("min_level", (int) row.cqN());
                    record.put("max_level", (int) row.cqO());
                    List<Map<String, Integer>> abilities = new ArrayList<>();
                    for (aMk ability : row.csd()) abilities.add(Map.of(
                        "spell_id", ability.d(), "level_parameter", (int) ability.tL()));
                    record.put("native_abilities", abilities);
                    record.put("initial_state_triples", descriptor.cle());
                    record.put("fight_properties", descriptor.fsp());
                    record.put("raw_native", ExportMonsterEncyclopedia.raw(row));
                    monsters.add(record);
                } catch (Exception failure) {
                    throw new RuntimeException("Monster " + row.d(), failure);
                }
            }
        });
        monsters.sort(Comparator.comparingInt(row -> (Integer) row.get("ref")));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema", "native-monster-combat-source-v1");
        result.put("source", "Offline aMb.csd/aMk ownership; fresh bbo.a(aMb,short)/blj descriptor; all public data getters retained");
        result.put("monsters", monsters);
        Files.writeString(Path.of(args[0]), new GsonBuilder().serializeNulls().create().toJson(result));
        System.out.println("Exported " + monsters.size() + " complete monster combat source rows");
    }
}
