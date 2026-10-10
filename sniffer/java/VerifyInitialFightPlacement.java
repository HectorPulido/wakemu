import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Installed-client placement decoders, using actual server-generated bodies. */
public class VerifyInitialFightPlacement {
    public static void main(String[] args) throws Exception {
        Path folder = Path.of(args[0]);
        int fight = Integer.parseInt(args[1]);
        cvq positions = new cvq();
        positions.dp(Files.readAllBytes(folder.resolve("13652.bin")));
        cvb admission = new cvb();
        admission.dp(Files.readAllBytes(folder.resolve("12847.bin")));
        cvl timer = new cvl();
        timer.dp(Files.readAllBytes(folder.resolve("13684.bin")));
        cuX complete = new cuX();
        complete.dp(Files.readAllBytes(folder.resolve("13026.bin")));
        if (positions.bhe() != fight || admission.bhe() != fight
                || timer.bhe() != fight || complete.bhe() != fight
                || !positions.eHN() || admission.eHb() != 2
                || admission.eHa() != positions.eHO().size() || timer.eHH() != 30000) {
            throw new AssertionError("initial placement consistency");
        }
        for (int index = 0; index < admission.eHa(); index++) {
            if (!positions.eHO().containsKey(admission.Mj(index))) {
                throw new AssertionError("admitted actor missing placement position");
            }
        }
        System.out.println("PASS native initial placement: fight=" + fight
                + ", actors=" + admission.eHa() + ", phase=" + admission.eHb()
                + ", identities=" + Arrays.toString(admission.eHp())
                + ", timer=" + timer.eHH() + ", creation complete");
    }
}
