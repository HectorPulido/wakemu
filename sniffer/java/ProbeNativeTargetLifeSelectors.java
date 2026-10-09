import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
/** Actual fcE predicates, with independently verified native fdy life states. */
public class ProbeNativeTargetLifeSelectors {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        long identity; boolean alive; boolean offPlay;
        public long Sn() { return identity; }
        public boolean baF() { return alive; }
        public boolean baG() { return offPlay; }
        public boolean bEe() { return true; }
    }
    public static void main(String[] args) throws Exception {
        Field singleton = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        singleton.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) singleton.get(null);
        Actor target = (Actor) unsafe.allocateInstance(Actor.class);
        Actor caster = (Actor) unsafe.allocateInstance(Actor.class);
        for (long identity : new long[]{-7,0,7}) {
            target.identity=identity;
            for (boolean alive : new boolean[]{false,true}) {
                target.alive=alive;
                for (long mask : new long[]{16,1L<<40,16|(1L<<40)}) {
                    boolean expected = ((mask&16)==0 || identity>0)
                        && ((mask&(1L<<40))==0 || alive);
                    String actual=fcE.j(new long[]{mask}).a(target,caster).toString();
                    if (!actual.equals(expected?"VALID":"INVALID")) throw new AssertionError(actual);
                    System.out.println("identity="+identity+" baF="+alive+" mask="+mask+" -> "+actual);
                }
            }
        }
        for (boolean offPlay : new boolean[]{false,true}) {
            target.offPlay=offPlay;
            for (long mask : new long[]{0,1L<<14}) {
                boolean expected = mask==0 || offPlay;
                String actual=fcE.j(new long[]{mask}).a(target,caster).toString();
                if (!actual.equals(expected?"VALID":"INVALID"))
                    throw new AssertionError("fcE16384 baG="+offPlay+" -> "+actual);
                System.out.println("fcE16384 baG="+offPlay+" mask="+mask+" -> "+actual);
            }
        }
        amP nonActor=(amP)Proxy.newProxyInstance(
            amP.class.getClassLoader(), new Class<?>[]{amP.class},
            (proxy,method,values)->{
                if(method.getName().equals("bEe"))return true;
                Class<?> type=method.getReturnType();
                if(type==boolean.class)return false;
                if(type==byte.class)return (byte)0;
                if(type==short.class)return (short)0;
                if(type==int.class)return 0;
                if(type==long.class)return 0L;
                if(type==float.class)return 0.0f;
                if(type==double.class)return 0.0d;
                if(type==char.class)return (char)0;
                return null;
            });
        String nonActorBaseline=fcE.j(new long[]{0}).a(nonActor,caster).toString();
        if (!nonActorBaseline.equals("VALID"))
            throw new AssertionError("non-eGj baseline should pass");
        String nonActorResult=fcE.j(new long[]{1L<<14}).a(nonActor,caster).toString();
        if (!nonActorResult.equals("INVALID")) throw new AssertionError("fcE16384 non-eGj");
        System.out.println("fcE16384 non-eGj baseline="+nonActorBaseline);
        System.out.println("fcE16384 non-eGj -> INVALID");
        fdy state=new fdy((byte)0,false,false,7);
        if (!state.baF()) throw new AssertionError("constructor must be sax");
        Field life=fdy.class.getDeclaredField("saE"); life.setAccessible(true);
        for(fdx value:fdx.values()) {
            life.set(state,value);
            if (state.baF()!=(value==fdx.sax)) throw new AssertionError("baF state");
            if (state.baG()!=(value==fdx.say)) throw new AssertionError("baG OFF_PLAY state");
            if (state.baK()!=(value==fdx.saz)) throw new AssertionError("baK OUT_OF_PLAY state");
            System.out.println("native life="+value+" baF="+state.baF()+" baG="+state.baG()+" baK="+state.baK());
        }
        System.out.println("PASS fcE16 positive identity; fcE40 baF; fcE16384 target eGj.baG; fdy sax only");
    }
}
