import java.util.*;import java.nio.file.*;import com.google.gson.GsonBuilder;
/** Original anC.p plus inherited anc/amX orientations and physical radii. */
public class ProbeNativeInverseConeAreas {
 public static void main(String[] args)throws Exception{
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int height:new int[]{-1,0,1,2,3,4}){
   anC area=new anC();area.p(new int[]{height});
   if(!area.bEm().equals("cone_inv-"+height))throw new AssertionError("Native inverse cone name");
   ProbeNativeOrientedAreas.probe(area,rows);
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows)+"\n");
  System.out.println("Native inverse cone "+rows.size()+" orientation/radius cases PASS");
 }
}
