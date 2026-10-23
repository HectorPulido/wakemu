import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Read-only native item-use effect closure for explicitly selected references. */
public class ExportConsumableDescriptors {
 static final Gson G=new GsonBuilder().serializeNulls().create();
 static final Map<Integer,int[]> GROUPS=new HashMap<>();
 static final Map<Integer,String> CRITERIA=new HashMap<>();
 static final Map<String,Object> EFFECTS=new LinkedHashMap<>();
 static void effect(int id,short level)throws Exception{
  String key=id+":"+level;if(EFFECTS.containsKey(key))return;
  eVn e=bcA.dcX().AH(id);if(e==null)throw new IllegalArgumentException("Missing effect "+id);
  Map<String,Object> r=new LinkedHashMap<>();r.put("id",id);r.put("level",(int)level);r.put("generic",e.awM());r.put("params",e.fKI());
  List<Integer> values=new ArrayList<>();for(int k=0;k<e.fKJ();k++)values.add(e.a(k,level,eVh.rpA));r.put("values",values);
  r.put("display",e.cys());r.put("criteria",CRITERIA.getOrDefault(id,""));r.put("native_metadata",ExportSpellEffectTrees.metadata(e));r.put("timing",ExportEffectRuntimeMetadata.timing(e,level));
  r.put("subscription",e.aZN());r.put("owner_on_caster",e.aZA());r.put("event_execution_count",(int)e.aZS());r.put("event_execution_count_per_level",e.cyc());
  r.put("children",GROUPS.getOrDefault(id,new int[0]));
  Object runner=eVi.fLJ().pS(e.awM());r.put("runner",runner==null?null:runner.getClass().getName());
  PC stat=runner instanceof eWN n?n.fNI():runner instanceof eWW n?n.fNI():null;
  r.put("stat_id",stat==null?null:(int)(stat.aKg()&255));r.put("stat_name",stat==null?null:stat.toString());
  EFFECTS.put(key,r);for(int child:GROUPS.getOrDefault(id,new int[0]))effect(child,level);
 }
 public static void main(String[]args)throws Exception{
  Set<Integer> refs=new HashSet<>();for(JsonElement e:JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray())refs.add(e.getAsInt());
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX r){GROUPS.put(r.d(),r.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw r){CRITERIA.put(r.aZE(),r.cyi());}});
  Map<String,Object> items=new LinkedHashMap<>();
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){if(!refs.contains(raw.d()))return;try{
   bJp i=new bIJ().f(raw);Map<String,Object> row=new LinkedHashMap<>();row.put("reference",i.d());row.put("level",(int)i.cmZ());row.put("use_criteria_present",i.a(fnE.sGD)!=null);Map<String,String> criteria=new LinkedHashMap<>();String[] rawCriteria=raw.cpz();if(rawCriteria!=null)for(int n=0;n+1<rawCriteria.length;n+=2)criteria.put(rawCriteria[n],rawCriteria[n+1]);row.put("use_criteria",criteria);row.put("use_action_present",i.gfJ()!=null);List<Integer>roots=new ArrayList<>();Iterator<eVn>it=i.gjg();while(it.hasNext()){eVn e=it.next();roots.add(e.aZE());effect(e.aZE(),i.cmZ());}row.put("effects",roots);items.put(""+i.d(),row);
  }catch(Exception ex){throw new IllegalStateException(ex);}}});
  // State roots are supplied at their actual applied levels, not item levels.
  JsonObject stateLevels=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
  for(var entry:stateLevels.entrySet())for(JsonElement e:entry.getValue().getAsJsonArray())effect(Integer.parseInt(entry.getKey()),e.getAsShort());
  Files.writeString(Path.of(args[2]),G.toJson(Map.of("items",items,"effects",EFFECTS)));System.out.println("items="+items.size()+" effect-levels="+EFFECTS.size());
 }
}
