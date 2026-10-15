import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;
import jdk.internal.org.objectweb.asm.*;

/** Offline native graphic-owner regression; never creates a game session. */
public final class ProbeNativeMovementStop {
    static final String FINISH = "AnimCourse02-Fin";
    static final String IDLE = "AnimStatique02";
    static class Graphic extends beS {
        List<String> attempts;
        boolean finishAccepted;
        boolean idleAvailable;
        Graphic() { super(null); }
        @Override public boolean eg(String name) { attempts.add(name); return name.equals(FINISH) ? finishAccepted : name.equals(IDLE) && idleAvailable; }
        @Override public boolean em(String name) { return name.equals(IDLE) && idleAvailable; }
        @Override public String bpT() { return IDLE; }
    }
    static void set(Object object, String name, Object value) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try { Field field = type.getDeclaredField(name); field.setAccessible(true); field.set(object, value); return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Object allocate(Class<?> type) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe"); field.setAccessible(true);
        return ((sun.misc.Unsafe)field.get(null)).allocateInstance(type);
    }
    static Graphic graphic(long identity) throws Exception {
        Graphic graphic = (Graphic)allocate(Graphic.class);
        graphic.attempts = new ArrayList<>(); graphic.idleAvailable = true;
        big owner = (big)allocate(bje.class);
        set(owner, "aHm", identity); set(owner, "hQB", graphic);
        set(graphic, "hPP", owner);
        return graphic;
    }
    public static void main(String[] args) throws Exception {
        byte[] original;
        try (var stream = ClassLoader.getSystemResourceAsStream("acS.class")) { original = stream.readAllBytes(); }
        byte[] transformed = CaptureAgent.movementPathCleared(original);
        int[] hooks = {0};
        new ClassReader(transformed).accept(new ClassVisitor(Opcodes.ASM8) {
            public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                return new MethodVisitor(Opcodes.ASM8) {
                    public void visitMethodInsn(int opcode, String owner, String method, String descriptor, boolean iface) {
                        if (owner.equals("NativeMovementStop")) {
                            if (!name.equals("bvC") || !method.equals("pathCleared") || !descriptor.equals("(LacS;)V"))
                                throw new AssertionError("Wrong native path-clear boundary");
                            hooks[0]++;
                        }
                    }
                };
            }
        }, 0);
        if (hooks[0] != 1) throw new AssertionError("Missing path-clear diagnostic hook");
        YF nativeActor = (YF)allocate(YF.class);
        set(nativeActor, "bHP", FINISH); set(nativeActor, "bSD", IDLE);
        if (nativeActor.eg(FINISH)) throw new AssertionError("Native same-name request must return false");
        if (!nativeActor.eg("UninventedAssetAvailabilityProbe") || !nativeActor.bkG().equals("UninventedAssetAvailabilityProbe"))
            throw new AssertionError("Native eg must change requested name without checking assets");
        Graphic hero = graphic(16);
        hero.finishAccepted = false; // Records a false native return; no missing-asset assertion.
        if (NativeMovementStop.finish(hero, FINISH) || !hero.attempts.equals(List.of(FINISH)))
            throw new AssertionError("Nonselected fallback behavior changed");
        var sameName = (java.util.Map<?, ?>)NativeMovementStop.diagnostic(16).get("finish_call");
        if (!Boolean.FALSE.equals(sameName.get("original_return")) || !Boolean.FALSE.equals(sameName.get("fallback_attempted")))
            throw new AssertionError("False original return was not recorded");
        Graphic changed = graphic(79); changed.finishAccepted = true;
        if (!NativeMovementStop.finish(changed, FINISH) || !changed.attempts.equals(List.of(FINISH)))
            throw new AssertionError("Changed native request was invoked twice");
        var changedEvent = (java.util.Map<?, ?>)NativeMovementStop.diagnostic(79).get("finish_call");
        if (!Boolean.TRUE.equals(changedEvent.get("original_return")) || !Boolean.FALSE.equals(changedEvent.get("fallback_attempted")))
            throw new AssertionError("True original return was not recorded");
        for (int identity = 100; identity < 165; identity++) NativeMovementStop.pathCleared(graphic(identity));
        if (!NativeMovementStop.diagnostic(100).isEmpty() || !NativeMovementStop.diagnostic(16).isEmpty()
                || !NativeMovementStop.diagnostic(164).containsKey("path_clear"))
            throw new AssertionError("Diagnostic actor population is not bounded to64");
        System.out.println("PASS original YF.eg false means same requested name, true does not check assets; deployed nonselected behavior preserved; original returns captured, diagnostic bounded64actors, exact nativebvC exit hook");
    }
}
