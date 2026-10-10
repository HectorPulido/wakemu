import java.lang.reflect.*;
/** Executes the installed client's two independent hero fade completion gates. */
public final class VerifyHeroFadeGate {
    public static void main(String[] args) throws Exception {
        dbV controller = new dbV();
        Constructor<?> ctor = dbW.class.getDeclaredConstructors()[0];
        ctor.setAccessible(true);
        Object transition = ctor.newInstance(controller, null, null, null, null, 0L, (byte)0);
        Field completed = dbW.class.getDeclaredField("omI");
        completed.setAccessible(true);
        Field predicate = dbW.class.getDeclaredField("omJ");
        predicate.setAccessible(true);
        ark gate = (ark) predicate.get(transition);
        completed.setBoolean(transition, true);
        controller.kN(false);
        if (gate.isValid()) throw new AssertionError("12054 alone must not finish fade");
        controller.kN(true);
        if (!gate.isValid()) throw new AssertionError("guild synchronization must release completed fade");
        completed.setBoolean(transition, false);
        if (gate.isValid()) throw new AssertionError("guild synchronization alone must not finish fade");
        qH guild = new qH();
        if (!guild.aG(java.nio.ByteBuffer.wrap(new byte[6])) || guild.VD != null || guild.VE != 0)
            throw new AssertionError("empty guild remote codec");
        System.out.println("PASS native dbX requires local completion AND guild synchronization; qH empty guild is six zero bytes");
        System.exit(0);
    }
}
