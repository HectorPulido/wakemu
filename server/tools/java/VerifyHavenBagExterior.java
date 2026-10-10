import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Verify live exterior identity/coordinates with native cwG, ua and ama codecs. */
public class VerifyHavenBagExterior {
    public static void main(String[] args) throws Exception {
        byte[] packet = Files.readAllBytes(Path.of(args[0]));
        cwG message = new cwG();
        if (!message.dp(packet) || message.cie().size() != 1) {
            throw new IllegalArgumentException("Invalid native cwG bag record");
        }
        ByteBuffer frame = ByteBuffer.wrap(packet);
        frame.getShort(); frame.getLong();
        if (frame.getLong() != 3700L) throw new IllegalArgumentException("Wrong exterior template");
        byte[] entity = new byte[Short.toUnsignedInt(frame.getShort())];
        frame.get(entity);
        aBn packed = ama.gg(frame.getLong());
        ByteBuffer fields = ByteBuffer.wrap(entity);
        if (fields.get() != 2 || fields.get() != 2 || fields.getInt() != 11
                || fields.get() != 3 || fields.getInt() != 24) {
            throw new IllegalArgumentException("Wrong native fg section table");
        }
        fields.position(25);
        long world = fields.getLong();
        int x = fields.getInt(), y = fields.getInt();
        short z = fields.getShort();
        fields.get(); fields.get();
        ua owner = new ua();
        if (!owner.aG(fields) || fields.hasRemaining()) {
            throw new IllegalArgumentException("Invalid native ua owner payload");
        }
        if (packed.getX() != x || packed.getY() != y || packed.bdn() != z) {
            throw new IllegalArgumentException("Native exterior positions disagree");
        }
        if (args.length > 1) {
            cyT result = new cyT();
            if (!result.dp(Files.readAllBytes(Path.of(args[1]))) || !result.eLZ()
                    || result.eMb() || result.eMa() == null) {
                throw new IllegalArgumentException("Invalid native foreign bag entry result");
            }
        }
        System.out.println("Native exterior verified: world=" + world + " position=" + x + "," + y + "," + z
                + " account=" + owner.abO + " actor=" + owner.Vh + " name=" + owner.abP);
    }
}
