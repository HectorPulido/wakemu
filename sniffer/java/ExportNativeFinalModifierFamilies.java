import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Registry-wide faq inheritance, including families not yet implemented. */
public class ExportNativeFinalModifierFamilies {
 public static void main(String[] args)throws Exception {
  Map<Integer,String> families=new TreeMap<>();
  for(Field field:eVi.class.getDeclaredFields())if(field.getType()==eVj.class){
   field.setAccessible(true);eVj entry=(eVj)field.get(null);
   Object runner=entry.bkv();
   if(runner instanceof faq){
    String previous=families.put(entry.d(),runner.getClass().getSimpleName());
    if(previous!=null)throw new IllegalStateException("Duplicate family "+entry.d());
   }
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Installed client eVi prototypes implementing faq", "families",families))+"\n");
  System.out.println("Native faq registry families: "+families);
 }
}
