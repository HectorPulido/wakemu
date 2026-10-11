import java.io.InputStream;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import jdk.internal.org.objectweb.asm.*;

/** Offline original-client contract probe; does not patch or launch the client. */
public final class ProbeNativeMapObjectives {
    private static final class View implements aeR {
        int additions;
        int removals;
        public void a(aeP point) { additions++; }
        public void b(aeP point) { removals++; }
    }

    private static final class Compass extends aeM {
        aeP latest;
        protected aeP a(int type, aeR view, Object value, int icon, int x, int y, int z, boolean flag) {
            latest = new aeP(view, value, icon, x, y, z, flag);
            return latest;
        }
    }

    private static final class Projection extends aeU {
        @Override public float aM(float x, float y) { return x - y; }
        @Override public float j(float x, float y, float z) { return x + y - z; }
    }

    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private static Set<String> calls(String owner, String method, String descriptor) throws Exception {
        Set<String> result = new HashSet<>();
        try (InputStream stream = ProbeNativeMapObjectives.class.getResourceAsStream("/" + owner + ".class")) {
            new ClassReader(stream.readAllBytes()).accept(new ClassVisitor(Opcodes.ASM8) {
                @Override public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                    if (!name.equals(method) || !desc.equals(descriptor)) return null;
                    return new MethodVisitor(Opcodes.ASM8) {
                        @Override public void visitMethodInsn(int opcode, String type, String name, String desc, boolean iface) {
                            result.add(type + "." + name + desc);
                        }
                    };
                }
            }, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        }
        return result;
    }

    public static void main(String[] args) throws Exception {
        Set<String> save = calls("cLa", "applyNote", "(LfQX;)V");
        check(save.contains("bUZ.esc()V"), "Save note must invoke local persistence");
        check(save.stream().noneMatch(s -> s.startsWith("bLp.")), "Saving a note does not select a compass destination");
        Set<String> disk = calls("bUZ", "a", "(JLgnu/trove/map/hash/TIntObjectHashMap;)V");
        check(disk.contains("FE.bV(Ljava/lang/String;)Ljava/io/FileOutputStream;"), "Notes use local files");
        Set<String> click = calls("cLa", "onMapClick", "(LfUu;LfKo;)V");
        check(click.contains("bLa.aa(III)LbUY;"), "Note creation must remain distinct");
        check(click.contains("bLc.a(JIFFFJLjava/lang/String;Ljava/lang/Object;Lgby;[FZ)V"), "Destination placement must publish locally");
        Set<String> target = calls("bLc", "a", "(JIFFFJLjava/lang/String;Ljava/lang/Object;Lgby;[FZ)V");
        check(target.contains("bLp.a(IJIIILjava/lang/Object;LaeQ;Z)V"), "Destination must reach native compass manager");
        for (Set<String> route : List.of(save, disk, click, target)) {
            check(route.stream().noneMatch(s -> s.startsWith("aAk.i(") || s.startsWith("aAk.j(")), "Unexpected network publication");
        }
        // Execute the original compass registry with a rendering-free view.
        // This demonstrates that a destination exists independently of server ACKs,
        // and that absent scene attachment delays coordinate publication.
        aeM.coU = new int[6];
        Compass compass = new Compass();
        View view = new View();
        compass.a(view);
        compass.a(2, 0L, 120, -42, 3, "destination", null, false);
        check(compass.j(2, 0L) && view.additions == 1, "Native destination registration must succeed");
        check(compass.coZ.size() == 1, "Absent scene must queue coordinate projection");
        compass.removeAll();
        check(!compass.j(2, 0L) && view.removals == 1, "Native destination cleanup must succeed");
        var unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        unsafeField.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) unsafeField.get(null);
        compass.e((Projection) unsafe.allocateInstance(Projection.class));
        compass.a(2, 0L, 250, -42, 3, "destination", null, false);
        check(compass.latest.getX() == 250 && compass.latest.getY() == -42,
            "Attached scene must apply actual native destination coordinates");
        // Exercise the installed native note codec with multiple coordinates/icons.
        for (int x : new int[]{-120, 0, 250}) {
            bUY original = new bUY(7, x, -42, 3, "Native objective", 2, false);
            FG writer = new FG();
            original.a(writer, 1);
            byte[] encoded = writer.aLJ();
            aoG reader = aoG.dx(encoded);
            bUY restored = new bUY();
            restored.b(reader, 1);
            check(restored.getX() == x && restored.getY() == -42, "Native XY coordinates must roundtrip");
            check(restored.NN() == 0, "Native saved notes intentionally omit altitude");
            check(restored.hF().equals("Native objective") && restored.bwX() == 2, "Native text/icon must roundtrip");
            check(reader.available() == 0, "Native note codec must consume all bytes");
        }
        System.out.println("PASS original client: local note persistence; separate destination->compass; native destination registry, scene attachment and cleanup; three native note roundtrips");
    }
}
