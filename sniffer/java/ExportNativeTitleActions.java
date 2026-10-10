import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
/** Offline native bIs title learning operands. */
public class ExportNativeTitleActions {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Field title=bIs.class.getDeclaredField("jiK");title.setAccessible(true);
  List<Object> rows=new ArrayList<>();
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){
   bJp item=new bIJ().f(raw);if(item.gfJ() instanceof bIs action){try{
    rows.add(Map.of("reference",item.d(),"action_id",action.d(),"title_id",title.getInt(action),"has_criteria",item.a(fnE.sGH)!=null||action.bdt()!=null));
   }catch(Exception error){throw new RuntimeException(error);}}
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Installed bIJ -> bIs.jiK native learned title ID","items",rows))+"\n");
 }
}
