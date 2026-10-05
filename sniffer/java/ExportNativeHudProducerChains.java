import java.nio.file.*;import java.util.*;import com.google.gson.*;
/** Original selected state producer trees, including raw subscription masks. */
public class ExportNativeHudProducerChains {
 static Map<Integer,int[]> groups=new HashMap<>();static Map<Integer,String> criteria=new HashMap<>();static Map<Integer,Object> effects=new TreeMap<>();
 static void effect(int ref){if(effects.containsKey(ref))return;eVn e=bcA.dcX().AH(ref);Map<String,Object> row=new LinkedHashMap<>();row.put("reference",ref);row.put("effect_class",e.awM());row.put("raw_parameters",e.fKI());row.put("criteria",criteria.get(ref));row.put("children",groups.getOrDefault(ref,new int[0]));row.put("metadata",ExportSpellEffectTrees.metadata(e));effects.put(ref,row);for(int child:groups.getOrDefault(ref,new int[0]))effect(child);}
 public static void main(String[]args)throws Exception{
  Set<Integer> wanted=new HashSet<>();for(String value:args[1].split(","))wanted.add(Integer.parseInt(value));
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){criteria.put(e.aZE(),e.cyi());}});
  Map<Integer,Object> states=new TreeMap<>();
  apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv s){if(wanted.contains(s.d())){states.put(s.d(),Map.of("roots",s.cku(),"max_level",s.aWa()));for(int r:s.cku())effect(r);}}});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Original aNv→aKX→aNw/eVn", "states",states,"effects",effects))+"\n");System.out.println("States "+states.size()+"; definitions "+effects.size());
 }
}
