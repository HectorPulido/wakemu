import java.lang.reflect.Proxy;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Actual Qq.bcT/anw cache across arm lengths, facing and owner positions. */
public class ProbeNativeRegisteredCrossGeometry {
    static class Glyph extends faY {
        Glyph(Qr row) { super(row); }
        Glyph() { super(); }
        protected Qq bcs() { return new Glyph(); }
        public List<amP> d(amP target) { return n(target); }
        public anS bEs() { return bcD().bEs(); }
        public void a(int x, int y, short z, Qe source) {}
    }

    static PV owner(int[] position) {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),
            new Class[]{PV.class}, (proxy, method, args) -> switch(method.getName()) {
                case "Sn" -> 7L;
                case "bcz" -> position[0];
                case "bcA" -> position[1];
                case "bcB" -> (short) position[2];
                case "bav", "bcM" -> (byte) 0;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }

    public static void main(String[] args) throws Exception {
        List<Object> cases = new ArrayList<>();
        int[][] arms = {{1}, {0}, {-1}, {2, 1}, {3, 2, 1, 0}, {0, 2, -1, 3}};
        int[][] centers = {{5, 2, 9}, {-7, 3, -1}};
        for (int[] parameters : arms) for (int[] center : centers) {
            for (int[] reference : new int[][]{center, {0, 0, 0}, {9, -4, 17}}) {
                for (int direction = 0; direction < 8; direction++) {
                    anw shape = new anw();
                    shape.p(parameters);
                    Glyph prototype = new Glyph(new Qr().oK(100).b(shape));
                    faV area = prototype.b(new fbm(901, center[0], center[1],
                        (short) center[2], null, 7, owner(reference), (short) 1,
                        aAS.wL(direction)));
                    area.bcT();
                    List<List<Integer>> cells = new ArrayList<>();
                    for (int[] cell : area.bcX()) cells.add(List.of(cell[0], cell[1]));
                    cells.sort(Comparator.<List<Integer>>comparingInt(p -> p.get(0))
                        .thenComparingInt(p -> p.get(1)));
                    for (List<Integer> cell : cells)
                        if (!area.d(new aBn(cell.get(0), cell.get(1), (short) -99)))
                            throw new AssertionError("Native cached XY membership");
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("description", shape.bEm());
                    row.put("parameters", parameters);
                    row.put("center", center);
                    row.put("reference", reference);
                    row.put("direction", direction);
                    row.put("cells", cells);
                    cases.add(row);
                }
            }
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source", "Actual client Qq.bcT/anw.bEl/anw.bEj");
        result.put("cases", cases);
        Files.writeString(Path.of(args[0]),
            new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n");
        System.out.println("PASS native registered cross geometry: " + cases.size() + " cases");
    }
}
