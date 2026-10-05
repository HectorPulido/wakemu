import java.lang.reflect.Field;
/** Actual fcE predicates, with independently verified native fdy life states. */
public class ProbeNativeTargetLifeSelectors {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        long identity; boolean alive;
        public long Sn() { return identity; }
        public boolean baF() { return alive; }
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
        System.out.println("PASS fcE16 positive identity; fcE40 baF; fdy sax only");
    }
}
