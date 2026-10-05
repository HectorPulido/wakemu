import java.lang.reflect.Field;
/** fcE bits42/45 compare target object to source dpu/dpr respectively. */
public class ProbeNativeTargetControllerSelectors {
    static class Actor extends ProbeNativeTargetLifeSelectors.Actor {
        eGj master, controller;
        boolean summon, corpse;
        public boolean dTE() { return summon; }
        public boolean baG() { return corpse; }
        public eGj dpu() { return master; }
        public eGj dpr() { return controller; }
    }
    public static void main(String[] args) throws Exception {
        Field singleton=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");singleton.setAccessible(true);
        sun.misc.Unsafe unsafe=(sun.misc.Unsafe)singleton.get(null);
        Actor source=(Actor)unsafe.allocateInstance(Actor.class);
        Actor target=(Actor)unsafe.allocateInstance(Actor.class);
        Actor other=(Actor)unsafe.allocateInstance(Actor.class);
        source.master=target;source.controller=other;
        for(long mask:new long[]{1L<<42,1L<<45}) {
            eGj expected=mask==(1L<<42)?target:other;
            for(Actor selected:new Actor[]{source,target,other}) {
                String actual=fcE.j(new long[]{mask}).a(selected,source).toString();
                if(!actual.equals(selected==expected?"VALID":"INVALID"))throw new AssertionError(actual);
                System.out.println("mask="+mask+" matches="+(selected==expected)+" -> "+actual);
            }
        }
        for(boolean summoned:new boolean[]{false,true}) {
            target.summon=summoned;
            for(eGj owner:new eGj[]{source,other}) {
                target.master=owner;
                String actual=fcE.j(new long[]{1L<<34}).a(target,source).toString();
                boolean expected=!(summoned&&owner==source);
                if(!actual.equals(expected?"VALID":"INVALID"))throw new AssertionError("own summon exclusion");
                System.out.println("bit34 summon="+summoned+" own="+(owner==source)+" -> "+actual);
            }
        }
        for(boolean corpse:new boolean[]{false,true}) {
            target.corpse=corpse;
            String actual=fcE.j(new long[]{1L<<14}).a(target,source).toString();
            if(!actual.equals(corpse?"VALID":"INVALID"))throw new AssertionError("corpse selector");
            System.out.println("bit14 baG="+corpse+" -> "+actual);
        }
        big ordinary=(big)unsafe.allocateInstance(bje.class);
        if(ordinary.dpu()!=ordinary||ordinary.dpr()!=ordinary)throw new AssertionError("null manager defaults self");
        System.out.println("PASS fcE42/45 object identity,34 own summon exclusion,14 corpse; big unregistered relations resolve self");
    }
}
