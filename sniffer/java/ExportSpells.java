import java.nio.file.*;
import java.util.*;
public class ExportSpells {
 public static void main(String[] args)throws Exception{
  if (args.length != 2) throw new IllegalArgumentException("Usage: ExportSpells CLIENT_DIRECTORY OUTPUT_TSV");
  apw.bGL().dd("jar:file:"+Path.of(args[0]).resolve("contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<String> lines=new ArrayList<>();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr r){
   StringBuilder s=new StringBuilder();
   for(java.lang.reflect.Field f:aNr.class.getDeclaredFields())try{f.setAccessible(true);Object v=f.get(r);if(v instanceof Number||v instanceof Boolean)s.append(f.getName()).append('=').append(v).append('\t');}catch(Exception e){throw new RuntimeException(e);}
   s.append("criteria=").append(Base64.getEncoder().encodeToString(r.cvc().getBytes(java.nio.charset.StandardCharsets.UTF_8))).append("\t");
   lines.add(s.toString());
  }});
  Path output = Path.of(args[1]).toAbsolutePath();
  Files.createDirectories(output.getParent());
  Files.write(output,lines);
  System.out.println("spell records "+lines.size());
 }
}
