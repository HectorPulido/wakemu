import jdk.internal.org.objectweb.asm.ClassWriter;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.MethodVisitor;
import jdk.internal.org.objectweb.asm.Opcodes;

/** Resolves transformed native classes without initializing the graphical client. */
public final class OpenPlantingAgentNativeVerify {
    public static void main(String[] args) throws Exception {
        for (String name : new String[] {"cYt", "cYv", "dev", "ffY"}) {
            byte[] original;
            try (var input = ClassLoader.getSystemResourceAsStream(name + ".class")) {
                if (input == null) throw new AssertionError("Missing native class " + name);
                original = input.readAllBytes();
            }
            byte[] patched = OpenPlantingAgent.patch(name, original);
            if (patched == null) throw new AssertionError("Native planting boundary was not transformed: " + name);
            int[] recoveryCalls = {0};
            new ClassReader(patched).accept(new ClassVisitor(Opcodes.ASM8) {
                public MethodVisitor visitMethod(int access, String method, String descriptor, String signature, String[] exceptions) {
                    return new MethodVisitor(Opcodes.ASM8) {
                        public void visitMethodInsn(int opcode, String owner, String method, String descriptor, boolean isInterface) {
                            if (owner.equals("OpenPlantingAgentRecovery")) recoveryCalls[0]++;
                        }
                    };
                }
            }, 0);
            int expectedCalls = name.equals("cYt") ? 2 : name.equals("ffY") ? 0 : 1;
            if (recoveryCalls[0] != expectedCalls)
                throw new AssertionError("Unexpected native recovery hook count " + name + ": " + recoveryCalls[0]);
            Class<?> nativeType = Class.forName(name, false, ClassLoader.getSystemClassLoader());
            nativeType.getDeclaredMethods();
            nativeType.getDeclaredConstructors();
            System.out.println("VERIFIED native transformed " + name);
        }
        ClassWriter writer = new ClassWriter(0);
        writer.visit(Opcodes.V17, Opcodes.ACC_PUBLIC, "cYt", null, "java/lang/Object", null);
        writer.visitEnd();
        boolean rejected = false;
        try { OpenPlantingAgent.patch("cYt", writer.toByteArray()); }
        catch (IllegalStateException expected) { rejected = true; }
        if (!rejected) throw new AssertionError("Missing native queue boundaries were not rejected");
        System.setProperty("wakfu.local.openPlanting", "false");
        if (OpenPlantingAgent.patch("cYt", writer.toByteArray()) != null)
            throw new AssertionError("Disabled planting agent must not transform classes");
        System.out.println("PASS native class verification and boundary guards");
    }
}
