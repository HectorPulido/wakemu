import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Small reproducible real catalog graph and native healing event source for tests. */
public class ExportNativeEventReplayFixture {
 static Map<Integer,int[]> groups=new TreeMap<>();static Map<Integer,String> criteria=new TreeMap<>();
 static Object field(eVn e,String name)throws Exception{var f=eVE.class.getDeclaredField(name);f.setAccessible(true);return f.get(e);}
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  List<Integer> ids=new ArrayList<>();apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw d){ids.add(d.aZE());criteria.put(d.aZE(),d.cyi());}});
  int source=ids.stream().filter(id->{eVn e=bcA.dcX().AH(id);return e.awM()==25&&e.fKR()<=1&&e.fKS()>=1;}).findFirst().orElseThrow();
  int damageSource=ids.stream().filter(id->{eVn e=bcA.dcX().AH(id);if(e.awM()!=1||e.fKR()>1||e.fKS()<1||e.fKJ()!=1||!criteria.get(id).isEmpty())return false;
   Map row=ExportSpellEffectTrees.metadata(e);Map selector=(Map)row.get("native_target_selector");
   return selector!=null&&((Number)selector.get("mask")).longValue()==1&&((List)row.get("native_effect_flags")).isEmpty();}).findFirst().orElseThrow();
  Map<String,Object> effects=new TreeMap<>(),retained=new TreeMap<>();
  for(int id:new int[]{308265,308266,308267,359836,source,damageSource}){
   eVn e=bcA.dcX().AH(id);Map<String,Object> row=new TreeMap<>(ExportSpellEffectTrees.metadata(e));
   row.put("effect_class",e.awM());row.put("parameters",field(e,"ryR"));row.put("parameter_count",e.fKJ());
   row.put("probability_base",field(e,"ryP"));row.put("probability_per_level",field(e,"ryQ"));
   row.put("criteria",criteria.get(id));row.put("children",groups.getOrDefault(id,new int[0]));row.put("variant",e.aZR());
   row.put("minimum_level",e.fKR());row.put("maximum_level",e.fKS());effects.put(""+id,row);
   Map<String,Object> meta=new TreeMap<>();for(String key:new String[]{"effect_class","parameters","variant","minimum_level","maximum_level"})meta.put(key,row.get(key));
   meta.put("definition_type",(int)e.aZD());meta.put("owner_on_caster",e.aZA());meta.put("subscription",e.aZN());
   meta.put("definition_dispellable",e instanceof eVv v?v.cxq():null);meta.put("event_target_code",(int)e.aZV().aKg());
   meta.put("event_caster_code",e.aZW()==null?null:(int)e.aZW().aKg());meta.put("event_global_subscription",e.aZx());
   meta.put("event_reverse_subscription",e.aZw());meta.put("event_priority",e.aZM());meta.put("event_suppresses_level_one",e.aZB());meta.put("event_execution_count",(int)e.aZS());retained.put(""+id,meta);
  }
  eXs heal=(eXs)eVi.fLJ().pS(25);heal.b(bcA.dcX().AH(source));heal.bbx();heal.bby();
  Map<String,Object> output=new TreeMap<>();output.put("effects",effects);output.put("source",source);output.put("damage_source",damageSource);output.put("native_source_event_ids",heal.bbw().stream().toArray());
  output.put("retained_metadata",Map.of("effects",retained,"spells",Map.of("6266",Map.of("protected",bPS.elL().IP(6266).elO()),"5249",Map.of("protected",bPS.elL().IP(5249).elO())),"states",Map.of()));
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().create().toJson(output));System.out.println("source="+source+" events="+heal.bbw());
 }
}
