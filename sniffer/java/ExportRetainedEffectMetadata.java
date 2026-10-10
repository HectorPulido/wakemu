import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParser;
public class ExportRetainedEffectMetadata {
 static Object canonical(Object value){
  if(value instanceof Map<?,?> map){Map<String,Object> sorted=new TreeMap<>();map.forEach((k,v)->sorted.put(k.toString(),canonical(v)));return sorted;}
  return value;
 }
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Integer>ids=new ArrayList<>();apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw row){ids.add(row.aZE());}});
  Map<String,Object> effects=new TreeMap<>();
  for(int id:ids){eVn e=bcA.dcX().AH(id);if(e==null)throw new IllegalStateException("Missing native effect"+id);
   Map<String,Object>m=new TreeMap<>();m.put("effect_class",e.awM());m.put("definition_type",(int)e.aZD());m.put("owner_on_caster",e.aZA());m.put("subscription",e.aZN());
   m.put("event_target_code",(int)e.aZV().aKg());m.put("event_caster_code",e.aZW()==null?null:(int)e.aZW().aKg());
   m.put("event_reverse_subscription",e.aZw());m.put("event_global_subscription",e.aZx());
   m.put("event_priority",e.aZM());m.put("event_suppresses_level_one",e.aZB());m.put("event_execution_count",(int)e.aZS());m.put("event_execution_count_per_level",e.cyc());
   var pf=eVE.class.getDeclaredField("ryR");pf.setAccessible(true);m.put("parameters",pf.get(e));m.put("variant",e.aZR());m.put("minimum_level",e.fKR());m.put("maximum_level",e.fKS());
   m.put("definition_dispellable",e instanceof eVv v?v.cxq():null);effects.put(""+id,m);
  }
  Map<String,Object> spells=new TreeMap<>();
  var spellRows=new JsonParser().parse(Files.readString(Path.of("server/protocol/spells.json"))).getAsJsonObject().getAsJsonArray("spells");
  for(var row:spellRows){int id=row.getAsJsonObject().get("id").getAsInt();fyF spell=bPS.elL().IP(id);spells.put(""+id,Map.of("protected",spell.elO()));}
  Map<String,Object> states=new TreeMap<>();List<Integer> stateIDs=new ArrayList<>();
  apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv state){stateIDs.add(state.d());}});fyZ.guX().a(new bbV());
  for(int id:stateIDs){fyW state=fyZ.guX().aax(id);states.put(""+id,Map.of("unremovable",state.guN(),"dispellable",state.cxq()));}
  Files.writeString(Path.of(args.length==0?"server/protocol/native-retained-effect-metadata.json":args[0]),new GsonBuilder().serializeNulls().create().toJson(canonical(Map.of("source","Native PK.aZD/aZA, eVv.cxq from bcA.AH(aNw)","effects",effects,"spells",spells,"states",states))));
  System.out.println("exported "+effects.size());
 }
}
