import java.lang.reflect.Field;
import sun.misc.Unsafe;

/** Original eVE methods, independent of scene/client/server. */
public class ProbeNativeSignedEffectLevels {
    static void set(Object o,String name,Object value)throws Exception {
        Field f=eVE.class.getDeclaredField(name);f.setAccessible(true);f.set(o,value);
    }
    public static void main(String[] args)throws Exception {
        Field f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);
        eVE effect=(eVE)((Unsafe)f.get(null)).allocateInstance(eVE.class);
        set(effect,"ryR",new float[]{7999,0,10,.5f});
        set(effect,"ryP",100f);set(effect,"ryQ",.5f);
        int count=0;
        for(short level:new short[]{-32768,-97,-1,0,32767}) {
            if(effect.w(0,level)!=7999 || effect.w(1,level)!=10+level*.5f || effect.eg(level)!=100+level*.5f)
                throw new AssertionError("signed native level "+level);
            count++;
        }
        System.out.println("PASS "+count+" native signed-level contracts");
    }
}
