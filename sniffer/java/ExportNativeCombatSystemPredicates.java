import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Tiny enum/constructor proof; no native effect catalog or live configuration. */
public class ExportNativeCombatSystemPredicates {
    public static void main(String[] args) throws Exception {
        Map<String, Object> configurations = new TreeMap<>();
        eEI fresh = new eEI();
        for (eEL entry : eEL.values()) {
            Object value = entry.getDefaultValue();
            Map<String, Object> row = new TreeMap<>();
            row.put("id", entry.aIX());
            row.put("boolean", value instanceof Boolean);
            if (value instanceof Boolean) {
                row.put("default", value);
                if (fresh.l(entry) != (Boolean) value) throw new AssertionError(entry.getKey());
            }
            configurations.put(entry.getKey(), row);
        }
        Map<String, Object> models = new TreeMap<>();
        for (fcz model : fcz.values()) {
            Map<String, Object> row = new TreeMap<>();
            row.put("name", model.name());
            row.put("category", model.fVU().name());
            row.put("is_pvp", model.fVU().fVT());
            if (models.put(Byte.toString(model.eSS()), row) != null) throw new AssertionError("Duplicate model");
        }
        Map<String, Object> out = new TreeMap<>();
        out.put("source", "eJs/eEL.tk/eEI.l fresh EnumMap -> eEL.getDefaultValue; eOL/fcz.fVU/fcL.fVT, actual installed native classes.");
        out.put("configurations", configurations);
        out.put("fight_models", models);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(out));
        System.out.println("Configurations=" + configurations.size() + " models=" + models.size() + " fresh defaults verified");
    }
}
