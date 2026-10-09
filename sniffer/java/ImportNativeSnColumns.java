import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;

/** Pin and validate every native physical map before publishing an offline catalog. */
public class ImportNativeSnColumns {
    static int integer(JsonElement value, int lower, int upper) {
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber())
            throw new IllegalArgumentException("Noninteger native field");
        String raw=value.getAsString();
        if (!raw.matches("-?\\d+")) throw new IllegalArgumentException("Noninteger native field");
        int result=Integer.parseInt(raw);
        if(result<lower||result>upper)throw new IllegalArgumentException("Signed native field out of bounds");
        return result;
    }
    public static void main(String[] args) throws Exception {
        Path input=Path.of(args[0]), output=Path.of(args[1]), topology=Path.of(args[2]);
        String pin=args[3];
        Path manifestPath=input.resolve("manifest.json");
        if(!ExportNativeSnColumns.sha(manifestPath).equals(pin))throw new IOException("Private bulk manifest pin mismatch");
        JsonObject manifest=JsonParser.parseString(Files.readString(manifestPath)).getAsJsonObject();
        if(!manifest.get("schema").getAsString().equals("native-Sn-Vy-bulk-v1"))throw new IOException("Wrong physical bulk schema");
        for(var entry:manifest.getAsJsonObject("sources_sha256").entrySet())
            if(!ExportNativeSnColumns.sha(Path.of(entry.getKey())).equals(entry.getValue().getAsString()))
                throw new IOException("Original-client library changed: "+entry.getKey());
        if(Files.exists(output))throw new IOException("Refusing to overwrite published physical catalog");
        Path staging=output.resolveSibling(output.getFileName()+".importing");
        Files.createDirectories(staging);
        int exported=0,failed=0; long totalColumns=0,totalSurfaces=0;
        Set<Integer> identities=new HashSet<>();
        for(JsonElement element:manifest.getAsJsonArray("maps")) {
            JsonObject row=element.getAsJsonObject();
            if(!row.get("status").getAsString().equals("exported")) {
                failed++;
                Path original=Path.of(row.get("map").getAsString());
                if(!ExportNativeSnColumns.sha(original).equals(row.get("source_sha256").getAsString()))
                    throw new IOException("Failed native map source changed");
                continue;
            }
            int id=integer(row.get("map_id"),1,Integer.MAX_VALUE);
            if(!identities.add(id))throw new IOException("Duplicate map identity");
            Path source=input.resolve(id+".json");
            String sourceHash=row.get("source_sha256").getAsString();
            if(!ExportNativeSnColumns.sha(topology.resolve(id+".jar")).equals(sourceHash)
               || !ExportNativeSnColumns.sha(source).equals(row.get("output_sha256").getAsString()))
                throw new IOException("Native physical source/output changed for "+id);
            JsonObject data;
            try(Reader reader=new InputStreamReader(Files.newInputStream(source), java.nio.charset.StandardCharsets.UTF_8)) {
                data=JsonParser.parseReader(reader).getAsJsonObject();
            }
            if(!data.get("schema").getAsString().equals("native-Sn-Vy-columns-v1")
               ||integer(data.get("map_id"),1,Integer.MAX_VALUE)!=id
               ||!data.get("source_sha256").getAsString().equals(sourceHash))throw new IOException("Physical map provenance mismatch");
            long columns=0,surfaces=0; Set<String> occupied=new HashSet<>();
            for(JsonElement chunkElement:data.getAsJsonArray("chunks")) {
                JsonObject chunk=chunkElement.getAsJsonObject();
                int x=integer(chunk.get("x"),Integer.MIN_VALUE,Integer.MAX_VALUE-18);
                int y=integer(chunk.get("y"),Integer.MIN_VALUE,Integer.MAX_VALUE-18);
                if(integer(chunk.get("width"),18,18)!=18||integer(chunk.get("height"),18,18)!=18)
                    throw new IOException("Wrong native chunk bounds");
                for(int cy=y;cy<y+18;cy++)for(int cx=x;cx<x+18;cx++)
                    if(!occupied.add(cx+","+cy))throw new IOException("Overlapping native chunk");
                Set<String> seen=new HashSet<>();
                for(JsonElement columnElement:chunk.getAsJsonArray("columns")) {
                    JsonArray column=columnElement.getAsJsonArray();
                    if(column.size()!=3)throw new IOException("Wrong physical column shape");
                    int cx=integer(column.get(0),x,x+17),cy=integer(column.get(1),y,y+17);
                    if(!seen.add(cx+","+cy))throw new IOException("Repeated physical column");
                    columns++;
                    for(JsonElement surfaceElement:column.get(2).getAsJsonArray()) {
                        JsonArray surface=surfaceElement.getAsJsonArray();
                        if(surface.size()!=6)throw new IOException("Incomplete physical surface");
                        integer(surface.get(0),-32768,32767); integer(surface.get(1),-128,127);
                        integer(surface.get(2),-128,127); integer(surface.get(3),-32768,32767);
                        integer(surface.get(4),-128,127);
                        if(!surface.get(5).isJsonPrimitive()||!surface.get(5).getAsJsonPrimitive().isBoolean())
                            throw new IOException("Invalid native physical boolean");
                        surfaces++;
                    }
                }
            }
            if(columns!=row.get("columns").getAsLong()||surfaces!=row.get("surfaces").getAsLong())
                throw new IOException("Physical map count mismatch");
            Files.copy(source,staging.resolve(source.getFileName()),StandardCopyOption.REPLACE_EXISTING);
            exported++;totalColumns+=columns;totalSurfaces+=surfaces;
        }
        if(exported!=934||failed!=27)throw new IOException("Pinned bulk completeness mismatch");
        Files.copy(manifestPath,staging.resolve("manifest.json"),StandardCopyOption.REPLACE_EXISTING);
        Files.writeString(staging.resolve("publication.json"),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of(
            "schema","native-Sn-publication-v1","bulk_manifest_sha256",pin,"exported",exported,"native_failures",failed,
            "columns",totalColumns,"surfaces",totalSurfaces,"importer_sha256",ExportNativeSnColumns.sha(Path.of("sniffer/java/ImportNativeSnColumns.java"))))+"\n");
        Files.move(staging,output,StandardCopyOption.ATOMIC_MOVE);
        System.out.println("PUBLISHED maps="+exported+" native_failures="+failed+" columns="+totalColumns+" surfaces="+totalSurfaces);
    }
}
