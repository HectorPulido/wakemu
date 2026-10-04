import java.nio.file.Path;
/** Offline native damage table for unarmed item2145; compile against client/lib/*. */
public class ExportUnarmedCombat {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        eVn damage = bcA.dcX().AH(3597);
        if (damage.awM() != 3 || damage.fKT() != null) throw new IllegalStateException("Unexpected native damage branch");
        System.out.print("[");
        for (short level=1;level<=200;level++) {
            if (level>1) System.out.print(",");
            System.out.print(damage.a(0,level,eVh.rpA));
        }
        System.out.println("]");
    }
}
