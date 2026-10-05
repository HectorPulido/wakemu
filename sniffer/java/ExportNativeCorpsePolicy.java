import java.nio.file.*;import java.lang.reflect.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Only constant native bcd overrides; inherited dynamic guards remain null. */
public class ExportNativeCorpsePolicy{
 public static void main(String[]args)throws Exception{
  Map<String,Object> rows=new TreeMap<>();
  for(Field f:eVi.class.getDeclaredFields())if(f.getType()==eVj.class&&Modifier.isStatic(f.getModifiers())){
   f.setAccessible(true);eVj entry=(eVj)f.get(null);Object q=entry.bkv();Class<?> cls=q.getClass();Method method=null;
   for(Class<?> c=cls;c!=null;c=c.getSuperclass())try{method=c.getDeclaredMethod("bcd");break;}catch(NoSuchMethodException ignored){}
   if(method==null)continue;
   Map<String,Object> row=new LinkedHashMap<>();row.put("runner",cls.getName());row.put("owner",method.getDeclaringClass().getName());row.put("bcd_constant",ExportNativeRunnerOwners.constant(method));rows.put(Integer.toString(entry.d()),row);
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(Map.of("source","Installed eVi prototypes; literal bcd overrides only. null is dynamic, not false.","effects",rows))+"\n");
  System.out.println("PASS original corpse policy population="+rows.size()+" group330="+rows.get("330"));
 }
}
