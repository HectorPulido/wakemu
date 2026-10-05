import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Original eWQ/eWR bbx/ffw events; dynamic PC stays absent until C. */
public final class ExportNativeCurrentStatEvents {
 public static void main(String[]args)throws Exception {
  Map<String,Object> effects=new TreeMap<>();
  for(Field f:eVi.class.getDeclaredFields()){
   if(f.getType()!=eVj.class||!Modifier.isStatic(f.getModifiers()))continue;
   f.setAccessible(true);eVj entry=(eVj)f.get(null);if(entry==null)continue;
   Object prototype=entry.bkv();if(!(prototype instanceof eWQ||prototype instanceof eWR))continue;
   eWW runner=(eWW)prototype;runner.bbx();
   Map<String,Object> row=new LinkedHashMap<>();row.put("runner",runner.getClass().getName());
   row.put("events",runner.bbw().stream().boxed().toList());
   PC stat=runner.fNI();row.put("fixed_stat_id",stat==null?null:stat.aKg()&255);
   effects.put(Integer.toString(entry.d()),row);
  }
  Map<String,Object> out=new LinkedHashMap<>();out.put("source","Original eVi prototypes, eWQ/eWR.bbx then Qe.bbw without PK extras; dynamic PC absent before C");out.put("effects",effects);
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(out));
  System.out.println("PASS exported "+effects.size()+" current-stat event prototypes");
 }
}
