import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
/** Original receiver and chat manager, with neutral/no-office/no-BG fixtures. */
public final class VerifyNationChatReceive {
    static void set(Object object, String name, Object value) throws Exception {
        Field field = object.getClass().getDeclaredField(name);
        field.setAccessible(true); field.set(object, value);
    }
    static final class NoBattle extends fAh {
        final fAg state = new fAg() {
            public boolean eyd() { return false; }
            public boolean edD() { return false; }
            public boolean eyc() { return false; }
            public boolean eyf() { return false; }
        };
        NoBattle() { tCZ = this; }
        public fAg mP(long id) { return state; }
    }
    public static void main(String[] args) throws Exception {
        try {
            TJ.btr.a(() -> TP.fl(0));
            aTJ account = new aTJ(); account.oh(5); set(aTx.cWt(), "hsh", account);
            frk.a(new aHd());
            biB actor = new biB(false); actor.dA(5); set(aTx.cWt(), "hsi", actor);
            NoBattle battle = new NoBattle();
            if (actor.fqe().etJ() != frk.sZj || actor.fqe().etW() != null || battle.mP(actor.arM()).eyc())
                throw new AssertionError("fixture must be neutral, no office, no battleground");
            EnumMap<aOd,aOb> channels = new EnumMap<>(aOd.class);
            List<aOa> received = new ArrayList<>();
            for (aOd channel : new aOd[]{aOd.exa, aOd.exd}) {
                aOb pipe = new aOb(channel) { public void jp(String text) {} };
                pipe.a(new aOc() {
                    public void b(aOa row) { received.add(row); }
                    public void b(aOb pipe, aNR event) {}
                });
                channels.put(channel, pipe);
            }
            set(aNZ.czR(), "eww", channels);
            NQ[] packets = {new Oh(), new NO()};
            aOd[] expected = {aOd.exa, aOd.exd};
            for (int i=0; i<packets.length; i++) {
                if (!packets[i].dp(Files.readAllBytes(Path.of(args[i]))))
                    throw new AssertionError("native response decode rejected");
                chc.eCN().b(packets[i]);
                aOa row = received.get(i);
                if (row.czW()!=expected[i] || !row.getMessage().equals("hola native"))
                    throw new AssertionError("original receiver delivered incorrect row");
                if (channels.get(expected[i]).cAj().size()!=1)
                    throw new AssertionError("native chat manager lost message");
                if (actor.fqe().etJ()!=frk.sZj || actor.fqe().etW()!=null || battle.mP(actor.arM()).eyc())
                    throw new AssertionError("receive mutated nation, office or battleground");
                System.out.println("PASS opcode="+packets[i].d()+" nativeChannel="+row.czW()+
                    " message="+row.getMessage()+" neutral=true office=null battleground=false");
            }
            System.exit(0);
        } catch (Throwable failure) { failure.printStackTrace(); System.exit(1); }
    }
}
