import java.io.InputStream;
import java.nio.ByteBuffer;
import java.util.Arrays;
import jdk.internal.org.objectweb.asm.*;

/** Verify the installed native completion callback and its coQ wire codec. */
public final class VerifySpectatorTerminalAck {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static final class Loader extends ClassLoader {
        Class<?> define(byte[] data) { return defineClass("aUH", data, 0, data.length); }
    }
    public static void main(String[] args) throws Exception {
        byte[] original;
        try (InputStream stream = VerifySpectatorTerminalAck.class.getResourceAsStream("/aUH.class")) {
            original = stream.readAllBytes();
        }
        byte[] transformed = CaptureAgent.spectatorTerminalAck(original);
        check(!Arrays.equals(original, transformed));
        int[] suppressed = {0}, nativePacket = {0}, outsideReads = {0};
        new ClassReader(transformed).accept(new ClassVisitor(Opcodes.ASM8) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                return new MethodVisitor(Opcodes.ASM8) {
                    @Override
                    public void visitFieldInsn(int opcode, String owner, String field, String descriptor) {
                        if (owner.equals("aUH") && field.equals("huP") && opcode == Opcodes.GETFIELD) {
                            if (name.equals("cbj")) suppressed[0]++; else outsideReads[0]++;
                        }
                    }
                    @Override
                    public void visitMethodInsn(int opcode, String owner, String method, String descriptor, boolean iface) {
                        if (name.equals("cbj") && owner.equals("coQ") && method.equals("<init>") && descriptor.equals("(IZ)V")) nativePacket[0]++;
                    }
                };
            }
        }, 0);
        check(suppressed[0] == 0 && nativePacket[0] == 1 && outsideReads[0] == 1);
        // Resolving every native method triggers JVM verification of the
        // transformed callback and unchanged stack-map frames.
        Class<?> loaded = new Loader().define(transformed);
        check(loaded.getDeclaredMethods().length > 0);
        for (boolean loss : new boolean[]{false, true}) {
            coQ packet = new coQ(106, loss);
            check(packet.d() == 12925);
            byte[] wire = packet.aWH();
            check(wire.length == 12);
            check(ByteBuffer.wrap(wire, 7, 4).getInt() == 106 && wire[11] == (loss ? 1 : 0));
        }
        System.out.println("Native aUH callback verified; one coQ12925 path, participant flags preserved, spectator ACK enabled");
    }
}
