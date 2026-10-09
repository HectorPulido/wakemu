import java.nio.file.*;
import java.nio.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Read every installed object's state through the native client decoder. */
public class ExportNativeInteractiveStates {
    static Object field(Object obj, String name) throws Exception {
        for (Class<?> type = obj.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field value = type.getDeclaredField(name);
                value.setAccessible(true);
                return value.get(obj);
            } catch (NoSuchFieldException missing) { }
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        JsonArray rows = JsonParser.parseString(Files.readString(Path.of("server/protocol/native-map-objects.json"))).getAsJsonArray();
        List<Map<String, Object>> states = new ArrayList<>();
        int failures = 0;
        for (JsonElement entry : rows) {
            JsonObject row = entry.getAsJsonObject();
            try {
                bEG object = bEE.valueOf(row.get("type").getAsString()).bej().bau();
                object.as(HexFormat.of().parseHex(row.get("payload_hex").getAsString()));
                Collection<?> actions = (Collection<?>) field(object, "bkZ");
                ByteBuffer buffer = ByteBuffer.allocate(19 + actions.size());
                buffer.put(HexFormat.of().parseHex("01020000000602"));
                buffer.putShort((Short) field(object, "bkP"));
                for (String flag : List.of("bkQ", "bkR", "bkS", "bkV", "bkW")) {
                    buffer.put((byte) ((Boolean) field(object, flag) ? 1 : 0));
                }
                buffer.put((Byte) field(object, "bkX"));
                buffer.putInt(actions.size());
                for (Object action : actions) buffer.put((Byte) field(action, "svb"));
                Map<String, Object> state = new LinkedHashMap<>();
                state.put("id", row.get("id").getAsLong());
                state.put("map_id", row.get("map_id").getAsInt());
                state.put("type", row.get("type").getAsString());
                state.put("payload_hex", HexFormat.of().formatHex(buffer.array()));
                states.add(state);
            } catch (Throwable error) {
                failures++;
                System.err.println(row.get("id") + " " + row.get("type") + " " + error);
            }
        }
        if (failures != 0) throw new IllegalStateException("Incomplete native state extraction: " + failures);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(states));
        System.out.println("Extracted " + states.size() + " native interactive states");
    }
}
