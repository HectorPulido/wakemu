import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import jdk.internal.org.objectweb.asm.*;

/** Original decoded eYc parameters, native selection guards and cvX boundary. */
public final class ProbeDecodedAreaRemoval {
    static final String CAPTURED_213 = "08e60910e60918c7c11720002a0f080d10f8ffffffffffffffff011800301d38a509480150818090725a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff0128016a1008001000200928003000380040004800";
    static final String CAPTURED = "08c70310c70318c7c11720002a1808f4ffffffffffffffff01100018ffffffffffffffffff01301d388303480150818090725a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff0128016a1008001000200228003000380040004800";
    static void set(Object object, String name, Object value) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try { Field field = type.getDeclaredField(name); field.setAccessible(true); field.set(object, value); return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static int operand(eZR runner, String name) throws Exception {
        Field field = eYc.class.getDeclaredField(name); field.setAccessible(true);
        return field.getInt(runner);
    }
    static class Manager extends Qs {
        final List<Long> removed = new ArrayList<>();
        public Qq dp(long uid) { return null; }
        public void b(Qq area) { removed.add(area.Sn()); }
    }
    static class Area extends faZ {
        boolean blocking;
        protected Qq bcs() { return new Area(); }
        public int aeV() { return 0; }
        public boolean bcv() { return true; }
        public boolean bcw() { return false; }
        public int df(long uid) { return 0; }
        public byte bav() { return 2; }
        public byte[] baz() { return new byte[0]; }
        public anS bEs() { return null; }
        public boolean bcP() { return blocking; }
        public boolean a(Qe source, amP target) { return true; }
        public void g(amP target) { }
        public long[] c(amP target) { return new long[0]; }
        public List<amP> d(amP target) { return List.of(); }
        public void a(int x, int y, short z, Qe source) { }
        public boolean e(amP target) { return true; }
        public void f(amP target) { }
    }
    static eZR runner(int family) {
        return (eZR)((Qe)eVi.fLJ().pS(family)).b(bcz.dcW());
    }
    public static void executeHydrationOnly(eZR runner, Qe source, boolean forced) {
        if (forced && runner instanceof eYc removal && removal.baZ() != null) removal.C(null);
        runner.a(source, forced);
    }
    static Class<?> patchedAction(boolean restoreGate) throws Exception {
        byte[] original;
        try (var stream = ClassLoader.getSystemResourceAsStream("aVo.class")) { original = stream.readAllBytes(); }
        byte[] patched = CaptureAgent.decodedAreaRemoval(original);
        if (!restoreGate) {
            ClassReader reader = new ClassReader(patched);
            ClassWriter writer = new ClassWriter(reader, 0);
            reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] exceptions) {
                    return new MethodVisitor(Opcodes.ASM8, super.visitMethod(access, name, desc, sig, exceptions)) {
                        public void visitMethodInsn(int op, String owner, String method, String descriptor, boolean iface) {
                            if (owner.equals("NativeDecodedAreaRemoval")) {
                                super.visitMethodInsn(op, "ProbeDecodedAreaRemoval", "executeHydrationOnly", descriptor, false);
                            } else super.visitMethodInsn(op, owner, method, descriptor, iface);
                        }
                    };
                }
            }, 0);
            patched = writer.toByteArray();
        }
        byte[] actionBytes = patched;
        return new ClassLoader(ProbeDecodedAreaRemoval.class.getClassLoader()) {
            Class<?> check() { return defineClass("aVo", actionBytes, 0, actionBytes.length); }
        }.check();
    }
    static void decodedAction(boolean patched) throws Exception {
        eZR removal = runner(843);
        removal.ds(HexFormat.of().parseHex(CAPTURED_213));
        if (((eVn)removal.baZ()).aZE() != 385223) throw new AssertionError("Wrong fight213 definition");
        Manager manager = new Manager();
        Area area = new Area();
        set(area, "bgV", 207L); set(area, "aHm", 1189L);
        set(area, "bhh", true); set(area, "bgX", new aBn(13, -8, (short)0));
        PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(), new Class[]{PN.class}, (o, m, a) -> {
            if (m.getName().equals("baf")) return manager;
            if (m.getReturnType() == boolean.class) return false;
            if (m.getReturnType() == int.class) return 0;
            return null;
        });
        set(removal, "bfw", context); set(removal, "bfs", area);
        set(removal, "bft", new aBn(13, -8, (short)0));
        // Both actions use the exact transformed native boundary; only the
        // former/new bridge implementation differs after aVo clears bfD.
        Class<?> actionType = patchedAction(patched);
        // The isolated patched aVo cannot share its constructor's aVq helper
        // with the parent loader. cYg needs only these two action fields.
        Field unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe"); unsafeField.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe)unsafeField.get(null);
        Object action = unsafe.allocateInstance(actionType);
        set(action, "hwi", removal); set(action, "hwj", true);
        Method execute = actionType.getDeclaredMethod("cYg"); execute.setAccessible(true);
        execute.invoke(action);
        List<Long> expected = patched ? List.of(1189L) : List.of();
        if (!manager.removed.equals(expected)) throw new AssertionError("Actual aVo immediate213 removal patched=" + patched + " actual=" + manager.removed);
    }
    static void boundary() throws Exception {
        byte[] original;
        try (var stream = ClassLoader.getSystemResourceAsStream("aVo.class")) { original = stream.readAllBytes(); }
        byte[] patched = CaptureAgent.decodedAreaRemoval(original);
        int[] calls = {0};
        new ClassReader(patched).accept(new ClassVisitor(Opcodes.ASM8) {
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] exceptions) {
                return new MethodVisitor(Opcodes.ASM8) {
                    public void visitMethodInsn(int op, String owner, String method, String descriptor, boolean iface) {
                        if (owner.equals("NativeDecodedAreaRemoval")) {
                            if (!name.equals("cYg") || !method.equals("execute") || !descriptor.equals("(LeZR;LQe;Z)V")) throw new AssertionError("Wrong execution boundary");
                            calls[0]++;
                        }
                    }
                };
            }
        }, 0);
        if (calls[0] != 2) throw new AssertionError("Decoded cvX branch hook count");
        Class<?> checked = new ClassLoader(ProbeDecodedAreaRemoval.class.getClassLoader()) {
            Class<?> check() { return defineClass("aVo", patched, 0, patched.length); }
        }.check();
        checked.getDeclaredMethods();
    }
    public static void main(String[] args) throws Exception {
        boundary();
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        eGM.a(null);
        decodedAction(false);
        decodedAction(true);
        eZR actual = runner(843); actual.ds(HexFormat.of().parseHex(CAPTURED));
        if (operand(actual, "rFc") != 0 || operand(actual, "rFd") != 0) throw new AssertionError("Captured decode must reproduce missing operands");
        if (((eVn)actual.baZ()).aZE() != 385223) throw new AssertionError("Wrong captured native definition");
        if (NativeDecodedAreaRemoval.initialize(actual, false) || operand(actual, "rFc") != 0) throw new AssertionError("Retained branch was recalculated");
        NativeDecodedAreaRemoval.initialize(actual, true);
        if (operand(actual, "rFc") != -1 || operand(actual, "rFd") != -1) throw new AssertionError("Captured operands were not hydrated");
        int cases = 0;
        Method apply = eYc.class.getDeclaredMethod("c", Qe.class, boolean.class); apply.setAccessible(true);
        for (int family : new int[]{843, 909, 911, 1021}) for (int reference : new int[]{-1, 207, 209})
            for (boolean removable : new boolean[]{false, true}) for (boolean blocking : new boolean[]{false, true}) {
                eZR removal = runner(family); removal.ds(HexFormat.of().parseHex(CAPTURED));
                Manager manager = new Manager(); Area area = new Area(); area.blocking = blocking;
                set(area, "bgV", 207L); set(area, "aHm", 901L); set(area, "bhh", removable); set(area, "bgX", new aBn(0, 0, (short)0));
                PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(), new Class[]{PN.class}, (o, m, a) -> switch(m.getName()) {
                    case "baf" -> manager; case "baa" -> null; default -> throw new AssertionError("Unexpected mutation/context " + m.getName());
                });
                eVv definition = (eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(), new Class[]{eVv.class}, (o, m, a) -> switch(m.getName()) {
                    case "fLb" -> false; case "aZE" -> 385223; case "fKJ" -> 1; case "a" -> reference; default -> throw new AssertionError("Unexpected calculation " + m.getName());
                });
                set(removal, "bfw", context); set(removal, "bfp", definition); set(removal, "bfs", area); set(removal, "bft", new aBn(0, 0, (short)0)); set(removal, "bfD", true);
                apply.invoke(removal, null, false);
                if (!manager.removed.isEmpty()) throw new AssertionError("Unhydrated default-zero runner unexpectedly removed a bag");
                NativeDecodedAreaRemoval.initialize(removal, true);
                apply.invoke(removal, null, false);
                boolean expected = removable && (reference == -1 || reference == 207) && (family != 1021 || blocking);
                if (!manager.removed.equals(expected ? List.of(901L) : List.of())) throw new AssertionError("Native selection guard family=" + family);
                if (area.Sn() != 901 || area.bct() != 207) throw new AssertionError("Area identity changed");
                cases++;
            }
        if (NativeDecodedAreaRemoval.initialize(new eXE(), true)) throw new AssertionError("Non-area family was recalculated");
        if (NativeDecodedAreaRemoval.initialize(new eXU(), true)) throw new AssertionError("Missing native definition was fabricated");
        System.out.println("PASS actual aVo.cYg fight213 execute1: hydration-only misses1189, patched removes1189; decoded fight208 effect385223, 48 original selection/removability/blocking cases, retained/non-area/missing-definition guards, two verified cvX branches");
    }
}
