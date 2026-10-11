import java.util.ArrayList;

/** Verify the real fresh actor instance field before POSITION publication. */
public class ProbeNativeConstructorInstance {
    public static void main(String[] args) throws Exception {
        ProbeNativeLevelGroup.Actor actor = new ProbeNativeLevelGroup.Actor();
        eKB criterion = new eKB(new ArrayList<>());
        if (actor.arM() != 0 || criterion.d(actor, actor, null, null) != 0)
            throw new AssertionError("Fresh constructor instance identity");
        actor.fE(1376);
        if (criterion.d(actor, actor, null, null) != 1376)
            throw new AssertionError("Published POSITION identity");
        System.out.println("PASS actual eGj/eKB: fresh=0, fE=1376");
    }
}
