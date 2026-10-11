import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
/** Read-only map environment actor location audit; graphics are not breed IDs. */
public class AuditNpcNativePlacements {
    public static void main(String[] args) throws Exception {
        List<Object> actors = new ArrayList<>();
        List<Object> failures = new ArrayList<>();
        int maps = 0, chunks = 0, unsupported = 0;
        for (Path path : Files.list(Path.of("client/contents/maps/env")).sorted().toList()) {
            if (!path.toString().endsWith(".jar")) continue;
            int map = Integer.parseInt(path.getFileName().toString().replace(".jar", ""));
            maps++;
            try (ZipFile zip = new ZipFile(path.toFile())) {
                for (var entry : Collections.list(zip.entries())) {
                    if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                    ach environment = new ach();
                    try {
                        aoG reader = aoG.dx(zip.getInputStream(entry).readAllBytes());
                        reader.aJn();
                        environment.a(reader);
                    } catch (RuntimeException error) { unsupported++; failures.add(Map.of("map_id", map, "entry", entry.getName(), "error", error.toString(), "stack", Arrays.toString(error.getStackTrace()))); continue; }
                    chunks++;
                    if (environment.bux() == null) continue;
                    for (aci actor : environment.bux()) {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("map_id", map);
                        row.put("chunk", entry.getName());
                        row.put("native_actor_id", actor.p);
                        row.put("graphics_id", actor.cgI);
                        row.put("native_type", actor.bFV);
                        row.put("x", environment.rL(actor.bbj));
                        row.put("y", environment.rM(actor.bbk));
                        row.put("z", actor.bbl);
                        row.put("direction", actor.bbw);
                        row.put("script", actor.cgJ);
                        row.put("parameters", actor.atc);
                        row.put("native_bTi", actor.bTi);
                        row.put("native_aYX", actor.aYX);
                        actors.add(row);
                    }
                }
            }
        }
        Map<String, Object> result = Map.of("maps", maps, "chunks", chunks, "unsupported_chunks", unsupported, "actors", actors, "failures", failures);
        Files.writeString(Path.of(args[0]), new GsonBuilder().create().toJson(result));
        System.out.println("maps=" + maps + " chunks=" + chunks + " unsupported=" + unsupported + " environment_actors=" + actors.size());
    }
}
