import java.nio.file.*;import java.util.*;import com.google.gson.*;
public class ExportAptitudeRules {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> bonuses=new ArrayList<>(),categories=new ArrayList<>();
  apw.bGL().a(new aJX(),new apB<aJX>(){public void load(aJX r){bonuses.add(Map.of("id",r.tJ(),"maximum",r.bWy(),"parameter_bwX",r.bwX(),"effect_references",r.cku()));}});
  apw.bGL().a(new aJY(),new apB<aJY>(){public void load(aJY r){categories.add(Map.of("id",r.cjG(),"grant_levels",r.ckv(),"bonuses",r.ckw()));}});
  Files.writeString(Path.of("server/protocol/aptitude-rules.json"),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","aZG/aZI loaders; eQI.QI/t/ak; eQH.dF native grant thresholds", "bonuses",bonuses,"categories",categories)));
  System.out.println("bonuses="+bonuses.size()+" categories="+categories.size());
 }
}
