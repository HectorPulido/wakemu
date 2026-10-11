import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;

/** Decodes the server chooser fixture through the installed native cyB parser. */
public final class VerifyNationSelection {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            throw new IllegalArgumentException("Usage: VerifyNationSelection packet.bin fraction30 fraction31 fraction32 fraction33");
        }
        byte[] body = Files.readAllBytes(Path.of(args[0]));
        cyB packet = new cyB();
        if (packet.d() != 14006 || !packet.dp(body)) {
            throw new AssertionError("Native nation chooser rejected the packet");
        }
        ArrayList<cyC> entries = packet.eLD();
        if (entries.size() != 4) {
            throw new AssertionError("Chooser must offer exactly four nations");
        }
        ByteBuffer raw = ByteBuffer.wrap(body);
        if (raw.getInt() != 4) throw new AssertionError("Unexpected encoded count");
        for (int i = 0; i < entries.size(); i++) {
            cyC entry = entries.get(i);
            int nation = 30 + i;
            float expected = Float.parseFloat(args[i + 1]);
            if (entry.Xt() != nation || entry.eLE() != 0
                    || Math.abs(entry.eLF() - expected) > 0.000001f
                    || !entry.eLG().isEmpty() || entry.etZ() != 0
                    || !entry.eLH().isEmpty()) {
                throw new AssertionError("Invalid native chooser entry for nation " + nation);
            }
            if (raw.getInt() != nation || raw.getInt() != 0
                    || Float.floatToIntBits(raw.getFloat()) != Float.floatToIntBits(entry.eLF())
                    || raw.getInt() != 0 || raw.getInt() != 0 || raw.getInt() != 0) {
                throw new AssertionError("Unexpected native chooser wire fields");
            }
            System.out.println("PASS nation=" + nation + " population=" + entry.eLF()
                    + " treasury=0 governor=empty territories=0 diplomacy=empty");
        }
        if (raw.hasRemaining()) throw new AssertionError("Trailing bytes in chooser packet");
        System.out.println("PASS original cyB14006 decoder; nations30..33 only; nation34 absent");
    }
}
