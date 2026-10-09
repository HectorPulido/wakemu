import java.nio.file.*;
/** Reuse the native spell-effect decoder without inventing spell containers. */
public class ExportAptitudeEffectClosure {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX row){ExportSpellEffectTrees.groups.put(row.d(),row.cku());}});
        apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw row){ExportSpellEffectTrees.expressions.put(row.aZE(),row.cyi());}});
        apw.bGL().a(new aJX(),new apB<aJX>(){public void load(aJX row){for(int ref:row.cku())ExportSpellEffectTrees.effect(ref);}});
        Files.write(Path.of(args[0]),ExportSpellEffectTrees.effects);
        System.out.println("Exported "+ExportSpellEffectTrees.effects.size()+" native aptitude closure effects");
    }
}
