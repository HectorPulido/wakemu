import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Read native generic-object parameters through the shipped object decoder. */
public class ExportNativeGenericSources {
    static Object field(Object obj, String name) throws Exception {
        for (Class<?> c = obj.getClass(); c != null; c = c.getSuperclass()) {
            try { Field f = c.getDeclaredField(name); f.setAccessible(true); return f.get(obj); }
            catch (NoSuchFieldException ignored) {}
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("CONTEXT OUTPUT");
        JsonArray objects = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject().getAsJsonArray("objects");
        JsonArray result = new JsonArray();
        for (JsonElement value : objects) {
            JsonObject row = value.getAsJsonObject().deepCopy();
            bEG obj = bEE.valueOf("GenericActivableInteractiveElement").bej().bau();
            obj.as(HexFormat.of().parseHex(row.get("payload_hex").getAsString()));
            String raw = (String)field(obj, "bbz");
            row.addProperty("native_parameters", raw);
            try { row.addProperty("descriptor_id", Integer.parseInt(raw)); }
            catch (NumberFormatException ignored) { row.addProperty("unsupported", "Nondecimal native parameter"); }
            result.add(row);
        }
        Files.writeString(Path.of(args[1]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Decoded native generic sources: " + result.size());
    }
}
