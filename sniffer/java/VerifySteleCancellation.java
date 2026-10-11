import java.nio.ByteBuffer;
/** Verify the installed type-34 occupation cancellation carrier. */
public class VerifySteleCancellation {
    public static void main(String[] args) throws Exception {
        cyN message = new cyN();
        message.dp(ByteBuffer.allocate(15).put((byte)3).putShort((short)34).putLong(99L).putInt(0).array());
        if (message.d()!=12088 || message.eKk()!=3 || message.eLS()!=34 || message.eKl()!=99L || message.aLJ().length!=0)
            throw new AssertionError("Invalid native stele cancellation");
        var field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        var unsafe = (sun.misc.Unsafe)field.get(null);
        if (((blM)unsafe.allocateInstance(blM.class)).dwv()!=34) throw new AssertionError("Invalid native occupation type");
        System.out.println("PASS native cyN cancellation decoder and blM type34");
    }
}
