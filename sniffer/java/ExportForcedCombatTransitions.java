import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
/** faz.B: preserve Sm's FIRST destination, including explicit blocked queries. */
public class ExportForcedCombatTransitions {
 record Column(int x,int y,Vy[] surfaces,int count) {}
 static long key(int x,int y){return ((long)x<<32)|(y&0xffffffffL);}
 public static void main(String[] args)throws Exception {
  int map=Integer.parseInt(args[0]); Path output=Path.of(args[1]);
  Map<Long,Column> columns=new TreeMap<>();
  Path archivePath=Path.of("client/contents/maps/tplg/"+map+".jar");
  try(ZipFile zip=new ZipFile(archivePath.toFile())) {
   for(ZipEntry entry:Collections.list(zip.entries())) {
    if(!entry.getName().matches("-?\\d+_-?\\d+"))continue;
    aoG reader=aoG.dx(zip.getInputStream(entry).readAllBytes()); VB chunk=VC.ag(reader.aJn());chunk.a(reader);
    for(int y=chunk.bbo;y<chunk.bbo+18;y++)for(int x=chunk.bbn;x<chunk.bbn+18;x++) {
     Vy[] surfaces=Vy.blX();int count=chunk.a(x,y,surfaces,0);
     if(count>0 && columns.putIfAbsent(key(x,y),new Column(x,y,surfaces,count))!=null)throw new IllegalStateException("Overlapping columns");
    }
   }
  }
  Files.createDirectories(output);
  // All native ordinary breed heights; no radius>0 support is asserted here.
  for(int height=1;height<=25;height++) {
   List<Object> rows=new ArrayList<>();
   for(Column from:columns.values())for(int i=0;i<from.count;i++) {
    Vy src=from.surfaces[i];if(src.bLD<0)continue;
    for(int[] delta:new int[][]{{1,0},{-1,0},{0,1},{0,-1}}) {
     int x=from.x+delta[0],y=from.y+delta[1];Column to=columns.get(key(x,y));Object destination=null;
     if(to!=null) {
      Sm policy=new Sm(height,(byte)0,4,true);
      int count=policy.a(i,0,from.count,from.surfaces,0,to.count,to.surfaces);
      if(count>0)destination=new int[]{x,y,to.surfaces[policy.boE[0]].bbl};
     }
     rows.add(Arrays.asList(new int[]{from.x,from.y,src.bbl},new int[]{x,y},destination));
    }
   }
   try(Writer writer=new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(output.resolve(map+"-h"+height+"-r0-j4.json.gz"))),java.nio.charset.StandardCharsets.UTF_8)) {
    new Gson().toJson(Map.of("map_id",map,"height",height,"radius",0,"jump",4,"source","Native faz.B first Sm.boE destination; Sm(height,0,4,true); all VB/Vy columns", "archive_sha256",ExportAllCombatMaps.sha(archivePath),"rows",rows),writer);
   }
  }
  System.out.println("Exported forced policies for map "+map+" to "+output);
 }
}
