import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/** Original logical displacement application on exact server bytes, headless. */
public final class VerifyPilotDisplacementQueue {
    static final java.util.concurrent.atomic.AtomicInteger errors = new java.util.concurrent.atomic.AtomicInteger();
    static final class Graphic extends beS {
        Graphic() { super(null); }
        public void dgT() { }
        public void dhg() { }
        public void e(float x, float y, float z) { }
        // big.b updates original eGj position before requesting this visual
        // reposition. Do not replace the logical actor position operation.
        public void a(aBn cell, boolean one, boolean two, boolean three) { }
    }
    static final class Actor extends bjo {
        final Qf manager = new VerifyCombatReconstructionSlice.StateCollection();
        public Qf bax() { return manager; }
    }
    static final class Application extends aVo {
        final buQ world;
        final Map<Long,Actor> actors;
        volatile boolean completed;
        Application(cvX packet, eZR runner, Map<Long,Actor> actors, PN context) {
            super(packet.cbc(), packet.eId(), packet.eII(), packet.bhe(), runner, packet.eIK());
            this.actors = actors;
            world = (buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(), new Class[]{buQ.class},
                (p,m,a)->switch(m.getName()) {
                    case "bbg" -> context;
                    case "kq" -> actors.get((Long)a[0]);
                    case "equals" -> p == a[0];
                    default -> null;
                });
        }
        protected buQ cjD() { return world; }
        public big iA(long id) { return actors.get(id); }
        // The native effect animation script requires incompatible graphics/
        // Lua libraries. Skip that visual wait only; original aVo.cbj/cYg and
        // the decoded original displacement runner perform logical execution.
        public long cby() { cYc(); return 0; }
        public void cbj() { super.cbj(); completed = true; }
    }
    static sun.misc.Unsafe setup() throws Exception {
        org.apache.log4j.BasicConfigurator.configure();
        org.apache.log4j.Logger.getRootLogger().addAppender(new org.apache.log4j.AppenderSkeleton() {
            protected void append(org.apache.log4j.spi.LoggingEvent event) {
                if (event.getLevel().isGreaterOrEqual(org.apache.log4j.Level.ERROR)) errors.incrementAndGet();
            }
            public void close() { }
            public boolean requiresLayout() { return false; }
        });
        var field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        var unsafe = (sun.misc.Unsafe)field.get(null);
        VerifyCombatReconstructionSlice.set(afw.bzi(), "bVh",
            unsafe.allocateInstance(VerifyPilotMovementQueue.Surface.class));
        var colors = fPT.class.getDeclaredField("vdA"); colors.setAccessible(true);
        for (var colorField : aGY.class.getDeclaredFields()) {
            if (colorField.getType() == fPS.class) {
                colorField.setAccessible(true);
                fPS color = (fPS)colorField.get(null);
                ((Map<String,awi>)colors.get(fPT.vdz)).put(color.getName(), awe.dmp);
            }
        }
        return unsafe;
    }
    static Actor actor(sun.misc.Unsafe unsafe, long id, int[] cell) throws Exception {
        Actor actor = new Actor(); actor.dA(id);
        Graphic graphic = (Graphic)unsafe.allocateInstance(Graphic.class);
        VerifyCombatReconstructionSlice.set(graphic, "hPP", actor);
        VerifyCombatReconstructionSlice.set(actor, "hQB", graphic);
        actor.T(cell[0], cell[1], (short)cell[2]);
        return actor;
    }
    static int[] cell(Actor actor) {
        aBn point = actor.baM(); return new int[]{point.getX(), point.getY(), point.bdn()};
    }
    public static void main(String[] args) throws Exception {
        var unsafe = setup();
        apw.bGL().dd("jar:file:" + Path.of(args[8]).toAbsolutePath() + "/%d.jar!/%d.bin");
        cvX packet = new cvX();
        VerifyCombatReconstructionSlice.check(packet.dp(Files.readAllBytes(Path.of(args[0]))), "native effect decode");
        iN wire = iN.bf(packet.eIJ());
        int[] source = {Integer.parseInt(args[2]), Integer.parseInt(args[3]), Integer.parseInt(args[4])};
        int[] target = {Integer.parseInt(args[5]), Integer.parseInt(args[6]), Integer.parseInt(args[7])};
        Map<Long,Actor> actors = new LinkedHashMap<>();
        actors.put(wire.Qw(), actor(unsafe, wire.Qw(), source));
        actors.put(wire.Qy(), actor(unsafe, wire.Qy(), target));
        PW registry = (PW)Proxy.newProxyInstance(PW.class.getClassLoader(), new Class[]{PW.class},
            (p,m,a)->m.getName().equals("de") ? actors.get((Long)a[0]) : null);
        var grid = new VerifyCombatReconstructionSlice.Grid();
        PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(), new Class[]{PN.class},
            (p,m,a)->switch(m.getName()) {
                case "bae" -> registry;
                case "bad" -> grid;
                case "baf", "baa" -> null;
                default -> m.invoke(bcz.dcW(), a);
            });
        eZR runner = (eZR)eVi.fLJ().pS(packet.eII()).b(context);
        VerifyCombatReconstructionSlice.check(runner.ds(packet.eIJ()) != null, "original runner payload hydration");
        VerifyCombatReconstructionSlice.check(runner.baZ() != null
            && ((eVn)runner.baZ()).aZE() == wire.Qs(), "exact native effect definition loaded");
        Application action = new Application(packet, runner, actors, context);
        action.cYb(); action.iD(wire.Qw()); action.fe(wire.Qy());
        var initial = new LinkedHashMap<Long,int[]>();
        actors.forEach((id,actor)->initial.put(id,cell(actor)));
        aER queue = new aER(); queue.c(action); queue.cbu();
        VerifyCombatReconstructionSlice.check(action.completed && queue.cbt().isEmpty(), "original logical callback/FIFO completed");
        VerifyCombatReconstructionSlice.check(errors.get() == 0, "native consumer emitted no swallowed execution error");
        var positions = new LinkedHashMap<Long,int[]>();
        actors.forEach((id,actor)->positions.put(id,cell(actor)));
        var output = new LinkedHashMap<String,Object>();
        output.put("completed_normally",true); output.put("opcode",12613);
        output.put("family",packet.eII()); output.put("action_id",packet.cbc());
        output.put("generic_effect",wire.Qs()); output.put("uid",wire.LV());
        output.put("caster",wire.Qw()); output.put("target",wire.Qy());
        output.put("initial_positions",initial); output.put("executed_positions",positions);
        output.put("native_completed_action_ids",new int[]{packet.cbc()}); output.put("queue_drained",true);
        output.put("scope","original hydrated runner/exact native definition/aVo logical cbj/aER; visual script/wait skipped; no rendering");
        Files.writeString(Path.of(args[1]),VerifyCombatReconstructionSlice.json(output)+"\n");
        System.out.println("PASS original displacement logical callback/FIFO");
        System.exit(0);
    }
}
