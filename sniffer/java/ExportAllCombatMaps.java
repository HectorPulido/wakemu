import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
import com.google.gson.stream.JsonWriter;

/** Offline native VB/Vy/Sm geometry, enumerating actual chunks, never a global bounding box. */
public class ExportAllCombatMaps {
    record Point(int x,int y,int z) implements Comparable<Point> {
        public int compareTo(Point other) {int c=Integer.compare(y,other.y);if(c==0)c=Integer.compare(x,other.x);return c==0?Integer.compare(z,other.z):c;}
    }
    record Edge(Point from,Point to) {}
    record Column(int x,int y,Vy[] surfaces,int count) {}
    static long key(int x,int y){return ((long)x<<32)|(y&0xffffffffL);}
    static String sha(Path path)throws Exception {
        MessageDigest hash=MessageDigest.getInstance("SHA-256");
        try(InputStream in=Files.newInputStream(path)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)hash.update(buffer,0,n);}
        return HexFormat.of().formatHex(hash.digest());
    }
    static void point(JsonWriter json,Point p)throws IOException {json.beginArray().value(p.x).value(p.y).value(p.z).endArray();}
    static Map<String,Object> export(Path archivePath,Path destination)throws Exception {
        int map=Integer.parseInt(archivePath.getFileName().toString().replace(".jar",""));
        long start=System.nanoTime();int chunks=0;
        Map<Long,Column> columns=new HashMap<>();Set<Point> cells=new TreeSet<>();
        try(ZipFile archive=new ZipFile(archivePath.toFile())) {
            List<? extends ZipEntry> entries=Collections.list(archive.entries());entries.sort(Comparator.comparing(ZipEntry::getName));
            for(ZipEntry entry:entries) {
                if(!entry.getName().matches("-?\\d+_-?\\d+"))continue;
                aoG reader=aoG.dx(archive.getInputStream(entry).readAllBytes());
                VB chunk;
                try {chunk=VC.ag(reader.aJn());chunk.a(reader);}catch(Exception error){throw new IOException("Chunk "+entry.getName()+" decode failed",error);}
                chunks++;
                for(int y=chunk.bbo;y<chunk.bbo+18;y++)for(int x=chunk.bbn;x<chunk.bbn+18;x++) {
                    Vy[] surfaces=Vy.blX();int count=chunk.a(x,y,surfaces,0);
                    if(count==0)continue;
                    Column column=new Column(x,y,surfaces,count);
                    Column previous=columns.putIfAbsent(key(x,y),column);
                    if(previous!=null)throw new IllegalStateException("Overlapping native chunks at "+x+","+y);
                    for(int i=0;i<count;i++)if(surfaces[i].bLD>=0)cells.add(new Point(x,y,surfaces[i].bbl));
                }
            }
        }
        Set<Edge> edges=new HashSet<>();
        int[][] deltas={{1,0},{-1,0},{0,1},{0,-1}};
        for(Column from:columns.values())for(int[]delta:deltas) {
            Column to=columns.get(key(from.x+delta[0],from.y+delta[1]));if(to==null)continue;
            for(int i=0;i<from.count;i++) {
                if(from.surfaces[i].bLD<0)continue;
                // Preserve the exact audited native movement constructor and source surface index.
                Sm movement=new Sm(3,(byte)0,2,true);
                int count=movement.a(i,0,from.count,from.surfaces,0,to.count,to.surfaces);
                Point source=new Point(from.x,from.y,from.surfaces[i].bbl);
                for(int j=0;j<count;j++) {
                    Vy surface=to.surfaces[movement.boE[j]];Point target=new Point(to.x,to.y,surface.bbl);
                    if(!cells.contains(target))throw new IllegalStateException("Native movement target is not walkable: "+target);
                    edges.add(new Edge(source,target));
                }
            }
        }
        List<Edge> ordered=new ArrayList<>(edges);ordered.sort(Comparator.comparing(Edge::from).thenComparing(Edge::to));
        Path output=destination.resolve(map+".json.gz"),temporary=destination.resolve(map+".json.gz.tmp");
        try(JsonWriter json=new JsonWriter(new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(temporary)), java.nio.charset.StandardCharsets.UTF_8))) {
            json.beginObject().name("map_id").value(map).name("source").value("Installed VB/Vy walkable surfaces and Sm(3,0,2,true) cardinal transitions; all native 18x18 chunks")
                .name("limits").value("Static movement geometry only; dynamic actors, criteria, LOS and fight placement policies are not inferred")
                .name("cells").beginArray();for(Point p:cells)point(json,p);json.endArray().name("edges").beginArray();
            for(Edge edge:ordered){json.beginArray();point(json,edge.from);point(json,edge.to);json.endArray();}
            json.endArray().endObject();
        }
        Files.move(temporary,output,StandardCopyOption.REPLACE_EXISTING);
        Map<String,Object> result=new LinkedHashMap<>();result.put("map_id",map);result.put("status","exported");result.put("chunks",chunks);result.put("columns",columns.size());
        result.put("cells",cells.size());result.put("edges",edges.size());result.put("bytes",Files.size(output));result.put("file",output.getFileName().toString());
        result.put("topology_sha256",sha(archivePath));result.put("geometry_sha256",sha(output));result.put("elapsed_ms",(System.nanoTime()-start)/1000000);return result;
    }
    public static void main(String[]args)throws Exception {
        Path input=Path.of(args.length>0?args[0]:"client/contents/maps/tplg"),output=Path.of(args.length>1?args[1]:"server/protocol/combat-maps");
        Files.createDirectories(output);List<Path> archives;
        try(var files=Files.list(input)){archives=files.filter(p->p.getFileName().toString().matches("\\d+\\.jar")).sorted(Comparator.comparingInt(p->Integer.parseInt(p.getFileName().toString().replace(".jar","")))).toList();}
        String clientHash=sha(Path.of("client/lib/wakfu-client.jar"));
        List<Map<String,Object>> rows=new ArrayList<>();Gson gson=new GsonBuilder().setPrettyPrinting().create();int failures=0,total=0;
        for(Path archive:archives){Map<String,Object> row;
            try{row=export(archive,output);}catch(Throwable error){if(error instanceof VirtualMachineError)throw error;row=new LinkedHashMap<>();row.put("map_id",Integer.parseInt(archive.getFileName().toString().replace(".jar","")));row.put("status","error");row.put("error",error.toString());
                StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));row.put("error_trace",trace.toString());
                row.put("topology_sha256",sha(archive));failures++;}
            rows.add(row);total++;
            // Checkpoint after each map makes progress and failures reviewable while exporting.
            Files.writeString(output.resolve("index.json"),gson.toJson(Map.of("maps",rows,"total_archives",archives.size(),"completed",total,"errors",failures,"generator","ExportAllCombatMaps","client_jar_sha256",clientHash)));
            if(total%25==0||row.get("status").equals("error"))System.out.println("maps="+total+"/"+archives.size()+" errors="+failures+" last="+row.get("map_id"));
        }
        System.out.println("COMPLETE maps="+total+" errors="+failures);
    }
}
