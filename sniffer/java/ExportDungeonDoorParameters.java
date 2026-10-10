import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Export native Door baseline parameters without starting the game or a server. */
public class ExportDungeonDoorParameters {
    static Object field(Object object, String name) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try { Field f = type.getDeclaredField(name); f.setAccessible(true); return f.get(object); }
            catch (NoSuchFieldException missing) { }
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        JsonArray input = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        List<Map<String, Object>> output = new ArrayList<>();
        for (JsonElement element : input) {
            JsonObject row = element.getAsJsonObject();
            if (!row.get("type").getAsString().equals("Door")) continue;
            bEG object = bEE.valueOf("Door").bej().bau();
            object.as(HexFormat.of().parseHex(row.get("payload_hex").getAsString()));
            Map<String, Object> result = new LinkedHashMap<>();
            for (String key : List.of("map_id", "id", "x", "y", "z")) result.put(key, row.get(key));
            result.put("native_class", object.getClass().getName());
            result.put("native_parameters", field(object, "bbz"));
            result.put("baseline_state", field(object, "bkP"));
            result.put("baseline_visible", field(object, "bkQ"));
            result.put("baseline_usable", field(object, "bkR"));
            result.put("baseline_selectable", field(object, "bkS"));
            result.put("baseline_raw_bkV", field(object, "bkV"));
            result.put("baseline_raw_bkW", field(object, "bkW"));
            result.put("unlock_authority", "not_encoded_in_Door_client_parameters");
            output.add(result);
        }
        Files.writeString(Path.of(args[1]), new GsonBuilder().setPrettyPrinting().create().toJson(output));
        System.out.println("Exported " + output.size() + " native doors");
    }
}
