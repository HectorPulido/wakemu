import java.nio.file.*;import java.util.*;import java.lang.reflect.*;import com.google.gson.GsonBuilder;
public class ExportNativeSpellReferences {public static void main(String[]a)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 Set<Integer> ids=new TreeSet<>();apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr spell){ids.add(spell.d());}});int[] refs=ids.stream().mapToInt(Integer::intValue).toArray();
 Files.writeString(Path.of(a[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source","Installed aNr native spell definitions consumed by bPS.IP/fyH, offline","references",refs))+"\n");System.out.println("Exported "+refs.length+" native spell references");}}
