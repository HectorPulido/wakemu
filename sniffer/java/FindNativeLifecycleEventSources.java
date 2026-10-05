import java.nio.file.*;import java.util.*;import com.google.gson.Gson;
/** One offline native definition load; event namespaces remain distinct. */
public class FindNativeLifecycleEventSources {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<Integer,List<Map<String,Object>>> sources=new TreeMap<>();sources.put(1001,new ArrayList<>());sources.put(1028,new ArrayList<>());int[]count={0};
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){
   count[0]++;eVn e=bcA.dcX().AH(raw.aZE());if(e==null)throw new IllegalStateException("missing effect "+raw.aZE());
   BitSet emitted=e.aZO();if(emitted==null)return;
   for(var entry:sources.entrySet())if(emitted.get(entry.getKey()))entry.getValue().add(Map.of("reference",e.aZE(),"effect_class",e.awM(),"emitted_bits",emitted.stream().toArray()));
  }});
  Map<String,Object>result=new TreeMap<>();result.put("source","Installed aNw->bcA.AH->eVn.aZO, offline. Absence does not prove external server event unavailable.");result.put("definitions_checked",count[0]);result.put("events",sources);
  Files.writeString(Path.of(args[0]),new Gson().toJson(result));System.out.println("Checked "+count[0]+" definitions:1001="+sources.get(1001).size()+",1028="+sources.get(1028).size());
 }
}
