import jdk.internal.org.objectweb.asm.*;
/** Replace one call inside eWn.fMO; preserve the native grant and user shortcut APIs. */
public final class NativeSpellGrantShortcutTransformer {
    private NativeSpellGrantShortcutTransformer() {}

    public static byte[] transform(byte[] data) {
        ClassReader reader = new ClassReader(data);
        if (!reader.getClassName().equals("eWn")) throw new IllegalArgumentException("Expected original eWn class");
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
        int[] matches = {0};
        reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
            @Override public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                MethodVisitor target = super.visitMethod(access, name, desc, signature, exceptions);
                if (!name.equals("fMO") || !desc.equals("()V")) return target;
                return new MethodVisitor(Opcodes.ASM8, target) {
                    @Override public void visitMethodInsn(int opcode, String owner, String method, String descriptor, boolean iface) {
                        if (opcode == Opcodes.INVOKEVIRTUAL && owner.equals("eGj")
                                && method.equals("a") && descriptor.equals("(BSLfyG;)Lfyt;")) {
                            super.visitMethodInsn(Opcodes.INVOKESTATIC, "NativeSpellGrantShortcut", "ensure", "(LeGj;BSLfyG;)Lfyt;", false);
                            matches[0]++;
                        } else super.visitMethodInsn(opcode, owner, method, descriptor, iface);
                    }
                };
            }
        }, 0);
        if (matches[0] != 1) throw new IllegalStateException("Expected exactly one native eWn grant shortcut insertion");
        return writer.toByteArray();
    }
}
