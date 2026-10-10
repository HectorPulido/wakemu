import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Decode the exact rK world-property component with the installed client. */
public final class VerifyExplorationMovementProperties {
    public static void main(String[] args) throws Exception {
        ByteBuffer bytes = ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
        rK component = new rK();
        if (!component.aG(bytes) || bytes.hasRemaining() || component.XP == null)
            throw new AssertionError("Incomplete world-property component");
        eHN<eHQ> authority = new eHN<>();
        for (int repeat = 0; repeat < 2; repeat++) {
            authority.b(component.XP.XT);
            if (authority.aZm().size() != 4)
                throw new AssertionError("Unexpected world property grant");
            for (int id : new int[] {85, 105, 117, 118}) {
                eHQ property = eHQ.Qm(id);
                if (!authority.a(property) || authority.b(property) != 1 || property.fxg() != null)
                    throw new AssertionError("Wrong exploration property " + id);
            }
        }
        System.out.println("PASS native rK/rN/wU/eHN: four exploration powers; idempotent restore");
    }
}
