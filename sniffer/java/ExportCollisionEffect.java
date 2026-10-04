import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Own synthetic native eVI definition, offline, no client/session execution. */
public class ExportCollisionEffect {
 public static void main(String[]args)throws Exception {
  eVn e=eVI.fMg();Map<String,Object> out=new TreeMap<>();
  out.put("reference",e.aZE());out.put("effect_class",e.awM());
  out.put("parameters",e.fKI());out.put("parameter_count",e.fKJ());
  out.put("variant",e.aZR());out.put("minimum_level",e.fKR());out.put("maximum_level",e.fKS());
  out.put("native_definition_class",e.getClass().getName());out.put("native_execution_mode",e.aZD());
  Map<String,Object> timing=new TreeMap<>();timing.put("clock_on_caster",e.aZT());timing.put("clock_on_target",e.aZU());
  for(String name:new String[]{"ryE","ryF","ryG","ryH","ryI","esr"}) {
   FieldAccess.put(timing,eVy.class,e,name);
  }
  out.put("native_timing_definition",timing);
  List<Integer> flags=new ArrayList<>();for(eVl f:eVl.values())if(e.a(f))flags.add((int)f.fLK());out.put("native_effect_flags",flags);
  out.put("event_suppresses_level_one",e.aZB());out.put("event_global_subscription",e.aZx());
  out.put("event_reverse_subscription",e.aZw());out.put("event_execution_count",e.aZS());
  out.put("owner_on_caster",e.aZA());out.put("subscription",e.aZN());out.put("event_priority",e.aZM());
  out.put("event_target_code",e.aZV()==null?null:e.aZV().aKg());
  out.put("event_caster_code",e.aZW()==null?null:e.aZW().aKg());
  out.put("definition_dispellable",((eVv)e).cxq());
  out.put("probability",e.eg((short)1));
  List<Object> masks=new ArrayList<>();for(BitSet b:new BitSet[]{e.aZG(),e.aZH(),e.aZI(),e.aZJ(),e.aZK(),e.aZL(),e.aZO()})masks.add(b==null?null:b.stream().toArray());out.put("target_masks",masks);
  String encoded=new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(out);
  Files.writeString(Path.of(args[0]),encoded+"\n");System.out.println("Exported own native synthetic collision definition");
 }
 static class FieldAccess {static void put(Map<String,Object> out,Class<?> owner,Object e,String n)throws Exception{var f=owner.getDeclaredField(n);f.setAccessible(true);out.put(n,f.get(e));}}
}
