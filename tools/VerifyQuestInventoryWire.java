import java.nio.ByteBuffer;
import java.util.Arrays;

/** Offline protocol proof against the unmodified installed native decoder. */
public final class VerifyQuestInventoryWire {
    public static void main(String[] args) {
        byte[] section = ByteBuffer.allocate(12).putShort((short)1).putInt(12686).putShort((short)25).putInt(0).array();
        qB decoded = new qB();
        ByteBuffer input = ByteBuffer.wrap(section);
        if (!decoded.aG(input) || input.hasRemaining() || decoded.Vt.afm.akG.size() != 1
                || decoded.Vt.afm.akG.get(0).abE != 12686 || decoded.Vt.afm.akG.get(0).aaO != 25)
            throw new AssertionError("Native QUEST section did not decode exactly");
        ByteBuffer output = ByteBuffer.allocate(decoded.DN());
        if (!decoded.aF(output) || !Arrays.equals(section, output.array()))
            throw new AssertionError("Native QUEST round trip differs");
        byte[] event = ByteBuffer.allocate(15).putLong(7L).put((byte)2).putInt(12686).putShort((short)25).array();
        cwN update = new cwN();
        if (!update.dp(event) || update.KU() != 7L || !update.eJA().hasNext()
                || update.eJA().next().gft() != fmM.sFw)
            throw new AssertionError("Native QUEST quantity event did not decode");
        System.out.println("PASS native qB/vh QUEST section + cwN13879 absolute quantity event");
    }
}
