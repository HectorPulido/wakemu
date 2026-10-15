import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Offline original-client HP-only versus complete postfight limit refresh. */
public final class ProbePostfightHealthLimits {
    public static void main(String[] args) throws Exception {
        byte[] envelope = Files.readAllBytes(Path.of(args[0]));
        ByteBuffer payload = ByteBuffer.wrap(envelope);
        long actorId = payload.getLong();
        int size = payload.getShort();
        if (size != payload.remaining() || payload.get() != 3) {
            throw new AssertionError("Expected owned format3 refresh envelope");
        }
        payload.position(10 + 39);
        tA snapshot = new tA();
        if (!snapshot.aG(payload)) throw new AssertionError("Native tA rejected snapshot");
        ffh live = new ffh();
        if (!live.b(snapshot)) throw new AssertionError("Native ffh rejected snapshot");
        fff hp = live.e(ffw.sgC);
        int current = hp.aYS();
        int maximum = hp.aYU();
        // Reproduce the reported HUD bounds without altering the server fixture.
        hp.or(Integer.MAX_VALUE);
        hp.on(current);
        if (hp.aYS() != current || hp.aYU() != Integer.MAX_VALUE) {
            throw new AssertionError("Failed to reproduce HP-only stale maximum");
        }
        // Native format10's HP component supplies only current, not maximum.
        hp.on(current);
        if (hp.aYU() != Integer.MAX_VALUE) {
            throw new AssertionError("HP-only update unexpectedly repaired maximum");
        }
        if (!live.b(snapshot) || live.e(ffw.sgC) != hp
                || hp.aYS() != current || hp.aYU() != maximum) {
            throw new AssertionError("Post-bootstrap owned limit refresh failed");
        }
        System.out.println("PASS original ffh/tA actor=" + actorId + " HP="
                + current + "/" + maximum + " stale INTMAX cleared on same native object");
    }
}
