import java.util.*;import java.util.zip.*;import java.nio.file.*;import com.google.gson.*;
/** Static original-client Sf rays; dynamic fighter blockers are not included. */
public class ExportCombatLOS {
 static class MapGeometry extends VE {
  final List<VB> chunks=new ArrayList<>();
  final Set<List<Integer>> probes=new LinkedHashSet<>();
  public VB aO(int x,int y){for(VB b:chunks)if(x>=b.bbn&&x<b.bbn+18&&y>=b.bbo&&y<b.bbo+18)return b;return null;}
  public VD aP(int x,int y){return null;}
  public boolean h(int x,int y,short z){probes.add(List.of(x,y));return false;} // Explicitly no dynamic VD obstruction.
 }
 public static void main(String[]args)throws Exception {
  int map=Integer.parseInt(args[0]);
  JsonObject input=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
  List<int[]> cells=new ArrayList<>();for(JsonElement e:input.getAsJsonArray("cells")){JsonArray a=e.getAsJsonArray();cells.add(new int[]{a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()});}
  MapGeometry geometry=new MapGeometry();
  try(ZipFile archive=new ZipFile("client/contents/maps/tplg/"+map+".jar")){for(var e:Collections.list(archive.entries()))if(e.getName().matches("-?\\d+_-?\\d+")){aoG r=aoG.dx(archive.getInputStream(e).readAllBytes());VB b=VC.ag(r.aJn());b.a(r);geometry.chunks.add(b);}}
  // MapGeometry exposes only native static VB; absent dynamic VD is deliberate.
  List<int[]> visible=new ArrayList<>();List<Object> rays=new ArrayList<>();Sf ray=Sf.bfW();ray.a(geometry);
  try{for(int i=0;i<cells.size();i++)for(int j=0;j<cells.size();j++){geometry.probes.clear();int[]s=cells.get(i),t=cells.get(j);ray.k(s[0],s[1],(short)s[2]);ray.l(t[0],t[1],(short)t[2]);if(ray.bfZ()){visible.add(new int[]{i,j});rays.add(List.of(i,j,new ArrayList<>(geometry.probes)));}}}finally{ray.bal();}
  System.out.println(new Gson().toJson(Map.of("map_id",map,"cells",cells,"visible_pairs",visible,"dynamic_probe_cells",rays,"source","Installed Java Sf.bfZ with native VB/Vz topology; no dynamic VD blockers","limits","Static geometry only. Actor/entity height and obstruction policy must be validated separately.")));
 }
}
