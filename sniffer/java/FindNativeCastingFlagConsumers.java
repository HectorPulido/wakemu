import java.nio.file.*;
import java.util.jar.*;
import jdk.internal.org.objectweb.asm.*;

/** Static bytecode callsites, with no client or data bootstrap. */
public class FindNativeCastingFlagConsumers {
    public static void main(String[] args) throws Exception {
        try (JarFile jar = new JarFile(args[0])) {
            var entries = jar.entries();
            while (entries.hasMoreElements()) {
                var entry = entries.nextElement();
                if (!entry.getName().endsWith(".class")) continue;
                new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8) {
                    String caller;
                    public void visitPermittedSubclass(String name) {}
                    public void visit(int version, int access, String name, String signature, String parent, String[] interfaces) { caller = name; }
                    public MethodVisitor visitMethod(int access, String method, String descriptor, String signature, String[] exceptions) {
                        return new MethodVisitor(Opcodes.ASM8) {
                            public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {
                                if ((name.equals("c") && desc.equals("(LfyG;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Z"))
                                    || (owner.equals("fyP") && (name.equals("cwN") || name.equals("cwU")))) {
                                    System.out.println(caller + "." + method + descriptor + " -> " + owner + "." + name + desc);
                                }
                            }
                        };
                    }
                }, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
            }
        }
    }
}
