import java.lang.reflect.*;
import java.nio.file.Path;
import java.util.*;
/** Actual installed fyF.a selects cwL from original state-dependent fyP. */
public final class ProbeNativeConditionalLos {
    static eHg actor(boolean precise, int precision) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class[]{eHg.class},
            (p,m,a)->switch(m.getName()) {
                case "kY" -> ((Long)a[0])==7757L && precise;
                case "df" -> ((Long)a[0])==7792L ? precision : -1;
                case "toString" -> "TypedStateActor";
                default -> throw new UnsupportedOperationException(m.getName());
            });
    }
    public static void main(String[] args)throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>(){public void load(aKX raw){}});
        apw.bGL().a(new aNw(), new apB<aNw>(){public void load(aNw raw){}});
        bPK definition=bPS.elL().IP(4813);
        Field raw=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");raw.setAccessible(true);
        sun.misc.Unsafe unsafe=(sun.misc.Unsafe)raw.get(null);
        bPO spell=(bPO)unsafe.allocateInstance(bPO.class);
        Field source=fyG.class.getDeclaredField("tww");source.setAccessible(true);source.set(spell,definition);
        Field level=fyG.class.getDeclaredField("eiA");level.setAccessible(true);
        int count=0;
        for(short evaluation:new short[]{1,20,200}) {
            level.setShort(spell,evaluation);
            for(boolean precise:new boolean[]{false,true})
                for(int precision:new int[]{-1,0,29,30,31,100}) {
                    boolean actual=definition.a(spell,actor(precise,precision),null,null);
                    if(actual != !(precise && precision>=30))throw new AssertionError("LOS threshold");
                    System.out.println(evaluation+","+precise+","+precision+","+actual);
                    count++;
                }
        }
        System.out.println("PASS installed4813 originalfyF.a conditional LOS "+count+" cases; typednon-eGj deckfalse");
    }
}
