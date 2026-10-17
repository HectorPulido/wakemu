import java.nio.file.Files;
import java.nio.file.Path;
import com.jogamp.opengl.GL;
import com.jogamp.opengl.GL2;
import java.lang.reflect.Proxy;
import java.util.Map;
import java.util.Arrays;

/** Detached original native movement queue probe; never edits client classes. */
public final class VerifyPilotMovementQueue {
    static final class Graphic extends beS {
        Graphic() { super(null); }
        public void dgT() { }
        public void dhg() { }
    }
    static final class Surface extends avR {
        Surface() { super(0L, "", false); }
        public boolean b(GL gl) { return false; }
        public void g(GL2 gl) { }
        public void g(GL gl) { }
        public void h(aqO value) { }
        public void i(aqO value) { }
        public boolean aQf() { return false; }
        public boolean c(GL gl) { return false; }
    }
    static class Movement extends aUY {
        final big actor;
        volatile boolean completed;
        Movement(cvP packet, big actor) {
            super(packet.cbc(), packet.eIc().aKg(), packet.awM(), packet.bhe(),
                  packet.OO(), packet.eIC(), packet.bgl(), aAS.wL(packet.eIB()), false);
            this.actor = actor;
        }
        public big iA(long id) { return id == actor.Sn() ? actor : null; }
        public buQ cjD() { return null; }
        protected void cbj() { super.cbj(); completed = true; }
    }

    public static void main(String[] args) throws Exception {
        org.apache.log4j.BasicConfigurator.configure();
        var unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        unsafeField.setAccessible(true);
        var unsafe = (sun.misc.Unsafe)unsafeField.get(null);
        VerifyCombatReconstructionSlice.set(afw.bzi(), "bVh", unsafe.allocateInstance(Surface.class));
        for (var field : aGY.class.getDeclaredFields()) {
            if (field.getType() == fPS.class) {
                field.setAccessible(true);
                fPS color = (fPS)field.get(null);
                var colorsField = fPT.class.getDeclaredField("vdA");
                colorsField.setAccessible(true);
                ((java.util.Map<String,awi>)colorsField.get(fPT.vdz)).put(color.getName(), awe.dmp);
            }
        }
        aHo input = (aHo)unsafe.allocateInstance(aHo.class);
        VerifyCombatReconstructionSlice.set(input, "dXq", new java.util.Stack<aJp>());
        VerifyCombatReconstructionSlice.set(aGZ.cfK(), "bNp", input);
        cvP packet = new cvP();
        VerifyCombatReconstructionSlice.check(packet.dp(Files.readAllBytes(Path.of(args[0]))),
                                             "native movement decode");
        bjo actor = new bjo();
        actor.dA(packet.OO());
        Graphic graphic = (Graphic)unsafe.allocateInstance(Graphic.class);
        VerifyCombatReconstructionSlice.set(graphic, "hPP", actor);
        add duration = (add)Proxy.newProxyInstance(add.class.getClassLoader(), new Class[]{add.class},
            (p,m,a)->switch(m.getName()) {
                case "a" -> m.getReturnType() == int.class ? 1 : null;
                case "bwk" -> -1;
                case "bwl" -> false;
                default -> null;
            });
        adx animation = (adx)Proxy.newProxyInstance(adx.class.getClassLoader(), new Class[]{adx.class},
            (p,m,a)->duration);
        VerifyCombatReconstructionSlice.set(graphic, "cjB", animation);
        VerifyCombatReconstructionSlice.set(graphic, "cjG", 1f);
        VerifyCombatReconstructionSlice.set(actor, "hQB", graphic);
        int[] origin = args.length > 2
            ? new int[]{Integer.parseInt(args[2]), Integer.parseInt(args[3]), Integer.parseInt(args[4])}
            : packet.bgl().bDV();
        actor.T(origin[0], origin[1], (short)origin[2]);
        VerifyCombatReconstructionSlice.check(Arrays.equals(origin, packet.bgl().bDV()),
                                             "explicit initial actor position equals native path origin");
        Movement action = new Movement(packet, actor);
        aAk.bUZ().start();
        aER queue = new aER();
        queue.c(action);
        VerifyCombatReconstructionSlice.check(!action.completed && actor.baM().equals(new aBn(origin)),
                                             "received movement has not executed before fence");
        queue.cbu();
        for (int attempt = 0; attempt < 100 && (!action.completed || !queue.cbt().isEmpty()); attempt++)
            Thread.sleep(10);
        VerifyCombatReconstructionSlice.check(action.completed, "original movement callback completed");
        VerifyCombatReconstructionSlice.check(queue.cbt().isEmpty(), "original FIFO drained after completion");
        int[] endpoint = packet.bgl().bDW();
        VerifyCombatReconstructionSlice.check(actor.baM().equals(new aBn(endpoint)), "original actor endpoint");
        if (args.length > 1) Files.writeString(Path.of(args[1]), VerifyCombatReconstructionSlice.json(Map.of(
            "completed_normally", true, "opcode", 13624, "action_id", packet.cbc(),
            "actor_id", actor.Sn(), "initial_position", origin, "executed_position", endpoint,
            "native_path", packet.bgl().bDX(), "native_completed_action_ids", new int[]{packet.cbc()},
            "queue_drained", queue.cbt().isEmpty(),
            "scope", "original aUY/beS/acS/big endpoint and aAp/aAk/aER completion; headless reset and duration fixtures; no rendering")) + "\n");
        System.out.println("PASS original movement endpoint and actual native timer/FIFO completion");
        System.exit(0);
    }
}
