import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Exact protector XYZ plus native worlds.lib territory-to-world identity. */
public class ExportNativeProtectorPositions {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  cdH.bla();cdH.exY().dW("jar:file:"+Path.of("client/contents/maps/data.jar").toAbsolutePath()+"!/worlds.lib");
  Properties names=new Properties();
  try(java.util.zip.ZipFile locale=new java.util.zip.ZipFile("client/contents/i18n/i18n_es.jar")){
   names.load(new java.io.InputStreamReader(locale.getInputStream(locale.getEntry("texts_es.properties")),java.nio.charset.StandardCharsets.UTF_8));
  }
  List<Object> positions=new ArrayList<>(),unresolved=new ArrayList<>();
  apw.bGL().a(new aMD(),new apB<aMD>(){public void load(aMD row){
   fwI territory=fxf.toy.Zp(row.ctH());
   Map<String,Object> record=new LinkedHashMap<>();
   record.put("protector_id",row.ctC());record.put("native_name_es",names.getProperty("content.48."+row.ctC(),""));record.put("territory_id",row.ctH());
   record.put("x",row.ctJ());record.put("y",row.ctK());record.put("z",row.cki());
   record.put("appearance_id",row.cpi());record.put("native_definition",new Gson().toJsonTree(row));
   if(territory==null){record.put("reason","territory_not_registered_in_installed_worlds");unresolved.add(record);}
   else{record.put("map_id",territory.arM());record.put("qualification","native_protector_position_only_breed_and_dialogue_unbound");positions.add(record);}
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("positions",positions,"unresolved",unresolved)));
  System.out.println("exact_protector_positions="+positions.size()+" unresolved="+unresolved.size());
 }
}
