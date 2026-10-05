import java.nio.file.*;
/** Original installed spell graphical definition, without game/UI execution. */
public final class ProbeNativeSpellVisualDefinition {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX r){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw r){}});
  for(String ref:args){bPK definition=bPS.elL().IP(Integer.parseInt(ref));
   if(definition==null)throw new AssertionError("Missing installed definition");
   System.out.println("reference="+definition.d()+" script="+definition.cbH()+" cwF="+definition.cwF()+" maxLevel="+definition.Fq());
  }
 }
}
