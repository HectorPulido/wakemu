import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
import com.google.gson.stream.JsonWriter;
/** Native faz.B priority; compact all heights without constructing 25 tables. */
public class ExportCompactForcedTransitions {
 record Column(int x,int y,Vy[] surfaces,int count) {}
 static long key(int x,int y){return ((long)x<<32)|(y&0xffffffffL);}
 static Map<String,Object> export(int map,Path directory)throws Exception {
  long began=System.nanoTime();Map<Long,Column> columns=new TreeMap<>();
  Path archivePath=Path.of("client/contents/maps/tplg/"+map+".jar");
  int chunks=0;
  try(ZipFile zip=new ZipFile(archivePath.toFile())) {
   List<? extends ZipEntry> entries=Collections.list(zip.entries());entries.sort(Comparator.comparing(ZipEntry::getName));
   for(ZipEntry entry:entries) {
    if(!entry.getName().matches("-?\\d+_-?\\d+"))continue;
    aoG reader=aoG.dx(zip.getInputStream(entry).readAllBytes());VB chunk=VC.ag(reader.aJn());chunk.a(reader);chunks++;
    for(int y=chunk.bbo;y<chunk.bbo+18;y++)for(int x=chunk.bbn;x<chunk.bbn+18;x++) {
     Vy[] surfaces=Vy.blX();int count=chunk.a(x,y,surfaces,0);
     if(count>0 && columns.putIfAbsent(key(x,y),new Column(x,y,surfaces,count))!=null)throw new IllegalStateException("Overlapping native columns");
    }
   }
  }
  Files.createDirectories(directory);Path output=directory.resolve(map+".json.gz"),temporary=directory.resolve(map+".json.gz.tmp");
  int queries=0,variants=0;
  try(JsonWriter json=new JsonWriter(new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(temporary)),java.nio.charset.StandardCharsets.UTF_8))) {
   json.setSerializeNulls(true);
   json.beginObject().name("schema_version").value(1).name("map_id").value(map).name("radius").value(0).name("jump").value(4)
    .name("heights").beginArray().value(1).value(25).endArray()
    .name("archive_sha256").value(ExportAllCombatMaps.sha(archivePath))
    .name("source").value("Native faz.B FIRST Sm.boE destination; Sm(height,0,4,true), all VB/Vy columns; height masks retain blocked queries and surface priority")
    .name("rows").beginArray();
   Sm[] policies=new Sm[25];for(int height=1;height<=25;height++)policies[height-1]=new Sm(height,(byte)0,4,true);
   for(Column from:columns.values())for(int i=0;i<from.count;i++) {
    Vy src=from.surfaces[i];if(src.bLD<0)continue;
    for(int[] delta:new int[][]{{1,0},{-1,0},{0,1},{0,-1}}) {
     int x=from.x+delta[0],y=from.y+delta[1];Column to=columns.get(key(x,y));
     Map<Integer,Integer> masks=new LinkedHashMap<>();
     for(int height=1;height<=25;height++) {
      Integer z=null;
      if(to!=null) {
       Sm policy=policies[height-1];int count=policy.a(i,0,from.count,from.surfaces,0,to.count,to.surfaces);
       if(count>0)z=(int)to.surfaces[policy.boE[0]].bbl;
      }
      masks.merge(z,1<<(height-1),(a,b)->a|b);
     }
     json.beginArray().value(from.x).value(from.y).value(src.bbl).value(delta[0]).value(delta[1]).beginArray();
     for(var choice:masks.entrySet()){json.beginArray().value(choice.getValue());if(choice.getKey()==null)json.nullValue();else json.value(choice.getKey());json.endArray();}
     json.endArray().endArray();queries++;variants+=masks.size();
    }
   }
   json.endArray().endObject();
  } catch(Exception error) {Files.deleteIfExists(temporary);throw error;}
  Files.move(temporary,output,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
  return Map.of("map_id",map,"status","exported","queries",queries,"distinct_results",variants,"chunks",chunks,"bytes",Files.size(output),"elapsed_ms",(System.nanoTime()-began)/1000000,"file",output.getFileName().toString());
 }
 public static void main(String[]args)throws Exception {
  if(args.length<3)throw new IllegalArgumentException("output-directory checkpoint-jsonl map-id ...");
  Path directory=Path.of(args[0]),checkpoint=Path.of(args[1]);Files.createDirectories(checkpoint.getParent());Gson gson=new Gson();
  try(BufferedWriter progress=Files.newBufferedWriter(checkpoint,StandardOpenOption.CREATE,StandardOpenOption.APPEND)) {
   for(int n=2;n<args.length;n++) {
    int map=Integer.parseInt(args[n]);Map<String,Object> result;
    try {result=export(map,directory);}catch(Exception error){result=Map.of("map_id",map,"status","error","exception_type",error.getClass().getName(),"reason",String.valueOf(error.getMessage()));}
    String line=gson.toJson(result);progress.write(line);progress.newLine();progress.flush();System.out.println(line);
   }
  }
 }
}
