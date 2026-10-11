import java.nio.file.*;
import java.util.*;
import java.util.zip.ZipFile;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import com.google.gson.GsonBuilder;
public class ExportItemInventoryTypes {
 public static void main(String[] args)throws Exception {
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 Properties names=new Properties();
 try(ZipFile locale=new ZipFile("client/contents/i18n/i18n_es.jar"); InputStreamReader reader=new InputStreamReader(locale.getInputStream(locale.getEntry("texts_es.properties")),StandardCharsets.UTF_8)){ names.load(reader); }
 List<Map<String,Object>> types=new ArrayList<>(),items=new ArrayList<>();
 Map<Integer,Integer> counts=new HashMap<>();
 apw.bGL().a(new aLU(),new apB<aLU>(){public void load(aLU r){Map<String,Object> o=new LinkedHashMap<>();o.put("type_id",r.aIX());o.put("name_es",names.getProperty("content.14."+r.aIX(),""));o.put("parent_id",r.cqp());o.put("slots",r.cqs());o.put("occupied_slots",r.cqt());o.put("cqq",r.cqq());o.put("cqr",r.cqr());o.put("cqu",r.cqu());o.put("cqv",r.cqv());types.add(o);}});
 apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO r){Map<String,Object> o=new LinkedHashMap<>();counts.merge(r.cpA(),1,Integer::sum);o.put("reference",r.d());o.put("type_id",r.cpA());o.put("rarity_id",r.cpL());o.put("level",r.cmZ());o.put("gfx_id",r.bwX());items.add(o);}});
 for(Map<String,Object> type:types)type.put("item_count",counts.getOrDefault(((Number)type.get("type_id")).intValue(),0));
 Map<String,Object> result=new LinkedHashMap<>();result.put("type_name_source","i18n_es.jar/texts_es.properties content.14.<type_id>");result.put("source","Native aLU type hierarchy and aLO cpA/type, cpL/rarity, cmZ/level, bwX/item icon graphics");result.put("types",types);result.put("items",items);Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(types.size()+" types; "+items.size()+" items");
 }
}
