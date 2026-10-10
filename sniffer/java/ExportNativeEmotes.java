import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Exports installed emote definitions without executing animations. */
public class ExportNativeEmotes {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> rows=new ArrayList<>(); Gson gson=new GsonBuilder().serializeNulls().create();
  apw.bGL().a(new aKY(),new apB<aKY>(){public void load(aKY row){rows.add(gson.toJsonTree(row));}});
  Path path=Path.of(args.length==0?".runtime/local/native-emote-definitions.json":args[0]);
  Files.writeString(path,gson.toJson(Map.of("source","Installed aKY; bkI1 ordinary,2 targeted,0 invalid per baq", "emotes",rows)));
  System.out.println("Exported "+rows.size()+" emote definitions to "+path);
 }
}
