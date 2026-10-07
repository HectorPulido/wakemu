import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.ClassWriter;
import jdk.internal.org.objectweb.asm.MethodVisitor;
import jdk.internal.org.objectweb.asm.Opcodes;
import jdk.internal.org.objectweb.asm.Label;

/** Test-only: suppress fj.zp's graphics notification, preserving all wire parsing/application. */
public final class HeadlessFjAgent {
  public static void premain(String args, Instrumentation instrumentation) {
    instrumentation.addTransformer(new ClassFileTransformer() {
      public byte[] transform(ClassLoader loader, String name, Class<?> redef,
          ProtectionDomain domain, byte[] bytes) {
        if (!"fj".equals(name) && !"PA".equals(name)) return null;
        ClassReader reader = new ClassReader(bytes);
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES);
        reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
          @Override public void visit(int version, int access, String name, String signature,
              String parent, String[] interfaces) {
            super.visit(version, access, name, signature, parent, interfaces);
          }
          @Override public void visitEnd() { super.visitEnd(); }
          @Override public MethodVisitor visitMethod(int access, String method, String desc,
              String signature, String[] exceptions) {
            MethodVisitor original = super.visitMethod(access, method, desc, signature, exceptions);
            boolean graphicsSignal = "fj".equals(name) && "zp".equals(method) && "()V".equals(desc);
            boolean statUiObserver = "PA".equals(name) && "aZk".equals(method) && "()V".equals(desc);
            if (!graphicsSignal && !statUiObserver) return original;
            return new MethodVisitor(Opcodes.ASM8) {
              @Override public void visitCode() {
                original.visitCode();
                if (graphicsSignal) {
                  Label done = new Label();
                  Label start = new Label();
                  Label end = new Label();
                  Label handler = new Label();
                  original.visitTryCatchBlock(start, end, handler, "java/lang/Throwable");
                  original.visitVarInsn(Opcodes.ALOAD, 0);
                  original.visitFieldInsn(Opcodes.GETFIELD, "fj", "oW", "Lfi;");
                  original.visitJumpInsn(Opcodes.IFNULL, done);
                  original.visitLabel(start);
                  original.visitVarInsn(Opcodes.ALOAD, 0);
                  original.visitFieldInsn(Opcodes.GETFIELD, "fj", "oW", "Lfi;");
                  original.visitMethodInsn(Opcodes.INVOKEINTERFACE, "fi", "zm", "()V", true);
                  original.visitLabel(end);
                  original.visitJumpInsn(Opcodes.GOTO, done);
                  original.visitLabel(handler);
                  original.visitInsn(Opcodes.POP);
                  original.visitLabel(done);
                  original.visitInsn(Opcodes.RETURN);
                  original.visitMaxs(2, 1);
                } else {
                  original.visitInsn(Opcodes.RETURN);
                  original.visitMaxs(0, 1);
                }
                original.visitEnd();
              }
            };
          }
        }, 0);
        return writer.toByteArray();
      }
    });
  }
}
