import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import com.google.gson.Gson;
import gnu.trove.set.hash.TByteHashSet;

/** Offline installed default byte-set topology and deterministic lifecycle oracle. */
public class ExportNativeTroveByteSet {
    static Object field(Object object, String name) throws Exception {
        for(Class<?> type=object.getClass(); type!=null; type=type.getSuperclass()) {
            try { Field f=type.getDeclaredField(name); f.setAccessible(true); return f.get(object); }
            catch(NoSuchFieldException missing) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Map<String,Object> state(TByteHashSet set) throws Exception {
        var result=new LinkedHashMap<String,Object>();
        result.put("keys",((byte[])field(set,"_set")).clone());
        result.put("states",((byte[])field(set,"_states")).clone());
        result.put("size",set.size()); result.put("free",field(set,"_free"));
        result.put("compact_removes",field(set,"_autoCompactRemovesRemaining"));
        return result;
    }
    public static void main(String[] args) throws Exception {
        TByteHashSet set=new TByteHashSet();
        var contract=new LinkedHashMap<String,Object>();
        contract.put("source","Installed TByteHashSet default; QL.c creates same constructor");
        contract.put("initial_capacity",((byte[])field(set,"_set")).length);
        contract.put("initial_compact_removes",field(set,"_autoCompactRemovesRemaining"));
        contract.put("load_factor",field(set,"_loadFactor"));
        contract.put("auto_compaction_factor",field(set,"_autoCompactionFactor"));
        Class<?> finder=Class.forName("gnu.trove.impl.PrimeFinder");
        Field primes=finder.getDeclaredField("primeCapacities"); primes.setAccessible(true);
        contract.put("prime_capacities",primes.get(null));
        Files.writeString(Path.of(args[0]),new Gson().toJson(contract));
        Random random=new Random(91837L);
        List<Object> cases=new ArrayList<>();
        for(int n=0;n<12000;n++) {
            byte key=(byte)(n<256?n:random.nextInt(256));
            boolean add=n<256||random.nextBoolean();
            boolean changed=add?set.add(key):set.remove(key);
            cases.add(Map.of("add",add,"key",(int)key,"changed",changed,
                             "order",set.toArray(),"state",state(set)));
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(cases));
        System.out.println("PASS exported native default byte-set contract and12000 lifecycle oracle steps");
    }
}
