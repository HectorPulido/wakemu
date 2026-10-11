import java.nio.ByteBuffer;
import com.google.protobuf.CodedInputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/** Verify Python-produced attachment replies, ProtoItem and BAGS legacy options. */
public final class VerifyNativeSublimationAttachments {
    static void check(fpI state, int basic, int special, String source) {
        if (state == null || state.ahz() != basic || state.ahB() != special)
            throw new AssertionError(source + " lost independent native attachment slots");
    }
    static boolean hasField(byte[] encoded, int number) throws Exception {
        CodedInputStream input = CodedInputStream.newInstance(encoded);
        for (int tag; (tag = input.readTag()) != 0;) {
            if ((tag >>> 3) == number) return true;
            if (!input.skipField(tag)) break;
        }
        return false;
    }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        for (String phase : new String[] {"special_only", "coexist", "remove_basic", "remove_special"}) {
            int basic = phase.equals("remove_basic") || phase.equals("special_only") ? 0 : 27111;
            int special = phase.equals("remove_special") ? 0 : 24130;
            cxA reply = phase.equals("coexist") || phase.equals("special_only") ? new cxv() : new cxw();
            if (!reply.dp(Files.readAllBytes(root.resolve(phase + ".reply"))) || reply.eKx().aIm())
                throw new AssertionError("Native reply rejected " + phase);
            check(reply.eKB(), basic, special, phase + " reply");
            kX item = kX.bG(Files.readAllBytes(root.resolve(phase + ".item")));
            check(fpK.g(item.adU()), basic, special, phase + " ProtoItem/reconnect");
            if (phase.equals("special_only")) {
                if (item.adU().ahu() != 0 || !reply.eKB().dZr().isEmpty()
                    || hasField(Files.readAllBytes(root.resolve(phase + ".item")), 56))
                    throw new AssertionError("Minimal special fpI invented sockets or element selection");
            }
            ByteBuffer bytes = ByteBuffer.wrap(Files.readAllBytes(root.resolve(phase + ".legacy")));
            yp legacy = new yp();
            if (!legacy.aG(bytes) || bytes.hasRemaining())
                throw new AssertionError("Native BAGS legacy option rejected " + phase);
            check(fpK.d(legacy), basic, special, phase + " BAGS legacy option");
            check(fpK.eQ(fpK.e(reply.eKB())), basic, special, phase + " native roundtrip");
            System.out.println("PASS " + phase + " BASIC=" + basic + " SPECIAL=" + special
                + " reply/ProtoItem/BAGS/native roundtrip");
        }
    }
}
