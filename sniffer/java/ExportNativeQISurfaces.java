import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
import com.google.gson.stream.JsonWriter;

/** Ordered VB.a(Vy[]) columns for QI.i/j; independent of Vz LOS and walkability. */
public class ExportNativeQISurfaces {
    static String sha(Path path) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream in = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536]; int n;
            while ((n = in.read(buffer)) != -1) hash.update(buffer, 0, n);
        }
        return HexFormat.of().formatHex(hash.digest());
    }

    static Map<String,Object> export(Path archivePath, Path output) throws Exception {
        int map = Integer.parseInt(archivePath.getFileName().toString().replace(".jar", ""));
        Path target = output.resolve(map + ".json"), temporary = output.resolve(map + ".json.tmp");
        int columns = 0, surfacesCount = 0, chunks = 0;
        Set<Long> occupied = new HashSet<>();
        try (ZipFile archive = new ZipFile(archivePath.toFile());
             JsonWriter json = new JsonWriter(new OutputStreamWriter(Files.newOutputStream(temporary), java.nio.charset.StandardCharsets.UTF_8))) {
            json.beginObject().name("schema").value("native-QI-Vy-columns-v1")
                .name("map_id").value(map).name("source_sha256").value(sha(archivePath))
                .name("chunks").beginArray();
            var entries = Collections.list(archive.entries());
            for (ZipEntry entry : entries) {
                if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                aoG reader = aoG.dx(archive.getInputStream(entry).readAllBytes());
                VB chunk;
                try { chunk = VC.ag(reader.aJn()); chunk.a(reader); }
                catch (Exception error) { throw new IOException("Native chunk decode failed: " + entry.getName(), error); }
                chunks++;
                json.beginObject().name("entry").value(entry.getName()).name("x").value(chunk.bbn)
                    .name("y").value(chunk.bbo).name("width").value(18).name("height").value(18)
                    .name("columns").beginArray();
                for (int y = chunk.bbo; y < chunk.bbo + 18; y++) {
                    for (int x = chunk.bbn; x < chunk.bbn + 18; x++) {
                        long key = ((long)x << 32) | (y & 0xffffffffL);
                        if (!occupied.add(key)) throw new IOException("Overlapping native chunk bounds at " + x + "," + y);
                        Vy[] surfaces = Vy.blX(); int count = chunk.a(x, y, surfaces, 0);
                        if (count < 0 || count > surfaces.length) throw new IOException("Invalid native Vy surface count");
                        if (count == 0) continue;
                        columns++; surfacesCount += count;
                        json.beginArray().value(x).value(y).beginArray();
                        for (int i = 0; i < count; i++) {
                            // Retain all signed flags and original order, including bLD=-1.
                            json.beginArray().value(surfaces[i].bbl).value(surfaces[i].bLD).endArray();
                        }
                        json.endArray().endArray();
                    }
                }
                json.endArray().endObject();
            }
            json.endArray().endObject();
        } catch (Exception error) {
            Files.deleteIfExists(temporary); throw error;
        }
        Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING);
        return Map.of("map_id", map, "status", "exported", "chunks", chunks, "columns", columns,
                      "surfaces", surfacesCount, "source_sha256", sha(archivePath), "output_sha256", sha(target));
    }

    public static void main(String[] args) throws Exception {
        Path input = Path.of(args[0]), output = Path.of(args[1]);
        Files.createDirectories(output);
        List<Path> archives;
        if (Files.isRegularFile(input)) archives = List.of(input);
        else try (var paths = Files.list(input)) {
            archives = paths.filter(p -> p.getFileName().toString().matches("\\d+\\.jar"))
                .sorted(Comparator.comparingInt(p -> Integer.parseInt(p.getFileName().toString().replace(".jar", "")))).toList();
        }
        List<Map<String,Object>> rows = new ArrayList<>(); int failures = 0;
        for (Path archive : archives) {
            try { rows.add(export(archive, output)); }
            catch (Exception error) {
                StringWriter trace = new StringWriter(); error.printStackTrace(new PrintWriter(trace));
                failures++; rows.add(Map.of("map", archive.toString(), "status", "error", "error", error.toString(),
                    "error_trace", trace.toString(), "source_sha256", sha(archive)));
            }
        }
        Map<String,String> libraryHashes = new TreeMap<>();
        try (var paths = Files.list(Path.of("client/lib"))) {
            for (Path path : paths.filter(p -> p.toString().endsWith(".jar")).toList()) {
                libraryHashes.put(path.toString(), sha(path));
            }
        }
        Map<String,Object> manifest = Map.of("sources_sha256", libraryHashes, "schema", "native-QI-Vy-bulk-v1", "maps", rows,
            "failures", failures, "client_sha256", sha(Path.of("client/lib/wakfu-client.jar")),
            "exporter_sha256", sha(Path.of("sniffer/java/ExportNativeQISurfaces.java")));
        Files.writeString(output.resolve("manifest.json"), new GsonBuilder().setPrettyPrinting().create().toJson(manifest));
        System.out.println("maps=" + archives.size() + " failures=" + failures);
        if (failures != 0) System.exit(1);
    }
}
