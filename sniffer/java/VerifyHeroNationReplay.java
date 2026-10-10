import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
/** Exercises the real nation component consumer and cached hero eligibility. */
public final class VerifyHeroNationReplay {
    static void set(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(target, value);
    }
    public static void main(String[] args) throws Exception {
        try {
            aTJ account = new aTJ(); account.oh(5); set(aTx.cWt(), "hsh", account);
            byte[] company = ByteBuffer.allocate(49).putInt(1).putInt(1)
                .putLong(5).putLong(4).putInt(0).putLong(0).putInt(0)
                .putInt(1).put((byte)1).array();
            eDP.foL().d(5, company);
            frk.a(new aHd()); frk nation = frk.XE(30); frp.sZy.o(nation); frk neutral = frk.sZj;
            biB actor = new biB(false); biz.dpY().al(actor);
            actor.fX(true); actor.fU(false);
            set(aTx.cWt(), "hsi", actor);
            for (int i = 0; i < args.length; i++) {
                cyo packet = new cyo(); packet.dp(Files.readAllBytes(Path.of(args[i])));
                eHk decoded = new eHk(); decoded.ew(packet.eLp());
                if (packet.eLp()[0] != 22) throw new AssertionError("expected format22");
                actor.dtj().a(actor.dtj().fvS(), packet.eLp());
                bit row = new bit(actor, null);
                boolean eligible = (Boolean)row.eH("isInCompanyNation");
                int expected = i == 0 ? 30 : 0;
                System.out.println("format22 native=" + decoded.fvS().Wi
                    + " actor=" + actor.Xt() + " cached=" + biz.dpY().an(actor)
                    + " companyEligible=" + eligible);
                if (decoded.fvS().Wi != expected || actor.Xt() != expected
                    || biz.dpY().an(actor) != expected || eligible != (i != 0))
                    throw new AssertionError("native nation transition failed");
            }
            System.out.println("PASS actual15548 original nation30 blocks heroes; adapted nation0 restores native company eligibility");
            System.exit(0);
        } catch (Throwable error) { error.printStackTrace(); System.exit(1); }
    }
}
