import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Native eXs prototypes and their exact element/value modes. */
public class ExportNativeHealingRegistry {
 public static void main(String[] args)throws Exception {
  Map<Integer,Object> rows=new TreeMap<>();
  Field element=eXs.class.getDeclaredField("rDs"),mode=eXs.class.getDeclaredField("rDt");
  element.setAccessible(true);mode.setAccessible(true);
  for(Field field:eVi.class.getDeclaredFields())if(field.getType()==eVj.class){
   field.setAccessible(true);eVj entry=(eVj)field.get(null);Object runner=entry.bkv();
   if(runner instanceof eXs){
    eVg value=(eVg)element.get(runner);Object policy=mode.get(runner);
    Map<String,Object> row=new LinkedHashMap<>();row.put("runner",runner.getClass().getSimpleName());
    row.put("event_id",value==null?null:value.fLG());row.put("element_id",value==null?null:value.aKg());row.put("element",value==null?null:value.name());
    row.put("value_mode",policy==null?null:policy.toString());rows.put(entry.d(),row);
   }
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(rows)+"\n");
  System.out.println("Native healing registry: "+rows);
 }
}
