import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
/** Exports original bgV maps, without substituting state levels for characteristic values. */
public class ExportNativeBreedHudResources {
 public static void main(String[] args)throws Exception {
  Field f=bgV.class.getDeclaredField("hXy");f.setAccessible(true);
  Map<eGE,ffw> stats=(Map<eGE,ffw>)f.get(null);
  Field g=bgV.class.getDeclaredField("hXz");g.setAccessible(true);
  Map<eGE,Integer> states=(Map<eGE,Integer>)g.get(null);
  List<Object> rows=new ArrayList<>();
  for(eGE breed:eGE.values()) {Map<String,Object> r=new LinkedHashMap<>();r.put("breed",(int)breed.aXA());r.put("native_breed_name",breed.name());ffw s=stats.get(breed);r.put("characteristic_id",s==null?null:(int)s.aKg());r.put("characteristic_native_name",s==null?null:s.name());r.put("description_key",s==null?null:s.aYi());r.put("popup_state_reference",states.get(breed));rows.add(r);}
  System.out.println(new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(Map.of("source","Original bgV.hXy/hXz; bkR.eH breedCharac*", "breeds",rows)));
 }
}
