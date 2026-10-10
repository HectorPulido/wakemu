import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
/** Export native bIw learning arguments without launching a game client. */
public class ExportNativeEmoteLearning {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Field emote=bIw.class.getDeclaredField("ezG"); emote.setAccessible(true);
  List<Object> rows=new ArrayList<>();
  apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO raw){
   bJp item=new bIJ().f(raw); foH action=item.gfJ();
   if(action instanceof bIw) try {rows.add(Map.of("item_ref",item.d(),"action_id",action.d(),
    "emote_id",emote.getInt(action),"has_criteria",item.a(fnE.sGH)!=null));}
   catch(IllegalAccessException error){throw new RuntimeException(error);}
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("items",rows))+"\n");
 }
}
