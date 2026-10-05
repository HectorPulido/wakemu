import java.util.*;import java.nio.file.*;import com.google.gson.GsonBuilder;
/** Exact anv.p height points plus native anc/amX orientations/radius membership. */
public class ProbeNativeConeAreas {
 public static void main(String[] args)throws Exception{
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int height:new int[]{-1,0,1,2,3,4}){
   anv area=new anv();area.p(new int[]{height});
   if(!area.bEm().equals("cone-"+height))throw new AssertionError("Serialized cone height");
   ProbeNativeOrientedAreas.probe(area,rows);
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows)+"\n");
  System.out.println("Native anv cone "+rows.size()+" orientation/radius cases PASS");
 }
}
