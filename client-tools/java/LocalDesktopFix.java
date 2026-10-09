import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.ClassWriter;
import jdk.internal.org.objectweb.asm.MethodVisitor;
import jdk.internal.org.objectweb.asm.Opcodes;
import jdk.internal.org.objectweb.asm.Type;
import jdk.internal.org.objectweb.asm.Label;

/** Local-only desktop, telemetry and minimal quest presentation adjustments. */
public final class LocalDesktopFix {
    public static void premain(String options, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override public byte[] transform(ClassLoader loader, String name, Class<?> type,
                    ProtectionDomain domain, byte[] bytes) {
                boolean telemetry = name.equals("cbW");
                boolean questCategory = name.equals("beq");
                boolean questHud = name.equals("bdR");
                if (!telemetry && !questCategory && !questHud && !name.equals("com/ankamagames/baseImpl/graphics/opengl/FullscreenUtils")) return null;
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(0);
                reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                    @Override public MethodVisitor visitMethod(int access, String method, String descriptor,
                            String signature, String[] exceptions) {
                        boolean replace = telemetry
                            ? (access & Opcodes.ACC_STATIC) != 0 && descriptor.endsWith(")V") && !method.startsWith("<")
                            : method.equals("showMenuAndDock") && descriptor.equals("(Z)V");
                        MethodVisitor visitor = super.visitMethod(replace ? access & ~Opcodes.ACC_NATIVE : access,
                            method, descriptor, signature, exceptions);
                        boolean filterCategory = questCategory && method.equals("a") && descriptor.equals("(Lber;)V");
                        boolean filterHud = questHud && method.equals("BB") && descriptor.equals("(I)Lber;");
                        // 5144 is the client's automatic low-level class-change offer,
                        // not inherited server progress. Exclude its presentation in
                        // the local minimal profile without reporting completion.
                        if (filterCategory || filterHud) return new MethodVisitor(Opcodes.ASM8, visitor) {
                            @Override public void visitCode() {
                                super.visitCode();
                                Label keep = new Label();
                                visitVarInsn(filterCategory ? Opcodes.ALOAD : Opcodes.ILOAD, 1);
                                if (filterCategory) visitMethodInsn(Opcodes.INVOKEVIRTUAL, "ber", "d", "()I", false);
                                visitIntInsn(Opcodes.SIPUSH, 5144);
                                visitJumpInsn(Opcodes.IF_ICMPNE, keep);
                                if (filterHud) visitInsn(Opcodes.ACONST_NULL);
                                visitInsn(filterHud ? Opcodes.ARETURN : Opcodes.RETURN);
                                visitLabel(keep);
                                visitFrame(Opcodes.F_SAME, 0, null, 0, null);
                            }
                        };
                        if (!replace) return visitor;
                        visitor.visitCode();
                        visitor.visitInsn(Opcodes.RETURN);
                        int locals = (access & Opcodes.ACC_STATIC) == 0 ? 1 : 0;
                        for (Type argument : Type.getArgumentTypes(descriptor)) locals += argument.getSize();
                        visitor.visitMaxs(0, locals);
                        visitor.visitEnd();
                        System.err.println(telemetry ? "LOCAL PROFILE: telemetry helper disabled"
                            : "LOCAL DESKTOP FIX: unsafe macOS menu/Dock call disabled for windowed experiment");
                        return null;
                    }
                }, 0);
                return writer.toByteArray();
            }
        });
    }
}
