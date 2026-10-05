import java.lang.reflect.*;
import java.util.*;

/** Real eXR.fPC lottery; controlled GS.nextInt bounds and candidate order. */
public class ProbeNativeRandomGroup {
    static class Children extends fyD {
        Children() { super(1); }
        public fyD cq(short level) { return this; }
    }
    static class Draws extends Random {
        final int[] bounds, rolls; int index;
        Draws(int[] bounds, int[] rolls) { this.bounds=bounds; this.rolls=rolls; }
        public int nextInt(int bound) {
            if (bound!=bounds[index]) throw new AssertionError("bound="+bound+" expected="+bounds[index]);
            return rolls[index++];
        }
    }
    static eVn child(int id, float probability, int minimum) {
        return (eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(), new Class<?>[]{eVn.class}, (p,m,a)->switch(m.getName()) {
            case "fKR" -> minimum;
            case "fKS" -> 200;
            case "fKT" -> null;
            case "eg" -> probability;
            case "aZE" -> id;
            case "equals" -> p==a[0];
            case "hashCode" -> id;
            case "toString" -> "child"+id;
            default -> throw new UnsupportedOperationException(m.getName());
        });
    }
    static void check(float[] weights, int count, int[] bounds, int[] rolls, int... expected) throws Exception {
        Children children=new Children();
        for(int i=0;i<weights.length;i++) children.v(child(i+1,weights[i],0));
        children.v(child(99,1000,1)); // Excluded at fresh fRR=0.
        eXR group=new eXR();
        Field defs=eYg.class.getDeclaredField("rFp");defs.setAccessible(true);defs.set(group,children);
        Field number=eXR.class.getDeclaredField("rEP");number.setAccessible(true);number.set(group,count);
        Field random=GS.class.getDeclaredField("aHu");random.setAccessible(true);
        Random nativeRandom=(Random)random.get(null);
        long seed=0;
        for(;seed<1000000;seed++) {
            Random candidate=new GT(seed);boolean matches=true;
            for(int i=0;i<bounds.length;i++)if(candidate.nextInt(bounds[i])!=rolls[i]) {matches=false;break;}
            if(matches)break;
        }
        if(seed==1000000)throw new AssertionError("No deterministic native draw seed");
        nativeRandom.setSeed(seed);
        Method select=eXR.class.getDeclaredMethod("fPC");select.setAccessible(true);
        List<?> selected=(List<?>)select.invoke(group);
        List<Integer> actual=new ArrayList<>();for(Object value:selected)actual.add(((eVn)value).aZE());
        if (!actual.equals(Arrays.stream(expected).boxed().toList()))throw new AssertionError(actual.toString());

    }
    public static void main(String[] args) throws Exception {
        check(new float[]{10,20,30},2,new int[]{60,50},new int[]{10,0},1,2);
        check(new float[]{0,20,30},1,new int[]{50},new int[]{0},1);
        check(new float[]{.7f,1.6f},1,new int[]{1},new int[]{0},1);
        check(new float[]{10,20},0,new int[]{},new int[]{});
        System.out.println("PASS eXR bounded draws, no replacement, zero boundary, float-to-int sums, level filtering");
    }
}
