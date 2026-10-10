import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.ByteBuffer;
/** Offline native eHj decode for positive-ID bje fighter updates. */
public class ProbeNativeSummonFighterStats {
    public static void main(String[] args) throws Exception {
        eHj data = new eHj();
        byte[] payload = Files.readAllBytes(Path.of(args[0]));
        ByteBuffer buffer = ByteBuffer.wrap(payload);
        int format = buffer.get() & 255;
        var select = eHd.class.getDeclaredMethod("a", eHe.class);
        select.setAccessible(true);
        for (eHe field : eHf.values()[format].fuK()) {
            gp part = (gp) select.invoke(data, field);
            if (!part.aG(buffer)) throw new AssertionError("Rejected " + field);
        }
        if (buffer.hasRemaining()) throw new AssertionError("Trailing native bytes");
        data.ew(payload);
        if (args.length > 1 && data.ftc().SX != Boolean.parseBoolean(args[1]))
            throw new AssertionError("Native AI control mismatch");
        if (data.ftb().XP == null) throw new AssertionError("Missing native property counters");
        eHN<ffe> properties = new eHN<>();
        if (!properties.b(data.ftb().XP.XT)) throw new AssertionError("Native property decode");
        if (!properties.a(ffe.Ua(40))) throw new AssertionError("Capture property missing");
        if (data.fsS().Vc != 901L) throw new AssertionError("Positive summon identity");
        if (bje.class.getMethod("dpT").getReturnType() != eHd.class)
            throw new AssertionError("bje native fighter data interface");
        System.out.println("PASS native eHj fighter format2 preserves positive summon ID901");
    }
}
