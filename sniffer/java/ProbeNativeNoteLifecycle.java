import java.io.InputStream;
import java.util.HashSet;
import java.util.Set;
import jdk.internal.org.objectweb.asm.*;

/** Checks installed note lifecycle bytecode without changing or initializing the client. */
public final class ProbeNativeNoteLifecycle {
    private static Set<String> calls(String owner, String name, String descriptor) throws Exception {
        Set<String> result = new HashSet<>();
        try (InputStream input = ProbeNativeNoteLifecycle.class.getResourceAsStream("/" + owner + ".class")) {
            if (input == null) throw new AssertionError(owner);
            new ClassReader(input.readAllBytes()).accept(new ClassVisitor(Opcodes.ASM8) {
                public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                    if (!method.equals(name) || !desc.equals(descriptor)) return null;
                    return new MethodVisitor(Opcodes.ASM8) {
                        public void visitMethodInsn(int opcode, String type, String method, String desc, boolean iface) {
                            result.add(type + "." + method + desc);
                        }
                    };
                }
            }, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        }
        return result;
    }
    private static void require(Set<String> calls, String expected) {
        if (!calls.contains(expected)) throw new AssertionError("Missing installed call " + expected + " in " + calls);
    }
    public static void main(String[] args) throws Exception {
        Set<String> create = calls("bLa", "a", "(IIIILjava/lang/String;Z)LbUY;");
        require(create, "bUZ.a(IIILjava/lang/String;IZ)LbUY;");
        require(create, "bLa.a(LbUY;)V");
        require(calls("bUZ", "a", "(IIILjava/lang/String;IZ)LbUY;"), "bUZ.esc()V");
        require(calls("bKM", "a", "(LbLo;)V"), "bLo.a(LbKM;)V");
        require(calls("bLm", "a", "(LbKM;)V"), "bLa.c(Lgnu/trove/list/array/TLongArrayList;)V");
        require(calls("bLa", "c", "(Lgnu/trove/list/array/TLongArrayList;)V"), "bLa.eeg()V");
        require(calls("bLa", "eeg", "()V"), "bLa.lE(J)V");
        require(calls("bLa", "lE", "(J)V"), "bUZ.mr(J)Lgnu/trove/map/hash/TIntObjectHashMap;");
        Set<String> renderer = calls("bKM", "a", "(LfKi;)V");
        require(renderer, "bLa.a(LfKi;)V");
        if (renderer.contains("bLa.c(Lgnu/trove/list/array/TLongArrayList;)V")) throw new AssertionError("Renderer unexpectedly reloads notes");
        require(calls("bUZ", "ms", "(J)J"), "cdH.mN(J)LcdI;");
        System.out.println("PASS native note creation registers in its bLa and persists through bUZ.esc");
        System.out.println("PASS world context attachment -> bLm.a -> bLa.c -> eeg -> lE -> bUZ.mr rehydrates notes");
        System.out.println("PASS renderer attachment has no direct note rehydrate; note world keys consult native world catalog");
        System.out.println("LIMIT static installed-class contract only; no GUI refresh or server scene reset was executed");
    }
}
