import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Exact ordered XY metadata; anE.bEm deliberately omits its point list. */
public class ExportNativePointAreas {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Integer> refs=new ArrayList<>();
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw row){refs.add(row.aZE());}});
  Map<String,Object> rows=new TreeMap<>();
  for(int ref:refs){eVn effect=bcA.dcX().AH(ref);anc area=effect.aZP();
   if(!(area instanceof anE)&&!(area instanceof anJ))continue;
   List<List<Integer>> points=new ArrayList<>();for(int[] point:area.bEl())points.add(List.of(point[0],point[1]));
   rows.put(Integer.toString(ref),Map.of("area_class",area.getClass().getName(),"area_native",area.bEm(),"native_area_points",points,"effect_class",effect.awM()));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows));
  System.out.println("Exported native point areas "+rows.size());
 }
}
