import java.lang.reflect.*;
import java.util.*;
import com.google.gson.Gson;

/** Offline native portal primitives and fee aggregate predicates. */
public final class ProbeNativePortalGeometry {
    public static void main(String[] args) throws Exception {
        Method aligned = fed.class.getDeclaredMethod("k", aBn.class, aBn.class);
        aligned.setAccessible(true);
        Method range = fed.class.getDeclaredMethod("al", int.class, int.class, int.class);
        range.setAccessible(true);
        List<Object> geometry = new ArrayList<>();
        int[] values = {Integer.MIN_VALUE, -46341, -2, -1, 0, 1, 2, 46341, Integer.MAX_VALUE};
        for (int x : values) for (int y : values) for (int tx : values) for (int ty : values) {
            aBn from = new aBn(x,y), to = new aBn(tx,ty);
            alb portal = (alb) Proxy.newProxyInstance(alb.class.getClassLoader(), new Class<?>[]{alb.class},
                (proxy, method, parameters) -> {
                    if (method.getName().equals("bcz")) return x;
                    if (method.getName().equals("bcA")) return y;
                    if (method.getName().equals("bcL")) return (byte)0;
                    throw new UnsupportedOperationException(method.toString());
                });
            geometry.add(Arrays.asList(x,y,tx,ty,ala.c(portal,to),from.cG(tx,ty),aligned.invoke(null,from,to)));
        }
        List<Object> ranges = new ArrayList<>();
        for (int min : values) for (int max : values) for (int distance : values)
            ranges.add(Arrays.asList(min,max,distance,range.invoke(null,min,max,distance)));
        Field entries = fee.class.getDeclaredField("sbm"), exits = fee.class.getDeclaredField("sbn");
        entries.setAccessible(true); exits.setAccessible(true);
        List<Object> flags = new ArrayList<>();
        for (int count=0; count<=3; count++) for (int bits=0; bits<(1<<(count*3)); bits++) {
            fee evaluator = new fee();
            Set entrySet = (Set)entries.get(evaluator); entrySet.add(null);
            Map map = (Map)exits.get(evaluator);
            List<Integer> masks = new ArrayList<>();
            for(int n=0;n<count;n++) {
                int mask=(bits>>(n*3))&7; masks.add(mask);
                Set<fyJ> failures = new HashSet<>();
                if((mask&1)!=0) failures.add(fyJ.twI);
                if((mask&2)!=0) failures.add(fyJ.twU);
                if((mask&4)!=0) failures.add(fyJ.twG);
                map.put(n,failures);
            }
            flags.add(Arrays.asList(masks,evaluator.fYt(),evaluator.fYu(),evaluator.fYv(),evaluator.fYw()));
        }
        Field categoryId=fyU.class.getDeclaredField("tye");categoryId.setAccessible(true);
        Map<String,Object> out=new LinkedHashMap<>();out.put("schema","native-portal-primitives-v1");
        out.put("same_cell_category",categoryId.getInt(fyU.tya));
        out.put("geometry",geometry);out.put("ranges",ranges);out.put("aggregates",flags);
        System.out.println(new Gson().toJson(out));
    }
}
