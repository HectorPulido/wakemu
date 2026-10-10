import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Native cwG/byZ state parser oracle; graphics registration requires a scene. */
public class VerifyHavenBagFurnitureWorld {
    public static void main(String[] args) throws Exception {
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        cwG packet = new cwG();
        if (!packet.dp(raw) || packet.cie().isEmpty()) throw new IllegalArgumentException("Empty dynamic packet");
        ByteBuffer input = ByteBuffer.wrap(raw);
        int count = input.getShort();
        for (int i = 0; i < count; i++) {
            long instance = input.getLong();
            long template = input.getLong();
            byte[] dynamic = new byte[Short.toUnsignedInt(input.getShort())];
            input.get(dynamic);
            aBn position = ama.gg(input.getLong());
            ByteBuffer part = ByteBuffer.wrap(dynamic);
            if (part.get() != 1 || part.get() != 3 || part.getInt() != 6 || part.get() != 0) {
                throw new IllegalArgumentException("Unexpected furniture part layout");
            }
            int x = part.getInt(), y = part.getInt();
            short z = part.getShort();
            int direction = Byte.toUnsignedInt(part.get());
            long owner = part.getLong();
            boolean virtual = part.get() == 1;
            byZ object;
            if (part.remaining() == 4) object = new bAs();
            else if (!part.hasRemaining()) object = new bDc();
            else throw new IllegalArgumentException("Invalid furniture subclass tail");
            object.aWs();
            object.as(dynamic);
            object.dA(instance);
            object.ld(template);
            if (object.Sn() != instance || object.dVR() != template || object.Xi() != owner
                    || object.bcz() != x || object.bcA() != y || object.bcB() != z
                    || object.bcy().wp() != direction || object.dSB() != virtual
                    || position.getX() != x || position.getY() != y || position.bdn() != z) {
                throw new IllegalArgumentException("Native furniture state mismatch");
            }
            for (fj parsed : object.zj()) {
                if (parsed.zr()) throw new IllegalArgumentException("Native furniture part parser rejected state");
            }
            System.out.println("Native " + object.getClass().getSimpleName() + " instance=" + instance
                    + " template=" + template + " owner=" + owner + " position=" + x + "," + y + "," + z);
        }
        if (input.hasRemaining()) throw new IllegalArgumentException("Trailing cwG data");
        if (args.length > 1) {
            cwH removal = new cwH();
            if (!removal.dp(Files.readAllBytes(Path.of(args[1]))) || removal.eJx().isEmpty()) {
                throw new IllegalArgumentException("Invalid native removal");
            }
        }
        System.out.println("cwG13664 and byZ furniture state verified; rendering requires cET scene registration.");
    }
}
