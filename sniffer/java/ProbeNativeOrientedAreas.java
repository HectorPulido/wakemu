import java.util.*;import java.nio.file.*;import com.google.gson.GsonBuilder;
/** Native anc/amX enumerated geometry, including coincident caster/center facing. */
public class ProbeNativeOrientedAreas {
 public static void main(String[]args)throws Exception{
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int[] params:new int[][]{{0,2},{1,2},{2,3}}){anI area=new anI();area.p(params);probe(area,rows);}
  for(int[] params:new int[][]{{0,0},{1,2},{2,3}}){anJ area=new anJ();area.p(params);probe(area,rows);}
  for(int[] params:new int[][]{{0,0},{1,0,0,1,0,-1},{-2,1,0,0,2,-1},{1,0,1,0}}){anE area=new anE();area.p(params);probe(area,rows);}
  for(int[] params:new int[][]{{3,3},{2,4},{3,5}}){anG area=new anG();area.p(params);probe(area,rows);}
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows));
  System.out.println("Native oriented areas "+rows.size()+" cases: enumeration/membership and Z-invariance PASS");
 }
 static void probe(anc area,List<Map<String,Object>> rows){
  for(int[] vector:new int[][]{{1,0},{0,1},{-1,0},{0,-1},{1,1},{-1,1},{-1,-1},{1,-1},{5,2},{2,5},{0,0}}){
   for(aAS fallback:vector[0]==0&&vector[1]==0?aAS.dyH:new aAS[]{aAS.dyA}){
    if(fallback.wp()<0||fallback.wp()>7)continue;
    List<List<Integer>> cells=new ArrayList<>();
    for(int[] cell:area.b(0,0,(short)9,-vector[0],-vector[1],(short)-5,fallback))cells.add(List.of(cell[0],cell[1]));
    Set<List<Integer>> unique=new HashSet<>(cells);
    List<List<Integer>> membership=new ArrayList<>();
    for(int x=-6;x<=6;x++)for(int y=-6;y<=6;y++){
     boolean actual=area.a(0,0,(short)2,-vector[0],-vector[1],(short)-9,fallback,x,y,(short)99);
     if(actual)membership.add(List.of(x,y));
     if((vector[0]!=0||vector[1]!=0||fallback.dyJ==0||fallback.dyK==0)&&actual!=unique.contains(List.of(x,y)))throw new AssertionError("Native cardinal area membership/enumeration "+area.bEm()+" vector="+Arrays.toString(vector)+" fallback="+fallback+" at="+x+","+y+" cells="+cells);
    }
    Map<String,Object> row=new TreeMap<>();row.put("class",area.getClass().getName());row.put("native",area.bEm());
    row.put("native_area_points",area.bEl());row.put("vector",vector);row.put("fallback_direction",fallback.wp());row.put("fallback_vector",List.of(fallback.dyJ,fallback.dyK));row.put("cells",cells);row.put("membership",membership);
    Map<Integer,List<List<Integer>>> radii=new TreeMap<>();
    for(byte radius:new byte[]{1,2}){List<List<Integer>> expanded=new ArrayList<>();
     for(int x=-6;x<=6;x++)for(int y=-6;y<=6;y++)if(area.b(0,0,(short)2,-vector[0],-vector[1],(short)-9,fallback,x,y,(short)99,radius))expanded.add(List.of(x,y));
     radii.put((int)radius,expanded);
    }
    row.put("radius_memberships",radii);rows.add(row);
   }
  }
  System.out.println(area.getClass().getName()+"/"+area.bEm()+" raw="+area.bEl().stream().map(Arrays::toString).toList());
 }
}
