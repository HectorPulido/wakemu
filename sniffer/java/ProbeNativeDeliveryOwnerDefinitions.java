import java.lang.reflect.*;
import java.util.*;

/** Offline registry and clone owner flags; dynamic parameter-dependent methods stay explicit. */
public class ProbeNativeDeliveryOwnerDefinitions {
    public static void main(String[] args) throws Exception {
        Set<String> unresolved = new HashSet<>(Arrays.asList("eYg", "eXR", "eYZ", "eZN"));
        for (Field field : eVi.class.getDeclaredFields()) {
            if (field.getType() != eVj.class) continue;
            field.setAccessible(true);
            eVj entry = (eVj) field.get(null);
            Object runner = entry.bkv();
            if (!(runner instanceof Qe prototype)) continue;
            Method a = runner.getClass().getMethod("bbA"), b = runner.getClass().getMethod("bbB");
            Boolean av = ExportNativeRunnerOwners.constant(a), bv = ExportNativeRunnerOwners.constant(b);
            if (av != null && bv != null) continue;
            String owner = a.getDeclaringClass().getName();
            if (unresolved.contains(owner)) {
                System.out.println(entry.d() + "," + runner.getClass().getName() + ",dynamic," + owner);
                continue;
            }
            Qe clone = (Qe) prototype.bbn();
            if (clone.bbA() != prototype.bbA() || clone.bbB() != prototype.bbB())
                throw new AssertionError("Prototype/clone owner disagreement: " + entry.d());
            System.out.println(entry.d() + "," + runner.getClass().getName() + ","
                + prototype.bbA() + "," + prototype.bbB() + ",clone_equal");
        }
        System.exit(0);
    }
}
