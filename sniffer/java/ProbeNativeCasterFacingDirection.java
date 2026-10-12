import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** eNz uses aBn.e(aAS), which adds and keeps diagonals. */
public final class ProbeNativeCasterFacingDirection {
 public static void main(String[] args) throws Exception {
  List<Map<String,Object>> rows=new ArrayList<>();
  for(aAS direction:aAS.values()) for(int x:new int[]{0,Integer.MIN_VALUE,Integer.MAX_VALUE}) {
   if(direction.dyI<0||direction.dyI>7)continue;
   aBn point=new aBn(x,17,(short)-3);
   point.e(direction);
   Map<String,Object> row=new LinkedHashMap<>();
   row.put("direction",direction.dyI);row.put("origin",new int[]{x,17,-3});
   row.put("point",new int[]{point.getX(),point.getY(),point.bdn()});rows.add(row);
  }
  if(rows.size()!=24)throw new AssertionError("Unexpected installed planar population");
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(rows));
  System.out.println("PASS installed eNz aBn.e/aAS direction rows="+rows.size());
 }
}
