import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;

/** Native bEG.dST approach mask/orientation and VA terrain height selection. */
public class ExportNativeTeleporterApproach {
    static final Map<Integer, List<VB>> maps = new HashMap<>();
    static List<VB> terrain(int map) throws Exception {
        if (maps.containsKey(map)) return maps.get(map);
        List<VB> chunks = new ArrayList<>();
        try (ZipFile zip = new ZipFile("client/contents/maps/tplg/" + map + ".jar")) {
            for (var entry : Collections.list(zip.entries())) {
                if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                aoG raw = aoG.dx(zip.getInputStream(entry).readAllBytes());
                VB chunk = VC.ag(raw.aJn());
                chunk.a(raw);
                chunks.add(chunk);
            }
        }
        maps.put(map, chunks);
        return chunks;
    }
    public static void main(String[] args) throws Exception {
        JsonArray catalog = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        JsonArray objects = JsonParser.parseString(Files.readString(Path.of("server/protocol/native-map-objects.json"))).getAsJsonArray();
        Map<String, JsonObject> sources = new HashMap<>();
        for (var element : catalog) {
            var row = element.getAsJsonObject();
            sources.put(row.get("map_id") + ":" + row.get("id"), row);
        }
        VF.a((short)6, (byte)0, (short)4);
        var moverField = VF.class.getDeclaredField("bMl");
        moverField.setAccessible(true);
        Sm mover = (Sm)moverField.get(null);
        for (var element : objects) {
            var row = element.getAsJsonObject();
            if (!row.get("type").getAsString().equals("Teleporter")) continue;
            var source = sources.get(row.get("map_id") + ":" + row.get("id"));
            if (source == null) continue;
            bEG object = bEE.valueOf("Teleporter").bej().bau();
            object.as(HexFormat.of().parseHex(row.get("payload_hex").getAsString()));
            short mask = (short)ExportGenericTeleporters.field(object, "bbx");
            var directions = QV.aa(mask);
            boolean blocksCenter = object.beu();
            if (blocksCenter) directions.remove(QV.bkv);
            source.addProperty("approach_mask", mask);
            source.addProperty("approach_orientation", object.bcy().dyI);
            source.addProperty("approach_blocks_center", blocksCenter);
            JsonArray positions = new JsonArray();
            for (QV relative : directions) {
                int x = object.bcz(), y = object.bcA();
                short z = object.bcB();
                if (relative != QV.bkv) {
                    aAS direction = aAS.wL((object.bcy().dyI + relative.beg()) % 8);
                    x += direction.dyJ; y += direction.dyK;
                    short selected = Short.MIN_VALUE;
                    try {
                        for (VB chunk : terrain(row.get("map_id").getAsInt())) {
                            if (x < chunk.bbn || x >= chunk.bbn + 18 || y < chunk.bbo || y >= chunk.bbo + 18) continue;
                            Vy[] surfaces = Vy.blX();
                            int count = chunk.a(x, y, surfaces, 0);
                            if (count > 0) selected = VA.a(0, count, surfaces, (short)(z + mover.bgf()), mover.bge());
                            break;
                        }
                    } catch (Exception unsupported) {
                        source.addProperty("approach_geometry_error", unsupported.getClass().getSimpleName());
                    }
                    if (selected == Short.MIN_VALUE) continue;
                    z = selected;
                }
                JsonObject position = new JsonObject();
                position.addProperty("x", x); position.addProperty("y", y); position.addProperty("z", z);
                positions.add(position);
            }
            source.add("approach_positions", positions);
        }
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(catalog));
    }
}
