import java.nio.file.*;import java.util.*;import com.google.gson.*;
/** fyG.dYF: fyF.gtQ -> eVg.fa -> event fLG, no account/network. */
public class ExportNativeSpellElements {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX r){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw r){}});
  Map<String,Object> spells=new TreeMap<>();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr r){bPK spell=bPS.elL().IP(r.d());eVg element=eVg.fa(spell.gtQ());
   Map<String,Object> row=new LinkedHashMap<>();row.put("native_element",spell.gtQ());row.put("element_name",element==null?null:element.name());row.put("event_id",element==null?null:element.fLG());spells.put(Integer.toString(r.d()),row);}});
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(Map.of("source","Installed aNr/bPK/fyF.gtQ -> fyG.dYF/eVg.fa/fLG; offline","spells",spells))+"\n");
  System.out.println("Exported "+spells.size()+" native spell element events");
 }
}
