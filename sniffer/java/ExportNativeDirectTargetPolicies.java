import java.nio.file.*;import java.util.*;
import java.io.*;import com.google.gson.Gson;
/** Complete aNw population: Qe.a aZX and eVE.a cym, never infer false. */
public class ExportNativeDirectTargetPolicies {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<String,Object> rows=new TreeMap<>();
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){
   eVn effect=bcA.dcX().AH(raw.aZE());
   if(!(effect instanceof eVE definition))throw new IllegalStateException("Unknown direct-target definition "+raw.aZE());
   rows.put(""+raw.aZE(),List.of(effect.awM(),definition.aZX(),definition.cym()));
  }});
  try(Writer out=new OutputStreamWriter(Files.newOutputStream(Path.of(args[0])),java.nio.charset.StandardCharsets.UTF_8)){
   new Gson().toJson(Map.of("schema",1,"source_count",rows.size(),"fields",List.of("effect_class","recalculate_targets","caster_is_target"),"effects",rows),out);
  }
  System.out.println("Exported complete native direct-target policies="+rows.size());
 }
}
