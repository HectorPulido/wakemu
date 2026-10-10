import java.nio.file.Files;
import java.nio.file.Path;

/** Decode regular NPC admission with the installed client, without a summon. */
public final class VerifyRiftNpcAdmission {
    public static void main(String[] args) throws Exception {
        cvg message = new cvg();
        int fight = Integer.parseInt(args[1]);
        long actor = Long.parseLong(args[2]);
        if (!message.dp(Files.readAllBytes(Path.of(args[0])))
                || message.d() != 13091 || message.bhe() != fight
                || message.OO() != actor || message.eHC() != 0
                || message.bcM() != 1 || message.eHD() != null
                || message.eHA().length == 0 || message.eHB().length != 2) {
            throw new AssertionError("Invalid ordinary NPC admission");
        }
        System.out.println("PASS cvg13091 ordinary NPC, enemy team, no controller");
    }
}
