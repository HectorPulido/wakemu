import java.nio.file.*;
/** Compact original spell -> casting Lua identity; no geometry inference. */
public class ExportNativeCastScripts {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX r){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw r){}});
  StringBuilder out=new StringBuilder();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr raw){
   bPK spell=bPS.elL().IP(raw.d());
   out.append(raw.d()).append('\t').append(spell.cbH()).append('\n');
  }});
  Files.writeString(Path.of(args[0]),out.toString());
 }
}
