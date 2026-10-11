import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;

/** Read native terrain and suitability evidence; never infer official spawns. */
public final class ExportFishingSurfaces {
    static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    public static void main(String[] args) throws Exception {
        if (args.length < 3) throw new IllegalArgumentException("client-root eligibility.json output.json [map ...]");
        Path maps = Path.of(args[0], "contents", "maps");
        JsonObject eligibility = JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        Set<String> filter = new HashSet<>(Arrays.asList(args).subList(3, args.length));
        List<Object> slots = new ArrayList<>(), assets = new ArrayList<>(), errors = new ArrayList<>();
        int chunks = 0, objectCount = 0;
        List<Object> manifest = new ArrayList<>(), missing = new ArrayList<>();
        for (Path candidate : Files.list(maps.resolve("tplg")).sorted().toList()) {
            String name = candidate.getFileName().toString();
            if (name.matches("\\d+\\.jar") && !Files.isRegularFile(maps.resolve("env").resolve(name)))
                missing.add(Map.of("map_id",Integer.parseInt(name.replace(".jar","")),"missing","environment_archive"));
        }
        for (Path path : Files.list(maps.resolve("env")).sorted().toList()) {
            String id = path.getFileName().toString().replace(".jar", "");
            if (!id.matches("\\d+") || (!filter.isEmpty() && !filter.contains(id))) continue;
            Path topology = maps.resolve("tplg").resolve(id + ".jar");
            if (!Files.isRegularFile(topology)) { missing.add(Map.of("map_id",Integer.parseInt(id),"missing","topology_archive")); continue; }
            int map = Integer.parseInt(id);
            assets.add(Map.of("map_id", map, "environment_sha256", sha(Files.readAllBytes(path)),
                    "topology_sha256", sha(Files.readAllBytes(topology))));
            try (ZipFile env = new ZipFile(path.toFile()); ZipFile geo = new ZipFile(topology.toFile())) {
                for (ZipEntry extra : Collections.list(geo.entries())) {
                    if (extra.getName().matches("-?\\d+_-?\\d+") && env.getEntry(extra.getName())==null)
                        missing.add(Map.of("map_id",map,"chunk",extra.getName(),"missing","environment_chunk"));
                }
                for (ZipEntry entry : Collections.list(env.entries())) {
                    if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                    ZipEntry shape = geo.getEntry(entry.getName());
                    if (shape == null) { missing.add(Map.of("map_id",map,"chunk",entry.getName(),"missing","topology_chunk")); continue; }
                    String phase = "environment_decode";
                    byte[] envBytes = env.getInputStream(entry).readAllBytes();
                    byte[] geoBytes = geo.getInputStream(shape).readAllBytes();
                    Map<String,Object> fact = new LinkedHashMap<>();
                    fact.put("map_id",map); fact.put("chunk",entry.getName());
                    fact.put("environment_header",envBytes[0]&255); fact.put("topology_header",geoBytes[0]&255);
                    fact.put("environment_bytes",envBytes.length); fact.put("topology_bytes",geoBytes.length);
                    fact.put("environment_sha256",sha(envBytes)); fact.put("topology_sha256",sha(geoBytes));
                    manifest.add(fact);
                    try {
                        aoG input = aoG.dx(envBytes); input.aJn();
                        aIl ground = new aIl(); ground.a(input);
                        fact.put("environment_status","decoded"); phase = "topology_decode";
                        aoG topologyInput = aoG.dx(geoBytes);
                        VB chunk = VC.ag(topologyInput.aJn()); chunk.a(topologyInput);
                        fact.put("topology_status","decoded"); phase = "surface_query";
                        chunks++;
                        if (ground.buw() != null) objectCount += ground.buw().length;
                        for (int y=chunk.bbo; y<chunk.bbo+18; y++) for (int x=chunk.bbn; x<chunk.bbn+18; x++) {
                            Vy[] surfaces = Vy.blX(); int count;
                            try { count = chunk.a(x,y,surfaces,0); }
                            catch (RuntimeException error) {
                                fact.put("surface_query_failures",((Number)fact.getOrDefault("surface_query_failures",0)).intValue()+1);
                                errors.add(Map.of("map_id",map,"chunk",entry.getName(),"phase","surface_query",
                                    "x",x,"y",y,"error",error.toString())); continue;
                            }
                            for (int index=0; index<count; index++) {
                                Vy surface = surfaces[index];
                                // Resource targets need not themselves be walkable: native collection approaches adjacent cells.
                                int groundId = ground.U(x,y,surface.bbl);
                                JsonElement references = eligibility.get(Integer.toString(groundId));
                                if (references == null) continue;
                                slots.add(Map.ofEntries(Map.entry("map_id",map),Map.entry("x",x),Map.entry("y",y),Map.entry("z",(int)surface.bbl),
                                        Map.entry("ground_id",groundId),Map.entry("eligible_resource_references",references),
                                        Map.entry("chunk",entry.getName()),Map.entry("environment_chunk_sha256",sha(envBytes)),
                                        Map.entry("walkable",surface.bLD>=0 && !surface.bLf),
                                        Map.entry("evidence_kind","native_suitable_terrain_not_spawn")));
                            }
                        }
                    } catch (Exception error) {
                        if (phase.equals("environment_decode")) {
                            try { aoG probe = aoG.dx(geoBytes); VB nativeChunk=VC.ag(probe.aJn()); nativeChunk.a(probe);
                                fact.put("topology_status","decoded_independently");
                            } catch (RuntimeException topologyError) { fact.put("topology_status","native_decoder_rejected"); fact.put("topology_error",topologyError.toString()); }
                        }
                        fact.put("failed_phase",phase); fact.put("error",error.toString());
                        errors.add(Map.of("map_id",map,"chunk",entry.getName(),"phase",phase,"error",error.toString(),"native_frame",Arrays.toString(error.getStackTrace())));
                    }
                }
            }
        }
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("schema_version",1);
        result.put("official_fixed_spawns_extracted",false);
        result.put("importable_without_distribution_policy",false);
        result.put("decoded_chunks",chunks); result.put("interactive_objects_seen",objectCount);
        result.put("chunk_manifest",manifest); result.put("missing_pairs",missing);
        result.put("assets",assets); result.put("errors",errors); result.put("candidate_surfaces",slots);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Maps="+assets.size()+" chunks="+chunks+" candidates="+slots.size()+" errors="+errors.size());
    }
}
