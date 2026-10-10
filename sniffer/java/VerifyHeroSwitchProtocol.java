import java.nio.*;
import java.util.*;
/** Native switch acknowledgment and completion request; no graphical mutations. */
public final class VerifyHeroSwitchProtocol {
    public static void main(String[] args) throws Exception {
        long target = 6;
        cwE packet = new cwE();
        packet.dp(ByteBuffer.allocate(9).put((byte)0).putLong(target).array());
        if (packet.d() != 13440 || packet.aXR() != target
            || fkM.fW(packet.bkq()) != fkM.suM)
            throw new AssertionError("native successful switch acknowledgment");
        for (fkM result : fkM.values())
            System.out.println("result=" + result.aKg() + " " + result.name());
        csF completion = new csF(target);
        byte[] wire = completion.aWH();
        System.out.println("completion opcode=" + completion.d()
            + " native envelope=" + java.util.HexFormat.of().formatHex(wire));
        if (completion.d() != 12054)
            throw new AssertionError("native switch completion opcode");
        byte[] body = ByteBuffer.allocate(8).putLong(target).array();
        if (wire.length < 8 || !Arrays.equals(body,
            Arrays.copyOfRange(wire, wire.length - 8, wire.length)))
            throw new AssertionError("native switch completion target");
        if (args.length == 2) {
            aTJ account = new aTJ();
            account.oh(1);
            java.lang.reflect.Field accountField = aTx.class.getDeclaredField("hsh");
            accountField.setAccessible(true);
            accountField.set(aTx.cWt(), account);
            flz.sxg.b(new flr(150, 0, (byte)0, 0));
            biB[] actors = new biB[2];
            for (int i = 0; i < 2; i++) {
                cue admission = new cue();
                admission.dp(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[i])));
                actors[i] = new biB(false);
                byte[] entity = admission.eGo();
                actors[i].dtj().a(actors[i].dtj().fsS(), entity);
                actors[i].dtj().a(actors[i].dtj().fsR(), entity);
                actors[i].dtj().a(actors[i].dtj().fsQ(), entity);
                fkK.suH.d(actors[i].Xi(), actors[i]);
            }
            bns slots = new bns();
            for (int i = 0; i < 2; i++) {
                java.lang.reflect.Field field = bns.class.getDeclaredField(i == 0 ? "iBF" : "iBG");
                field.setAccessible(true);
                ((bnr)field.get(slots)).a(new bit(actors[i], null));
            }
            slots.ka(actors[1].Sn());
            bnr main = (bnr)slots.eH("mainSlot");
            bnr hero = (bnr)slots.eH("heroSlot0");
            if (main.dyy().dgD() != actors[1] || hero.dyy().dgD() != actors[0]
                || fkK.suH.sY(actors[0].Sn()) != actors[0]
                || fkK.suH.sY(actors[1].Sn()) != actors[1])
                throw new AssertionError("native company slot swap or registry identity");
            System.out.println("PASS actual bns.ka swaps existing company slots and preserves both owned actor objects");
        }
        System.out.println("PASS native13440 result0 target6 and native12054 completion identity");
        System.exit(0);
    }
}
