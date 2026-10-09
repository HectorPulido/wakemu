import java.lang.reflect.*;import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
public class ExportNativeMaximumEvents {
 public static void main(String[]args)throws Exception {
  Map<String,Object> effects=new TreeMap<>();
  for(Field field:eVi.class.getDeclaredFields()){
   if(field.getType()!=eVj.class||!Modifier.isStatic(field.getModifiers()))continue;
   field.setAccessible(true);eVj entry=(eVj)field.get(null);
   if(entry==null||!Set.of(20,31,41,191).contains(entry.d()))continue;
   if(!(entry.bkv() instanceof eWN runner))throw new AssertionError("not eWN");
   runner.bbx();PC stat=runner.fNI();
   effects.put(Integer.toString(entry.d()),Map.of("runner",runner.getClass().getName(),"events",runner.bbw().stream().boxed().toList(),"fixed_stat_id",stat.aKg()&255,"bbA",runner.bbA(),"bbB",runner.bbB()));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Actual eVi eWN prototypes: bbx events/fixed PC/registration guards", "effects",effects)));
  System.out.println(effects);
 }
}
