import java.util.*;import java.util.zip.*;import java.nio.file.*;import com.google.gson.*;
/** Original Sf/fcr pairs and dynamic probes, not approximate LOS. */
public class ProbeNativeGenericLOS {
 static Map<String,Object> ray(ExportCombatLOS.MapGeometry geometry,int[]s,int[]t){
  geometry.probes.clear();Sf ray=Sf.bfW();ray.a(geometry);ray.k(s[0],s[1],(short)s[2]);ray.l(t[0],t[1],(short)t[2]);
  boolean visible=ray.bfZ();ray.bal();return Map.of("visible",visible,"probes",new ArrayList<>(geometry.probes));
 }
 static class Geometry extends ExportCombatLOS.MapGeometry {
  Set<List<Integer>>blocked=Set.of();
  public boolean h(int x,int y,short z){super.h(x,y,z);return blocked.contains(List.of(x,y));}
 }
 public static void main(String[]args)throws Exception{
  Geometry map=new Geometry();
  try(ZipFile archive=new ZipFile("client/contents/maps/tplg/1134.jar")){for(var entry:Collections.list(archive.entries()))if(entry.getName().matches("-?\\d+_-?\\d+")){
   aoG reader=aoG.dx(archive.getInputStream(entry).readAllBytes());VB chunk=VC.ag(reader.aJn());chunk.a(reader);map.chunks.add(chunk);
  }}
  List<Map<String,Object>>rows=new ArrayList<>();Random random=new Random(7);
  for(int i=0;i<500;i++){
   int[]s={-25+random.nextInt(30),-20+random.nextInt(30),-5+random.nextInt(20)};
   int[]t={s[0]-8+random.nextInt(17),s[1]-8+random.nextInt(17),-5+random.nextInt(20)};
   rows.add(Map.of("source",s,"target",t,"ray",ray(map,s,t)));
  }
  for(int[]t:new int[][]{{-14,-4,0},{-15,-5,-1},{-15,-3,0}})for(int sourceHeight:new int[]{0,6,40})for(int targetHeight:new int[]{6,12,40}){
   int[]s={-15,-3,0};boolean cast=fcr.a(s[0],s[1],(short)s[2],sourceHeight,t[0],t[1],(short)t[2],Math.max(6,(int)(targetHeight*.8f)),map);
   rows.add(Map.of("source",s,"target",t,"source_height",sourceHeight,"target_height",targetHeight,"cast",cast,
     "first",ray(map,new int[]{s[0],s[1],s[2]+(int)(sourceHeight*.8f)},t),
     "second",ray(map,new int[]{s[0],s[1],s[2]+(int)(sourceHeight*.8f)},new int[]{t[0],t[1],t[2]+Math.max(6,(int)(targetHeight*.8f))})));
  }
  int[]s={-14,-10,-1},t={-11,-10,-1};
  for(List<Integer>block:List.of(List.of(-14,-10),List.of(-13,-10),List.of(-11,-10))){
   map.blocked=Set.of(block);
   boolean visible=fcr.a(s[0],s[1],(short)s[2],6,t[0],t[1],(short)t[2],6,map);
   rows.add(Map.of("source",s,"target",t,"source_height",6,"target_height",6,"blockers",List.of(block),"cast",visible));
  }
  Files.writeString(Path.of(args[0]),new Gson().toJson(Map.of("map_id",1134,"rows",rows)));
  System.out.println("Native Sf/fcr cases="+rows.size());
 }
}
