import java.nio.file.*;
import java.nio.*;
import java.util.*;
import com.google.gson.*;
/** Native13974 and wW decode: exact protector definition to published actor ID. */
public class AuditCapturedProtectorActorLinks {
 public static void main(String[] args)throws Exception{
  List<Object> links=new ArrayList<>();int snapshots=0,records=0;
  for(String line:Files.readAllLines(Path.of(args[0]))){
   JsonObject frame=JsonParser.parseString(line).getAsJsonObject();
   if(!frame.has("opcode")||frame.get("opcode").getAsInt()!=13974)continue;
   csW snapshot=new csW();snapshot.dp(Base64.getDecoder().decode(frame.get("body_base64").getAsString()));snapshots++;
   for(byte[] raw:snapshot.eEY()){
    ByteBuffer buffer=ByteBuffer.wrap(raw);wW protector=new wW();
    if(!protector.aG(buffer)||buffer.hasRemaining())throw new AssertionError("Invalid protector record");
    records++;
    if(args.length>2 && args[2].equals("--all") || protector.aiQ==424 || protector.aiS!=null && protector.aiS.ajf==-1706442046308330L)
     links.add(Map.of("frame_index",frame.get("frame_index").getAsInt(),"protector_id",protector.aiQ,"actor_id",protector.aiS==null?0L:protector.aiS.ajf,"record_base64",Base64.getEncoder().encodeToString(raw),"native",new Gson().toJsonTree(protector)));
   }
  }
  Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("snapshots",snapshots,"protector_records",records,"links",links)));
  System.out.println("snapshots="+snapshots+" records="+records+" matched_links="+links.size());
 }
}
