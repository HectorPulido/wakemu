import java.nio.file.*;import java.util.*;import com.google.gson.*;
/** Offline dynamic-characteristic definitions aimed at native breed HUD stats. */
public class ExportNativeHudResourceEffects {
 public static void main(String[]args)throws Exception {
  Set<Integer> classes=Set.of(38,39,40,46,235,236);
  Set<Integer> stats=Set.of(50,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,117,123);
  List<Object> effects=new ArrayList<>();Map<Integer,int[]> groups=new HashMap<>(),states=new HashMap<>();int[] seen={0};
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv g){states.put(g.d(),g.cku()==null?new int[0]:g.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){
   seen[0]++;if(!classes.contains(e.awM()))return;
   float[] p=e.bdh();if(p.length<6||p[5]!=0||!stats.contains((int)p[4])||p[4]!=(int)p[4])return;
   Map<String,Object> r=new LinkedHashMap<>();r.put("reference",e.aZE());r.put("effect_class",e.awM());r.put("stat_id",(int)p[4]);r.put("parameters",p);r.put("criteria",e.cyi());
   Set<Integer> ancestry=new TreeSet<>();ancestry.add(e.aZE());boolean changed=true;
   while(changed){changed=false;for(var g:groups.entrySet())if(!ancestry.contains(g.getKey()))for(int child:g.getValue())if(ancestry.contains(child)){ancestry.add(g.getKey());changed=true;break;}}
   List<Integer> owners=new ArrayList<>();for(var st:states.entrySet())for(int root:st.getValue())if(ancestry.contains(root)){owners.add(st.getKey());break;}
   r.put("ancestor_effects",ancestry);r.put("state_owners",owners);effects.add(r);
  }});
  Map<String,Object> result=new LinkedHashMap<>();result.put("source","Installed aNw definitions; audited dynamic eWQ/eWR parameter2 characteristic");result.put("scanned",seen[0]);result.put("effects",effects);
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(result)+"\n");System.out.println("Definitions "+seen[0]+"; HUD dynamic producers "+effects.size());
 }
}
