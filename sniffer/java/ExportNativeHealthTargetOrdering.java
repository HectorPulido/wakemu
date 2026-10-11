import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
/** Separate native flag8 identity artifact; never publishes the runtime registry. */
public class ExportNativeHealthTargetOrdering {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Integer> ids=new ArrayList<>();
  apw.bGL().a(new aNw(),new apB<aNw>() { public void load(aNw row) { ids.add(row.aZE()); } });
  Map<String,Object> rows=new TreeMap<>();
  for(int id:ids) {
   eVn effect=bcA.dcX().AH(id);
   if(!effect.a(eVl.rwE)) continue;
   List<Integer> flags=new ArrayList<>();
   for(eVl flag:eVl.values()) if(effect.a(flag)) flags.add((int)flag.fLK());
   rows.put(""+id,Map.of("effect_class",effect.awM(),"native_effect_flags",flags,
    "maximum_targets",(int)effect.fKH(),"ordering_contract","faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1"));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows)+"\n");
  System.out.println("Native flag8 identities exported="+rows.size()+"; runtime registry unchanged");
 }
}
