import java.nio.file.Path;

/** Installed state grades/timing only; no reconstructed fight or score inputs. */
public final class ProbeNativeBossScoreStateGrades {
    static int checks;

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
        checks++;
    }

    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        for (int reference : new int[]{8988, 9031, 7110}) {
            bQh original = (bQh) fyZ.guX().aax(reference);
            check(original != null, "installed original state " + reference);
            bQh selected = (bQh) original.cu((short) (reference == 8988 ? 10 : 1));
            check(selected.cmZ() == (reference == 8988 ? 10 : 1), "actual native grade " + reference);
            check(selected.gtL() == -1 && selected.guH() == 0, "native indefinite turn-only marker " + reference);
            for (eVn effect : selected.guJ()) {
                check(effect.awM() == 400, "original marker child stays cosmetic " + effect.aZE());
            }
            System.out.println("state=" + reference + " grade=" + selected.cmZ()
                + " duration=" + selected.gtL() + " realtime=" + selected.guH());
        }
        System.out.println("PASS " + checks + " native boss score/difficulty state checks");
    }
}
