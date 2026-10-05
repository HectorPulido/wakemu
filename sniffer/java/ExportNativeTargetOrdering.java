import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Native faK distance flags14/26 plus faH signed-byte target cap. */
public class ExportNativeTargetOrdering {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Integer> ids=new ArrayList<>();apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw row){ids.add(row.aZE());}});
  Map<String,Object> rows=new TreeMap<>();
  for(int id:ids){eVn e=bcA.dcX().AH(id);
   if(!e.a(eVl.rwK)&&!e.a(eVl.rwW))continue;
   List<Integer> flags=new ArrayList<>();for(eVl flag:eVl.values())if(e.a(flag))flags.add((int)flag.fLK());
   rows.put(""+id,Map.of("effect_class",e.awM(),"native_effect_flags",flags,"maximum_targets",(int)e.fKH()));
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(rows)+"\n");
  System.out.println("Exported native distance ordering definitions="+rows.size()+" source definitions="+ids.size());
 }
}
