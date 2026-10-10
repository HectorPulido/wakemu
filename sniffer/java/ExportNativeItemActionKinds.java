import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Offline native item-use categories and native account cosmetic enum. */
public class ExportNativeItemActionKinds {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> rows=new ArrayList<>(),categories=new ArrayList<>();
  for(fn kind:fn.values()) categories.add(Map.of("id",kind.getNumber(),"name",kind.getValueDescriptor().getName()));
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){
   bJp item=new bIJ().f(raw); foH action=item.gfJ();
   if(action!=null)rows.add(Map.of("reference",item.d(),"action_id",action.d(),"class",action.getClass().getName(),"kind",action.dYJ().name(),"kind_key",action.dYJ().aYi(),"has_criteria",item.a(fnE.sGH)!=null));
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("items",rows,"categories",categories))+"\n");
 }
}
