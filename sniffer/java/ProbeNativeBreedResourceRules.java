import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Selected original definition trees. Formula evidence, not a server projection. */
public class ProbeNativeBreedResourceRules {
 static Map<Integer,int[]> groups=new HashMap<>();static Map<Integer,String> criteria=new HashMap<>();static Set<Integer> seen=new HashSet<>();
 static void effect(int ref){if(!seen.add(ref))return;eVn e=bcA.dcX().AH(ref);Map<String,Object> r=new LinkedHashMap<>();r.put("effect",ref);r.put("class",e.awM());r.put("min",e.fKR());r.put("max",e.fKS());r.put("criteria",criteria.get(ref));r.put("raw",e.fKI());r.put("children",groups.get(ref));System.out.println(new Gson().toJson(r));for(int c:groups.getOrDefault(ref,new int[0]))effect(c);}
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
 apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){criteria.put(e.aZE(),e.cyi());}});
 fyZ.guX().a(new bbV());
 for(int ref:new int[]{3442,3425,9312,9313,9342,8924,3462}){fyW s=fyZ.guX().aax(ref);System.out.println("STATE "+ref);for(eVn e:s.guJ())effect(e.aZE());}
 System.out.println("PASS: original resource definition trees read without runtime mutation");
 }
}
