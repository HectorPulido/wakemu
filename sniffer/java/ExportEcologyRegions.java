import java.nio.file.*;import java.util.*;import com.google.gson.*;
public class ExportEcologyRegions{
 static List<Object> families(Vr[] input){List<Object> out=new ArrayList<>();for(Vr r:input)out.add(Map.of("family_id",r.bKP,"parameter_bKQ",r.bKQ,"parameter_bKR",r.bKR));return out;}
 public static void main(String[] args)throws Exception{
 cdH.bla();cdH.exY().dW("jar:file:"+Path.of("client/contents/maps/data.jar").toAbsolutePath()+"!/worlds.lib");
 List<Object> maps=new ArrayList<>();for(cdI m:cdH.exY().eya()){List<Object> regions=new ArrayList<>();for(cdJ r:m.lVI.valueCollection()){Map<String,Object> row=new LinkedHashMap<>();row.put("region_id",r.eyj());row.put("monster_families",families(r.eyl().bKS));row.put("plant_families",families(r.eyk().bKV));row.put("monster_capacity",r.eyl().bKT);row.put("plant_capacity",r.eyk().bKW);List<Object> polygons=new ArrayList<>();for(cdK p:r.eym()){Map<String,Object> poly=new LinkedHashMap<>();for(String n:new String[]{"lVP","lVQ","lVR"}){var f=cdK.class.getDeclaredField(n);f.setAccessible(true);poly.put(n,f.get(p));}polygons.add(poly);}row.put("native_spawn_definitions",polygons);regions.add(row);}maps.add(Map.of("map_id",m.lVl,"regions",regions));}
 Files.writeString(Path.of("server/protocol/ecology-regions.json"),new Gson().toJson(maps));System.out.println("Maps "+maps.size());}}
