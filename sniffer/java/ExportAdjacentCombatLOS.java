import java.util.*;import java.util.zip.*;import java.nio.file.*;import java.io.*;import com.google.gson.*;
/** Exact native Sf rays for cardinal neighbors on every exported surface. */
public class ExportAdjacentCombatLOS {
 static class Geometry extends ExportCombatLOS.MapGeometry {
  final Map<Long,VB> columns=new HashMap<>();
  public VB aO(int x,int y){return columns.get(((long)x<<32)^(y&0xffffffffL));}
 }
 static void export(int map,Path input,Path output)throws Exception{
  JsonObject data;try(InputStream file=Files.newInputStream(input);InputStream decoded=input.toString().endsWith(".gz")?new GZIPInputStream(file):file;Reader reader=new InputStreamReader(decoded)){data=JsonParser.parseReader(reader).getAsJsonObject();}
  List<int[]>cells=new ArrayList<>();Map<Long,List<Integer>>columns=new HashMap<>();
  for(JsonElement e:data.getAsJsonArray("cells")){JsonArray a=e.getAsJsonArray();int[]c={a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()};int id=cells.size();cells.add(c);columns.computeIfAbsent(((long)c[0]<<32)^(c[1]&0xffffffffL),k->new ArrayList<>()).add(id);}
  Geometry geometry=new Geometry();try(ZipFile archive=new ZipFile("client/contents/maps/tplg/"+map+".jar")){for(var e:Collections.list(archive.entries()))if(e.getName().matches("-?\\d+_-?\\d+")){aoG r=aoG.dx(archive.getInputStream(e).readAllBytes());VB b=VC.ag(r.aJn());b.a(r);geometry.chunks.add(b);for(int x=b.bbn;x<b.bbn+18;x++)for(int y=b.bbo;y<b.bbo+18;y++)geometry.columns.put(((long)x<<32)^(y&0xffffffffL),b);}}
  List<int[]>visible=new ArrayList<>();List<Object>rays=new ArrayList<>();Sf ray=Sf.bfW();ray.a(geometry);
  try{for(int i=0;i<cells.size();i++){int[]s=cells.get(i);for(int[]d:new int[][]{{1,0},{-1,0},{0,1},{0,-1}}){int x=s[0]+d[0],y=s[1]+d[1];for(int j:columns.getOrDefault(((long)x<<32)^(y&0xffffffffL),List.of())){int[]t=cells.get(j);geometry.probes.clear();ray.k(s[0],s[1],(short)s[2]);ray.l(t[0],t[1],(short)t[2]);if(ray.bfZ()){visible.add(new int[]{i,j});rays.add(List.of(i,j,new ArrayList<>(geometry.probes)));}}}}}finally{ray.bal();}
  Files.createDirectories(output.getParent());try(OutputStream file=Files.newOutputStream(output);GZIPOutputStream gz=new GZIPOutputStream(file);Writer writer=new OutputStreamWriter(gz)){new Gson().toJson(Map.of("map_id",map,"cells",cells,"visible_pairs",visible,"dynamic_probe_cells",rays,"scope","cardinal-adjacent-only","source","Installed Sf.bfZ native static VB/Vz; every exported altitude, no guessed adjacency or dynamic VD blockers"),writer);}
  System.out.println(map+" cells="+cells.size()+" visible="+visible.size());
 }
 public static void main(String[]args)throws Exception{
  if(args.length==3){export(Integer.parseInt(args[0]),Path.of(args[1]),Path.of(args[2]));return;}
  Path directory=Path.of(args[0]),destination=Path.of(args[1]);JsonObject index=JsonParser.parseString(Files.readString(directory.resolve("index.json"))).getAsJsonObject();
  for(JsonElement e:index.getAsJsonArray("maps")){JsonObject m=e.getAsJsonObject();if(!m.has("file")||m.get("file").isJsonNull())continue;int map=m.get("map_id").getAsInt();Path input=directory.resolve(m.get("file").getAsString());if(!Files.exists(input))continue;try{export(map,input,destination.resolve(map+".json.gz"));}catch(Throwable failure){System.err.println("FAILED "+map+" "+failure);}}
 }
}
