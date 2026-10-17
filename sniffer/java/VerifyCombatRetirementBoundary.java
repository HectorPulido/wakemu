import java.lang.reflect.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Original cvK/aTS.E/fbX/fcb/fdt/QI boundary, with graphic hooks excluded. */
public final class VerifyCombatRetirementBoundary {
    static final int FIGHT = 99;
    static final long ACTOR = 901;
    static final class Actor extends ProbeNativeFightersBreedRange.A {
        long identity;
        byte slot = -1;
        Fight fight;
        int deathHook, detachHook;
        public long Sn() { return identity; }
        public fcb dpt() { return fight; }
        public buH doI() { return fight; }
        public boolean dnz() { return true; }
        public byte bcN() { return slot; }
        public void M(byte value) { slot = value; }
        public boolean bcO() { return true; }
        public boolean bcP() { return true; }
        public boolean bcQ() { return true; }
        public byte bcK() { return 0; }
        public boolean dTC() { return false; }
        // These hooks normally manage graphics, effects and controller cleanup.
        // fdt status and QI removal remain the untouched native implementations.
        public void baJ() { deathHook++; }
        public void frj() { detachHook++; }
        public void aa(big actor) {} // Detached graphical notification hook.
    }
    static final class Fight extends ProbeNativeFightersBreedRange.F {
        Fight() { super(); }
        public int d() { return FIGHT; }
    }
    static final class Completion extends aET {
        final Runnable callback;
        Throwable failure;
        Completion(Runnable callback) { super(1, 0, 0); this.callback = callback; }
        protected long cby() {
            try { callback.run(); return 0; }
            catch (RuntimeException | Error error) { failure = error; throw error; }
        }
        protected void cbj() {}
    }
    static void field(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true); field.set(object, value);
    }
    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    static byte[] packet(int fight, long actor, int state) {
        return ByteBuffer.allocate(21).putInt(fight).putInt(7).putInt(-1)
            .putLong(actor).put((byte) state).array();
    }
    public static void main(String[] arguments) throws Exception {
        Path output = Path.of(arguments[0]); Files.createDirectories(output);
        eGM.a(null);
        for (int state : new int[]{0, 1, 2, 3, 7}) {
            byte[] body = packet(FIGHT, ACTOR, state);
            cvK reader = new cvK();
            check(reader.dp(body) && reader.bhe() == FIGHT && reader.OO() == ACTOR
                  && reader.eIs() == state, "Original cvK field contract");
            Files.write(output.resolve("12727-state" + state + ".bin"), body);
        }
        check(!new cvK().dp(new byte[20]), "Truncated original cvK must reject");

        Fight fight = (Fight) ProbeNativeFightersBreedRange.U.allocateInstance(Fight.class);
        Actor actor = (Actor) ProbeNativeFightersBreedRange.U.allocateInstance(Actor.class);
        actor.identity = ACTOR; actor.slot = -1; actor.x = 1; actor.y = 1; actor.fight = fight;
        fdt<big> population = new fdt<>();
        field(fight, fcb.class, "rRN", population);
        field(fight, buH.class, "jqt", Collections.emptyList());
        ProbeNativeQIRegistry.Grid grid = new ProbeNativeQIRegistry.Grid();
        field(fight, fcb.class, "rRQ", grid);
        population.a(actor, (byte) 0, false, actor);
        grid.f(actor);
        fev stats = (fev) Proxy.newProxyInstance(fev.class.getClassLoader(), new Class[]{fev.class},
            (object, method, args) -> method.getName().equals("rI") ? false : 0);
        feq ordering = new feq(fight, stats);
        Tc table = new Tc(ordering);
        SQ insertion = new SQ(); insertion.a(SR.pv(0)); insertion.pt(0);
        table.a(ACTOR, (short) 0, insertion);
        bvY timeline = new bvY(fight, new feN(), stats, ordering, table);
        field(timeline, SU.class, "brX", true); // Explicit active native timeline input.
        field(fight, fcb.class, "rRP", timeline);
        check(timeline.bhp() && table.bsw.bhH().contains(ACTOR),
              "Actual active native timeline contains the fighter");
        byte originalSlot = actor.slot;
        check(population.ry(ACTOR) == actor && actor.baF(), "Registered live identity");
        check(population.bv(actor) && actor.baG(), "Explicit actual OFF_PLAY prerequisite");
        timeline.eT(ACTOR);
        check(!table.bsw.bhH().contains(ACTOR) && timeline.sbE.containsKey(ACTOR),
              "Native prior clock stage removes active member and saves its retirement record");
        check(grid.O(originalSlot) == actor && grid.g(1, 1, (short) 0),
              "OFF_PLAY preserves physical registration");

        cvK reader = new cvK(); reader.dp(packet(FIGHT, ACTOR, 2));
        aTS action = new aTS(FIGHT, reader.cbc(), reader.eId(), reader.eIs(), 0, false);
        Method completion = aTS.class.getDeclaredMethod("E", big.class);
        completion.setAccessible(true);
        aER queue = new aER();
        Completion retirement = new Completion(() -> {
            try { completion.invoke(action, actor); }
            catch (InvocationTargetException error) { throw new RuntimeException(error.getCause()); }
            catch (ReflectiveOperationException error) { throw new RuntimeException(error); }
        });
        queue.c(retirement);
        check(actor.baG() && grid.O(originalSlot) == actor,
              "Receipt before explicit completion cannot retire the fighter");
        queue.cbu();
        if (retirement.failure != null) retirement.failure.printStackTrace();
        check(retirement.failure == null, "Native completion callback failed: " + retirement.failure);
        check(queue.cbt().isEmpty(), "Original completion queue drained");
        check(actor.baK() && !actor.baF() && !actor.baG(), "Native state2 OUT_OF_PLAY");
        check(population.ry(ACTOR) == actor && population.by(actor),
              "OUT_OF_PLAY retains roster identity; it is not despawn");
        check(actor.slot == -1 && grid.O(originalSlot) == null
              && !grid.g(1, 1, (short) 0), "Native fcb.H/aQ/QI.g physical retirement");
        check(!table.bsw.bhH().contains(ACTOR) && !timeline.sbE.containsKey(ACTOR),
              "Native state2 clears the prior removed-timeline record without restoring membership");
        check(actor.deathHook == 1 && actor.detachHook == 1,
              "Actual native fcb/fbX callbacks ran once: death=" + actor.deathHook
              + " detach=" + actor.detachHook);

        Completion malformed = new Completion(() -> { throw new IllegalStateException("deliberate failed callback"); });
        aER failedQueue = new aER(); failedQueue.c(malformed); failedQueue.cbu();
        check(malformed.failure instanceof IllegalStateException,
              "Failed callback must remain visible independently of queue state");

        Map<String, Object> observations = new LinkedHashMap<>();
        observations.put("completed_normally", true);
        observations.put("fight", FIGHT); observations.put("actor", ACTOR);
        observations.put("prerequisite", "actual fdt OFF_PLAY, registered QI and prior native fem.eT removal");
        observations.put("state2_completed", true);
        observations.put("before_completion_physical_registered", true);
        observations.put("after_completion_out_of_play", actor.baK());
        observations.put("after_completion_roster_retained", population.ry(ACTOR) == actor);
        observations.put("after_completion_physical_registered", grid.O(originalSlot) != null);
        observations.put("after_completion_queue_empty", queue.cbt().isEmpty());
        observations.put("timeline_execution_active", timeline.bhp());
        observations.put("initial_timeline_registered", true);
        observations.put("before_completion_timeline_registered", false);
        observations.put("before_completion_removed_timeline_record", true);
        observations.put("after_completion_timeline_registered", table.bsw.bhH().contains(ACTOR));
        observations.put("after_completion_removed_timeline_record", timeline.sbE.containsKey(ACTOR));
        observations.put("completion_callback_successful", retirement.failure == null);
        observations.put("deliberate_failed_callback_detected", malformed.failure != null);
        observations.put("consumer_path", "prior fdt.bv/fem.eT -> SU.eu/Tc.eV; cvK.dp -> explicit completion -> aTS.E -> fbX.aD -> fcb.aD/buH.H/aS/fcb.H/aQ/fcb.bd -> fdt.bw, QI.g, fem.eu");
        observations.put("excluded", List.of("aTS.cby animation and scheduler timing", "full aTS state0 admission", "timeline removal timing", "rendering", "actor death/effect/controller hooks baJ/frj/dnO/aa", "native fight listener list empty", "states1/3 and unknown statuses", "exploration despawn"));
        Files.writeString(output.resolve("observations.json"), VerifyCombatReconstructionSlice.json(observations));
        System.out.println("PASS original state2 completion: OUT_OF_PLAY + QI removed; roster retained");
    }
}
