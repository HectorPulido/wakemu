import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;

/** Offline player exploration topology, separate from published combat geometry. */
public class ExportMiningNavigation {
    record Cell(int x, int y, int z) implements Comparable<Cell> {
        public int compareTo(Cell b) {
            int result = Integer.compare(y, b.y);
            if (result == 0) result = Integer.compare(x, b.x);
            return result == 0 ? Integer.compare(z, b.z) : result;
        }
        int[] array() { return new int[] {x,y,z}; }
    }
    record Column(int x, int y, Vy[] surfaces, int count) {}
    static long key(int x, int y) { return ((long)x << 32) | (y & 0xffffffffL); }
    static String sha(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("map_id output.json candidates.json");
        int map = Integer.parseInt(args[0]);
        Path archivePath = Path.of("client/contents/maps/tplg/" + map + ".jar");
        Map<Long,Column> columns = new LinkedHashMap<>();
        TreeSet<Cell> cells = new TreeSet<>();
        List<Object> surfaceFacts = new ArrayList<>();
        int chunks = 0;
        List<Object> decodeErrors = new ArrayList<>();
        VF.bmq(); VF.bms(); VF.fs(map); VF.a((short)6,(byte)0,(short)4);
        try (ZipFile archive = new ZipFile(archivePath.toFile())) {
            List<? extends ZipEntry> entries = Collections.list(archive.entries());
            entries.sort(Comparator.comparing(ZipEntry::getName));
            for (ZipEntry entry : entries) {
                if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                aoG reader = aoG.dx(archive.getInputStream(entry).readAllBytes());
                VB chunk = VC.ag(reader.aJn());
                try { chunk.a(reader); } catch (RuntimeException error) {
                    decodeErrors.add(Map.of("chunk",entry.getName(),"error",error.toString())); continue;
                }
                VF.a(map,(short)Math.floorDiv(chunk.bbn,18),(short)Math.floorDiv(chunk.bbo,18),(short)0,chunk);
                chunks++;
                for (int y=chunk.bbo; y<chunk.bbo+18; y++) for (int x=chunk.bbn; x<chunk.bbn+18; x++) {
                    Vy[] surfaces = Vy.blX();
                    int count;
                    try { count = chunk.a(x,y,surfaces,0); }
                    catch (RuntimeException error) { decodeErrors.add(Map.of("chunk",entry.getName(),
                        "phase","surface_query","x",x,"y",y,"error",error.toString())); continue; }
                    if (count == 0) continue;
                    if (columns.putIfAbsent(key(x,y),new Column(x,y,surfaces,count)) != null)
                        throw new IllegalStateException("Overlapping native chunks");
                    for (int index=0; index<count; index++) {
                        Vy s = surfaces[index];
                        surfaceFacts.add(Map.of("position",new int[] {x,y,s.bbl},"index",index,
                            "bLD",s.bLD,"bLE",s.bLE,"bLF",s.bLF,"aYX",s.aYX,"bLf",s.bLf));
                        if (s.bLD>=0 && !s.bLf) cells.add(new Cell(x,y,s.bbl));
                    }
                }
            }
        }
        List<int[][]> edges = new ArrayList<>();
        int[][] deltas = {{1,0},{-1,0},{0,1},{0,-1}};
        for (Column from : columns.values()) for (int[] delta : deltas) {
            Column to = columns.get(key(from.x+delta[0],from.y+delta[1]));
            if (to == null) continue;
            for (int i=0; i<from.count; i++) {
                Vy source = from.surfaces[i];
                if (source.bLD<0 || source.bLf) continue;
                // Player biB -> bjo -> big -> eGj; inherited height 6 / type 0 / jump 4.
                Sm movement = new Sm(6,(byte)0,4,true);
                int count;
                try { count = movement.a(i,0,from.count,from.surfaces,0,to.count,to.surfaces); }
                catch (RuntimeException error) { decodeErrors.add(Map.of("phase","movement_query",
                    "x",from.x,"y",from.y,"error",error.toString())); continue; }
                for (int j=0; j<count; j++) {
                    Vy target = to.surfaces[movement.boE[j]];
                    Cell end = new Cell(to.x,to.y,target.bbl);
                    if (!cells.contains(end)) throw new IllegalStateException("Nonwalkable native target");
                    edges.add(new int[][] {new int[] {from.x,from.y,source.bbl},end.array()});
                }
            }
        }
        edges.sort(Comparator.comparing(Arrays::deepToString));
        List<int[]> orderedCells = cells.stream().map(Cell::array).toList();
        Map<String,Object> output = new LinkedHashMap<>();
        output.put("map_id",map); output.put("chunks",chunks);
        output.put("profile","native_world_exploration_4_0_6");
        output.put("profile_authority","biB -> bjo -> big -> eGj; bcK=6, bcL=0, bvz=4; faz.fSR reads those actor methods");
        output.put("topology_sha256",sha(archivePath));
        output.put("client_sha256",sha(Path.of("client/lib/wakfu-client.jar")));
        List<Object> approaches = new ArrayList<>();
        JsonObject evidence = JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();
        for (JsonElement item : evidence.getAsJsonArray("candidate_surfaces")) {
            JsonObject row = item.getAsJsonObject();
            if (row.get("map_id").getAsInt()!=map) continue;
            int x=row.get("x").getAsInt(), y=row.get("y").getAsInt(); short z=row.get("z").getAsShort();
            List<int[]> nativeApproaches = new ArrayList<>();
            try { for (aBn point : VF.a(new aBn(x,y,z),1,fyk.aaa(73),false,
                    point -> fyk.a((short)6,point.bdn(),z,73))) {
                Cell cell = new Cell(point.getX(),point.getY(),point.bdn());
                if (cells.contains(cell)) nativeApproaches.add(cell.array());
            } } catch (RuntimeException error) {
                nativeApproaches.clear();
                decodeErrors.add(Map.of("phase","native_resource_approach",
                    "position",new int[]{x,y,z},"error",error.toString()));
            }
            approaches.add(Map.of("position",new int[]{x,y,z},"approaches",nativeApproaches,
                "ground_id",row.get("ground_id").getAsInt(),
                "eligible_refs",row.getAsJsonArray("eligible_resource_references")));
        }
        output.put("resource_approaches",approaches);
        output.put("decode_errors",decodeErrors);
        output.put("provenance",Map.of("source","installed-client",
            "approach_authority","cWn.gu:VF.a:profession73",
            "topology_sha256",sha(archivePath),"client_sha256",sha(Path.of("client/lib/wakfu-client.jar"))));
        output.put("cells",orderedCells); output.put("edges",edges); output.put("surfaces",surfaceFacts);
        output.put("limits","Static cardinal exploration transitions only; no dynamic obstacle state or fight unlock authority");
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(output)+"\n");
        System.out.println("map="+map+" chunks="+chunks+" cells="+cells.size()+" edges="+edges.size());
    }
}
