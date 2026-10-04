import java.util.*;import java.nio.file.*;import com.google.gson.GsonBuilder;
/** All native subscription consumers, with spell/state ancestry, not emitters. */
public class ExportLifecycleSubscriptions {
 static Map<Integer,int[]> groups=new HashMap<>();
 static Map<Integer,Map<String,Object>> rows=new TreeMap<>();
 static void attach(int root,String kind,int identity,Set<Integer> seen){
  if(!seen.add(root))return;
  var row=rows.get(root);if(row!=null)((Set<Integer>)row.get(kind)).add(identity);
  for(int child:groups.getOrDefault(root,new int[0]))attach(child,kind,identity,seen);
 }
 public static void main(String[]args)throws Exception{
  int event=Integer.parseInt(args[0]);
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX row){groups.put(row.d(),row.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){
   eVn e=bcA.dcX().AH(raw.aZE());BitSet[] masks={e.aZG(),e.aZH(),e.aZI(),e.aZJ(),e.aZK(),e.aZL()};
   if(Arrays.stream(masks).noneMatch(mask->mask!=null&&mask.get(event)))return;
   Map<String,Object> row=new TreeMap<>(ExportSpellEffectTrees.metadata(e));
   row.put("reference",e.aZE());row.put("effect_class",e.awM());row.put("criteria",raw.cyi());
   row.put("event_reverse_subscription",e.aZw());row.put("event_global_subscription",e.aZx());
   row.put("event_execution_count",(int)e.aZS());row.put("event_target_code",(int)e.aZV().aKg());
   row.put("event_caster_code",e.aZW()==null?null:(int)e.aZW().aKg());
   row.put("children",groups.getOrDefault(e.aZE(),new int[0]));
   row.put("spells",new TreeSet<Integer>());row.put("states",new TreeSet<Integer>());rows.put(e.aZE(),row);
  }});
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr spell){for(int root:spell.cku())attach(root,"spells",spell.d(),new HashSet<>());}});
  apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv state){if(state.cku()!=null)for(int root:state.cku())attach(root,"states",state.d(),new HashSet<>());}});
  Files.writeString(Path.of(args[1]),new GsonBuilder().serializeNulls().create().toJson(rows));
  System.out.println("Native event"+event+" subscriptions="+rows.size());
 }
}
