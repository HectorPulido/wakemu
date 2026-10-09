import java.nio.file.*;import java.util.*;import com.google.gson.*;
public class RiftCatalogProbe {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> rows=new ArrayList<>();apw.bGL().a(new aLF(),new apB<aLF>(){public void load(aLF r){Map<String,Object> m=new LinkedHashMap<>();m.put("id",r.d());m.put("raw_cpb",r.cpb());m.put("raw_cpc",r.cpc());m.put("raw_rI",r.rI());m.put("raw_cpf",r.cpf());m.put("raw_cnn",r.cnn());List<Integer> refs=new ArrayList<>();for(aLI v:r.cpd())refs.add(v.cpi());m.put("raw_cpd_cpi",refs);List<Object> locations=new ArrayList<>();for(aLH v:r.cpe()){Map<String,Object> l=new LinkedHashMap<>();l.put("raw_arM",v.arM());l.put("raw_cnn",v.cnn());locations.add(l);}m.put("raw_cpe",locations);rows.add(m);}});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(rows));System.out.println("definitions="+rows.size());
 }
}
