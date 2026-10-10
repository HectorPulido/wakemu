import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Offline native account cosmetic learning metadata. */
public class ExportNativeCosmeticActions {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> rows=new ArrayList<>();
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){
   bJp item=new bIJ().f(raw);
   if(item.gfJ() instanceof bIt action) rows.add(Map.of("reference",item.d(),"action_id",action.d(),"category",action.dzN().getNumber(),"category_name",action.dzN().getValueDescriptor().getName(),"has_criteria",item.a(fnE.sGH)!=null));
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Installed bIJ -> bIt.dzN -> fn numeric native cosmetic category; source item is the owned cosmetic reference","items",rows))+"\n");
 }
}
