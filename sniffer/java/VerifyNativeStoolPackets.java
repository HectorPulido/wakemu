import java.nio.ByteBuffer;
import java.lang.reflect.Field;

/** Independent installed-client decoder checks; does not start the game client. */
public final class VerifyNativeStoolPackets {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        cth start = new cth();
        require(start.dp(ByteBuffer.allocate(19).put((byte) 1).putShort((short) 16)
                .putLong(25457).putLong(907).array()), "start decode");
        require(start.d() == 13579 && start.eKk() == 1 && start.eLS() == 16
                && start.eFo() == 25457 && start.fD() == 907, "start fields");
        for (byte phase : new byte[] {2, 3}) {
            cyN stop = new cyN();
            require(stop.dp(ByteBuffer.allocate(15).put(phase).putShort((short) 16)
                    .putLong(907).putInt(0).array()), "stop decode");
            require(stop.d() == 12088 && stop.eKk() == phase && stop.eLS() == 16
                    && stop.eKl() == 907 && stop.aLJ().length == 0, "stop fields");
        }
        bDV stool = new bDV();
        Field occupant = bDV.class.getDeclaredField("aEp");
        occupant.setAccessible(true);
        for (long actor : new long[] {907, 0}) {
            // fg framing: one field, slot 3, offset 6, repeated slot byte, long payload.
            byte[] overlay = ByteBuffer.allocate(15).put((byte) 1).put((byte) 3).putInt(6)
                    .put((byte) 3).putLong(actor).array();
            cwL update = new cwL();
            require(update.dp(ByteBuffer.allocate(25).putLong(25457).putShort((short) 15)
                    .put(overlay).array()), "object update decode");
            require(update.d() == 12344 && update.eEz() == 25457, "object update fields");
            stool.as(update.eJz());
            require(occupant.getLong(stool) == actor, "occupancy overlay");
        }
        for (QT action : QT.values()) {
            if (action.name().contains("SIT") || action.name().contains("STAND")) {
                System.out.println(action.name() + "=" + action.beb());
            }
        }
        System.out.println("PASS native stool start, stop phases 2/3 and occupied/free overlays");
    }
}
