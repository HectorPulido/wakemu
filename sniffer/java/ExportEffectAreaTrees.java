import java.nio.file.*;
/** All installed effect-area roots and their native child closure, offline. */
public class ExportEffectAreaTrees extends ExportGrantedSpellEffectTrees {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){expressions.put(e.aZE(),e.cyi());}});
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa a){for(int ref:a.cku())effect(ref);}});
  Files.write(Path.of(args[0]),effects);
  System.out.println("Exported native effect-area closure: "+effects.size()+" effects");
 }
}
