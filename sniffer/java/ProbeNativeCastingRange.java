import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Proxy;

/** Pure original fcj range calculation; stdin CSV: min,max,modifiable,range,carried,cap. */
public class ProbeNativeCastingRange {
    static int nativeRange(int minimum, int maximum, boolean modifiable,
                           int bonus, boolean carried, boolean capped) {
        PV actor = (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),
            new Class<?>[]{PV.class, eHH.class}, (proxy, method, args) -> {
                if (method.getName().equals("c") && args[0] == ffw.sgK) return bonus;
                if (method.getName().equals("buX")) return carried;
                if (method.getName().equals("a") && args[0] == ffe.sdz) return capped;
                throw new UnsupportedOperationException(method.toString());
            });
        return new fcj<>(null).a(actor, modifiable, minimum, maximum);
    }
    public static void main(String[] args) throws Exception {
        System.err.println("native property sdz=" + ffe.sdz.aKg()
            + "; characteristic sgK=" + ffw.sgK.aKg());
        int count = 0;
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] fields = line.split(",");
                if (fields.length != 6) throw new IllegalArgumentException(line);
                int result = nativeRange(Integer.parseInt(fields[0]), Integer.parseInt(fields[1]),
                    Boolean.parseBoolean(fields[2]), Integer.parseInt(fields[3]),
                    Boolean.parseBoolean(fields[4]), Boolean.parseBoolean(fields[5]));
                System.out.println(result);
                count++;
            }
        }
        System.err.println("native range cases=" + count);
    }
}
