import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

/** Verify account artifacts through the installed flY/eDP/flX authority. */
public final class VerifyExplorationSecrets {
    private static final Set<Integer> ITEMS = Set.of(
        18722,20784,18384,19434,21598,21599,18103,18385,18591,19113,22087);
    public static void main(String[] args) throws Exception {
        byte[] body = Files.readAllBytes(Path.of(args[0]));
        ByteBuffer envelope = ByteBuffer.wrap(body);
        if (envelope.getInt() != 1 || envelope.getInt() != 4)
            throw new AssertionError("Expected account INVENTORY section 4");
        long account = 123L;
        flY inventory = new flY();
        eDP.foL().a(account, inventory);
        byte[] section = new byte[envelope.remaining()];
        envelope.get(section);
        for (int repeat = 0; repeat < 2; repeat++) {
            ByteBuffer payload = ByteBuffer.wrap(section);
            inventory.a(account, payload);
            if (payload.hasRemaining() || inventory.geO().size() != 11)
                throw new AssertionError("Expected 11 account artifacts");
            for (int ref : ITEMS)
                if (inventory.Rh(ref) != 1 || flX.aj(account, ref) != 1)
                    throw new AssertionError("Artifact unavailable " + ref);
        }
        System.out.println("PASS native account section4/flY/eDP/flX: 11 artifacts; idempotent restore");
    }
}
