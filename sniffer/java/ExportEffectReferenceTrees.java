import java.nio.file.*;

/** Explicit effect-reference closure using the shared full metadata exporter. */
public class ExportEffectReferenceTrees extends ExportGrantedSpellEffectTrees {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
            + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() {
            public void load(aKX row) { groups.put(row.d(), row.cku()); }
        });
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw row) { expressions.put(row.aZE(), row.cyi()); }
        });
        for (String text : Files.readAllLines(Path.of(args[0]))) effect(Integer.parseInt(text));
        Files.write(Path.of(args[1]), effects);
        System.out.println("Exported " + effects.size() + " explicit effect definitions");
    }
}
