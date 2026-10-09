import java.nio.file.Files;
import java.nio.file.Path;
/** Offline native eHj decode for positive-ID bje fighter updates. */
public class ProbeNativeSummonFighterStats {
    public static void main(String[] args) throws Exception {
        eHj data = new eHj();
        data.ew(Files.readAllBytes(Path.of(args[0])));
        if (data.fsS().Vc != 901L) throw new AssertionError("Positive summon identity");
        if (bje.class.getMethod("dpT").getReturnType() != eHd.class)
            throw new AssertionError("bje native fighter data interface");
        System.out.println("PASS native eHj fighter format2 preserves positive summon ID901");
    }
}
