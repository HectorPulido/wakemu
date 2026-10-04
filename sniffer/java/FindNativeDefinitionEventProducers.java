import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Offline loaded aZO sources; integers in another namespace are not trigger events. */
public class FindNativeDefinitionEventProducers {
 public static void main(String[]args)throws Exception{
  int needle=Integer.parseInt(args[0]);List<Map<String,Object>> rows=new ArrayList<>();
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw record){
   eVn e=bcA.dcX().AH(record.aZE());if(e.aZO()!=null&&e.aZO().get(needle)){
    Map<String,Object> row=new TreeMap<>();row.put("reference",e.aZE());row.put("effect_class",e.awM());
    row.put("emitted_events",e.aZO().stream().toArray());row.put("parameters",new ArrayList<Integer>());
    row.put("minimum_level",e.fKR());row.put("maximum_level",e.fKS());row.put("criteria",record.cyi());
    rows.add(row);
   }
  }});
  Map<Integer,int[]> groups=new TreeMap<>();
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  for(var row:rows){
   int ref=(Integer)row.get("reference");eVn e=bcA.dcX().AH(ref);
   var field=eVE.class.getDeclaredField("ryR");field.setAccessible(true);row.put("parameters",field.get(e));
   row.putAll(ExportSpellEffectTrees.metadata(e));row.put("children",groups.getOrDefault(ref,new int[0]));
   Set<Integer> ancestry=new TreeSet<>();ancestry.add(ref);boolean changed;
   do{changed=false;for(var group:groups.entrySet())for(int child:group.getValue())if(ancestry.contains(child))changed|=ancestry.add(group.getKey());}while(changed);
   row.put("ancestors",ancestry);List<Integer> spells=new ArrayList<>();
   apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr spell){for(int root:spell.cku())if(ancestry.contains(root)){spells.add(spell.d());break;}}});
   row.put("spells",spells);
   List<Integer> states=new ArrayList<>();
   apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv state){if(state.cku()!=null)for(int root:state.cku())if(ancestry.contains(root)){states.add(state.d());break;}}});
   row.put("states",states);
  }
  rows.sort(Comparator.comparingInt(row -> (Integer)row.get("reference")));
  Files.writeString(Path.of(args[1]),new GsonBuilder().serializeNulls().create().toJson(rows));
  System.out.println("Native aZO event "+needle+" sources="+rows.size());for(var row:rows)System.out.println("ref="+row.get("reference")+" spells="+row.get("spells")+" states="+row.get("states")+" ancestors="+row.get("ancestors"));
 }
}
