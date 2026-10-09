import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
import sun.misc.Unsafe;
/** Offline original eWE application/removal and event prototype probe. */
public class ProbeNativeDeathScript {
 static Field field(Class<?> type,String name)throws Exception {
  while(type!=null){try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException e){type=type.getSuperclass();}}
  throw new NoSuchFieldException(name);
 }
 public static void main(String[]args)throws Exception {
  Field unsafe=Unsafe.class.getDeclaredField("theUnsafe");unsafe.setAccessible(true);Unsafe u=(Unsafe)unsafe.get(null);
  eGj actor=(eGj)u.allocateInstance(bje.class);eWE runner=new eWE();
  Field target=field(eWE.class,"bfs"),amount=field(eWE.class,"aSg"),script=field(eGj.class,"pGU");
  Method apply=eWE.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
  target.set(runner,actor);List<Map<String,Object>> rows=new ArrayList<>();
  for(int value:new int[]{Integer.MIN_VALUE,-1,0,37,Integer.MAX_VALUE}){
   actor.PI(42);amount.setInt(runner,value);apply.invoke(runner,null,false);
   if(script.getInt(actor)!=value)throw new AssertionError("application");
   runner.bbR();if(script.getInt(actor)!=-1)throw new AssertionError("removal");
   rows.add(Map.of("before",42,"amount",value,"applied",value,"removed",-1));
  }
  actor.PI(99);runner.bbR();if(script.getInt(actor)!=-1)throw new AssertionError("notreset");

  runner.bbx();Map<String,Object> result=new LinkedHashMap<>();result.put("runner","eWE");result.put("events",runner.bbw().stream().boxed().toList());result.put("bbz",runner.bbz());result.put("bbA",runner.bbA());result.put("bbB",runner.bbB());result.put("bcd",runner.bcd());result.put("rows",rows);result.put("overwritten_script_removal_resets_minus_one",true);
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(result);
 }
}
