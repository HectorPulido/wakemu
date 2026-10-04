import java.lang.reflect.*;
import java.nio.ByteBuffer;

/** Decode the same pW fight section the server emits, then native eGn.zm. */
public class ProbeNativeFightAffiliation {
    public static void main(String[] args) throws Exception {
        Field singleton = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        singleton.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) singleton.get(null);
        Field context = eGj.class.getDeclaredField("pGC");
        context.setAccessible(true);
        Constructor<?> serializer = Class.forName("eGn").getDeclaredConstructor(eGj.class,pW.class);
        serializer.setAccessible(true);
        Method apply = Class.forName("eGn").getDeclaredMethod("zm");
        apply.setAccessible(true);
        for (byte team : new byte[]{0,1,127,-1}) {
            ProbeNativeLevelGroup.Actor actor = (ProbeNativeLevelGroup.Actor) unsafe.allocateInstance(ProbeNativeLevelGroup.Actor.class);
            context.set(actor,new eGz<>() {});
            ByteBuffer wire = ByteBuffer.allocate(10).putInt(77);
            wire.put(new byte[]{0,0,0,0,team,0}).flip();
            pW section = new pW();
            if (!section.aG(wire) || wire.hasRemaining()) throw new AssertionError("fight section");
            apply.invoke(serializer.newInstance(actor,section));
            if (actor.bcN()!=team) throw new AssertionError("bcN != serialized affiliation");
            System.out.println("pW.Uj="+team+" -> eGn.zm -> eGj.bcN="+actor.bcN());
        }
    }
}
