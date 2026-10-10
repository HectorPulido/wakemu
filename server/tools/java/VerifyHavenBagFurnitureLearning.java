import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Validate furniture learning bodies with the installed native client classes. */
public class VerifyHavenBagFurnitureLearning {
    private static byte[] body(Nx request, int opcode, int length) {
        byte[] wire = request.aWH();
        ByteBuffer buffer = ByteBuffer.wrap(wire);
        if (buffer.getInt() != wire.length || buffer.get() != 3
                || Short.toUnsignedInt(buffer.getShort()) != opcode
                || buffer.remaining() != length) {
            throw new IllegalArgumentException("Unexpected native routed request framing");
        }
        byte[] body = new byte[length];
        buffer.get(body);
        return body;
    }

    public static void main(String[] args) throws Exception {
        byte[] reply = Files.readAllBytes(Path.of(args[0]));
        czi notification = new czi();
        if (!notification.dp(reply) || notification.eMg().isEmpty() || !notification.aHi()) {
            throw new IllegalArgumentException("Invalid native furniture learned notification");
        }
        byte[] component = Files.readAllBytes(Path.of(args[1]));
        ByteBuffer input = ByteBuffer.wrap(component);
        if (input.getInt() != 1 || input.getInt() != 11) {
            throw new IllegalArgumentException("Expected account FURNITURE section");
        }
        fvr known = new fvr();
        known.a(7L, input);
        if (input.hasRemaining()) throw new IllegalArgumentException("Trailing account component bytes");
        for (int reference : notification.eMg()) {
            if (!known.Yp(reference)) throw new IllegalArgumentException("Missing learned reference " + reference);
        }
        byte[] learn = body(new cqd(80L, new bIx(466)), 13220, 12);
        if (!Arrays.equals(learn, ByteBuffer.allocate(12).putInt(466).putLong(80L).array())) {
            throw new IllegalArgumentException("Learning request does not match exact action/UID schema");
        }
        byte[] deploy = body(new crM(6293, 2770L, 1, 2, (short) 0, 3), 13826, 26);
        byte[] expected = ByteBuffer.allocate(26).putInt(6293).putLong(2770L)
                .putInt(1).putInt(2).putShort((short) 0).putInt(3).array();
        if (!Arrays.equals(deploy, expected)) throw new IllegalArgumentException("Placement schema mismatch");
        System.out.println("Native czi/fvr replies verified for " + notification.eMg()
                + "; cqd13220=12 bytes (action/UID), crM13826=26 bytes (reference/template/position).");
    }
}
