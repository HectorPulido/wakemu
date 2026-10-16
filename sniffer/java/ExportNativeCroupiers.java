import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Read-only export of installed exchange-machine definitions. */
public final class ExportNativeCroupiers {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Map<String,Object>> machines=new ArrayList<>();
  apw.bGL().a(new aLa(),new apB<aLa>(){public void load(aLa raw){
   Map<String,Object> m=new LinkedHashMap<>();m.put("id",raw.d());m.put("visual_id",raw.ckK());m.put("category_id",raw.cnx());m.put("raw_cny",raw.cny());
   List<Map<String,Object>> offers=new ArrayList<>();
   for(aLc o:raw.cnz()){
    Map<String,Object> r=new LinkedHashMap<>();r.put("id",o.cnA());r.put("kamas_cost",o.cnC());r.put("alternate_currency_cost",o.cnD());r.put("offer_flag",o.cnF());r.put("criteria",o.clT());
    List<Map<String,Object>> costs=new ArrayList<>();for(aLb c:o.cnB())costs.add(Map.of("reference",c.aAi(),"quantity",c.bfh()));r.put("costs",costs);
    List<Map<String,Object>> rewards=new ArrayList<>();for(aLd p:o.cnE())rewards.add(Map.of("reference",p.aAi(),"quantity",p.bfh(),"binding_id",p.cnG(),"raw_cnH",p.cnH()));r.put("rewards",rewards);offers.add(r);
   }m.put("offers",offers);machines.add(m);
  }});
  machines.sort(Comparator.comparingInt(m->(Integer)m.get("id")));
  Map<String,Object> root=new LinkedHashMap<>();root.put("version",1);root.put("source",Map.of("native_definition","aLa/aLc/aLb/aLd","asset_directory","client/contents/bdata"));root.put("machines",machines);
  if(args.length>1)root.put("placements",JsonParser.parseString(Files.readString(Path.of(args[1]))));
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(root));
  System.out.println("Exported machines="+machines.size()+" offers="+machines.stream().mapToInt(m->((List<?>)m.get("offers")).size()).sum());
 }
}
