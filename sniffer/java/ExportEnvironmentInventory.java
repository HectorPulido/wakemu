import java.io.ByteArrayOutputStream;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.ZipFile;
import com.google.gson.*;

/** Inventory only: never emits an activation catalog or modifies original assets. */
public class ExportEnvironmentInventory {
    static aIl parse(byte[] bytes) {
        aoG reader = aoG.dx(bytes);
        if (reader.aJn() != 0) throw new IllegalArgumentException("Unknown environment version");
        aIl map = new aIl();
        map.a(reader);
        if (reader.available() != 0) throw new IllegalArgumentException("Unconsumed environment bytes");
        return map;
    }
    static byte[] legacyParticles(byte[] bytes) throws Exception {
        if (bytes.length < 6) throw new IllegalArgumentException("Incomplete environment header");
        int count = bytes[5] & 255;
        if (count == 0 || bytes.length < 6 + count * 13) throw new IllegalArgumentException("No legacy particle candidate");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(bytes, 0, 6);
        for (int i = 0; i < count; i++) {
            out.write(bytes, 6 + i * 13, 13);
            // Current acC has four extra sub-cell fields; their legacy values are unknown.
            // Neutral padding is an inventory diagnostic, not an original-client repair.
            out.write(new byte[4]);
        }
        out.write(bytes, 6 + count * 13, bytes.length - 6 - count * 13);
        return out.toByteArray();
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Object> objects = new ArrayList<>(), chunks = new ArrayList<>();
        int archives = 0;
        for (Path path : Files.list(Path.of("client/contents/maps/env")).sorted().toList()) {
            if (!path.toString().endsWith(".jar")) continue;
            archives++;
            int mapId = Integer.parseInt(path.getFileName().toString().replace(".jar", ""));
            try (ZipFile zip = new ZipFile(path.toFile())) {
                for (var entry : Collections.list(zip.entries())) {
                    if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                    byte[] bytes = zip.getInputStream(entry).readAllBytes();
                    Map<String, Object> chunk = new LinkedHashMap<>();
                    chunk.put("map_id", mapId); chunk.put("chunk", entry.getName());
                    chunk.put("sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
                    String qualification = "original_native_reader";
                    try {
                        aIl parsed;
                        try { parsed = parse(bytes); }
                        catch (RuntimeException original) {
                            chunk.put("original_error", original.toString());
                            parsed = parse(legacyParticles(bytes));
                            qualification = "legacy_particle_diagnostic_not_active";
                        }
                        List<Object> pending = new ArrayList<>();
                        if (parsed.buw() != null) for (acq object : parsed.buw()) {
                            bEE type = bEE.cb(object.bkI);
                            bEG decoded = null;
                            if (type != null) { decoded = type.bej().bau(); decoded.as(object.azM); }
                            Map<String, Object> row = new LinkedHashMap<>();
                            row.put("map_id", mapId); row.put("chunk", entry.getName()); row.put("id", object.aHm);
                            row.put("native_type_id", object.bkI);
                            row.put("type", type == null ? "UNKNOWN_NATIVE_TYPE_" + object.bkI : type.name());
                            if (decoded != null) { row.put("x", decoded.getWorldX()); row.put("y", decoded.getWorldY()); row.put("z", decoded.getAltitude()); }
                            else row.put("decode_limitation", "Original acq record preserved; installed bEE has no factory for this type");
                            row.put("qualification", qualification);
                            row.put("payload_hex", HexFormat.of().formatHex(object.azM)); pending.add(row);
                        }
                        objects.addAll(pending); chunk.put("qualification", qualification); chunk.put("objects", pending.size());
                    } catch (Throwable failure) { chunk.put("error", failure.toString()); }
                    chunks.add(chunk);
                }
            }
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema_version", 1); result.put("archives", archives); result.put("chunks", chunks); result.put("objects", objects);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("archives=" + archives + " chunks=" + chunks.size() + " inventory_objects=" + objects.size());
        System.exit(0);
    }
}
