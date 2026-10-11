import com.google.gson.JsonParser;
import java.lang.reflect.*;
import java.util.*;
import gnu.trove.map.hash.TIntObjectHashMap;
/** Offline native criterion oracle: known definitions, empty facts, unknown IDs. */
public class VerifyNpcInitialCriteriaFacts {
    public static void main(String[] args) throws Exception {
        bdM manager = new bdM(0, new TIntObjectHashMap<bdV>(), new TIntObjectHashMap<bdD>());
        for (int id : new int[]{10595, 10606, 10607}) {
            bdS objective = new bdS(id, null, null, "", "", false, new aJO[0]);
            manager.hJa.put(id, objective);
            eNe criterion = new eNe();
            Field objectiveId = eNe.class.getDeclaredField("jjD");
            objectiveId.setAccessible(true);
            objectiveId.setInt(criterion, id);
            if (manager.Bd(id) || criterion.a(null, null, null, manager) != -1)
                throw new AssertionError("Fresh known objective is not incomplete: " + id);
            objective.fo(true);
            if (!manager.Bd(id) || criterion.a(null, null, null, manager) != 0)
                throw new AssertionError("Completed objective not reflected: " + id);
            objective.reset();
            if (manager.Bd(id)) throw new AssertionError("Reset failed");
            System.out.println("objective=" + id + " initial=false completed=true reset=false");
        }
        if (args.length > 0) {
            String manifest = java.nio.file.Files.readString(java.nio.file.Path.of(args[0]));
            String hex = JsonParser.parseString(manifest).getAsJsonObject().get("hex").getAsString();
            byte[] raw = java.util.HexFormat.of().parseHex(hex);
            java.nio.ByteBuffer sectionBytes = java.nio.ByteBuffer.wrap(raw);
            oN section = new oN();
            if (!section.aG(sectionBytes) || sectionBytes.hasRemaining() || section.Sf || section.Se.length != 18)
                throw new AssertionError("Unexpected native ACHIEVEMENTS envelope");
            manager.dT(section.Se);
            for (int id : new int[]{10595, 10606, 10607})
                if (manager.Bd(id)) throw new AssertionError("Empty facts completed objective " + id);
            java.nio.ByteBuffer facts = java.nio.ByteBuffer.wrap(section.Se);
            if (facts.getInt() != 5 || facts.get() != 0 || facts.getInt() != 0 || facts.getInt() != 0 || facts.getInt() != 0 || facts.get() != 0 || facts.hasRemaining())
                throw new AssertionError("Unexpected empty facts or trailing bytes");
            System.out.println("actual_ACHIEVEMENTS=21bytes payload=18 version=5 uncompressed all_counts=0 no_trailing_bytes known_objectives=false");
        }
        try {
            manager.Bd(-987654);
            throw new AssertionError("Missing objective silently accepted");
        } catch (RuntimeException expected) {
            System.out.println("unknown_objective=throws");
        }
        Object worldContext = Proxy.newProxyInstance(fya.class.getClassLoader(), new Class<?>[]{fya.class},
            (proxy, method, values) -> {
                if (method.getName().equals("arM")) return 1385L;
                if (method.getName().equals("toString")) return "NativeWorldIdentity1385";
                throw new UnsupportedOperationException(method.toString());
            });
        eKB instance = new eKB(new ArrayList<alS>());
        if (instance.d(worldContext, null, null, null) != 1385L)
            throw new AssertionError("Native GetInstanceId did not read arM");
        System.out.println("GetInstanceId=arM=1385");
    }
}
