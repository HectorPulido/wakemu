import java.nio.file.Path;
import java.util.*;

/** Actual fdq/fdl/TIntObjectHashMap link order, offline installed prototype978. */
public class ProbeNativeMicrobotNetwork {
    static class Owner extends biw {
        public byte bcM() { return 0; }
        public long Sn() { return 7; }
        public Qf bax() { return null; }
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        final faV[] prototype = new faV[1];
        apw.bGL().a(new aKa(), new apB<aKa>() {
            public void load(aKa raw) {
                if (raw.d() == 978) prototype[0] = bcN.hFx.a(raw);
            }
        });
        if (prototype[0] == null) throw new AssertionError("Missing installed microbot");
        Owner owner = new Owner();
        Random random = new Random(808339);
        for (int trial = 0; trial < 100; trial++) {
            int distance = trial % 5;
            fdq network = new fdq(7, distance);
            Set<String> used = new HashSet<>();
            List<String> points = new ArrayList<>();
            for (int i = 0; i < 20; i++) {
                int x = random.nextInt(17) - 8;
                int y = random.nextInt(17) - 8;
                if (!used.add(x + "," + y)) continue;
                faW area = (faW) prototype[0].b(new fbm(1000 + i, x, y, (short) 0,
                        null, 7, owner, (short) 30, aAS.wL(7)));
                if (!network.a(area, null, null)) throw new AssertionError("Registration failed");
                points.add("[" + x + "," + y + ",0]");
            }
            List<String> segments = new ArrayList<>();
            for (fdl link : network.fXQ()) {
                aBn a = link.fXO(), b = link.fXP();
                segments.add("[[" + a.getX() + "," + a.getY() + ",0],["
                    + b.getX() + "," + b.getY() + ",0]]");
            }
            System.out.println("{\"distance\":" + distance + ",\"points\":["
                + String.join(",", points) + "],\"segments\":["
                + String.join(",", segments) + "]}");
        }
    }
}
