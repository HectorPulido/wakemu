import java.lang.reflect.Proxy;

/** Original fcj range acceptance, without catalogs, a fight or a client. */
public class ProbeNativeCastingDistance {
    public static void main(String[] args) {
        int[][] rows = {
            {0, 0, 2, 0, 1, 4, 0},
            {0, 0, 0, 0, 1, 4, 0},
            {0, 0, 0, 0, 1, 4, 1},
            {0, 0, Integer.MIN_VALUE, 0, 1, 4, 1},
            {0, 0, Integer.MIN_VALUE, 0, Integer.MIN_VALUE, 4, 0},
            {0, 0, Integer.MAX_VALUE, 2, Integer.MIN_VALUE, 4, 0},
            {Integer.MIN_VALUE, 0, Integer.MAX_VALUE, 0, 1, 1, 0},
            {0, 0, Integer.MIN_VALUE, Integer.MIN_VALUE, 1, 4, 1}
        };
        fcj<PVContainer, PV> query = new fcj<>(null);
        for (int[] row : rows) {
            PV caster = (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),
                new Class<?>[]{PV.class}, (proxy, method, arguments) -> {
                    if (method.getName().equals("bcz")) return row[0];
                    if (method.getName().equals("bcA")) return row[1];
                    throw new AssertionError("Unexpected PV query " + method);
                });
            boolean accepted = query.a(caster, null, row[4], row[5],
                                       row[6] == 1, row[2], row[3]);
            System.out.printf("%d,%d,%d,%d,%d,%d,%d,%s%n", row[0], row[1],
                row[2], row[3], row[4], row[5], row[6], accepted);
        }
    }

    // The range overload does not consume its container; only its generic bound
    // is needed for compilation; no synthetic eVo instance is constructed.
    private interface PVContainer extends eVo {}
}
